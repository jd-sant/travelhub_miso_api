from uuid import UUID

from core.jwt_handler import decode_token
from domain.schemas.auth import TokenValidationRequest, TokenValidationResponse
from domain.use_cases.base import BaseUseCase
from errors import InvalidTokenError


class ValidateTokenUseCase(
    BaseUseCase[TokenValidationRequest, TokenValidationResponse]
):
    def execute(
        self, payload: TokenValidationRequest
    ) -> TokenValidationResponse:
        claims = decode_token(payload.token)
        try:
            user_id = UUID(claims["sub"])
        except (ValueError, KeyError) as exc:
            raise InvalidTokenError("Token inválido") from exc
        return TokenValidationResponse(
            user_id=user_id,
            email=claims["email"],
            role=claims["role"],
            valid=True,
        )
