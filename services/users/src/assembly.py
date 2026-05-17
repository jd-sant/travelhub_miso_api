from fastapi import Depends
from sqlmodel import Session

from adapters.repositories.user_repository import SQLModelUserRepository
from db.session import get_session
from domain.ports.user_repository import UserRepository
from domain.use_cases.create_user import CreateUserUseCase
from domain.use_cases.list_users import ListUsersUseCase
from domain.use_cases.verify_credentials import VerifyCredentialsUseCase


def get_user_repository(
    session: Session = Depends(get_session),
) -> UserRepository:
    return SQLModelUserRepository(session)


def get_create_user_use_case(
    repository: UserRepository = Depends(get_user_repository),
) -> CreateUserUseCase:
    return CreateUserUseCase(repository)


def get_list_users_use_case(
    repository: UserRepository = Depends(get_user_repository),
) -> ListUsersUseCase:
    return ListUsersUseCase(repository)


def get_verify_credentials_use_case(
    repository: UserRepository = Depends(get_user_repository),
) -> VerifyCredentialsUseCase:
    return VerifyCredentialsUseCase(repository)
