from fastapi import APIRouter, Depends, HTTPException, Request, status

from assembly import get_create_user_use_case, get_list_users_use_case
from core.decorators import require_role
from core.roles import UserRole
from domain.schemas.user import UserCreateRequest, UserResponse
from domain.use_cases.create_user import CreateUserUseCase
from domain.use_cases.list_users import ListUsersUseCase
from errors import UserConflictError

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreateRequest,
    use_case: CreateUserUseCase = Depends(get_create_user_use_case),
) -> UserResponse:
    try:
        return use_case.execute(payload)
    except UserConflictError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El correo electrónico ya existe",
        )


@router.get("", response_model=list[UserResponse], status_code=status.HTTP_200_OK)
@require_role(UserRole.ADMIN)
def get_users(
    request: Request,
    use_case: ListUsersUseCase = Depends(get_list_users_use_case),
) -> list[UserResponse]:
    return use_case.execute()
