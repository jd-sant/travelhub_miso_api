from uuid import UUID

import jwt
from fastapi import HTTPException, Request, status

from core.config import settings


HOTEL_ROLE_ALIASES = {"hotel_partner", "hotel"}


class AuthenticatedUser:
    __slots__ = ("id", "email", "role", "raw_claims")

    def __init__(self, *, id: UUID, email: str, role: str, raw_claims: dict):
        self.id = id
        self.email = email
        self.role = role
        self.raw_claims = raw_claims


def _extract_token(request: Request) -> str:
    header = request.headers.get("Authorization")
    if not header or not header.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization Bearer token requerido",
        )
    return header.split(" ", 1)[1].strip()


def _decode(token: str) -> dict:
    try:
        return jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalido",
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalido",
        ) from exc


def get_current_hotel_user(request: Request) -> AuthenticatedUser:
    claims = _decode(_extract_token(request))
    raw_sub = claims.get("sub")
    if not raw_sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalido",
        )
    try:
        user_id = UUID(raw_sub)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="sub invalido en token",
        ) from exc

    role = str(claims.get("role") or "")
    if role not in HOTEL_ROLE_ALIASES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere rol de hotel",
        )

    return AuthenticatedUser(
        id=user_id,
        email=str(claims.get("email") or ""),
        role=role,
        raw_claims=claims,
    )


