from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

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
    ):
        self.repository = repository
        self.scheduler = scheduler

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
        self, id_property: UUID, currency: str, check_in: datetime, check_out: datetime
    ) -> Decimal:
        """
        Calculate total price including local taxes based on country
        Supports: COP, USD, ARS, CLP, PEN, MXN
        """
        # TODO: usar id_property para consultar la tarifa real por noche
        # desde el servicio de propiedades cuando ese endpoint este disponible.
        # Tarifas de impuestos por país (normalmente vendrían de un servicio externo)
        tax_rates = {
            "COP": Decimal("0.19"),  # Colombia 19%
            "USD": Decimal("0.08"),  # Estados Unidos 8%
            "ARS": Decimal("0.21"),  # Argentina 21%
            "CLP": Decimal("0.19"),  # Chile 19%
            "PEN": Decimal("0.18"),  # Perú 18%
            "MXN": Decimal("0.16"),  # México 16%
        }

        # Cálculo base: 100 por noche (simplificado; vendría de la tarifa real de la habitación)
        num_nights = (check_out - check_in).days
        base_price = Decimal(100) * num_nights

        # Aplicar impuesto
        tax_rate = tax_rates.get(currency, Decimal("0.16"))
        total = base_price * (1 + tax_rate)

        return total.quantize(Decimal("0.01"))
