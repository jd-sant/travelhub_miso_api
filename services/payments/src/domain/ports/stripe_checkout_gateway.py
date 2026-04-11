from abc import ABC, abstractmethod


class StripeCheckoutGateway(ABC):
    @abstractmethod
    def create_and_confirm_payment(
        self,
        *,
        amount_in_cents: int,
        currency: str,
        confirmation_token_id: str,
        idempotency_key: str,
        metadata: dict[str, str],
    ) -> dict:
        pass

    @abstractmethod
    def construct_event(self, *, payload: bytes, signature: str) -> dict:
        pass
