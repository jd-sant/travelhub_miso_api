from uuid import UUID

from domain.ports.user_repository import UserRepository
from domain.schemas.user import UserResponse
from domain.use_cases.base import BaseUseCase
from errors import UserNotFoundError


class GetUserByIdUseCase(BaseUseCase[UUID, UserResponse]):
    def __init__(self, repository: UserRepository):
        self.repository = repository

    def execute(self, user_id: UUID) -> UserResponse:
        user = self.repository.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError(f"User {user_id} was not found")
        return user
