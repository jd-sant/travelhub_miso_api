import jwt

from core.config import settings
from errors import InvalidTokenError, TokenExpiredError


def decode_token(token: str) -> dict:
    """
    Decodifica un JWT token.

    Usa la misma secret key que Security Service para validación.
    """
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
