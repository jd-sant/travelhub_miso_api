from uuid import uuid4

from sqlmodel import Session

from adapters.models.payment import Payment
from core.config import settings


_INTERNAL_HEADERS = {"X-Internal-Api-Key": settings.internal_api_key}


def _persist_payment(
    session: Session,
    *,
    reservation_id,
    amount_in_cents: int,
    currency: str,
    status: str = "confirmed",
) -> Payment:
    payment = Payment(
        reservation_id=reservation_id,
        traveler_id=uuid4(),
        provider_code="fake_stripe",
        status=status,
        amount_in_cents=amount_in_cents,
        currency=currency,
        payment_method_token_hash=uuid4().hex,
        request_fingerprint=uuid4().hex,
        duplicate_guard_key=uuid4().hex,
        request_checksum=uuid4().hex,
        idempotency_key=uuid4().hex,
    )
    session.add(payment)
    session.commit()
    session.refresh(payment)
    return payment


def test_by_reservations_requires_internal_api_key(client):
    response = client.post(
        "/api/v1/internal/payments/by-reservations",
        json={"reservation_ids": [str(uuid4())]},
    )
    assert response.status_code == 403


def test_by_reservations_rejects_invalid_internal_api_key(client):
    response = client.post(
        "/api/v1/internal/payments/by-reservations",
        headers={"X-Internal-Api-Key": "invalid-key"},
        json={"reservation_ids": [str(uuid4())]},
    )
    assert response.status_code == 403


def test_by_reservations_returns_empty_when_no_ids(client):
    response = client.post(
        "/api/v1/internal/payments/by-reservations",
        headers=_INTERNAL_HEADERS,
        json={"reservation_ids": []},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["available_currencies"] == []


def test_by_reservations_aggregates_amounts_per_reservation_and_currency(client, test_engine):
    reservation_a = uuid4()
    reservation_b = uuid4()
    other_reservation = uuid4()

    with Session(test_engine) as session:
        _persist_payment(session, reservation_id=reservation_a, amount_in_cents=10_000, currency="COP")
        _persist_payment(session, reservation_id=reservation_a, amount_in_cents=15_000, currency="COP")
        _persist_payment(session, reservation_id=reservation_a, amount_in_cents=20_00, currency="USD")
        _persist_payment(session, reservation_id=reservation_b, amount_in_cents=5_000, currency="COP")
        _persist_payment(
            session,
            reservation_id=reservation_a,
            amount_in_cents=99_999,
            currency="COP",
            status="failed",
        )
        _persist_payment(session, reservation_id=other_reservation, amount_in_cents=999, currency="COP")

    response = client.post(
        "/api/v1/internal/payments/by-reservations",
        headers=_INTERNAL_HEADERS,
        json={"reservation_ids": [str(reservation_a), str(reservation_b)]},
    )
    assert response.status_code == 200
    body = response.json()

    items_by_key = {
        (item["reservation_id"], item["currency"]): item["amount_in_cents"]
        for item in body["items"]
    }
    assert items_by_key[(str(reservation_a), "COP")] == 25_000
    assert items_by_key[(str(reservation_a), "USD")] == 2_000
    assert items_by_key[(str(reservation_b), "COP")] == 5_000
    assert (str(other_reservation), "COP") not in items_by_key

    assert body["available_currencies"] == ["COP", "USD"]


def test_by_reservations_filters_by_status(client, test_engine):
    reservation_id = uuid4()

    with Session(test_engine) as session:
        _persist_payment(
            session,
            reservation_id=reservation_id,
            amount_in_cents=8_000,
            currency="COP",
            status="confirmed",
        )
        _persist_payment(
            session,
            reservation_id=reservation_id,
            amount_in_cents=4_000,
            currency="COP",
            status="failed",
        )

    response = client.post(
        "/api/v1/internal/payments/by-reservations",
        headers=_INTERNAL_HEADERS,
        json={"reservation_ids": [str(reservation_id)], "status": "failed"},
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["amount_in_cents"] == 4_000
