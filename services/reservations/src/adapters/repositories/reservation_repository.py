from datetime import UTC, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy import update
from sqlmodel import Session, select

from adapters.models.reservation import Reservation
from domain.ports.reservation_repository import ReservationRepository
from domain.schemas.reservation import ReservationCreateRequest, ReservationResponse
from errors import (
    ReservationConcurrencyError,
    ReservationConflictError,
    RoomNotAvailableError,
)


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
        version=model.version,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class SQLModelReservationRepository(ReservationRepository):
    def __init__(self, session: Session):
        self.session = session

    def add(
        self,
        payload: ReservationCreateRequest,
        total_price: Decimal,
        reservation_id: UUID | None = None,
    ) -> ReservationResponse:
        # Verificar disponibilidad antes de crear
        if not self.check_room_availability(
            payload.id_room, payload.check_in_date, payload.check_out_date
        ):
            raise RoomNotAvailableError(
                f"Room {payload.id_room} is not available for the selected dates"
            )

        reservation = Reservation(
            id=reservation_id or uuid4(),
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
        self,
        id_room: UUID,
        check_in: datetime,
        check_out: datetime,
        exclude_reservation_id: UUID | None = None,
    ) -> bool:
        # Verificar si la habitación tiene reservas activas en el rango de fechas
        query = select(Reservation).where(
            (Reservation.id_room == id_room)
            & (Reservation.status != "cancelled")
            & (Reservation.check_in_date < check_out)
            & (Reservation.check_out_date > check_in)
        )
        if exclude_reservation_id is not None:
            query = query.where(Reservation.id != exclude_reservation_id)

        conflicting = self.session.exec(query).first()
        return conflicting is None

    def update_status(
        self,
        id: UUID,
        status: str,
        *,
        expected_version: int | None = None,
    ) -> Optional[ReservationResponse]:
        where_clause = Reservation.id == id
        if expected_version is not None:
            where_clause = where_clause & (Reservation.version == expected_version)

        result = self.session.exec(
            update(Reservation)
            .where(where_clause)
            .values(
                status=status,
                version=Reservation.version + 1,
                updated_at=datetime.now(UTC),
            )
        )

        if result.rowcount == 0:
            exists = self.session.exec(
                select(Reservation.id).where(Reservation.id == id)
            ).first()
            if not exists:
                return None
            raise ReservationConcurrencyError("Reservation version conflict")

        self.session.commit()
        reservation = self.session.exec(
            select(Reservation).where(Reservation.id == id)
        ).first()
        return _to_response(reservation) if reservation else None

    def apply_updates(
        self,
        id: UUID,
        *,
        status: str,
        expected_version: int | None = None,
        check_in_date: datetime | None = None,
        check_out_date: datetime | None = None,
        number_of_guests: int | None = None,
        total_price: Decimal | None = None,
        last_policy_snapshot: str | None = None,
        cancelled_at: datetime | None = None,
        cancellation_reason: str | None = None,
    ) -> Optional[ReservationResponse]:
        where_clause = Reservation.id == id
        if expected_version is not None:
            where_clause = where_clause & (Reservation.version == expected_version)

        update_values = {
            "status": status,
            "version": Reservation.version + 1,
            "updated_at": datetime.now(UTC),
        }
        if check_in_date is not None:
            update_values["check_in_date"] = check_in_date
        if check_out_date is not None:
            update_values["check_out_date"] = check_out_date
        if number_of_guests is not None:
            update_values["number_of_guests"] = number_of_guests
        if total_price is not None:
            update_values["total_price"] = total_price
        if last_policy_snapshot is not None:
            update_values["last_policy_snapshot"] = last_policy_snapshot
        if cancelled_at is not None:
            update_values["cancelled_at"] = cancelled_at
        if cancellation_reason is not None:
            update_values["cancellation_reason"] = cancellation_reason

        result = self.session.exec(
            update(Reservation).where(where_clause).values(**update_values)
        )

        if result.rowcount == 0:
            exists = self.session.exec(
                select(Reservation.id).where(Reservation.id == id)
            ).first()
            if not exists:
                return None
            raise ReservationConcurrencyError("Reservation version conflict")

        self.session.commit()
        reservation = self.session.exec(
            select(Reservation).where(Reservation.id == id)
        ).first()
        return _to_response(reservation) if reservation else None
