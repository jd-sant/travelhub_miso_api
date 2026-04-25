from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status

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
    _: None = Depends(_verify_api_key),
    repository: UserRepository = Depends(get_user_repository),
) -> UserResponse:
    user = repository.get_by_id(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado",
        )
    return user


@router.post(
    "/users/search-by-name",
    response_model=list[UserSummary],
    status_code=status.HTTP_200_OK,
)
def search_users_by_name(
    payload: UserSearchByNameRequest,
    _: None = Depends(_verify_api_key),
    repository: UserRepository = Depends(get_user_repository),
) -> list[UserSummary]:
    return repository.search_by_name(payload.query)


@router.post(
    "/users/by-ids",
    response_model=list[UserSummary],
    status_code=status.HTTP_200_OK,
)
def list_users_by_ids(
    payload: UserBatchByIdsRequest,
    _: None = Depends(_verify_api_key),
    repository: UserRepository = Depends(get_user_repository),
) -> list[UserSummary]:
    return repository.list_by_ids(payload.ids)
