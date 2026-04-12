from core.config import settings
from domain.ports.stripe_checkout_gateway import StripeCheckoutGateway
from errors import StripeIdempotencyConflictError, StripePaymentFailureError


class StripeSdkCheckoutGateway(StripeCheckoutGateway):
    def __init__(self):
        import stripe

        self._stripe = stripe
        stripe.api_key = settings.stripe_secret_key.get_secret_value()

    def create_and_confirm_payment(
        self,
        *,
        amount_in_cents: int,
        currency: str,
        confirmation_token_id: str,
        idempotency_key: str,
        metadata: dict[str, str],
    ) -> dict:
        try:
            intent = self._stripe.PaymentIntent.create(
                amount=amount_in_cents,
                currency=currency.lower(),
                confirm=True,
                automatic_payment_methods={"enabled": True},
                confirmation_token=confirmation_token_id,
                metadata=metadata,
                idempotency_key=idempotency_key,
            )
            return dict(intent)
        except self._stripe.error.CardError as exc:
            error_payload = self._extract_card_error_payload(exc)
            raise StripePaymentFailureError(
                code=(
                    error_payload.get("decline_code")
                    or error_payload.get("code")
                    or getattr(exc, "code", None)
                ),
                message=(
                    error_payload.get("message")
                    or getattr(exc, "user_message", None)
                    or str(exc)
                ),
            ) from exc
        except self._stripe.error.IdempotencyError as exc:
            raise StripeIdempotencyConflictError(str(exc)) from exc

    def construct_event(self, *, payload: bytes, signature: str) -> dict:
        event = self._stripe.Webhook.construct_event(
            payload=payload,
            sig_header=signature,
            secret=settings.stripe_webhook_secret.get_secret_value(),
        )
        return dict(event)

    def _extract_card_error_payload(self, exc) -> dict[str, str | None]:
        payload: dict[str, str | None] = {
            "code": None,
            "decline_code": None,
            "message": None,
        }

        error = getattr(exc, "error", None)
        if error is not None:
            payload["code"] = getattr(error, "code", None)
            payload["decline_code"] = getattr(error, "decline_code", None)
            payload["message"] = getattr(error, "message", None)

        if payload["message"] is None:
            json_body = getattr(exc, "json_body", None)
            if isinstance(json_body, dict):
                error_body = json_body.get("error")
                if isinstance(error_body, dict):
                    payload["code"] = payload["code"] or error_body.get("code")
                    payload["decline_code"] = payload["decline_code"] or error_body.get("decline_code")
                    payload["message"] = payload["message"] or error_body.get("message")

        return payload
