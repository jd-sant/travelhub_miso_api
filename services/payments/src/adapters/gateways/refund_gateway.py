from domain.ports.refund_gateway import RefundGateway


class DefaultRefundGateway(RefundGateway):
    def process_refund(self, *, reason: str) -> None:
        _ = reason