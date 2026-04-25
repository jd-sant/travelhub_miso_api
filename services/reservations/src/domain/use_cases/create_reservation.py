from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from adapters.services.properties_client import PropertiesServiceClient
from domain.ports.reservation_repository import ReservationRepository
from domain.ports.reservation_scheduler import ReservationScheduler
from domain.schemas.reservation import ReservationCreateRequest, ReservationResponse
from domain.use_cases.base import BaseUseCase
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
    ):
        self.repository = repository
        self.scheduler = scheduler
        self.properties_client = properties_client

    def execute(self, payload: ReservationCreateRequest) -> ReservationResponse:
        reservation_id = uuid4()

        # Validar fechas
        if payload.check_in_date >= payload.check_out_date:
            raise InvalidReservationDateError(
                "Check-out date must be after check-in date"
            )

        # Verificar disponibilidad de la habitación
        is_available = self.repository.check_room_availability(
            payload.id_room, payload.check_in_date, payload.check_out_date
        )
        if not is_available:
            raise RoomNotAvailableError(
                f"Room {payload.id_room} is not available for the selected dates"
            )

        # Calcular el precio total con impuestos
        total_price = self._calculate_price_with_taxes(
            payload.id_property, payload.currency, payload.check_in_date, payload.check_out_date
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
            reservation = self.repository.add(payload, total_price, reservation_id=reservation_id)
        except Exception:
            if self.scheduler is not None:
                try:
                    self.scheduler.cancel_reservation_expiration(str(reservation_id))
                except Exception:
                    pass
            raise

        return reservation

    def _calculate_price_with_taxes(
        self, id_property: UUID, currency: str, check_in: datetime, check_out: datetime
    ) -> Decimal:
        """
        Calculate total price including local taxes based on country.
        Uses the property's real price_per_night when the properties client is
        available; otherwise falls back to a flat base rate.
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

        num_nights = (check_out - check_in).days
        per_night = Decimal("100")
        if self.properties_client is not None:
            try:
                property_data = self.properties_client.get_by_id(id_property)
                raw_rate = property_data.get("price_per_night")
                if raw_rate is not None:
                    per_night = Decimal(str(raw_rate))
            except Exception:
                pass

        base_price = per_night * num_nights
        tax_rate = tax_rates.get(currency, Decimal("0.16"))
        total = base_price * (1 + tax_rate)

        return total.quantize(Decimal("0.01"))
