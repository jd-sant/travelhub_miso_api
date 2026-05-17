from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from adapters.services.privacy_audit_client import record_sensitive_data_event
from assembly import get_create_user_use_case, get_list_users_use_case
from core.decorators import require_role
from core.roles import UserRole
from core.transport import assert_secure_transport
from domain.schemas.user import UserCreateRequest, UserResponse
from domain.use_cases.create_user import CreateUserUseCase
from domain.use_cases.list_users import ListUsersUseCase
from errors import InvalidUserRoleError, UserConflictError

router = APIRouter(prefix="/users", tags=["users"])


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _current_user_id(request: Request) -> UUID | None:
    user = getattr(request.state, "user", None)
    if not isinstance(user, dict):
        return None
    raw_id = user.get("sub") or user.get("id")
    try:
        return UUID(str(raw_id)) if raw_id else None
    except ValueError:
        return None


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreateRequest,
    request: Request,
    use_case: CreateUserUseCase = Depends(get_create_user_use_case),
) -> UserResponse:
    assert_secure_transport(request)
    try:
        user = use_case.execute(payload)
        record_sensitive_data_event(
            action="user.pii.created",
            resource_type="user",
            resource_id=str(user.id),
            pii_fields=["email", "phone", "full_name", "hotel_name"],
            source_ip=_get_client_ip(request),
            actor_user_id=user.id,
            country_code=user.country_code,
            metadata={"channel": "public_registration"},
        )
        return user
    except UserConflictError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El correo electrónico ya existe",
        )
    except InvalidUserRoleError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )


@router.get("", response_model=list[UserResponse], status_code=status.HTTP_200_OK)
@require_role(UserRole.ADMIN)
def get_users(
    request: Request,
    use_case: ListUsersUseCase = Depends(get_list_users_use_case),
) -> list[UserResponse]:
    assert_secure_transport(request)
    users = use_case.execute()
    record_sensitive_data_event(
        action="user.pii.exported",
        resource_type="user",
        resource_id="bulk",
        pii_fields=["email", "phone", "full_name", "hotel_name"],
        source_ip=_get_client_ip(request),
        actor_user_id=_current_user_id(request),
        metadata={"count": len(users), "channel": "admin_users"},
    )
    return users
