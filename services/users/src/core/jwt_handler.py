from uuid import UUID

import jwt

from core.config import settings


def decode_token(token: str) -> dict:
    """
    Decodifica un JWT token.
    
    Usa la misma secret key que Security Service para validación.
    """
    # Intenta obtener las settings de JWT de environment
    jwt_secret = get_jwt_secret_key()
    jwt_algorithm = get_jwt_algorithm()
    
    try:
        return jwt.decode(
            token,
            jwt_secret,
            algorithms=[jwt_algorithm],
        )
    except jwt.ExpiredSignatureError as exc:
        from errors import TokenExpiredError
        raise TokenExpiredError("Token expirado") from exc
    except jwt.InvalidTokenError as exc:
        from errors import InvalidTokenError
        raise InvalidTokenError("Token inválido") from exc


def get_jwt_secret_key() -> str:
    """Obtiene la secret key para JWT"""
    import os
    return os.getenv("JWT_SECRET_KEY", "dev-secret-key-change-me")


def get_jwt_algorithm() -> str:
    """Obtiene el algoritmo para JWT"""
    import os
    return os.getenv("JWT_ALGORITHM", "HS256")
