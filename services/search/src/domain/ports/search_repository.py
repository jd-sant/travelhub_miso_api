from abc import ABC, abstractmethod

from domain.schemas.search import SearchQuery, SearchResult


class SearchRepository(ABC):
    @abstractmethod
    def search(self, query: SearchQuery) -> SearchResult:
        pass
