from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from domain.schemas.reservation import (
    CancellationPolicyType,
    ReservationCancellationPreviewResponse,
    ReservationEventCreateRequest,
    ReservationEventResult,
    ReservationEventType,
    ReservationModificationPreviewRequest,
    ReservationPolicySnapshot,
)


def test_modification_preview_request_validates_guest_count():
    with pytest.raises(Exception):
        ReservationModificationPreviewRequest(
            check_in_date=datetime.now(UTC) + timedelta(days=2),
            check_out_date=datetime.now(UTC) + timedelta(days=5),
            number_of_guests=0,
        )


def test_cancellation_preview_schema_accepts_expected_values():
    payload = ReservationCancellationPreviewResponse(
        reservation_id=uuid4(),
        policy_applied=ReservationPolicySnapshot(
            policy_type=CancellationPolicyType.partial_refund,
            minimum_notice_hours=24,
            penalty_percentage=Decimal("25.5"),
            timezone="America/Bogota",
        ),
        refund_amount=Decimal("150.00"),
        penalty_amount=Decimal("50.00"),
        refund_type=CancellationPolicyType.partial_refund,
        eligible_until=datetime.now(UTC) + timedelta(days=1),
        change_allowed=True,
        reasons=[],
    )

    assert payload.policy_applied.policy_type == CancellationPolicyType.partial_refund
    assert payload.refund_amount == Decimal("150.00")
    assert payload.penalty_amount == Decimal("50.00")


def test_event_create_request_defaults_result_to_success():
    event = ReservationEventCreateRequest(
        reservation_id=uuid4(),
        event_type=ReservationEventType.modification_previewed,
    )

    assert event.result == ReservationEventResult.success
