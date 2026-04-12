from domain.ports.search_repository import SearchRepository
from domain.schemas.search import SearchQuery, SearchResult
from domain.use_cases.base import BaseUseCase


class SearchPropertiesUseCase(BaseUseCase[SearchQuery, SearchResult]):
    def __init__(self, repository: SearchRepository):
        self.repository = repository

    def execute(self, payload: SearchQuery) -> SearchResult:
        return self.repository.search(payload)
