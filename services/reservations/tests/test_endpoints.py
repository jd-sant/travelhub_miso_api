from datetime import UTC, datetime, timedelta
from uuid import uuid4


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
