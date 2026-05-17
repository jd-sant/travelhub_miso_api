from uuid import UUID

import jwt
from fastapi import HTTPException, Request, status

from core.config import settings


HOTEL_ROLE = "hotel"
TRAVELER_ROLE = "traveler"


class AuthenticatedUser:
    __slots__ = ("id", "email", "role", "raw_claims")

    def __init__(self, *, id: UUID, email: str, role: str, raw_claims: dict):
        self.id = id
        self.email = email
        self.role = role
        self.raw_claims = raw_claims


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
            detail="Token expirado",
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido",
        ) from exc


def _extract_token(request: Request) -> str:
    header = request.headers.get("Authorization")
    if not header or not header.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization Bearer token requerido",
        )
    return header.split(" ", 1)[1].strip()


def get_current_user(request: Request) -> AuthenticatedUser:
    token = _extract_token(request)
    claims = _decode(token)
    sub = claims.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token sin sujeto",
        )
    try:
        user_id = UUID(sub)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="sub inválido en token",
        ) from exc

    return AuthenticatedUser(
        id=user_id,
        email=claims.get("email", ""),
        role=claims.get("role", ""),
        raw_claims=claims,
    )


def require_hotel(user: AuthenticatedUser) -> AuthenticatedUser:
    if user.role != HOTEL_ROLE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere rol de hotel",
        )
    return user


def get_current_hotel_user(request: Request) -> AuthenticatedUser:
    return require_hotel(get_current_user(request))


def require_traveler(user: AuthenticatedUser) -> AuthenticatedUser:
    if user.role != TRAVELER_ROLE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere rol de viajero",
        )
    return user


def get_current_traveler_user(request: Request) -> AuthenticatedUser:
    return require_traveler(get_current_user(request))
