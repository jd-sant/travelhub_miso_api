"""Dependency providers for the Search service."""

from sqlmodel import Session

from adapters.repositories import SQLModelSearchRepository
from domain.use_cases import SearchPropertiesUseCase


def get_search_repository(session: Session) -> SQLModelSearchRepository:
    return SQLModelSearchRepository(session)


def get_search_properties_use_case(
    session: Session,
) -> SearchPropertiesUseCase:
    repository = get_search_repository(session)
    return SearchPropertiesUseCase(repository)
