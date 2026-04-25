from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from adapters.models.reservation import Reservation
from core.config import settings
from domain.ports.reservation_repository import ReservationRepository
from domain.schemas.reservation import ReservationCreateRequest, ReservationResponse
from errors import ReservationConflictError, RoomNotAvailableError


_SORTABLE_COLUMNS = {
    "check_in_date": Reservation.check_in_date,
    "created_at": Reservation.created_at,
    "total_price": Reservation.total_price,
}


def _strip_tz(value):
    if value is None:
        return None
    return value.replace(tzinfo=None) if value.tzinfo else value


def _hold_expires_at(created_at: datetime) -> datetime:
    return created_at + timedelta(minutes=settings.reservation_scheduler_delay_minutes)


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
        hold_expires_at=_hold_expires_at(model.created_at),
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

    def list_by_properties(
        self,
        property_ids: list[UUID],
        *,
        statuses: list[str] | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        guest_ids: list[UUID] | None = None,
        sort_by: str = "check_in_date",
        sort_dir: str = "desc",
        page: int = 1,
        page_size: int = 10,
    ) -> tuple[list[ReservationResponse], int]:
        if not property_ids:
            return [], 0

        column = _SORTABLE_COLUMNS.get(sort_by, Reservation.check_in_date)
        order_clause = column.asc() if sort_dir == "asc" else column.desc()

        base = select(Reservation).where(Reservation.id_property.in_(property_ids))
        if statuses:
            base = base.where(Reservation.status.in_(statuses))
        if start_date is not None:
            base = base.where(Reservation.check_out_date >= start_date)
        if end_date is not None:
            base = base.where(Reservation.check_in_date <= end_date)
        if guest_ids:
            base = base.where(Reservation.id_traveler.in_(guest_ids))

        total = len(self.session.exec(base).all())
        offset = max(page - 1, 0) * page_size
        paged = base.order_by(order_clause).offset(offset).limit(page_size)
        items = [_to_response(m) for m in self.session.exec(paged).all()]
        return items, total

    def list_confirmed_ids_by_properties(
        self,
        property_ids: list[UUID],
        *,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[UUID]:
        if not property_ids:
            return []
        statement = select(Reservation.id).where(
            Reservation.id_property.in_(property_ids),
            Reservation.status == "confirmed",
        )
        if start_date is not None:
            statement = statement.where(Reservation.check_out_date >= start_date)
        if end_date is not None:
            statement = statement.where(Reservation.check_in_date <= end_date)
        return list(self.session.exec(statement).all())

    def list_confirmed_with_check_in_by_properties(
        self,
        property_ids: list[UUID],
        *,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[tuple[UUID, datetime]]:
        if not property_ids:
            return []
        statement = select(Reservation.id, Reservation.check_in_date).where(
            Reservation.id_property.in_(property_ids),
            Reservation.status == "confirmed",
        )
        if start_date is not None:
            statement = statement.where(Reservation.check_out_date >= start_date)
        if end_date is not None:
            statement = statement.where(Reservation.check_in_date <= end_date)
        return [(rid, ci) for rid, ci in self.session.exec(statement).all()]

    def operational_metrics_for_properties(
        self,
        property_ids: list[UUID],
        *,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> dict:
        if not property_ids:
            return {"active_reservations": 0, "total_nights": 0}

        now_naive = datetime.now(UTC).replace(tzinfo=None)
        active_stmt = select(func.count()).select_from(Reservation).where(
            Reservation.id_property.in_(property_ids),
            Reservation.status == "confirmed",
            Reservation.check_out_date >= now_naive,
        )
        active = self.session.exec(active_stmt).one()
        if isinstance(active, tuple):
            active = active[0]

        start_naive = _strip_tz(start_date)
        end_naive = _strip_tz(end_date)
        nights_stmt = select(Reservation.check_in_date, Reservation.check_out_date).where(
            Reservation.id_property.in_(property_ids),
            Reservation.status == "confirmed",
        )
        if start_naive is not None:
            nights_stmt = nights_stmt.where(Reservation.check_out_date >= start_naive)
        if end_naive is not None:
            nights_stmt = nights_stmt.where(Reservation.check_in_date <= end_naive)

        total_nights = 0
        for check_in, check_out in self.session.exec(nights_stmt).all():
            check_in = _strip_tz(check_in)
            check_out = _strip_tz(check_out)
            window_start = max(check_in, start_naive) if start_naive else check_in
            window_end = min(check_out, end_naive) if end_naive else check_out
            delta = (window_end - window_start).days
            if delta > 0:
                total_nights += delta

        return {"active_reservations": int(active or 0), "total_nights": total_nights}
