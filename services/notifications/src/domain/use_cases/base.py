from abc import ABC, abstractmethod
from typing import Generic, TypeVar

RequestT = TypeVar("RequestT")
ResponseT = TypeVar("ResponseT")


class BaseUseCase(ABC, Generic[RequestT, ResponseT]):
    @abstractmethod
    def execute(self, request: RequestT) -> ResponseT:
        raise NotImplementedError
