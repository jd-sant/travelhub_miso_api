from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy import update, asc
from sqlmodel import Session, select

from adapters.models.reservation_change import ReservationChange
from adapters.models.reservation_internal_note import ReservationInternalNote
from adapters.models.reservation import Reservation
from core.config import settings
from domain.ports.reservation_repository import ReservationRepository
from domain.schemas.reservation import (
    HotelReservationListItem,
    InternalNoteResponse,
    PriceBreakdown,
    ReservationChangeRecord,
    ReservationCreateRequest,
    ReservationResponse,
)
from errors import ReservationConcurrencyError, ReservationConflictError, RoomNotAvailableError


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


def _build_price_breakdown(model: Reservation) -> PriceBreakdown | None:
    accommodation = model.accommodation_in_cents or 0
    cleaning = model.cleaning_fee_in_cents or 0
    service = model.service_fee_in_cents or 0
    taxes = model.taxes_in_cents or 0
    if not (accommodation or cleaning or service or taxes):
        return None
    nights = max(1, (model.check_out_date - model.check_in_date).days)
    nightly_rate = accommodation // nights if nights else accommodation
    return PriceBreakdown(
        accommodation_in_cents=accommodation,
        cleaning_fee_in_cents=cleaning,
        service_fee_in_cents=service,
        taxes_in_cents=taxes,
        total_in_cents=accommodation + cleaning + service + taxes,
        currency=model.currency,
        nights=nights,
        nightly_rate_in_cents=nightly_rate,
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
        hold_expires_at=_hold_expires_at(model.created_at),
        version=model.version,
        created_at=model.created_at,
        updated_at=model.updated_at,
        price_breakdown=_build_price_breakdown(model),
    )


def _to_hotel_item(model: Reservation) -> HotelReservationListItem:
    return HotelReservationListItem(
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
        version=model.version,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


_CANCELLED_STATUSES = frozenset({
    "cancelled",
    "cancel_requested",
    "refund_pending",
    "refund_completed",
    "refund_failed",
    "additional_charge_failed",
})


class SQLModelReservationRepository(ReservationRepository):
    def __init__(self, session: Session):
        self.session = session

    def add(
        self,
        payload: ReservationCreateRequest,
        total_price: Decimal,
        reservation_id: UUID | None = None,
        breakdown=None,
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
            accommodation_in_cents=getattr(breakdown, "accommodation_in_cents", 0) or 0,
            cleaning_fee_in_cents=getattr(breakdown, "cleaning_fee_in_cents", 0) or 0,
            service_fee_in_cents=getattr(breakdown, "service_fee_in_cents", 0) or 0,
            taxes_in_cents=getattr(breakdown, "taxes_in_cents", 0) or 0,
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

    def list_by_traveler(
        self,
        id_traveler: UUID,
        status_group: str | None = None,
    ) -> list[ReservationResponse]:
        query = (
            select(Reservation)
            .where(Reservation.id_traveler == id_traveler)
            .order_by(asc(Reservation.check_in_date))
        )
        now = datetime.now(UTC)
        if status_group == "active":
            query = query.where(
                Reservation.status.notin_(_CANCELLED_STATUSES),
                Reservation.check_out_date >= now,
            )
        elif status_group == "past":
            query = query.where(
                Reservation.status.notin_(_CANCELLED_STATUSES),
                Reservation.check_out_date < now,
            )
        elif status_group == "cancelled":
            query = query.where(Reservation.status.in_(_CANCELLED_STATUSES))
        models = self.session.exec(query).all()
        return [_to_response(m) for m in models]

    def list_by_property(
        self,
        id_property: UUID,
        *,
        status: str | None = None,
    ) -> list[HotelReservationListItem]:
        statement = select(Reservation).where(Reservation.id_property == id_property)
        if status is not None:
            statement = statement.where(Reservation.status == status)
        models = self.session.exec(
            statement.order_by(Reservation.created_at.desc())
        ).all()
        return [_to_hotel_item(model) for model in models]

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

        start_naive = _strip_tz(start_date)
        end_naive = _strip_tz(end_date)

        base = select(Reservation).where(Reservation.id_property.in_(property_ids))
        if statuses:
            base = base.where(Reservation.status.in_(statuses))
        if start_naive is not None:
            base = base.where(Reservation.check_out_date >= start_naive)
        if end_naive is not None:
            base = base.where(Reservation.check_in_date <= end_naive)
        if guest_ids:
            base = base.where(Reservation.id_traveler.in_(guest_ids))

        count_stmt = select(func.count()).select_from(base.subquery())
        total = self.session.exec(count_stmt).one()
        if isinstance(total, tuple):
            total = total[0]

        offset = max(page - 1, 0) * page_size
        paged = base.order_by(order_clause).offset(offset).limit(page_size)
        items = [_to_response(m) for m in self.session.exec(paged).all()]
        return items, int(total or 0)

    def list_confirmed_ids_by_properties(
        self,
        property_ids: list[UUID],
        *,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[UUID]:
        if not property_ids:
            return []
        start_naive = _strip_tz(start_date)
        end_naive = _strip_tz(end_date)
        statement = select(Reservation.id).where(
            Reservation.id_property.in_(property_ids),
            Reservation.status == "confirmed",
        )
        if start_naive is not None:
            statement = statement.where(Reservation.check_out_date >= start_naive)
        if end_naive is not None:
            statement = statement.where(Reservation.check_in_date <= end_naive)
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
        start_naive = _strip_tz(start_date)
        end_naive = _strip_tz(end_date)
        statement = select(Reservation.id, Reservation.check_in_date).where(
            Reservation.id_property.in_(property_ids),
            Reservation.status == "confirmed",
        )
        if start_naive is not None:
            statement = statement.where(Reservation.check_out_date >= start_naive)
        if end_naive is not None:
            statement = statement.where(Reservation.check_in_date <= end_naive)
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

    def add_change(self, payload: ReservationChangeRecord) -> ReservationChangeRecord:
        model = ReservationChange(
            id=payload.id,
            reservation_id=payload.reservation_id,
            action=payload.action,
            previous_status=payload.previous_status,
            new_status=payload.new_status,
            reason=payload.reason,
            actor_user_id=payload.actor_user_id,
            source_ip=payload.source_ip,
            created_at=payload.created_at,
        )
        self.session.add(model)
        self.session.commit()
        self.session.refresh(model)
        return ReservationChangeRecord(
            id=model.id,
            reservation_id=model.reservation_id,
            action=model.action,
            previous_status=model.previous_status,
            new_status=model.new_status,
            reason=model.reason,
            actor_user_id=model.actor_user_id,
            source_ip=model.source_ip,
            created_at=model.created_at,
        )

    def list_changes(self, reservation_id: UUID) -> list[ReservationChangeRecord]:
        models = self.session.exec(
            select(ReservationChange)
            .where(ReservationChange.reservation_id == reservation_id)
            .order_by(ReservationChange.created_at.asc())
        ).all()
        return [
            ReservationChangeRecord(
                id=m.id,
                reservation_id=m.reservation_id,
                action=m.action,
                previous_status=m.previous_status,
                new_status=m.new_status,
                reason=m.reason,
                actor_user_id=m.actor_user_id,
                source_ip=m.source_ip,
                created_at=m.created_at,
            )
            for m in models
        ]

    def add_note(
        self,
        reservation_id: UUID,
        content: str,
        author_user_id: UUID,
        author_name: str | None,
    ) -> InternalNoteResponse:
        model = ReservationInternalNote(
            reservation_id=reservation_id,
            content=content,
            author_user_id=author_user_id,
            author_name=author_name,
        )
        self.session.add(model)
        self.session.commit()
        self.session.refresh(model)
        return InternalNoteResponse(
            id=model.id,
            reservation_id=model.reservation_id,
            content=model.content,
            author_user_id=model.author_user_id,
            author_name=model.author_name,
            created_at=model.created_at,
        )

    def list_notes(self, reservation_id: UUID) -> list[InternalNoteResponse]:
        models = self.session.exec(
            select(ReservationInternalNote)
            .where(ReservationInternalNote.reservation_id == reservation_id)
            .order_by(ReservationInternalNote.created_at.asc())
        ).all()
        return [
            InternalNoteResponse(
                id=m.id,
                reservation_id=m.reservation_id,
                content=m.content,
                author_user_id=m.author_user_id,
                author_name=m.author_name,
                created_at=m.created_at,
            )
            for m in models
        ]
