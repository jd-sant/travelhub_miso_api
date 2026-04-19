from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from botocore.exceptions import ClientError

from adapters.services.scheduler_service import EventBridgeReservationScheduler
from core.config import Settings
from domain.schemas.reservation import ReservationCreateRequest
from domain.use_cases.create_reservation import CreateReservationUseCase
from errors import ReservationSchedulingError
from entrypoints.api import main as main_module


class _FakeSchedulerClient:
    def __init__(self):
        self.created_payload = None
        self.deleted_name = None
        self.fail_create = None
        self.fail_delete = None

    def create_schedule(self, **kwargs):
        if self.fail_create is not None:
            raise self.fail_create
        self.created_payload = kwargs

    def delete_schedule(self, **kwargs):
        if self.fail_delete is not None:
            raise self.fail_delete
        self.deleted_name = kwargs.get("Name")


class _RepoAddFails:
    def check_room_availability(self, *_args, **_kwargs):
        return True

    def add(self, *_args, **_kwargs):
        raise RuntimeError("db failure")


class _RecordingScheduler:
    def __init__(self):
        self.scheduled = []
        self.cancelled = []

    def schedule_reservation_expiration(self, reservation_id: str) -> str:
        self.scheduled.append(reservation_id)
        return f"verify-reservation-{reservation_id}"

    def cancel_reservation_expiration(self, reservation_id: str) -> None:
        self.cancelled.append(reservation_id)


def _build_request() -> ReservationCreateRequest:
    check_in = datetime.now(UTC) + timedelta(days=2)
    check_out = check_in + timedelta(days=2)
    return ReservationCreateRequest(
        id_traveler=uuid4(),
        id_property=uuid4(),
        id_room=uuid4(),
        check_in_date=check_in,
        check_out_date=check_out,
        number_of_guests=2,
        currency="USD",
    )


def test_scheduler_create_and_cancel_success_paths():
    scheduler = EventBridgeReservationScheduler.__new__(EventBridgeReservationScheduler)
    scheduler._client = _FakeSchedulerClient()
    scheduler._lambda_arn = "arn:aws:lambda:us-east-1:123456789012:function:fn"
    scheduler._scheduler_role_arn = "arn:aws:iam::123456789012:role/scheduler-role"
    scheduler._api_base_url = "https://api.example.com"
    scheduler._scheduler_group_name = "default"
    scheduler._delay_minutes = 15

    reservation_id = str(uuid4())
    schedule_name = scheduler.schedule_reservation_expiration(reservation_id)
    scheduler.cancel_reservation_expiration(reservation_id)

    assert schedule_name == f"verify-reservation-{reservation_id}"
    assert scheduler._client.created_payload["Name"] == schedule_name
    assert scheduler._client.deleted_name == schedule_name


def test_scheduler_raises_runtime_error_on_create_failure():
    scheduler = EventBridgeReservationScheduler.__new__(EventBridgeReservationScheduler)
    scheduler._client = _FakeSchedulerClient()
    scheduler._lambda_arn = "arn:aws:lambda:us-east-1:123:function:fn"
    scheduler._scheduler_role_arn = "arn:aws:iam::123:role/r"
    scheduler._api_base_url = "https://api.example.com"
    scheduler._scheduler_group_name = "default"
    scheduler._delay_minutes = 15
    scheduler._client.fail_create = ClientError(
        {
            "Error": {
                "Code": "AccessDeniedException",
                "Message": "denied",
            }
        },
        "CreateSchedule",
    )

    with pytest.raises(RuntimeError, match="Error creating schedule: denied"):
        scheduler.schedule_reservation_expiration(str(uuid4()))


def test_scheduler_cancel_ignores_not_found_and_raises_other_errors():
    scheduler = EventBridgeReservationScheduler.__new__(EventBridgeReservationScheduler)
    scheduler._client = _FakeSchedulerClient()
    scheduler._scheduler_group_name = "default"

    scheduler._client.fail_delete = ClientError(
        {"Error": {"Code": "ResourceNotFoundException", "Message": "missing"}},
        "DeleteSchedule",
    )
    scheduler.cancel_reservation_expiration(str(uuid4()))

    scheduler._client.fail_delete = ClientError(
        {"Error": {"Code": "InternalError", "Message": "boom"}},
        "DeleteSchedule",
    )
    with pytest.raises(RuntimeError, match="Error deleting schedule"):
        scheduler.cancel_reservation_expiration(str(uuid4()))


def test_create_reservation_rolls_back_schedule_when_repository_add_fails():
    scheduler = _RecordingScheduler()
    use_case = CreateReservationUseCase(repository=_RepoAddFails(), scheduler=scheduler)

    with pytest.raises(RuntimeError, match="db failure"):
        use_case.execute(_build_request())

    assert len(scheduler.scheduled) == 1
    assert scheduler.cancelled == scheduler.scheduled


def test_create_reservation_wraps_scheduler_errors():
    class _FailingScheduler:
        def schedule_reservation_expiration(self, _reservation_id: str) -> str:
            raise RuntimeError("scheduler unavailable")

        def cancel_reservation_expiration(self, _reservation_id: str) -> None:
            return None

    class _Repo:
        def check_room_availability(self, *_args, **_kwargs):
            return True

        def add(self, *_args, **_kwargs):
            raise AssertionError("should not be called")

    use_case = CreateReservationUseCase(repository=_Repo(), scheduler=_FailingScheduler())
    with pytest.raises(ReservationSchedulingError):
        use_case.execute(_build_request())


def test_settings_validate_scheduler_config(monkeypatch):
    settings = Settings()

    monkeypatch.setenv("RESERVATION_SCHEDULER_ENABLED", "false")
    settings.validate_scheduler_config()

    monkeypatch.setenv("RESERVATION_SCHEDULER_ENABLED", "true")
    monkeypatch.delenv("LAMBDA_ARN", raising=False)
    monkeypatch.delenv("SCHEDULER_ROLE_ARN", raising=False)
    monkeypatch.delenv("API_BASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="missing configuration"):
        settings.validate_scheduler_config()

    monkeypatch.setenv("LAMBDA_ARN", "arn:aws:lambda:us-east-1:123:function:fn")
    monkeypatch.setenv("SCHEDULER_ROLE_ARN", "arn:aws:iam::123:role/r")
    monkeypatch.setenv("API_BASE_URL", "https://api.example.com")
    settings.validate_scheduler_config()


def test_reservation_scheduler_uses_noop_in_local_dev(monkeypatch):
    monkeypatch.setenv("ENV", "development")
    monkeypatch.setenv("RESERVATION_SCHEDULER_ENABLED", "true")
    monkeypatch.setenv("LAMBDA_ARN", "arn:aws:lambda:us-east-1:123:function:fn")
    monkeypatch.setenv("SCHEDULER_ROLE_ARN", "arn:aws:iam::123:role/r")
    monkeypatch.setenv("API_BASE_URL", "https://api.example.com")

    from entrypoints.api.routers.reservations import get_reservation_scheduler

    scheduler = get_reservation_scheduler()

    assert scheduler.__class__.__name__ == "NoOpReservationScheduler"


def test_lifespan_invokes_bootstrap_hooks(monkeypatch):
    called = {"db": 0, "validate": 0}

    monkeypatch.setattr(main_module, "create_db_and_tables", lambda: called.__setitem__("db", called["db"] + 1))
    monkeypatch.setattr(
        main_module,
        "settings",
        SimpleNamespace(validate_scheduler_config=lambda: called.__setitem__("validate", called["validate"] + 1), allowed_cors_origins=["http://localhost:3000"]),
    )

    async def _run_lifespan() -> None:
        async with main_module.lifespan(main_module.app):
            pass

    asyncio.run(_run_lifespan())

    assert called == {"db": 1, "validate": 1}
