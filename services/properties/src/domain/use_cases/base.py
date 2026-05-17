from abc import ABC, abstractmethod
from typing import Generic, TypeVar

TInput = TypeVar("TInput")
TOutput = TypeVar("TOutput")


class BaseUseCase(ABC, Generic[TInput, TOutput]):
    @abstractmethod
    def execute(self, *args, **kwargs) -> TOutput:
        pass
