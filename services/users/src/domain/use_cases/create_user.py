from core.roles import UserRole
from domain.ports.user_repository import UserRepository
from domain.schemas.user import UserCreateRequest, UserResponse
from domain.use_cases.base import BaseUseCase
from errors import InvalidUserRoleError, UserConflictError


class CreateUserUseCase(BaseUseCase[UserCreateRequest, UserResponse]):
    def __init__(self, repository: UserRepository):
        self.repository = repository

    def execute(self, payload: UserCreateRequest) -> UserResponse:
        existing = self.repository.get_by_email(str(payload.email))
        if existing is not None:
            raise UserConflictError("El correo electrónico ya existe")

        requested_role = (payload.role or "").strip().lower()
        normalized_role = "hotel" if requested_role == "hotel_partner" else requested_role
        if normalized_role and not UserRole.is_valid(normalized_role):
            raise InvalidUserRoleError("El rol solicitado no es válido")

        user = self.repository.add(payload)
        role = (
            UserRole.HOTEL
            if normalized_role == UserRole.HOTEL or payload.hotel_name
            else UserRole.TRAVELER
        )
        self.repository.assign_role(user.id, role)
        return user
