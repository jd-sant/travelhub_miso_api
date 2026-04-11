from fastapi import Depends
from sqlmodel import Session

from adapters.repositories.property_repository import (
    SQLModelPropertyRepository,
)
from db.session import get_session
from domain.ports.property_repository import PropertyRepository
from domain.use_cases.get_property_detail import (
    GetPropertyDetailUseCase,
)
from domain.use_cases.get_properties_list import (
    GetPropertiesListUseCase,
)


def get_property_repository(
    session: Session = Depends(get_session),
) -> PropertyRepository:
    return SQLModelPropertyRepository(session)


def get_property_detail_use_case(
    repository: PropertyRepository = Depends(get_property_repository),
) -> GetPropertyDetailUseCase:
    return GetPropertyDetailUseCase(repository)


def get_properties_list_use_case(
    repository: PropertyRepository = Depends(get_property_repository),
) -> GetPropertiesListUseCase:
    return GetPropertiesListUseCase(repository)
