"""Tests para EventBridgeReservationScheduler.schedule_arrival_reminder."""
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

from adapters.services.scheduler_service import (
    EventBridgeReservationScheduler,
    NoOpReservationScheduler,
)


@pytest.fixture
def boto_client(monkeypatch):
    """Stub completo de boto3.client('scheduler')."""
    import adapters.services.scheduler_service as scheduler_module

    fake_boto3 = MagicMock()
    fake_client = MagicMock()
    fake_boto3.client.return_value = fake_client
    monkeypatch.setattr(scheduler_module, "boto3", fake_boto3, raising=False)
    monkeypatch.setitem(__import__("sys").modules, "boto3", fake_boto3)
    return fake_client


@pytest.fixture
def scheduler(boto_client):
    return EventBridgeReservationScheduler(
        aws_region="us-east-1",
        lambda_arn="arn:aws:lambda:us-east-1:000:function:reservation-checker",
        scheduler_role_arn="arn:aws:iam::000:role/scheduler-invocation",
        api_base_url="https://api.travelhub.app",
        scheduler_group_name="reservations",
    )


def test_schedule_arrival_reminder_sends_correct_input(scheduler, boto_client):
    fire_at = datetime.now(timezone.utc) + timedelta(hours=24)
    name = scheduler.schedule_arrival_reminder("res-123", fire_at)

    assert name == "arrival-reminder-res-123"
    boto_client.create_schedule.assert_called_once()
    kwargs = boto_client.create_schedule.call_args.kwargs
    assert kwargs["Name"] == "arrival-reminder-res-123"
    assert kwargs["GroupName"] == "reservations"
    assert kwargs["ScheduleExpressionTimezone"] == "UTC"
    assert kwargs["FlexibleTimeWindow"] == {"Mode": "OFF"}
    assert kwargs["ActionAfterCompletion"] == "DELETE"

    target = kwargs["Target"]
    assert target["Arn"].endswith(":reservation-checker")
    payload = json.loads(target["Input"])
    assert payload == {
        "reservation_id": "res-123",
        "api_url": "https://api.travelhub.app/api/v1/internal/reservations/res-123/fire-arrival-reminder",
    }


def test_schedule_arrival_reminder_with_past_fire_at_clamps_to_30_seconds(
    scheduler, boto_client
):
    """Si check_in - LEAD_MINUTES <= now() (lead chico en pruebas), igual debe
    disparar — no skipear."""
    past = datetime.now(timezone.utc) - timedelta(minutes=5)
    name = scheduler.schedule_arrival_reminder("res-past", past)

    assert name == "arrival-reminder-res-past"
    expression = boto_client.create_schedule.call_args.kwargs["ScheduleExpression"]
    # at(YYYY-MM-DDTHH:MM:SS) — cualquier futuro válido (clampeado a now+30s)
    assert expression.startswith("at(")
    parsed = datetime.strptime(
        expression[3:-1], "%Y-%m-%dT%H:%M:%S"
    ).replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    assert parsed >= now - timedelta(seconds=5)
    assert parsed <= now + timedelta(seconds=60)


def test_schedule_arrival_reminder_wraps_aws_errors(scheduler, boto_client):
    boto_client.create_schedule.side_effect = ClientError(
        {"Error": {"Code": "ValidationException", "Message": "bad"}},
        "CreateSchedule",
    )
    with pytest.raises(RuntimeError, match="arrival reminder schedule"):
        scheduler.schedule_arrival_reminder(
            "r", datetime.now(timezone.utc) + timedelta(hours=1)
        )


def test_cancel_arrival_reminder_swallows_resource_not_found(scheduler, boto_client):
    boto_client.delete_schedule.side_effect = ClientError(
        {"Error": {"Code": "ResourceNotFoundException", "Message": "gone"}},
        "DeleteSchedule",
    )
    # No debe lanzar
    scheduler.cancel_arrival_reminder("res-missing")


def test_cancel_arrival_reminder_propagates_other_errors(scheduler, boto_client):
    boto_client.delete_schedule.side_effect = ClientError(
        {"Error": {"Code": "AccessDenied", "Message": "denied"}},
        "DeleteSchedule",
    )
    with pytest.raises(RuntimeError):
        scheduler.cancel_arrival_reminder("r")


def test_noop_scheduler_is_safe_to_use_in_dev():
    sched = NoOpReservationScheduler()
    name = sched.schedule_arrival_reminder("r1", datetime.now(timezone.utc))
    assert name == "noop-arrival-reminder-r1"
    sched.cancel_arrival_reminder("r1")  # no-op, no debe lanzar
