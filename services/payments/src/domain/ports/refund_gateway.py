from abc import ABC, abstractmethod


class RefundGateway(ABC):
    @abstractmethod
    def process_refund(self, *, reason: str) -> None:
        pass