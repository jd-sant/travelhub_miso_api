from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import jwt
import pytest
from sqlmodel import Session

from adapters.models.reservation import Reservation
from core.config import settings
from entrypoints.api.main import app
from assembly import (
    get_payments_client,
    get_properties_client,
    get_users_client,
)


HOTEL_OWNER_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
OTHER_OWNER_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
PROPERTY_A = UUID("11111111-1111-1111-1111-111111111111")
PROPERTY_B = UUID("22222222-2222-2222-2222-222222222222")
PROPERTY_C = UUID("33333333-3333-3333-3333-333333333333")


class FakePropertiesClient:
    def __init__(self):
        self.properties_by_owner = {
            HOTEL_OWNER_ID: [
                {"id": str(PROPERTY_A), "name": "Suite Deluxe", "bedrooms": 2},
                {"id": str(PROPERTY_B), "name": "Penthouse", "bedrooms": 3},
            ],
            OTHER_OWNER_ID: [
                {"id": str(PROPERTY_C), "name": "Mountain Lodge", "bedrooms": 4},
            ],
        }

    def list_by_owner(self, owner_id):
        return self.properties_by_owner.get(owner_id, [])

    def get_owned_property_ids(self, owner_id):
        return [UUID(p["id"]) for p in self.list_by_owner(owner_id)]


class FakeUsersClient:
    def __init__(self):
        self.users_by_id = {
            UUID("99999999-9999-9999-9999-999999999991"): {
                "id": "99999999-9999-9999-9999-999999999991",
                "full_name": "Ana García",
                "email": "ana@example.com",
            },
            UUID("99999999-9999-9999-9999-999999999992"): {
                "id": "99999999-9999-9999-9999-999999999992",
                "full_name": "Bob Smith",
                "email": "bob@example.com",
            },
        }

    def search_by_name(self, query):
        q = query.lower()
        return [
            u
            for u in self.users_by_id.values()
            if q in u["full_name"].lower()
        ]

    def list_by_ids(self, ids):
        return [self.users_by_id[i] for i in ids if i in self.users_by_id]


class FakePaymentsClient:
    def __init__(self):
        self.list_response = {
            "items": [],
            "available_currencies": [],
        }
        self.last_call = None

    def list_by_reservations(
        self,
        reservation_ids,
        *,
        status="confirmed",
    ):
        self.last_call = {
            "reservation_ids": list(reservation_ids),
            "status": status,
        }
        return self.list_response


def _hotel_token(owner_id=HOTEL_OWNER_ID):
    payload = {
        "sub": str(owner_id),
        "email": "hotel@example.com",
        "role": "hotel",
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) + timedelta(minutes=10),
    }
    return jwt.encode(
        payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )


def _traveler_token():
    payload = {
        "sub": str(uuid4()),
        "email": "trav@example.com",
        "role": "traveler",
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) + timedelta(minutes=10),
    }
    return jwt.encode(
        payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )


def _seed_reservation(
    session: Session,
    *,
    id_property: UUID,
    id_traveler: UUID,
    status: str,
    check_in: datetime,
    nights: int = 2,
    total: Decimal = Decimal("400.00"),
) -> Reservation:
    reservation = Reservation(
        id=uuid4(),
        id_traveler=id_traveler,
        id_property=id_property,
        id_room=uuid4(),
        check_in_date=check_in,
        check_out_date=check_in + timedelta(days=nights),
        number_of_guests=2,
        total_price=total,
        currency="COP",
        status=status,
    )
    session.add(reservation)
    session.commit()
    session.refresh(reservation)
    return reservation


@pytest.fixture
def fakes_overridden():
    properties = FakePropertiesClient()
    users = FakeUsersClient()
    payments = FakePaymentsClient()
    app.dependency_overrides[get_properties_client] = lambda: properties
    app.dependency_overrides[get_users_client] = lambda: users
    app.dependency_overrides[get_payments_client] = lambda: payments
    yield {"properties": properties, "users": users, "payments": payments}
    for dep in (get_properties_client, get_users_client, get_payments_client):
        app.dependency_overrides.pop(dep, None)


def test_host_listing_requires_auth(client):
    response = client.get("/api/v1/reservations/host/me")
    assert response.status_code == 401


def test_host_listing_rejects_traveler_role(client, fakes_overridden):
    response = client.get(
        "/api/v1/reservations/host/me",
        headers={"Authorization": f"Bearer {_traveler_token()}"},
    )
    assert response.status_code == 403


def test_host_listing_returns_only_my_properties(client, session, fakes_overridden):
    base_check_in = datetime.now(UTC) + timedelta(days=2)
    traveler_a = UUID("99999999-9999-9999-9999-999999999991")
    traveler_b = UUID("99999999-9999-9999-9999-999999999992")
    other_traveler = uuid4()

    _seed_reservation(
        session,
        id_property=PROPERTY_A,
        id_traveler=traveler_a,
        status="confirmed",
        check_in=base_check_in,
    )
    _seed_reservation(
        session,
        id_property=PROPERTY_B,
        id_traveler=traveler_b,
        status="pending_payment",
        check_in=base_check_in + timedelta(days=4),
    )
    _seed_reservation(
        session,
        id_property=PROPERTY_C,
        id_traveler=other_traveler,
        status="confirmed",
        check_in=base_check_in,
    )

    response = client.get(
        "/api/v1/reservations/host/me",
        headers={"Authorization": f"Bearer {_hotel_token()}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    property_ids = {item["id_property"] for item in body["items"]}
    assert property_ids == {str(PROPERTY_A), str(PROPERTY_B)}
    actions_by_status = {
        item["status"]: {action["action"] for action in item["available_actions"]}
        for item in body["items"]
    }
    assert actions_by_status["confirmed"] == {"cancel"}
    assert actions_by_status["pending_payment"] == {"confirm", "cancel"}


def test_host_listing_filter_by_status_and_guest(client, session, fakes_overridden):
    base_check_in = datetime.now(UTC) + timedelta(days=2)
    traveler_a = UUID("99999999-9999-9999-9999-999999999991")
    traveler_b = UUID("99999999-9999-9999-9999-999999999992")
    _seed_reservation(
        session,
        id_property=PROPERTY_A,
        id_traveler=traveler_a,
        status="confirmed",
        check_in=base_check_in,
    )
    _seed_reservation(
        session,
        id_property=PROPERTY_B,
        id_traveler=traveler_b,
        status="confirmed",
        check_in=base_check_in,
    )

    response = client.get(
        "/api/v1/reservations/host/me?status=confirmed&guest_name=ana",
        headers={"Authorization": f"Bearer {_hotel_token()}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["guest_full_name"] == "Ana García"
    assert body["items"][0]["id_traveler"] == str(traveler_a)


def test_host_listing_pagination_and_sort(client, session, fakes_overridden):
    base_check_in = datetime.now(UTC) + timedelta(days=2)
    traveler = UUID("99999999-9999-9999-9999-999999999991")
    for offset_days, total in [(0, "100.00"), (3, "300.00"), (6, "200.00")]:
        _seed_reservation(
            session,
            id_property=PROPERTY_A,
            id_traveler=traveler,
            status="confirmed",
            check_in=base_check_in + timedelta(days=offset_days),
            total=Decimal(total),
        )

    response = client.get(
        "/api/v1/reservations/host/me?sort_by=total_price&sort_dir=asc&page=1&page_size=2",
        headers={"Authorization": f"Bearer {_hotel_token()}"},
    )
    body = response.json()
    assert body["total"] == 3
    assert body["page"] == 1
    assert body["page_size"] == 2
    prices = [item["total_price"] for item in body["items"]]
    assert prices == ["100.00", "200.00"]


def test_host_metrics_uses_payments_aggregate(client, session, fakes_overridden):
    base_check_in = datetime.now(UTC) - timedelta(days=2)
    reservation = _seed_reservation(
        session,
        id_property=PROPERTY_A,
        id_traveler=uuid4(),
        status="confirmed",
        check_in=base_check_in,
        nights=3,
    )
    fakes_overridden["payments"].list_response = {
        "items": [
            {
                "reservation_id": str(reservation.id),
                "amount_in_cents": 7500,
                "currency": "COP",
            },
        ],
        "available_currencies": ["COP"],
    }

    response = client.get(
        "/api/v1/reservations/host/me/metrics",
        headers={"Authorization": f"Bearer {_hotel_token()}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["revenue_amount"] == "75.00"
    assert body["revenue_currency"] == "COP"
    assert body["available_currencies"] == ["COP"]
    assert body["total_nights"] >= 1
    assert body["active_reservations"] >= 1
    call = fakes_overridden["payments"].last_call
    assert call["status"] == "confirmed"


def test_host_revenue_trends_returns_buckets(client, session, fakes_overridden):
    base_check_in = datetime.now(UTC).replace(microsecond=0) - timedelta(days=4)
    reservation_a = _seed_reservation(
        session,
        id_property=PROPERTY_A,
        id_traveler=uuid4(),
        status="confirmed",
        check_in=base_check_in,
        nights=2,
    )
    reservation_b = _seed_reservation(
        session,
        id_property=PROPERTY_A,
        id_traveler=uuid4(),
        status="confirmed",
        check_in=base_check_in + timedelta(days=1),
        nights=2,
    )
    fakes_overridden["payments"].list_response = {
        "items": [
            {
                "reservation_id": str(reservation_a.id),
                "amount_in_cents": 7000,
                "currency": "COP",
            },
            {
                "reservation_id": str(reservation_b.id),
                "amount_in_cents": 5000,
                "currency": "COP",
            },
        ],
        "available_currencies": ["COP"],
    }
    response = client.get(
        "/api/v1/reservations/host/me/revenue-trends?granularity=day",
        headers={"Authorization": f"Bearer {_hotel_token()}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["granularity"] == "day"
    assert body["currency"] == "COP"
    assert body["available_currencies"] == ["COP"]
    assert len(body["buckets"]) == 2
    assert body["buckets"][0]["revenue"] == "70.00"
    assert body["buckets"][1]["revenue"] == "50.00"
