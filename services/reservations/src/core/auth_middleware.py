from typing import Optional

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from core.jwt_handler import decode_token
from errors import InvalidTokenError, TokenExpiredError


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        auth_header = request.headers.get("Authorization")
        if auth_header:
            try:
                token = auth_header.replace("Bearer ", "")
                request.state.user = decode_token(token)
            except (InvalidTokenError, TokenExpiredError):
                pass
            except Exception:
                pass
        return await call_next(request)


def get_current_user(request: Request) -> Optional[dict]:
    return getattr(request.state, "user", None)
