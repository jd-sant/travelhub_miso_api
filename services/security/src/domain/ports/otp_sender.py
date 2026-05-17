from abc import ABC, abstractmethod


class OtpSender(ABC):
    @abstractmethod
    def send(self, email: str, code: str) -> None:
        pass
