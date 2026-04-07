from datetime import UTC, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from adapters.models.reservation import Reservation
from domain.ports.reservation_repository import ReservationRepository
from domain.schemas.reservation import ReservationCreateRequest, ReservationResponse
from errors import ReservationConflictError, RoomNotAvailableError


def _to_response(model: Reservation) -> ReservationResponse:
    return ReservationResponse(
        id=model.id,
        id_traveler=model.id_traveler,
        id_property=model.id_property,
        id_room=model.id_room,
        check_in_date=model.check_in_date,
        check_out_date=model.check_out_date,
        number_of_guests=model.number_of_guests,
        total_price=model.total_price,
        currency=model.currency,
        status=model.status,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class SQLModelReservationRepository(ReservationRepository):
    def __init__(self, session: Session):
        self.session = session

    def add(self, payload: ReservationCreateRequest, total_price: Decimal) -> ReservationResponse:
        # Verificar disponibilidad antes de crear
        if not self.check_room_availability(
            payload.id_room, payload.check_in_date, payload.check_out_date
        ):
            raise RoomNotAvailableError(
                f"Room {payload.id_room} is not available for the selected dates"
            )

        reservation = Reservation(
            id_traveler=payload.id_traveler,
            id_property=payload.id_property,
            id_room=payload.id_room,
            check_in_date=payload.check_in_date,
            check_out_date=payload.check_out_date,
            number_of_guests=payload.number_of_guests,
            total_price=total_price,
            currency=payload.currency,
            status="pending_payment",
        )
        self.session.add(reservation)
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise ReservationConflictError("Conflict while creating reservation") from exc
        self.session.refresh(reservation)
        return _to_response(reservation)

    def get_by_id(self, id: UUID) -> Optional[ReservationResponse]:
        model = self.session.exec(
            select(Reservation).where(Reservation.id == id)
        ).first()
        return _to_response(model) if model else None

    def list_by_traveler(self, id_traveler: UUID) -> list[ReservationResponse]:
        models = self.session.exec(
            select(Reservation).where(Reservation.id_traveler == id_traveler)
        ).all()
        return [_to_response(m) for m in models]

    def check_room_availability(
        self, id_room: UUID, check_in: datetime, check_out: datetime
    ) -> bool:
        # Verificar si la habitación tiene reservas activas en el rango de fechas
        conflicting = self.session.exec(
            select(Reservation).where(
                (Reservation.id_room == id_room)
                & (Reservation.status != "cancelled")
                & (Reservation.check_in_date < check_out)
                & (Reservation.check_out_date > check_in)
            )
        ).first()
        return conflicting is None

    def update_status(self, id: UUID, status: str) -> Optional[ReservationResponse]:
        reservation = self.session.exec(
            select(Reservation).where(Reservation.id == id)
        ).first()
        if not reservation:
            return None
        reservation.status = status
        reservation.updated_at = datetime.now(UTC)
        self.session.add(reservation)
        self.session.commit()
        self.session.refresh(reservation)
        return _to_response(reservation)
