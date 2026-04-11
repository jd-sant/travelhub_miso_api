from typing import Optional

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from core.jwt_handler import decode_token
from errors import InvalidTokenError, TokenExpiredError


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware que extrae y valida JWT de los headers.
    
    Deja el usuario autenticado en request.state.user si el token es válido.
    No falla si no hay token, permite que los endpoints decidan si es requerido.
    """

    async def dispatch(self, request: Request, call_next):
        # Extrae el token del header Authorization
        auth_header = request.headers.get("Authorization")
        
        if auth_header:
            try:
                # Espera formato: "Bearer <token>"
                token = auth_header.replace("Bearer ", "")
                
                # Decodifica y valida el JWT
                claims = decode_token(token)
                
                # Deja el usuario disponible para el endpoint
                request.state.user = claims
                
            except (InvalidTokenError, TokenExpiredError):
                # Si el token es inválido o expirado, no falla aquí
                # Los endpoints pueden validar después si es necesario
                pass
            except Exception:
                # Cualquier otro error, ignora
                pass
        
        # Continúa con la siguiente middleware/endpoint
        response = await call_next(request)
        return response


def get_current_user(request: Request) -> Optional[dict]:
    """
    Obtiene el usuario actual del request.state.
    
    Retorna None si no hay usuario autenticado.
    """
    return getattr(request.state, "user", None)
