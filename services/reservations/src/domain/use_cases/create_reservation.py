from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from adapters.services.properties_client import PropertiesServiceClient
from core.config import settings
from domain.ports.reservation_repository import ReservationRepository
from domain.ports.reservation_scheduler import ReservationScheduler
from domain.schemas.reservation import ReservationCreateRequest, ReservationResponse
from domain.use_cases.base import BaseUseCase
from domain.ports.property_service_client import PropertyServiceClient
from errors import (
    InvalidReservationDateError,
    ReservationSchedulingError,
    RoomNotAvailableError,
)


@dataclass(frozen=True)
class ComputedBreakdown:
    accommodation_in_cents: int
    cleaning_fee_in_cents: int
    service_fee_in_cents: int
    taxes_in_cents: int
    nights: int
    nightly_rate_in_cents: int

    @property
    def total_in_cents(self) -> int:
        return (
            self.accommodation_in_cents
            + self.cleaning_fee_in_cents
            + self.service_fee_in_cents
            + self.taxes_in_cents
        )


class CreateReservationUseCase(BaseUseCase[ReservationCreateRequest, ReservationResponse]):
    def __init__(
        self,
        repository: ReservationRepository,
        scheduler: ReservationScheduler | None = None,
        properties_client: PropertiesServiceClient | None = None,
        property_client: PropertyServiceClient | None = None,
    ):
        self.repository = repository
        self.scheduler = scheduler
        self.properties_client = properties_client
        self.property_client = property_client

    def execute(self, payload: ReservationCreateRequest) -> ReservationResponse:
        reservation_id = uuid4()
        normalized_payload = ReservationCreateRequest(
            id_traveler=payload.id_traveler,
            id_property=payload.id_property,
            id_room=payload.id_room,
            check_in_date=self._normalize_datetime(payload.check_in_date),
            check_out_date=self._normalize_datetime(payload.check_out_date),
            number_of_guests=payload.number_of_guests,
            currency=payload.currency,
        )

        # Validar fechas
        if normalized_payload.check_in_date >= normalized_payload.check_out_date:
            raise InvalidReservationDateError(
                "Check-out date must be after check-in date"
            )

        # Verificar disponibilidad de la habitación
        is_available = self.repository.check_room_availability(
            normalized_payload.id_room,
            normalized_payload.check_in_date,
            normalized_payload.check_out_date,
        )
        if not is_available:
            raise RoomNotAvailableError(
                f"Room {normalized_payload.id_room} is not available for the selected dates"
            )

        # Calcular el desglose canónico de precio
        breakdown = self._calculate_breakdown(
            normalized_payload.id_property,
            normalized_payload.check_in_date,
            normalized_payload.check_out_date,
            normalized_payload.number_of_guests,
        )
        total_price = (Decimal(breakdown.total_in_cents) / Decimal(100)).quantize(
            Decimal("0.01")
        )

        if self.scheduler is not None:
            try:
                self.scheduler.schedule_reservation_expiration(str(reservation_id))
            except Exception as exc:
                raise ReservationSchedulingError(
                    "La reservacion no pudo completarse"
                ) from exc

        # Crear la reserva con el precio calculado
        try:
            reservation = self.repository.add(
                normalized_payload,
                total_price,
                reservation_id=reservation_id,
                breakdown=breakdown,
            )
        except Exception:
            if self.scheduler is not None:
                try:
                    self.scheduler.cancel_reservation_expiration(str(reservation_id))
                except Exception:
                    pass
            raise

        return reservation

    def _normalize_datetime(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value
        return value.astimezone(UTC).replace(tzinfo=None)

    def _calculate_breakdown(
        self,
        id_property: UUID,
        check_in: datetime,
        check_out: datetime,
        guests: int,
    ) -> ComputedBreakdown:
        """
        Construye el desglose canónico de precio:
            accommodation = price_per_night x nights x guests
            service_fee   = round(accommodation x service_fee_rate)
            subtotal      = accommodation + cleaning_fee + service_fee
            taxes         = round(subtotal x property.tax_rate)
            total         = subtotal + taxes
        Cuando la propiedad no está disponible se usan defaults razonables
        para que la reserva pueda crearse en entornos sin properties.
        """
        nights = max(1, (check_out - check_in).days)
        guests = max(1, guests)
        price_per_night, cleaning_fee, tax_rate = self._fetch_property_pricing(
            id_property
        )
        service_fee_rate = Decimal(settings.service_fee_rate)

        accommodation_cents = int(
            (price_per_night * nights * guests * 100).to_integral_value()
        )
        cleaning_cents = int((cleaning_fee * 100).to_integral_value())
        service_cents = int(
            (Decimal(accommodation_cents) * service_fee_rate).to_integral_value()
        )
        subtotal_cents = accommodation_cents + cleaning_cents + service_cents
        taxes_cents = int(
            (Decimal(subtotal_cents) * tax_rate).to_integral_value()
        )
        nightly_rate_cents = (
            accommodation_cents // nights if nights > 0 else accommodation_cents
        )

        return ComputedBreakdown(
            accommodation_in_cents=accommodation_cents,
            cleaning_fee_in_cents=cleaning_cents,
            service_fee_in_cents=service_cents,
            taxes_in_cents=taxes_cents,
            nights=nights,
            nightly_rate_in_cents=nightly_rate_cents,
        )

    def _fetch_property_pricing(
        self, property_id: UUID
    ) -> tuple[Decimal, Decimal, Decimal]:
        import logging
        logger = logging.getLogger(__name__)
        if not self.property_client:
            logger.warning("property_pricing_no_client", extra={"property_id": str(property_id)})
            return (Decimal(100), Decimal(0), Decimal("0.16"))
        try:
            details = self.property_client.get_property(property_id)
            return (
                details.price_per_night,
                details.cleaning_fee,
                details.tax_rate,
            )
        except Exception as exc:
            logger.warning(
                "property_pricing_fetch_failed",
                extra={"property_id": str(property_id), "error": str(exc)},
            )
            return (Decimal(100), Decimal(0), Decimal("0.16"))
