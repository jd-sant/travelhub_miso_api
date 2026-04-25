from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlmodel import Session

from adapters.models.payment import Payment
from core.config import settings


def _seed_payment(
    session: Session,
    *,
    reservation_id: UUID,
    amount: int,
    status: str = "confirmed",
    currency: str = "cop",
    created_at: datetime | None = None,
) -> Payment:
    payment = Payment(
        reservation_id=reservation_id,
        traveler_id=uuid4(),
        provider_code="fake_stripe",
        status=status,
        amount_in_cents=amount,
        currency=currency,
        payment_method_token_hash=f"hash-{uuid4()}",
        request_fingerprint=f"fp-{uuid4()}",
        duplicate_guard_key=f"guard-{uuid4()}",
        request_checksum=f"chk-{uuid4()}",
        idempotency_key=f"idem-{uuid4()}",
    )
    if created_at is not None:
        payment.created_at = created_at
        payment.updated_at = created_at
    session.add(payment)
    session.commit()
    session.refresh(payment)
    return payment


def test_aggregate_returns_total_for_confirmed_payments(client, test_engine):
    reservation_id = uuid4()
    other_reservation_id = uuid4()
    with Session(test_engine) as session:
        _seed_payment(session, reservation_id=reservation_id, amount=10000)
        _seed_payment(session, reservation_id=reservation_id, amount=5000)
        _seed_payment(
            session,
            reservation_id=reservation_id,
            amount=999,
            status="failed",
        )
        _seed_payment(session, reservation_id=other_reservation_id, amount=20000)

    response = client.post(
        "/api/v1/internal/payments/aggregate",
        json={
            "reservation_ids": [str(reservation_id)],
            "status": "confirmed",
        },
        headers={"X-Internal-Api-Key": settings.internal_api_key},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total_amount_cents"] == 15000
    assert body["count"] == 2
    assert body["currency"] == "cop"
    assert body["buckets"] == []


def test_aggregate_groups_by_day(client, test_engine):
    reservation_id = uuid4()
    base = datetime(2026, 4, 10, 12, 0, tzinfo=timezone.utc)
    with Session(test_engine) as session:
        _seed_payment(
            session,
            reservation_id=reservation_id,
            amount=1000,
            created_at=base,
        )
        _seed_payment(
            session,
            reservation_id=reservation_id,
            amount=2000,
            created_at=base + timedelta(hours=2),
        )
        _seed_payment(
            session,
            reservation_id=reservation_id,
            amount=3000,
            created_at=base + timedelta(days=1),
        )

    response = client.post(
        "/api/v1/internal/payments/aggregate",
        json={
            "reservation_ids": [str(reservation_id)],
            "granularity": "day",
        },
        headers={"X-Internal-Api-Key": settings.internal_api_key},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 3
    assert body["total_amount_cents"] == 6000
    buckets = body["buckets"]
    assert len(buckets) == 2
    assert buckets[0]["amount_cents"] == 3000
    assert buckets[0]["count"] == 2
    assert buckets[1]["amount_cents"] == 3000
    assert buckets[1]["count"] == 1


def test_aggregate_requires_api_key(client):
    response = client.post(
        "/api/v1/internal/payments/aggregate",
        json={"reservation_ids": [str(uuid4())]},
    )
    assert response.status_code == 403


def test_aggregate_empty_reservation_ids(client):
    response = client.post(
        "/api/v1/internal/payments/aggregate",
        json={"reservation_ids": []},
        headers={"X-Internal-Api-Key": settings.internal_api_key},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total_amount_cents"] == 0
    assert body["count"] == 0
    assert body["buckets"] == []
