from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from adapters.services.properties_client import PropertiesServiceClient
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

        # Calcular el precio total con impuestos
        total_price = self._calculate_price_with_taxes(
            normalized_payload.id_property,
            normalized_payload.currency,
            normalized_payload.check_in_date,
            normalized_payload.check_out_date,
            normalized_payload.number_of_guests,
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
                normalized_payload, total_price, reservation_id=reservation_id
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

    def _calculate_price_with_taxes(
        self, id_property: UUID, currency: str, check_in: datetime, check_out: datetime, number_of_guests: int
    ) -> Decimal:
        """
        Calculate total price including local taxes based on country.
        Uses the property's real price_per_night when the properties client is
        available; otherwise falls back to a flat base rate.
        Formula: price_per_night × guests × nights × (1 + tax_rate)
       Supports: COP, USD, ARS, CLP, PEN, MXN
        """
        tax_rates = {
            "COP": Decimal("0.19"),
            "USD": Decimal("0.08"),
            "ARS": Decimal("0.21"),
            "CLP": Decimal("0.19"),
            "PEN": Decimal("0.18"),
            "MXN": Decimal("0.16"),
        }

        price_per_night = self._get_property_price(id_property)

        num_nights = (check_out - check_in).days
        base_price = price_per_night * number_of_guests * num_nights

        tax_rate = tax_rates.get(currency, Decimal("0.16"))
        total = base_price * (1 + tax_rate)

        return total.quantize(Decimal("0.01"))

    def _get_property_price(self, property_id: UUID) -> Decimal:
        try:
            if self.property_client:
                property_details = self.property_client.get_property(property_id)
                return property_details.price_per_night
        except Exception:
            pass
        return Decimal(100)
