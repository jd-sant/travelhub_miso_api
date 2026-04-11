from abc import ABC, abstractmethod

from domain.schemas.payment import GatewayChargeResult, PaymentChargeRequest


class PaymentGateway(ABC):
    @abstractmethod
    def charge(self, payload: PaymentChargeRequest) -> GatewayChargeResult:
        pass
