from uuid import UUID

from sqlmodel import Session, select

from adapters.models.reservation_event import ReservationEvent
from core.security import sanitize_sensitive_data
from domain.ports.reservation_event_repository import ReservationEventRepository
from domain.schemas.reservation import (
    ReservationEventCreateRequest,
    ReservationEventResponse,
)


def _to_response(model: ReservationEvent) -> ReservationEventResponse:
    return ReservationEventResponse(
        id=model.id,
        reservation_id=model.reservation_id,
        event_type=model.event_type,
        actor_user_id=model.actor_user_id,
        source_ip=model.source_ip,
        result=model.result,
        before_payload=model.before_payload,
        after_payload=model.after_payload,
        created_at=model.created_at,
    )


class SQLModelReservationEventRepository(ReservationEventRepository):
    def __init__(self, session: Session):
        self.session = session

    def add(self, payload: ReservationEventCreateRequest) -> ReservationEventResponse:
        model = ReservationEvent(
            reservation_id=payload.reservation_id,
            event_type=payload.event_type,
            actor_user_id=payload.actor_user_id,
            source_ip=payload.source_ip,
            result=payload.result,
            before_payload=sanitize_sensitive_data(payload.before_payload),
            after_payload=sanitize_sensitive_data(payload.after_payload),
        )
        self.session.add(model)
        self.session.commit()
        self.session.refresh(model)
        return _to_response(model)

    def list_by_reservation(self, reservation_id: UUID) -> list[ReservationEventResponse]:
        models = self.session.exec(
            select(ReservationEvent)
            .where(ReservationEvent.reservation_id == reservation_id)
            .order_by(ReservationEvent.created_at.asc())
        ).all()
        return [_to_response(model) for model in models]
