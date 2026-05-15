from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from core.config import settings
from domain.ports.property_service_client import PropertyServiceClient
from domain.ports.pricing_service_client import PricingServiceClient
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
        pricing_client: PricingServiceClient | None = None,
    ):
        self.reservation_repository = reservation_repository
        self.property_client = property_client
        self.event_repository = event_repository
        self.pricing_client = pricing_client

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
        self,
        currency: str,
        check_in: datetime,
        check_out: datetime,
        number_of_guests: int,
        property_id: UUID | None = None,
    ) -> Decimal:
        """Espejo de la fórmula canónica de `CreateReservationUseCase`:
            accommodation = price_per_night × nights × guests
            service       = round(accommodation × service_fee_rate)
            subtotal      = accommodation + cleaning_fee + service
            taxes         = round(subtotal × property.tax_rate)
            total         = subtotal + taxes
        """
        nights = max(1, (check_out - check_in).days)
        guests = max(1, number_of_guests)
        price_per_night, cleaning_fee, tax_rate = self._fetch_property_pricing(
            property_id=property_id,
            check_in=check_in,
            check_out=check_out,
            guests=guests,
            expected_currency=currency,
        )
        service_fee_rate = Decimal(settings.service_fee_rate)

        accommodation = (price_per_night * nights * guests).quantize(Decimal("0.01"))
        cleaning = cleaning_fee.quantize(Decimal("0.01"))
        service = (accommodation * service_fee_rate).quantize(Decimal("0.01"))
        subtotal = accommodation + cleaning + service
        taxes = (subtotal * tax_rate).quantize(Decimal("0.01"))
        return (subtotal + taxes).quantize(Decimal("0.01"))

    def _fetch_property_pricing(
        self,
        property_id: UUID | None,
        check_in: datetime | None = None,
        check_out: datetime | None = None,
        guests: int = 1,
        expected_currency: str | None = None,
    ) -> tuple[Decimal, Decimal, Decimal]:
        if not (property_id and self.property_client):
            return (Decimal(100), Decimal(0), Decimal("0.16"))
        try:
            details = self.property_client.get_property(property_id)
            effective_price = None
            if (
                self.pricing_client is not None
                and check_in is not None
                and check_out is not None
            ):
                effective_price = self.pricing_client.get_effective_price(
                    property_id=property_id,
                    check_in=check_in,
                    check_out=check_out,
                    guests=guests,
                )
            nightly_price = details.price_per_night
            if effective_price is not None:
                effective_price_amount, effective_currency = effective_price
                property_currency = (expected_currency or "").upper()
                if property_currency and effective_currency.upper() == property_currency:
                    nightly_price = effective_price_amount
            return (
                nightly_price,
                details.cleaning_fee,
                details.tax_rate,
            )
        except Exception:
            return (Decimal(100), Decimal(0), Decimal("0.16"))

    def _get_property_price(self, property_id: UUID | None) -> Decimal:
        return self._fetch_property_pricing(property_id)[0]

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
