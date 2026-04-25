from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from domain.ports.property_service_client import PropertyServiceClient
from domain.ports.reservation_event_repository import ReservationEventRepository
from domain.ports.reservation_repository import ReservationRepository
from domain.schemas.property_service import (
    PropertyCancellationPolicyResponse,
    PropertyDetailResponse,
)
from domain.schemas.reservation import (
    CancellationPolicyType,
    ReservationEventCreateRequest,
    ReservationEventResult,
    ReservationEventType,
    ReservationPolicySnapshot,
    ReservationPriceBreakdown,
    ReservationResponse,
)
from errors import ReservationNotFoundError


class ReservationPreviewBaseUseCase:
    def __init__(
        self,
        reservation_repository: ReservationRepository,
        property_client: PropertyServiceClient,
        event_repository: ReservationEventRepository,
    ):
        self.reservation_repository = reservation_repository
        self.property_client = property_client
        self.event_repository = event_repository

    def _get_reservation(self, reservation_id: UUID) -> ReservationResponse:
        reservation = self.reservation_repository.get_by_id(reservation_id)
        if not reservation:
            raise ReservationNotFoundError("Reservation not found")
        return reservation

    def _get_property(self, property_id: UUID) -> PropertyDetailResponse:
        return self.property_client.get_property(property_id)

    def _get_policy(
        self, property_id: UUID
    ) -> PropertyCancellationPolicyResponse:
        return self.property_client.get_cancellation_policy(property_id)

    def _build_policy_snapshot(
        self, policy: PropertyCancellationPolicyResponse
    ) -> ReservationPolicySnapshot:
        return ReservationPolicySnapshot(
            policy_type=CancellationPolicyType(policy.policy_type),
            minimum_notice_hours=policy.minimum_notice_hours,
            penalty_percentage=policy.penalty_percentage,
            timezone=policy.timezone,
        )

    def _build_price_breakdown(
        self, total_price: Decimal, currency: str
    ) -> ReservationPriceBreakdown:
        return ReservationPriceBreakdown(total_price=total_price, currency=currency)

    def _normalize_datetime(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value
        return value.astimezone(UTC).replace(tzinfo=None)

    def _calculate_price_with_taxes(
        self, currency: str, check_in: datetime, check_out: datetime, number_of_guests: int, property_id: UUID | None = None
    ) -> Decimal:
        tax_rates = {
            "COP": Decimal("0.19"),
            "USD": Decimal("0.08"),
            "ARS": Decimal("0.21"),
            "CLP": Decimal("0.19"),
            "PEN": Decimal("0.18"),
            "MXN": Decimal("0.16"),
        }

        price_per_night = self._get_property_price(property_id) if property_id else Decimal(100)

        num_nights = (check_out - check_in).days
        base_price = price_per_night * number_of_guests * num_nights
        tax_rate = tax_rates.get(currency, Decimal("0.16"))
        total = base_price * (1 + tax_rate)
        return total.quantize(Decimal("0.01"))

    def _get_property_price(self, property_id: UUID | None) -> Decimal:
        try:
            if property_id and self.property_client:
                property_details = self.property_client.get_property(property_id)
                return property_details.price_per_night
        except Exception:
            pass
        return Decimal(100)

    def _record_event(
        self,
        *,
        reservation_id: UUID,
        event_type: ReservationEventType,
        result: ReservationEventResult,
        before_payload: dict | None = None,
        after_payload: dict | None = None,
    ) -> None:
        self.event_repository.add(
            ReservationEventCreateRequest(
                reservation_id=reservation_id,
                event_type=event_type,
                result=result,
                before_payload=before_payload,
                after_payload=after_payload,
            )
        )
