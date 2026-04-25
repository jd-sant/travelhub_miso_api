from typing import Optional

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from core.jwt_handler import decode_token
from errors import InvalidTokenError, TokenExpiredError


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        auth_header = request.headers.get("Authorization")
        if auth_header:
            try:
                scheme, token = auth_header.strip().split(" ", 1)
                if scheme.lower() != "bearer" or not token.strip():
                    return JSONResponse(
                        status_code=401,
                        content={"detail": "Token de autenticación inválido"},
                    )
                request.state.user = decode_token(token.strip())
            except (InvalidTokenError, TokenExpiredError, ValueError):
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Token de autenticación inválido"},
                )
        return await call_next(request)


def get_current_user(request: Request) -> Optional[dict]:
    return getattr(request.state, "user", None)
