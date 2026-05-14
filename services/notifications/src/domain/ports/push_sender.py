from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class PushSendResult:
    provider_message_id: str
    success: bool
    error: str | None = None


class PushSender(ABC):
    @abstractmethod
    def send(
        self,
        *,
        device_token: str,
        title: str,
        body: str,
        data: dict[str, str],
    ) -> PushSendResult:
        raise NotImplementedError
