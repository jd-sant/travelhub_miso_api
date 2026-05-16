from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from adapters.services.privacy_audit_client import record_sensitive_data_event
from assembly import get_user_repository, get_verify_credentials_use_case
from core.config import settings
from domain.ports.user_repository import UserRepository
from domain.schemas.user import (
    UserBatchByIdsRequest,
    UserResponse,
    UserSearchByNameRequest,
    UserSummary,
    VerifyCredentialsRequest,
    VerifyCredentialsResponse,
)
from domain.use_cases.verify_credentials import VerifyCredentialsUseCase
from errors import InvalidCredentialsError

router = APIRouter(prefix="/internal", tags=["internal"])


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _verify_api_key(
    x_internal_api_key: str = Header(default=None),
) -> None:
    if x_internal_api_key != settings.internal_api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden",
        )


@router.post(
    "/verify-credentials",
    response_model=VerifyCredentialsResponse,
    status_code=status.HTTP_200_OK,
)
def verify_credentials(
    payload: VerifyCredentialsRequest,
    _: None = Depends(_verify_api_key),
    use_case: VerifyCredentialsUseCase = Depends(
        get_verify_credentials_use_case
    ),
) -> VerifyCredentialsResponse:
    try:
        return use_case.execute(payload)
    except InvalidCredentialsError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas",
        )


@router.get(
    "/users/{user_id}",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
)
def get_user_by_id(
    user_id: UUID,
    request: Request,
    _: None = Depends(_verify_api_key),
    x_actor_user_id: str | None = Header(default=None),
    repository: UserRepository = Depends(get_user_repository),
) -> UserResponse:
    user = repository.get_by_id(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado",
        )
    actor_user_id = _parse_uuid(x_actor_user_id)
    record_sensitive_data_event(
        action="user.pii.accessed",
        resource_type="user",
        resource_id=str(user.id),
        pii_fields=["email", "phone", "full_name", "hotel_name"],
        source_ip=_get_client_ip(request),
        actor_user_id=actor_user_id,
        country_code=user.country_code,
        metadata={"channel": "internal_user_lookup"},
    )
    return user


@router.post(
    "/users/search-by-name",
    response_model=list[UserSummary],
    status_code=status.HTTP_200_OK,
)
def search_users_by_name(
    payload: UserSearchByNameRequest,
    request: Request,
    _: None = Depends(_verify_api_key),
    x_actor_user_id: str | None = Header(default=None),
    repository: UserRepository = Depends(get_user_repository),
) -> list[UserSummary]:
    users = repository.search_by_name(payload.query)
    record_sensitive_data_event(
        action="user.pii.searched",
        resource_type="user",
        resource_id="search-by-name",
        pii_fields=["email", "full_name"],
        source_ip=_get_client_ip(request),
        actor_user_id=_parse_uuid(x_actor_user_id),
        metadata={"result_count": len(users)},
    )
    return users


@router.post(
    "/users/by-ids",
    response_model=list[UserSummary],
    status_code=status.HTTP_200_OK,
)
def list_users_by_ids(
    payload: UserBatchByIdsRequest,
    request: Request,
    _: None = Depends(_verify_api_key),
    x_actor_user_id: str | None = Header(default=None),
    repository: UserRepository = Depends(get_user_repository),
) -> list[UserSummary]:
    users = repository.list_by_ids(payload.ids)
    record_sensitive_data_event(
        action="user.pii.batch_accessed",
        resource_type="user",
        resource_id="by-ids",
        pii_fields=["email", "full_name"],
        source_ip=_get_client_ip(request),
        actor_user_id=_parse_uuid(x_actor_user_id),
        metadata={"requested_count": len(payload.ids), "result_count": len(users)},
    )
    return users


def _parse_uuid(value: str | None) -> UUID | None:
    if not value:
        return None
    try:
        return UUID(value)
    except ValueError:
        return None
