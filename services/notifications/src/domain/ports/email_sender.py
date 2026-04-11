from abc import ABC, abstractmethod


class EmailSender(ABC):
    @abstractmethod
    def send(self, *, recipient_email: str, subject: str, body: str) -> str:
        raise NotImplementedError
