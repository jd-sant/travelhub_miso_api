from abc import ABC, abstractmethod
from typing import Generic, TypeVar

InputType = TypeVar("InputType")
OutputType = TypeVar("OutputType")


class BaseUseCase(ABC, Generic[InputType, OutputType]):
    @abstractmethod
    def execute(self, payload: InputType) -> OutputType:
        pass
