from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from adapters.models.reservation_command_log import ReservationCommandLog
from domain.ports.reservation_command_log_repository import (
    ReservationCommandLogRepository,
)
from domain.schemas.reservation import ReservationCommandType


class SQLModelReservationCommandLogRepository(ReservationCommandLogRepository):
    def __init__(self, session: Session):
        self.session = session

    def get_by_idempotency(
        self,
        reservation_id: UUID,
        command_type: ReservationCommandType,
        idempotency_key: str,
    ) -> dict | None:
        model = self.session.exec(
            select(ReservationCommandLog)
            .where(ReservationCommandLog.reservation_id == reservation_id)
            .where(ReservationCommandLog.command_type == command_type.value)
            .where(ReservationCommandLog.idempotency_key == idempotency_key)
        ).first()
        return model.response_payload if model else None

    def add(
        self,
        reservation_id: UUID,
        command_type: ReservationCommandType,
        idempotency_key: str,
        response_payload: dict,
    ) -> None:
        model = ReservationCommandLog(
            reservation_id=reservation_id,
            command_type=command_type.value,
            idempotency_key=idempotency_key,
            response_payload=response_payload,
        )
        self.session.add(model)
        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            raise
