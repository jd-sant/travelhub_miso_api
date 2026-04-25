from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from domain.schemas.payment import (
    PaymentChargeResponse,
    PaymentEventResponse,
    PaymentProcessingOutboxRecord,
    PaymentStatus,
    ReservationConfirmationOutboxRecord,
)


class PaymentRepository(ABC):
    @abstractmethod
    def find_by_idempotency_key(self, idempotency_key: str) -> PaymentChargeResponse | None:
        pass

    @abstractmethod
    def find_recent_duplicate(
        self,
        *,
        request_fingerprint: str,
        since: datetime,
    ) -> PaymentChargeResponse | None:
        pass

    @abstractmethod
    def save_payment_result(self, payment: PaymentChargeResponse) -> PaymentChargeResponse:
        pass

    @abstractmethod
    def get_by_id(self, payment_id: UUID) -> PaymentChargeResponse | None:
        pass

    @abstractmethod
    def find_by_gateway_charge_id(self, gateway_charge_id: str) -> PaymentChargeResponse | None:
        pass

    @abstractmethod
    def add_events(self, payment_id: UUID, events: list[PaymentEventResponse]) -> None:
        pass

    @abstractmethod
    def list_events(
        self,
        payment_id: UUID,
        *,
        after_created_at: datetime | None = None,
    ) -> list[PaymentEventResponse]:
        pass

    @abstractmethod
    def upsert_reservation_confirmation_outbox_failure(
        self,
        *,
        payment_id: UUID,
        reservation_id: UUID,
        error_message: str,
        next_retry_at: datetime,
        max_attempts: int,
    ) -> None:
        pass

    @abstractmethod
    def list_due_reservation_confirmation_outbox(
        self,
        *,
        now: datetime,
        limit: int,
    ) -> list[ReservationConfirmationOutboxRecord]:
        pass

    @abstractmethod
    def mark_reservation_confirmation_outbox_succeeded(
        self,
        *,
        outbox_id: UUID,
        processed_at: datetime,
    ) -> None:
        pass

    @abstractmethod
    def mark_reservation_confirmation_outbox_retry(
        self,
        *,
        outbox_id: UUID,
        next_retry_at: datetime,
        error_message: str,
        attempt_count: int,
        mark_as_failed: bool,
    ) -> None:
        pass

    @abstractmethod
    def count_reservation_confirmation_outbox_pending(self, *, now: datetime) -> int:
        pass

    @abstractmethod
    def upsert_payment_processing_outbox(
        self,
        *,
        payment_id: UUID,
        checkout_session_id: UUID,
        source_ip: str | None,
        next_retry_at: datetime,
        max_attempts: int,
    ) -> None:
        pass

    @abstractmethod
    def get_payment_processing_outbox(
        self,
        *,
        payment_id: UUID,
    ) -> PaymentProcessingOutboxRecord | None:
        pass

    @abstractmethod
    def list_due_payment_processing_outbox(
        self,
        *,
        now: datetime,
        limit: int,
    ) -> list[PaymentProcessingOutboxRecord]:
        pass

    @abstractmethod
    def mark_payment_processing_outbox_processing(
        self,
        *,
        outbox_id: UUID,
        attempt_count: int,
        processing_started_at: datetime,
    ) -> None:
        pass

    @abstractmethod
    def mark_payment_processing_outbox_succeeded(
        self,
        *,
        outbox_id: UUID,
        processed_at: datetime,
    ) -> None:
        pass

    @abstractmethod
    def mark_payment_processing_outbox_retry(
        self,
        *,
        outbox_id: UUID,
        next_retry_at: datetime,
        error_message: str,
        attempt_count: int,
        mark_as_failed: bool,
    ) -> None:
        pass

    @abstractmethod
    def list_amounts_by_reservations(
        self,
        reservation_ids: list[UUID],
        *,
        status: PaymentStatus = PaymentStatus.confirmed,
    ) -> tuple[list[tuple[UUID, int, str]], list[str]]:
        pass

    @abstractmethod
    def count_payment_processing_outbox_pending(self, *, now: datetime) -> int:
        pass
