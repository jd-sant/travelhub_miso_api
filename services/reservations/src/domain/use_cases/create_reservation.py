from datetime import datetime
from decimal import Decimal
from uuid import UUID

from domain.ports.reservation_repository import ReservationRepository
from domain.schemas.reservation import ReservationCreateRequest, ReservationResponse
from domain.use_cases.base import BaseUseCase
from errors import InvalidReservationDateError, RoomNotAvailableError


class CreateReservationUseCase(BaseUseCase[ReservationCreateRequest, ReservationResponse]):
    def __init__(self, repository: ReservationRepository):
        self.repository = repository

    def execute(self, payload: ReservationCreateRequest) -> ReservationResponse:
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

        # Crear la reserva con el precio calculado
        reservation = self.repository.add(payload, total_price)
        return reservation

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
