from uuid import uuid4

from domain.ports.payment_gateway import PaymentGateway
from domain.schemas.payment import GatewayChargeResult, PaymentChargeRequest, PaymentStatus
from errors import UnsupportedPaymentOperationError


class FakeStripePaymentGateway(PaymentGateway):
    def charge(self, payload: PaymentChargeRequest) -> GatewayChargeResult:
        token = payload.payment_method_token.lower()
        charge_id = f"ch_{uuid4().hex[:24]}"

        if token.startswith("pm_fail_insufficient_funds"):
            return GatewayChargeResult(
                status=PaymentStatus.failed,
                gateway_charge_id=charge_id,
                gateway_status="failed",
                failure_reason="insufficient_funds",
            )

        if token.startswith("pm_fail"):
            return GatewayChargeResult(
                status=PaymentStatus.failed,
                gateway_charge_id=charge_id,
                gateway_status="failed",
                failure_reason="card_declined",
            )

        return GatewayChargeResult(
            status=PaymentStatus.confirmed,
            gateway_charge_id=charge_id,
            gateway_status="succeeded",
            card_brand="visa",
            card_last4="4242",
        )


class UnsupportedDirectChargeGateway(PaymentGateway):
    def __init__(self, provider_code: str):
        self.provider_code = provider_code

    def charge(self, payload: PaymentChargeRequest) -> GatewayChargeResult:
        raise UnsupportedPaymentOperationError(
            "El endpoint /payments/charges solo esta disponible cuando "
            f"PAYMENT_PROVIDER=fake_stripe. Proveedor configurado: {self.provider_code}."
        )
