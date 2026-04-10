from typing import Optional
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from adapters.models.role import Role
from adapters.models.user import User
from adapters.models.user_role import UserRole
from core.security import hash_password
from domain.ports.user_repository import UserRepository
from domain.schemas.user import UserCreateRequest, UserCredentialsData, UserResponse
from errors import UserConflictError


def _to_response(model: User) -> UserResponse:
    return UserResponse(
        id=model.id,
        email=model.email,
        phone=model.phone,
        full_name=model.full_name,
        hotel_name=model.hotel_name,
        status=model.status,
    )


class SQLModelUserRepository(UserRepository):
    def __init__(self, session: Session):
        self.session = session

    def add(self, payload: UserCreateRequest) -> UserResponse:
        user = User(
            email=str(payload.email),
            phone=payload.phone,
            password=hash_password(payload.password),
            full_name=payload.full_name,
            hotel_name=payload.hotel_name,
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
            select(User).where(User.email == email)
        ).first()
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
            .where(User.email == email)
        ).all()
        if not rows:
            return None

        user = rows[0][0]
        role_names = [r for _, r in rows if r is not None]

        return UserCredentialsData(
            id=user.id,
            email=user.email,
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
