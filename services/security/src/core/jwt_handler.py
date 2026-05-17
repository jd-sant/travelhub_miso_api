from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import jwt

from core.config import settings
from errors import InvalidTokenError, TokenExpiredError


def create_token(user_id: UUID, email: str, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expiration_minutes),
        "jti": str(uuid4()),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenExpiredError("Token expirado") from exc
    except jwt.InvalidTokenError as exc:
        raise InvalidTokenError("Token inválido") from exc
