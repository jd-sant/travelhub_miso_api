from abc import ABC, abstractmethod

from domain.schemas.availability import (
    PropertyAvailabilityQuery,
    PropertyAvailabilityResponse,
)
from domain.schemas.search import SearchQuery, SearchResult


class SearchRepository(ABC):
    @abstractmethod
    def search(self, query: SearchQuery) -> SearchResult:
        pass

    @abstractmethod
    def check_availability(
        self, query: PropertyAvailabilityQuery
    ) -> PropertyAvailabilityResponse:
        pass
