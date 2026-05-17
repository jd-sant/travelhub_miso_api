from core.security import verify_password
from domain.ports.user_repository import UserRepository
from domain.schemas.user import VerifyCredentialsRequest, VerifyCredentialsResponse
from domain.use_cases.base import BaseUseCase
from errors import InvalidCredentialsError


class VerifyCredentialsUseCase(
    BaseUseCase[VerifyCredentialsRequest, VerifyCredentialsResponse]
):
    def __init__(self, repository: UserRepository):
        self.repository = repository

    def execute(
        self, payload: VerifyCredentialsRequest
    ) -> VerifyCredentialsResponse:
        data = self.repository.get_by_email_with_password_and_roles(
            str(payload.email)
        )
        if data is None:
            raise InvalidCredentialsError()

        if not verify_password(payload.password, data.password):
            raise InvalidCredentialsError()

        return VerifyCredentialsResponse(
            id=data.id,
            email=data.email,
            status=data.status,
            roles=data.roles,
        )
