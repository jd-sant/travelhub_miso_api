from core.roles import UserRole
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
            raise UserConflictError("El correo electronico ya existe")

        user = self.repository.add(payload)
        requested_role = (payload.role or "").strip().lower()
        role = (
            UserRole.HOTEL
            if requested_role in {"hotel", "hotel_partner"} or payload.hotel_name
            else UserRole.TRAVELER
        )
        self.repository.assign_role(user.id, role)
        return user
