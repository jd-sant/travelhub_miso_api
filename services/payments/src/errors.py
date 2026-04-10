from uuid import UUID


class PaymentNotFoundError(Exception):
    pass


class DuplicatePaymentError(Exception):
    def __init__(self, duplicate_payment_id: UUID, reason: str = "duplicate_window"):
        self.duplicate_payment_id = duplicate_payment_id
        self.reason = reason
        super().__init__(f"Duplicate payment detected: {duplicate_payment_id}")


class InvalidChecksumError(Exception):
    pass


class InsecureTransportError(Exception):
    pass


class UnsupportedPaymentOperationError(Exception):
    pass


class PaymentCheckoutSessionNotFoundError(Exception):
    pass


class StripeConfigurationError(Exception):
    pass


class StripeWebhookVerificationError(Exception):
    pass


class StripePaymentFailureError(Exception):
    def __init__(self, code: str | None = None, message: str | None = None):
        self.code = code
        self.message = message
        super().__init__(message or code or "Stripe payment failed")


class StripeIdempotencyConflictError(Exception):
    pass
