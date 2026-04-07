from domain.ports.user_repository import UserRepository
from domain.schemas.user import UserCreateRequest, UserResponse
from domain.use_cases.base import BaseUseCase
from errors import UserConflictError


class CreateUserUseCase(BaseUseCase[UserCreateRequest, UserResponse]):
    def __init__(self, repository: UserRepository):
        self.repository = repository

    def execute(self, payload: UserCreateRequest) -> UserResponse:
        existing = self.repository.get_by_email(str(payload.email))
        if existing is not None:
            raise UserConflictError("El correo electrónico ya existe")

        user = self.repository.add(payload)
        self.repository.assign_role(user.id, payload.role)
        return user
