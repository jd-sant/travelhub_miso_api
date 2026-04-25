from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import jwt

from domain.schemas.property_service import (
    PropertyCancellationPolicyResponse,
    PropertyDetailResponse,
)
from domain.schemas.reservation import CancellationPolicyType
from entrypoints.api.main import app
from entrypoints.api.routers.reservations import (
    get_payment_service_client,
    get_property_service_client,
)
from entrypoints.api.routers.internal import get_reservation_repository
from core.config import settings
from errors import ReservationConcurrencyError


class FakePropertyServiceClient:
    def __init__(
        self,
        *,
        max_guests: int = 12,
        price_per_night: int = 100,
        policy_type: CancellationPolicyType = CancellationPolicyType.full_refund,
        minimum_notice_hours: int = 24,
        penalty_percentage: Decimal = Decimal("0.00"),
    ):
        self.max_guests = max_guests
        self.price_per_night = price_per_night
        self.policy_type = policy_type
        self.minimum_notice_hours = minimum_notice_hours
        self.penalty_percentage = penalty_percentage

    def get_property(self, property_id):
        return PropertyDetailResponse(id=property_id, max_guests=self.max_guests, price_per_night=Decimal(self.price_per_night))

    def get_cancellation_policy(self, property_id):
        now = datetime.now(UTC)
        return PropertyCancellationPolicyResponse(
            property_id=property_id,
            policy_type=self.policy_type,
            minimum_notice_hours=self.minimum_notice_hours,
            penalty_percentage=self.penalty_percentage,
            timezone="UTC",
            is_active=True,
            created_at=now,
            updated_at=now,
        )


class FakePaymentServiceClient:
    def __init__(self):
        self.refund_calls = []
        self.additional_charge_calls = []

    def request_refund(
        self,
        *,
        reservation_id,
        amount_in_cents,
        reason,
        idempotency_key,
        source_ip=None,
    ):
        self.refund_calls.append(
            {
                "reservation_id": str(reservation_id),
                "amount_in_cents": amount_in_cents,
                "reason": reason,
                "idempotency_key": idempotency_key,
            }
        )

    def request_additional_charge(
        self,
        *,
        reservation_id,
        traveler_id,
        amount_in_cents,
        currency,
        idempotency_key,
        source_ip=None,
    ):
        self.additional_charge_calls.append(
            {
                "reservation_id": str(reservation_id),
                "traveler_id": str(traveler_id),
                "amount_in_cents": amount_in_cents,
                "currency": currency,
                "idempotency_key": idempotency_key,
            }
        )


class TestReservationEndpoints:
    """Tests for reservation API endpoints."""

    def test_create_reservation_successfully(self, client):
        """Test creating a reservation successfully."""
        traveler_id = str(uuid4())
        property_id = str(uuid4())
        room_id = str(uuid4())
        check_in = (datetime.now(UTC) + timedelta(days=5)).isoformat()
        check_out = (datetime.now(UTC) + timedelta(days=8)).isoformat()

        payload = {
            "id_traveler": traveler_id,
            "id_property": property_id,
            "id_room": room_id,
            "check_in_date": check_in,
            "check_out_date": check_out,
            "number_of_guests": 2,
            "currency": "COP",
        }

        response = client.post("/api/v1/reservations", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "pending_payment"
        assert data["total_price"] == "714.00"  # 3 noches * 2 huéspedes * 100 * 1.19
        assert data["currency"] == "COP"
        assert "id" in data
        assert "created_at" in data
        assert "hold_expires_at" in data

    def test_create_reservation_returns_400_if_checkout_before_checkin(self, client):
        """Test that creating reservation fails if checkout is before checkin."""
        traveler_id = str(uuid4())
        property_id = str(uuid4())
        room_id = str(uuid4())
        check_in = (datetime.now(UTC) + timedelta(days=5)).isoformat()
        check_out = (datetime.now(UTC) + timedelta(days=3)).isoformat()  # Antes de la fecha de ingreso

        payload = {
            "id_traveler": traveler_id,
            "id_property": property_id,
            "id_room": room_id,
            "check_in_date": check_in,
            "check_out_date": check_out,
            "number_of_guests": 2,
            "currency": "COP",
        }

        response = client.post("/api/v1/reservations", json=payload)

        assert response.status_code == 400
        assert "Check-out date must be after check-in date" in response.json()["detail"]

    def test_create_reservation_returns_400_if_room_not_available(self, client):
        """Test that creating reservation fails if room is already booked."""
        traveler_id_1 = str(uuid4())
        traveler_id_2 = str(uuid4())
        property_id = str(uuid4())
        room_id = str(uuid4())
        check_in = datetime.now(UTC) + timedelta(days=5)
        check_out = check_in + timedelta(days=3)

        # Crear la primera reserva
        payload_1 = {
            "id_traveler": traveler_id_1,
            "id_property": property_id,
            "id_room": room_id,
            "check_in_date": check_in.isoformat(),
            "check_out_date": check_out.isoformat(),
            "number_of_guests": 2,
            "currency": "COP",
        }
        response_1 = client.post("/api/v1/reservations", json=payload_1)
        assert response_1.status_code == 201

        # Intentar crear una reserva solapada
        payload_2 = {
            "id_traveler": traveler_id_2,
            "id_property": property_id,
            "id_room": room_id,
            "check_in_date": (check_in + timedelta(days=1)).isoformat(),
            "check_out_date": (check_out + timedelta(days=1)).isoformat(),
            "number_of_guests": 2,
            "currency": "USD",
        }
        response_2 = client.post("/api/v1/reservations", json=payload_2)

        assert response_2.status_code == 400
        assert "not available" in response_2.json()["detail"]

    def test_get_reservation_successfully(self, client):
        """Test retrieving a reservation."""
        traveler_id = str(uuid4())
        property_id = str(uuid4())
        room_id = str(uuid4())
        check_in = (datetime.now(UTC) + timedelta(days=5)).isoformat()
        check_out = (datetime.now(UTC) + timedelta(days=8)).isoformat()

        # Crear reserva
        payload = {
            "id_traveler": traveler_id,
            "id_property": property_id,
            "id_room": room_id,
            "check_in_date": check_in,
            "check_out_date": check_out,
            "number_of_guests": 2,
            "currency": "COP",
        }
        create_response = client.post("/api/v1/reservations", json=payload)
        reservation_id = create_response.json()["id"]

        # Obtener reserva
        get_response = client.get(f"/api/v1/reservations/{reservation_id}")

        assert get_response.status_code == 200
        data = get_response.json()
        assert data["id"] == reservation_id
        assert data["id_traveler"] == traveler_id
        assert data["status"] == "pending_payment"
        assert "hold_expires_at" in data

    def test_get_reservation_returns_404_if_not_found(self, client):
        """Test that get returns 404 for nonexistent reservation."""
        fake_id = str(uuid4())

        response = client.get(f"/api/v1/reservations/{fake_id}")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    def test_get_reservation_returns_400_for_invalid_id_format(self, client):
        """Test that get returns 400 for invalid UUID format."""
        invalid_id = "not-a-valid-uuid"

        response = client.get(f"/api/v1/reservations/{invalid_id}")

        assert response.status_code == 400
        assert "Invalid reservation ID format" in response.json()["detail"]

    def test_get_reservations_by_user_returns_reservation_ids(self, client):
        traveler_id = str(uuid4())
        property_id = str(uuid4())
        check_in = (datetime.now(UTC) + timedelta(days=5)).isoformat()
        check_out = (datetime.now(UTC) + timedelta(days=8)).isoformat()

        created_ids: list[str] = []
        for _ in range(2):
            payload = {
                "id_traveler": traveler_id,
                "id_property": property_id,
                "id_room": str(uuid4()),
                "check_in_date": check_in,
                "check_out_date": check_out,
                "number_of_guests": 2,
                "currency": "COP",
            }
            response = client.post("/api/v1/reservations", json=payload)
            assert response.status_code == 201
            created_ids.append(response.json()["id"])

        response = client.get(f"/api/v1/reservations/users/{traveler_id}")

        assert response.status_code == 200
        body = response.json()
        assert len(body) == 2
        assert all(item["reservation"]["id_traveler"] == traveler_id for item in body)
        # New enriched fields present
        assert all("property_name" in item for item in body)
        assert all("property_cover_image_url" in item for item in body)

    def test_get_reservations_by_user_sorted_by_check_in_asc(self, client):
        """Reservations should be ordered by check_in_date ascending (próximas primero)."""
        traveler_id = str(uuid4())
        property_id = str(uuid4())
        now = datetime.now(UTC)

        # Create two reservations with different check-in dates (later one first)
        for days_ahead in [10, 3]:
            payload = {
                "id_traveler": traveler_id,
                "id_property": property_id,
                "id_room": str(uuid4()),
                "check_in_date": (now + timedelta(days=days_ahead)).isoformat(),
                "check_out_date": (now + timedelta(days=days_ahead + 2)).isoformat(),
                "number_of_guests": 1,
                "currency": "USD",
            }
            client.post("/api/v1/reservations", json=payload)

        response = client.get(f"/api/v1/reservations/users/{traveler_id}")
        assert response.status_code == 200
        body = response.json()
        assert len(body) == 2
        first_check_in = body[0]["reservation"]["check_in_date"]
        second_check_in = body[1]["reservation"]["check_in_date"]
        assert first_check_in < second_check_in

    def test_get_reservations_by_user_filter_cancelled(self, client):
        """status_group=cancelled returns only cancelled reservations."""
        traveler_id = str(uuid4())
        property_id = str(uuid4())
        now = datetime.now(UTC)

        # Create two reservations
        reservation_ids = []
        for i in range(2):
            payload = {
                "id_traveler": traveler_id,
                "id_property": property_id,
                "id_room": str(uuid4()),
                "check_in_date": (now + timedelta(days=5 + i)).isoformat(),
                "check_out_date": (now + timedelta(days=7 + i)).isoformat(),
                "number_of_guests": 1,
                "currency": "USD",
            }
            resp = client.post("/api/v1/reservations", json=payload)
            reservation_ids.append(resp.json()["id"])

        # Cancel the first reservation via internal endpoint
        client.patch(
            f"/api/v1/internal/reservations/{reservation_ids[0]}/status",
            json={"status": "cancelled"},
            headers={"X-Internal-Api-Key": settings.internal_api_key},
        )

        # Filter by cancelled
        response = client.get(
            f"/api/v1/reservations/users/{traveler_id}?status_group=cancelled"
        )
        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        assert body[0]["id"] == reservation_ids[0]

        # Filter by active — should return the non-cancelled one
        response = client.get(
            f"/api/v1/reservations/users/{traveler_id}?status_group=active"
        )
        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        assert body[0]["id"] == reservation_ids[1]

    def test_get_reservations_by_user_returns_empty_array_when_no_reservations(self, client):
        response = client.get(f"/api/v1/reservations/users/{uuid4()}")

        assert response.status_code == 200
        assert response.json() == []

    def test_get_reservations_by_user_returns_400_for_invalid_id_format(self, client):
        response = client.get("/api/v1/reservations/users/not-a-valid-uuid")

        assert response.status_code == 400
        assert response.json()["detail"] == "Invalid user ID format"

    def test_cancellation_confirm_preflight_allows_traveler_header(self, client):
        response = client.options(
            "/api/v1/reservations/0cbd3379-5b04-40b0-a8d2-61b80fba434b/cancellation/confirm",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type, x-traveler-id",
            },
        )

        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
        assert "x-traveler-id" in response.headers["access-control-allow-headers"].lower()

    def test_checkstatus_cancels_pending_payment_reservation(self, client):
        traveler_id = str(uuid4())
        property_id = str(uuid4())
        room_id = str(uuid4())
        check_in = (datetime.now(UTC) + timedelta(days=5)).isoformat()
        check_out = (datetime.now(UTC) + timedelta(days=8)).isoformat()

        payload = {
            "id_traveler": traveler_id,
            "id_property": property_id,
            "id_room": room_id,
            "check_in_date": check_in,
            "check_out_date": check_out,
            "number_of_guests": 2,
            "currency": "COP",
        }
        create_response = client.post("/api/v1/reservations", json=payload)
        reservation_id = create_response.json()["id"]

        response = client.post(
            f"/api/v1/internal/reservations/{reservation_id}/checkstatus",
            headers={"X-Internal-Api-Key": settings.internal_api_key},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status_before"] == "pending_payment"
        assert data["status_after"] == "cancelled"
        assert data["action_applied"] == "cancelled"
        assert data["reservation"]["status"] == "cancelled"

    def test_checkstatus_does_not_change_non_pending_status(self, client):
        traveler_id = str(uuid4())
        property_id = str(uuid4())
        room_id = str(uuid4())
        check_in = (datetime.now(UTC) + timedelta(days=5)).isoformat()
        check_out = (datetime.now(UTC) + timedelta(days=8)).isoformat()

        payload = {
            "id_traveler": traveler_id,
            "id_property": property_id,
            "id_room": room_id,
            "check_in_date": check_in,
            "check_out_date": check_out,
            "number_of_guests": 2,
            "currency": "COP",
        }
        create_response = client.post("/api/v1/reservations", json=payload)
        reservation_id = create_response.json()["id"]

        client.post(
            f"/api/v1/internal/reservations/{reservation_id}/checkstatus",
            headers={"X-Internal-Api-Key": settings.internal_api_key},
        )
        second_response = client.post(
            f"/api/v1/internal/reservations/{reservation_id}/checkstatus",
            headers={"X-Internal-Api-Key": settings.internal_api_key},
        )

        assert second_response.status_code == 200
        data = second_response.json()
        assert data["status_before"] == "cancelled"
        assert data["status_after"] == "cancelled"
        assert data["action_applied"] == "none"

    def test_checkstatus_returns_404_if_not_found(self, client):
        response = client.post(
            f"/api/v1/internal/reservations/{uuid4()}/checkstatus",
            headers={"X-Internal-Api-Key": settings.internal_api_key},
        )

        assert response.status_code == 404
        assert "Reservation not found" in response.json()["detail"]

    def test_checkstatus_returns_400_for_invalid_id_format(self, client):
        response = client.post(
            "/api/v1/internal/reservations/not-a-valid-uuid/checkstatus",
            headers={"X-Internal-Api-Key": settings.internal_api_key},
        )

        assert response.status_code == 400
        assert "Invalid reservation ID format" in response.json()["detail"]

    def test_checkstatus_returns_403_without_api_key(self, client):
        traveler_id = str(uuid4())
        property_id = str(uuid4())
        room_id = str(uuid4())
        check_in = (datetime.now(UTC) + timedelta(days=5)).isoformat()
        check_out = (datetime.now(UTC) + timedelta(days=8)).isoformat()

        payload = {
            "id_traveler": traveler_id,
            "id_property": property_id,
            "id_room": room_id,
            "check_in_date": check_in,
            "check_out_date": check_out,
            "number_of_guests": 2,
            "currency": "COP",
        }
        create_response = client.post("/api/v1/reservations", json=payload)
        reservation_id = create_response.json()["id"]

        response = client.post(f"/api/v1/internal/reservations/{reservation_id}/checkstatus")

        assert response.status_code == 403
        assert response.json()["detail"] == "Forbidden"

    def test_internal_patch_status_updates_reservation(self, client):
        traveler_id = str(uuid4())
        property_id = str(uuid4())
        room_id = str(uuid4())
        check_in = (datetime.now(UTC) + timedelta(days=5)).isoformat()
        check_out = (datetime.now(UTC) + timedelta(days=8)).isoformat()

        payload = {
            "id_traveler": traveler_id,
            "id_property": property_id,
            "id_room": room_id,
            "check_in_date": check_in,
            "check_out_date": check_out,
            "number_of_guests": 2,
            "currency": "COP",
        }
        create_response = client.post("/api/v1/reservations", json=payload)
        reservation_id = create_response.json()["id"]

        response = client.patch(
            f"/api/v1/internal/reservations/{reservation_id}/status",
            json={"status": "cancelled"},
            headers={"X-Internal-Api-Key": settings.internal_api_key},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status_before"] == "pending_payment"
        assert data["status_after"] == "cancelled"
        assert data["action_applied"] == "cancelled"
        assert data["reservation"]["status"] == "cancelled"

    def test_internal_patch_status_returns_403_with_invalid_key(self, client):
        traveler_id = str(uuid4())
        property_id = str(uuid4())
        room_id = str(uuid4())
        check_in = (datetime.now(UTC) + timedelta(days=5)).isoformat()
        check_out = (datetime.now(UTC) + timedelta(days=8)).isoformat()

        payload = {
            "id_traveler": traveler_id,
            "id_property": property_id,
            "id_room": room_id,
            "check_in_date": check_in,
            "check_out_date": check_out,
            "number_of_guests": 2,
            "currency": "COP",
        }
        create_response = client.post("/api/v1/reservations", json=payload)
        reservation_id = create_response.json()["id"]

        response = client.patch(
            f"/api/v1/internal/reservations/{reservation_id}/status",
            json={"status": "cancelled"},
            headers={"X-Internal-Api-Key": "wrong-key"},
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "Forbidden"

    def test_internal_patch_status_returns_422_for_invalid_status(self, client):
        traveler_id = str(uuid4())
        property_id = str(uuid4())
        room_id = str(uuid4())
        check_in = (datetime.now(UTC) + timedelta(days=5)).isoformat()
        check_out = (datetime.now(UTC) + timedelta(days=8)).isoformat()

        payload = {
            "id_traveler": traveler_id,
            "id_property": property_id,
            "id_room": room_id,
            "check_in_date": check_in,
            "check_out_date": check_out,
            "number_of_guests": 2,
            "currency": "COP",
        }
        create_response = client.post("/api/v1/reservations", json=payload)
        reservation_id = create_response.json()["id"]

        response = client.patch(
            f"/api/v1/internal/reservations/{reservation_id}/status",
            json={"status": "unknown_status"},
            headers={"X-Internal-Api-Key": settings.internal_api_key},
        )

        assert response.status_code == 422

    def test_health_check_endpoint(self, client):
        """Test health check endpoint."""
        response = client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_create_reservation_with_different_currencies(self, client):
        """Test creating reservations with different currencies."""
        currencies_and_expected_prices = {
            "COP": "714.00",  # 3 noches * 2 huéspedes * 100 * 1.19
            "USD": "648.00",  # 3 noches * 2 huéspedes * 100 * 1.08
            "ARS": "726.00",  # 3 noches * 2 huéspedes * 100 * 1.21
            "CLP": "714.00",  # 3 noches * 2 huéspedes * 100 * 1.19
            "PEN": "708.00",  # 3 noches * 2 huéspedes * 100 * 1.18
            "MXN": "696.00",  # 3 noches * 2 huéspedes * 100 * 1.16
        }

        check_in = (datetime.now(UTC) + timedelta(days=5)).isoformat()
        check_out = (datetime.now(UTC) + timedelta(days=8)).isoformat()

        for currency, expected_price in currencies_and_expected_prices.items():
            payload = {
                "id_traveler": str(uuid4()),
                "id_property": str(uuid4()),
                "id_room": str(uuid4()),
                "check_in_date": check_in,
                "check_out_date": check_out,
                "number_of_guests": 2,
                "currency": currency,
            }

            response = client.post("/api/v1/reservations", json=payload)

            assert response.status_code == 201
            data = response.json()
            assert data["total_price"] == expected_price
            assert data["currency"] == currency

    def _hotel_token(self) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "sub": str(uuid4()),
            "email": "hotel@example.com",
            "role": "hotel",
            "iat": now,
            "exp": now + timedelta(minutes=30),
            "jti": str(uuid4()),
        }
        return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

    def test_hotel_can_list_property_reservations(self, client):
        payload = {
            "id_traveler": str(uuid4()),
            "id_property": str(uuid4()),
            "id_room": str(uuid4()),
            "check_in_date": (datetime.now(UTC) + timedelta(days=5)).isoformat(),
            "check_out_date": (datetime.now(UTC) + timedelta(days=8)).isoformat(),
            "number_of_guests": 2,
            "currency": "COP",
        }
        created = client.post("/api/v1/reservations", json=payload)
        assert created.status_code == 201

        response = client.get(
            f"/api/v1/hotel/reservations?propertyId={payload['id_property']}",
            headers={"Authorization": f"Bearer {self._hotel_token()}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id_property"] == payload["id_property"]

    def test_hotel_can_confirm_pending_reservation(self, client):
        payload = {
            "id_traveler": str(uuid4()),
            "id_property": str(uuid4()),
            "id_room": str(uuid4()),
            "check_in_date": (datetime.now(UTC) + timedelta(days=5)).isoformat(),
            "check_out_date": (datetime.now(UTC) + timedelta(days=8)).isoformat(),
            "number_of_guests": 2,
            "currency": "COP",
        }
        created = client.post("/api/v1/reservations", json=payload)
        reservation_id = created.json()["id"]

        response = client.post(
            f"/api/v1/hotel/reservations/{reservation_id}/confirm",
            json={"reason": "confirmacion manual"},
            headers={"Authorization": f"Bearer {self._hotel_token()}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status_before"] == "pending_payment"
        assert data["status_after"] == "confirmed"
        assert data["action_applied"] == "confirmed"
        assert data["refund_requested"] is False

    def test_hotel_can_cancel_confirmed_reservation(self, client):
        payload = {
            "id_traveler": str(uuid4()),
            "id_property": str(uuid4()),
            "id_room": str(uuid4()),
            "check_in_date": (datetime.now(UTC) + timedelta(days=5)).isoformat(),
            "check_out_date": (datetime.now(UTC) + timedelta(days=8)).isoformat(),
            "number_of_guests": 2,
            "currency": "COP",
        }
        created = client.post("/api/v1/reservations", json=payload)
        reservation_id = created.json()["id"]
        client.post(
            f"/api/v1/hotel/reservations/{reservation_id}/confirm",
            json={"reason": "confirmacion manual"},
            headers={"Authorization": f"Bearer {self._hotel_token()}"},
        )

        response = client.post(
            f"/api/v1/hotel/reservations/{reservation_id}/cancel",
            json={"reason": "maintenance"},
            headers={"Authorization": f"Bearer {self._hotel_token()}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status_before"] == "confirmed"
        assert data["status_after"] == "cancelled"
        assert data["refund_requested"] is True

    def test_hotel_cannot_confirm_cancelled_reservation(self, client):
        payload = {
            "id_traveler": str(uuid4()),
            "id_property": str(uuid4()),
            "id_room": str(uuid4()),
            "check_in_date": (datetime.now(UTC) + timedelta(days=5)).isoformat(),
            "check_out_date": (datetime.now(UTC) + timedelta(days=8)).isoformat(),
            "number_of_guests": 2,
            "currency": "COP",
        }
        created = client.post("/api/v1/reservations", json=payload)
        reservation_id = created.json()["id"]
        client.post(
            f"/api/v1/hotel/reservations/{reservation_id}/cancel",
            json={"reason": "maintenance"},
            headers={"Authorization": f"Bearer {self._hotel_token()}"},
        )

        response = client.post(
            f"/api/v1/hotel/reservations/{reservation_id}/confirm",
            json={"reason": "confirmacion manual"},
            headers={"Authorization": f"Bearer {self._hotel_token()}"},
        )

        assert response.status_code == 409

    def test_hotel_endpoints_return_401_for_invalid_token(self, client):
        response = client.get(
            f"/api/v1/hotel/reservations?propertyId={uuid4()}",
            headers={"Authorization": "Bearer invalid-token"},
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "Token inválido"

    def test_hotel_cancel_reason_is_truncated_for_long_other_note(self, client):
        payload = {
            "id_traveler": str(uuid4()),
            "id_property": str(uuid4()),
            "id_room": str(uuid4()),
            "check_in_date": (datetime.now(UTC) + timedelta(days=5)).isoformat(),
            "check_out_date": (datetime.now(UTC) + timedelta(days=8)).isoformat(),
            "number_of_guests": 2,
            "currency": "COP",
        }
        created = client.post("/api/v1/reservations", json=payload)
        reservation_id = created.json()["id"]

        response = client.post(
            f"/api/v1/hotel/reservations/{reservation_id}/cancel",
            json={"reason": "other", "note": "x" * 500},
            headers={"Authorization": f"Bearer {self._hotel_token()}"},
        )

        assert response.status_code == 200
        assert len(response.json()["reason"]) <= 500

    def test_preview_modification_returns_preview(self, client):
        traveler_id = str(uuid4())
        property_id = str(uuid4())
        room_id = str(uuid4())
        check_in = (datetime.now(UTC) + timedelta(days=5)).isoformat()
        check_out = (datetime.now(UTC) + timedelta(days=7)).isoformat()

        payload = {
            "id_traveler": traveler_id,
            "id_property": property_id,
            "id_room": room_id,
            "check_in_date": check_in,
            "check_out_date": check_out,
            "number_of_guests": 2,
            "currency": "COP",
        }
        create_response = client.post("/api/v1/reservations", json=payload)
        reservation_id = create_response.json()["id"]

        client.patch(
            f"/api/v1/internal/reservations/{reservation_id}/status",
            json={"status": "confirmed"},
            headers={"X-Internal-Api-Key": settings.internal_api_key},
        )

        app.dependency_overrides[get_property_service_client] = lambda: FakePropertyServiceClient()
        try:
            response = client.post(
                f"/api/v1/reservations/{reservation_id}/modifications/preview",
                json={
                    "check_in_date": (datetime.now(UTC) + timedelta(days=6)).isoformat(),
                    "check_out_date": (datetime.now(UTC) + timedelta(days=9)).isoformat(),
                    "number_of_guests": 3,
                },
            )
        finally:
            app.dependency_overrides.pop(get_property_service_client, None)

        assert response.status_code == 200
        body = response.json()
        assert body["change_allowed"] is True
        assert body["requires_additional_charge"] is True
        assert body["delta_amount"] == "595.00"
        assert body["reservation_after_preview"]["number_of_guests"] == 3

    def test_preview_cancellation_returns_preview(self, client):
        traveler_id = str(uuid4())
        property_id = str(uuid4())
        room_id = str(uuid4())
        check_in = (datetime.now(UTC) + timedelta(days=5)).isoformat()
        check_out = (datetime.now(UTC) + timedelta(days=7)).isoformat()

        payload = {
            "id_traveler": traveler_id,
            "id_property": property_id,
            "id_room": room_id,
            "check_in_date": check_in,
            "check_out_date": check_out,
            "number_of_guests": 2,
            "currency": "COP",
        }
        create_response = client.post("/api/v1/reservations", json=payload)
        reservation_id = create_response.json()["id"]

        client.patch(
            f"/api/v1/internal/reservations/{reservation_id}/status",
            json={"status": "confirmed"},
            headers={"X-Internal-Api-Key": settings.internal_api_key},
        )

        app.dependency_overrides[get_property_service_client] = lambda: FakePropertyServiceClient()
        try:
            response = client.post(
                f"/api/v1/reservations/{reservation_id}/cancellation/preview"
            )
        finally:
            app.dependency_overrides.pop(get_property_service_client, None)

        assert response.status_code == 200
        body = response.json()
        assert body["change_allowed"] is True
        assert body["refund_amount"] == "476.00"
        assert body["penalty_amount"] == "0.00"
        assert body["refund_type"] == "full_refund"

    def test_preview_cancellation_rejects_unconfirmed_reservation(self, client):
        traveler_id = str(uuid4())
        property_id = str(uuid4())
        room_id = str(uuid4())
        check_in = (datetime.now(UTC) + timedelta(days=5)).isoformat()
        check_out = (datetime.now(UTC) + timedelta(days=7)).isoformat()

        payload = {
            "id_traveler": traveler_id,
            "id_property": property_id,
            "id_room": room_id,
            "check_in_date": check_in,
            "check_out_date": check_out,
            "number_of_guests": 2,
            "currency": "COP",
        }
        create_response = client.post("/api/v1/reservations", json=payload)
        reservation_id = create_response.json()["id"]

        app.dependency_overrides[get_property_service_client] = lambda: FakePropertyServiceClient()
        try:
            response = client.post(
                f"/api/v1/reservations/{reservation_id}/cancellation/preview"
            )
        finally:
            app.dependency_overrides.pop(get_property_service_client, None)

        assert response.status_code == 200
        body = response.json()
        assert body["change_allowed"] is False
        assert any("confirmed" in reason.lower() for reason in body["reasons"])

    def test_confirm_modification_is_idempotent(self, client):
        traveler_id = str(uuid4())
        property_id = str(uuid4())
        room_id = str(uuid4())
        check_in = (datetime.now(UTC) + timedelta(days=5)).isoformat()
        check_out = (datetime.now(UTC) + timedelta(days=7)).isoformat()

        payload = {
            "id_traveler": traveler_id,
            "id_property": property_id,
            "id_room": room_id,
            "check_in_date": check_in,
            "check_out_date": check_out,
            "number_of_guests": 2,
            "currency": "COP",
        }
        created = client.post("/api/v1/reservations", json=payload)
        reservation_id = created.json()["id"]

        client.patch(
            f"/api/v1/internal/reservations/{reservation_id}/status",
            json={"status": "confirmed"},
            headers={"X-Internal-Api-Key": settings.internal_api_key},
        )

        app.dependency_overrides[get_property_service_client] = lambda: FakePropertyServiceClient()
        app.dependency_overrides[get_payment_service_client] = lambda: FakePaymentServiceClient()
        confirm_payload = {
            "idempotency_key": "idem-mod-1",
            "check_in_date": (datetime.now(UTC) + timedelta(days=6)).isoformat(),
            "check_out_date": (datetime.now(UTC) + timedelta(days=9)).isoformat(),
            "number_of_guests": 3,
        }
        try:
            first = client.post(
                f"/api/v1/reservations/{reservation_id}/modifications/confirm",
                json=confirm_payload,
                headers={"X-Traveler-Id": traveler_id},
            )
            second = client.post(
                f"/api/v1/reservations/{reservation_id}/modifications/confirm",
                json=confirm_payload,
                headers={"X-Traveler-Id": traveler_id},
            )
        finally:
            app.dependency_overrides.pop(get_property_service_client, None)
            app.dependency_overrides.pop(get_payment_service_client, None)

        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json() == second.json()
        assert first.json()["idempotency_key"] == "idem-mod-1"

    def test_confirm_endpoints_enforce_reservation_ownership(self, client):
        traveler_id = str(uuid4())
        non_owner_id = str(uuid4())
        property_id = str(uuid4())
        room_id = str(uuid4())
        check_in = (datetime.now(UTC) + timedelta(days=5)).isoformat()
        check_out = (datetime.now(UTC) + timedelta(days=7)).isoformat()

        payload = {
            "id_traveler": traveler_id,
            "id_property": property_id,
            "id_room": room_id,
            "check_in_date": check_in,
            "check_out_date": check_out,
            "number_of_guests": 2,
            "currency": "COP",
        }
        created = client.post("/api/v1/reservations", json=payload)
        reservation_id = created.json()["id"]

        client.patch(
            f"/api/v1/internal/reservations/{reservation_id}/status",
            json={"status": "confirmed"},
            headers={"X-Internal-Api-Key": settings.internal_api_key},
        )

        app.dependency_overrides[get_property_service_client] = lambda: FakePropertyServiceClient()
        app.dependency_overrides[get_payment_service_client] = lambda: FakePaymentServiceClient()
        try:
            response = client.post(
                f"/api/v1/reservations/{reservation_id}/cancellation/confirm",
                json={"idempotency_key": "idem-cancel-1", "reason": "user-request"},
                headers={"X-Traveler-Id": non_owner_id},
            )
        finally:
            app.dependency_overrides.pop(get_property_service_client, None)
            app.dependency_overrides.pop(get_payment_service_client, None)

        assert response.status_code == 403
        assert "does not belong" in response.json()["detail"]

    def test_history_returns_confirm_event_with_actor_and_source_ip(self, client):
        traveler_id = str(uuid4())
        property_id = str(uuid4())
        room_id = str(uuid4())
        check_in = (datetime.now(UTC) + timedelta(days=5)).isoformat()
        check_out = (datetime.now(UTC) + timedelta(days=7)).isoformat()

        payload = {
            "id_traveler": traveler_id,
            "id_property": property_id,
            "id_room": room_id,
            "check_in_date": check_in,
            "check_out_date": check_out,
            "number_of_guests": 2,
            "currency": "COP",
        }
        created = client.post("/api/v1/reservations", json=payload)
        reservation_id = created.json()["id"]

        client.patch(
            f"/api/v1/internal/reservations/{reservation_id}/status",
            json={"status": "confirmed"},
            headers={"X-Internal-Api-Key": settings.internal_api_key},
        )

        app.dependency_overrides[get_property_service_client] = lambda: FakePropertyServiceClient()
        app.dependency_overrides[get_payment_service_client] = lambda: FakePaymentServiceClient()
        try:
            confirm_response = client.post(
                f"/api/v1/reservations/{reservation_id}/cancellation/confirm",
                json={"idempotency_key": "idem-cancel-history", "reason": "schedule-change"},
                headers={"X-Traveler-Id": traveler_id},
            )
        finally:
            app.dependency_overrides.pop(get_property_service_client, None)
            app.dependency_overrides.pop(get_payment_service_client, None)

        assert confirm_response.status_code == 200

        history_response = client.get(
            f"/api/v1/reservations/{reservation_id}/history",
            headers={"X-Traveler-Id": traveler_id},
        )
        assert history_response.status_code == 200
        body = history_response.json()
        assert body["reservation_id"] == reservation_id
        event_types = [item["event_type"] for item in body["events"]]
        assert "cancellation_confirmed" in event_types

        cancellation_event = [
            item for item in body["events"] if item["event_type"] == "cancellation_confirmed"
        ][-1]
        assert cancellation_event["actor_user_id"] == traveler_id
        assert cancellation_event["source_ip"] is not None

    def test_internal_refund_result_callback_updates_cancel_requested_to_refund_completed(self, client):
        traveler_id = str(uuid4())
        property_id = str(uuid4())
        room_id = str(uuid4())

        create_response = client.post(
            "/api/v1/reservations",
            json={
                "id_traveler": traveler_id,
                "id_property": property_id,
                "id_room": room_id,
                "check_in_date": (datetime.now(UTC) + timedelta(days=5)).isoformat(),
                "check_out_date": (datetime.now(UTC) + timedelta(days=7)).isoformat(),
                "number_of_guests": 2,
                "currency": "COP",
            },
        )
        reservation_id = create_response.json()["id"]

        client.patch(
            f"/api/v1/internal/reservations/{reservation_id}/status",
            json={"status": "cancel_requested"},
            headers={"X-Internal-Api-Key": settings.internal_api_key},
        )

        callback_response = client.post(
            f"/api/v1/internal/reservations/{reservation_id}/refund-result",
            json={
                "status": "succeeded",
                "refund_id": str(uuid4()),
                "amount_in_cents": 50000,
            },
            headers={"X-Internal-Api-Key": settings.internal_api_key},
        )

        assert callback_response.status_code == 200
        body = callback_response.json()
        assert body["status_before"] == "cancel_requested"
        assert body["status_after"] == "cancelled"

    def test_internal_additional_charge_result_callback_updates_modification_pending(self, client):
        traveler_id = str(uuid4())
        property_id = str(uuid4())
        room_id = str(uuid4())

        create_response = client.post(
            "/api/v1/reservations",
            json={
                "id_traveler": traveler_id,
                "id_property": property_id,
                "id_room": room_id,
                "check_in_date": (datetime.now(UTC) + timedelta(days=5)).isoformat(),
                "check_out_date": (datetime.now(UTC) + timedelta(days=7)).isoformat(),
                "number_of_guests": 2,
                "currency": "COP",
            },
        )
        reservation_id = create_response.json()["id"]

        client.patch(
            f"/api/v1/internal/reservations/{reservation_id}/status",
            json={"status": "confirmed"},
            headers={"X-Internal-Api-Key": settings.internal_api_key},
        )

        app.dependency_overrides[get_property_service_client] = lambda: FakePropertyServiceClient()
        app.dependency_overrides[get_payment_service_client] = lambda: FakePaymentServiceClient()
        try:
            confirm_response = client.post(
                f"/api/v1/reservations/{reservation_id}/modifications/confirm",
                json={
                    "idempotency_key": "idem-mod-callback-1",
                    "check_in_date": (datetime.now(UTC) + timedelta(days=6)).isoformat(),
                    "check_out_date": (datetime.now(UTC) + timedelta(days=9)).isoformat(),
                    "number_of_guests": 3,
                },
                headers={"X-Traveler-Id": traveler_id},
            )
        finally:
            app.dependency_overrides.pop(get_property_service_client, None)
            app.dependency_overrides.pop(get_payment_service_client, None)

        assert confirm_response.status_code == 200
        assert confirm_response.json()["status_after"] == "modification_pending_payment"

        callback_response = client.post(
            f"/api/v1/internal/reservations/{reservation_id}/additional-charge-result",
            json={
                "status": "succeeded",
                "payment_id": str(uuid4()),
                "amount_in_cents": 15000,
            },
            headers={"X-Internal-Api-Key": settings.internal_api_key},
        )

        assert callback_response.status_code == 200
        body = callback_response.json()
        assert body["status_before"] == "modification_pending_payment"
        assert body["status_after"] == "modification_confirmed"

    def test_internal_refund_result_returns_409_on_concurrency_conflict(self, client):
        traveler_id = str(uuid4())
        reservation_id = client.post(
            "/api/v1/reservations",
            json={
                "id_traveler": traveler_id,
                "id_property": str(uuid4()),
                "id_room": str(uuid4()),
                "check_in_date": (datetime.now(UTC) + timedelta(days=5)).isoformat(),
                "check_out_date": (datetime.now(UTC) + timedelta(days=7)).isoformat(),
                "number_of_guests": 2,
                "currency": "COP",
            },
        ).json()["id"]

        class ConflictReservationRepository:
            def get_by_id(self, _reservation_id):
                return type(
                    "R",
                    (),
                    {
                        "id": UUID(reservation_id),
                        "id_traveler": UUID(traveler_id),
                        "status": "cancel_requested",
                        "version": 1,
                        "model_dump": lambda self, mode="json": {
                            "id": reservation_id,
                            "status": "cancel_requested",
                        },
                    },
                )()

            def apply_updates(self, *_args, **_kwargs):
                raise ReservationConcurrencyError("Reservation version conflict")

        app.dependency_overrides[get_reservation_repository] = (
            lambda: ConflictReservationRepository()
        )
        try:
            response = client.post(
                f"/api/v1/internal/reservations/{reservation_id}/refund-result",
                json={"status": "succeeded", "refund_id": str(uuid4()), "amount_in_cents": 50000},
                headers={"X-Internal-Api-Key": settings.internal_api_key},
            )
        finally:
            app.dependency_overrides.pop(get_reservation_repository, None)

        assert response.status_code == 409
        assert response.json()["detail"]["message"] == "Reservation version conflict"
