from typing import Optional
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy import or_
from sqlmodel import Session, select

from adapters.models.role import Role
from adapters.models.user import User
from adapters.models.user_role import UserRole
from core.config import settings
from core.privacy import (
    build_lookup_hash,
    decrypt_sensitive_value,
    encrypt_sensitive_value,
    normalize_country_code,
    resolve_data_region,
)
from core.security import hash_password
from domain.ports.user_repository import UserRepository
from domain.schemas.user import (
    UserCreateRequest,
    UserCredentialsData,
    UserResponse,
    UserSummary,
)
from errors import UserConflictError


def _to_response(model: User) -> UserResponse:
    encryption_key = settings.users_pii_encryption_key
    return UserResponse(
        id=model.id,
        email=decrypt_sensitive_value(model.email, encryption_key) or "",
        phone=decrypt_sensitive_value(model.phone, encryption_key) or "",
        full_name=decrypt_sensitive_value(model.full_name, encryption_key) or "",
        hotel_name=decrypt_sensitive_value(model.hotel_name, encryption_key),
        country_code=model.country_code,
        data_region=model.data_region,
        status=model.status,
    )


def _email_filter(email: str):
    email_hash = build_lookup_hash(email, settings.users_email_lookup_hash_secret)
    return or_(User.email_lookup_hash == email_hash, User.email == email)


class SQLModelUserRepository(UserRepository):
    def __init__(self, session: Session):
        self.session = session

    def add(self, payload: UserCreateRequest) -> UserResponse:
        country_code = normalize_country_code(payload.country_code)
        data_region = resolve_data_region(
            country_code,
            policies=settings.data_residency_policies,
            default_region=settings.default_data_region,
        )
        email = str(payload.email)
        email_lookup_hash = build_lookup_hash(
            email,
            settings.users_email_lookup_hash_secret,
        )
        existing_user = self.session.exec(
            select(User.id).where(_email_filter(email)).limit(1)
        ).first()
        if existing_user is not None:
            raise UserConflictError("Conflict while creating user")
        pii_encrypted = settings.users_pii_encryption_enabled
        encryption_key = settings.users_pii_encryption_key
        user = User(
            email=(
                encrypt_sensitive_value(email, encryption_key)
                if pii_encrypted
                else email
            ),
            email_lookup_hash=email_lookup_hash,
            phone=(
                encrypt_sensitive_value(payload.phone, encryption_key)
                if pii_encrypted
                else payload.phone
            ),
            password=hash_password(payload.password),
            full_name=(
                encrypt_sensitive_value(payload.full_name, encryption_key)
                if pii_encrypted
                else payload.full_name
            ),
            hotel_name=(
                encrypt_sensitive_value(payload.hotel_name, encryption_key)
                if pii_encrypted
                else payload.hotel_name
            ),
            country_code=country_code,
            data_region=data_region,
            pii_encrypted=pii_encrypted,
            status=payload.status,
        )
        self.session.add(user)
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise UserConflictError("Conflict while creating user") from exc
        self.session.refresh(user)
        return _to_response(user)

    def get_by_email(self, email: str) -> Optional[UserResponse]:
        model = self.session.exec(
            select(User).where(_email_filter(email))
        ).first()
        return _to_response(model) if model else None

    def get_by_id(self, user_id: UUID) -> Optional[UserResponse]:
        model = self.session.get(User, user_id)
        return _to_response(model) if model else None

    def list_all(self) -> list[UserResponse]:
        models = self.session.exec(select(User)).all()
        return [_to_response(m) for m in models]

    def get_by_email_with_password_and_roles(
        self, email: str
    ) -> Optional[UserCredentialsData]:
        rows = self.session.exec(
            select(User, Role.name)
            .outerjoin(UserRole, User.id == UserRole.user_id)
            .outerjoin(Role, UserRole.role_id == Role.id)
            .where(_email_filter(email))
        ).all()
        if not rows:
            return None

        user = rows[0][0]
        role_names = [r for _, r in rows if r is not None]

        return UserCredentialsData(
            id=user.id,
            email=decrypt_sensitive_value(
                user.email,
                settings.users_pii_encryption_key,
            )
            or "",
            password=user.password,
            status=user.status,
            roles=role_names,
        )

    def assign_role(self, user_id: UUID, role_name: str) -> None:
        role = self.session.exec(
            select(Role).where(Role.name == role_name)
        ).first()

        if not role:
            role = Role(name=role_name)
            self.session.add(role)
            self.session.commit()
            self.session.refresh(role)

        user_role = UserRole(user_id=user_id, role_id=role.id)
        self.session.add(user_role)
        self.session.commit()

    def search_by_name(self, query: str, limit: int = 50) -> list[UserSummary]:
        if not query.strip():
            return []
        normalized_query = query.strip().lower()
        if settings.users_pii_encryption_enabled:
            rows = self.session.exec(select(User)).all()
            matches: list[UserSummary] = []
            for user in rows:
                full_name = decrypt_sensitive_value(
                    user.full_name,
                    settings.users_pii_encryption_key,
                ) or ""
                if normalized_query in full_name.lower():
                    matches.append(
                        UserSummary(
                            id=user.id,
                            full_name=full_name,
                            email=decrypt_sensitive_value(
                                user.email,
                                settings.users_pii_encryption_key,
                            ) or "",
                        )
                    )
                if len(matches) >= limit:
                    break
            return matches
        pattern = f"%{normalized_query}%"
        rows = self.session.exec(
            select(User)
            .where(User.full_name.ilike(pattern))
            .limit(limit)
        ).all()
        return [
            UserSummary(
                id=u.id,
                full_name=decrypt_sensitive_value(
                    u.full_name,
                    settings.users_pii_encryption_key,
                )
                or "",
                email=decrypt_sensitive_value(
                    u.email,
                    settings.users_pii_encryption_key,
                )
                or "",
            )
            for u in rows
        ]

    def list_by_ids(self, ids: list[UUID]) -> list[UserSummary]:
        if not ids:
            return []
        rows = self.session.exec(select(User).where(User.id.in_(ids))).all()
        return [
            UserSummary(
                id=u.id,
                full_name=decrypt_sensitive_value(
                    u.full_name,
                    settings.users_pii_encryption_key,
                )
                or "",
                email=decrypt_sensitive_value(
                    u.email,
                    settings.users_pii_encryption_key,
                )
                or "",
            )
            for u in rows
        ]
