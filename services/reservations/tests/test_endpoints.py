from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

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
from core.config import settings


class FakePropertyServiceClient:
    def __init__(
        self,
        *,
        max_guests: int = 12,
        policy_type: CancellationPolicyType = CancellationPolicyType.full_refund,
        minimum_notice_hours: int = 24,
        penalty_percentage: Decimal = Decimal("0.00"),
    ):
        self.max_guests = max_guests
        self.policy_type = policy_type
        self.minimum_notice_hours = minimum_notice_hours
        self.penalty_percentage = penalty_percentage

    def get_property(self, property_id):
        return PropertyDetailResponse(id=property_id, max_guests=self.max_guests)

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
        assert data["total_price"] == "357.00"  # 3 noches * 100 * 1.19
        assert data["currency"] == "COP"
        assert "id" in data
        assert "created_at" in data

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
            "COP": "357.00",  # 3 noches * 100 * 1.19
            "USD": "324.00",  # 3 noches * 100 * 1.08
            "ARS": "363.00",  # 3 noches * 100 * 1.21
            "CLP": "357.00",  # 3 noches * 100 * 1.19
            "PEN": "354.00",  # 3 noches * 100 * 1.18
            "MXN": "348.00",  # 3 noches * 100 * 1.16
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
        assert body["delta_amount"] == "119.00"
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
        assert body["refund_amount"] == "238.00"
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
        assert body["status_after"] == "refund_completed"

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
            json={"status": "modification_pending_payment"},
            headers={"X-Internal-Api-Key": settings.internal_api_key},
        )

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
