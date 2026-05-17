from domain.ports.user_repository import UserRepository
from domain.schemas.user import UserResponse
from domain.use_cases.base import BaseUseCase


class ListUsersUseCase(BaseUseCase[None, list[UserResponse]]):
    def __init__(self, repository: UserRepository):
        self.repository = repository

    def execute(self) -> list[UserResponse]:
        return self.repository.list_all()
