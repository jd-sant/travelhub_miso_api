import pytest
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from adapters.repositories.reservation_repository import SQLModelReservationRepository
from domain.schemas.reservation import ReservationCreateRequest, ReservationResponse
from errors import RoomNotAvailableError, ReservationConflictError


class TestReservationRepository:
    """Tests for SQLModelReservationRepository."""

    def test_add_creates_reservation_successfully(
        self, reservation_repository, valid_create_request
    ):
        """Test that a valid reservation is created successfully."""
        total_price = Decimal("348.00")  # 100 * 3 noches * 1.16 (impuesto)

        result = reservation_repository.add(valid_create_request, total_price)

        assert result.id is not None
        assert result.id_traveler == valid_create_request.id_traveler
        assert result.id_property == valid_create_request.id_property
        assert result.id_room == valid_create_request.id_room
        assert result.status == "pending_payment"
        assert result.total_price == total_price
        assert result.currency == "COP"

    def test_get_by_id_returns_reservation(
        self, reservation_repository, valid_create_request
    ):
        """Test retrieving a reservation by ID."""
        total_price = Decimal("348.00")
        created = reservation_repository.add(valid_create_request, total_price)

        retrieved = reservation_repository.get_by_id(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.id_traveler == created.id_traveler

    def test_get_by_id_returns_none_for_nonexistent_reservation(
        self, reservation_repository
    ):
        """Test that get_by_id returns None for nonexistent ID."""
        result = reservation_repository.get_by_id(uuid4())

        assert result is None

    def test_list_by_traveler_returns_all_traveler_reservations(
        self, reservation_repository, traveler_id, property_id, room_id
    ):
        """Test listing all reservations for a specific traveler."""
        total_price = Decimal("348.00")

        # Crear 3 reservas para el mismo viajero
        for i in range(3):
            check_in = datetime.now(UTC) + timedelta(days=5 + i * 10)
            check_out = check_in + timedelta(days=3)
            request = ReservationCreateRequest(
                id_traveler=traveler_id,
                id_property=property_id,
                id_room=uuid4(),  # Habitación diferente cada vez
                check_in_date=check_in,
                check_out_date=check_out,
                number_of_guests=2,
                currency="COP",
            )
            reservation_repository.add(request, total_price)

        results = reservation_repository.list_by_traveler(traveler_id)

        assert len(results) == 3
        assert all(r.id_traveler == traveler_id for r in results)

    def test_check_room_availability_returns_true_if_available(
        self, reservation_repository, valid_create_request
    ):
        """Test that room availability check returns True for available room."""
        is_available = reservation_repository.check_room_availability(
            valid_create_request.id_room,
            valid_create_request.check_in_date,
            valid_create_request.check_out_date,
        )

        assert is_available is True

    def test_check_room_availability_returns_false_if_overlapping_reservation(
        self, reservation_repository, traveler_id, property_id, room_id
    ):
        """Test that availability check returns False for overlapping reservations."""
        total_price = Decimal("348.00")

        # Crear la primera reserva
        check_in_1 = datetime.now(UTC) + timedelta(days=5)
        check_out_1 = check_in_1 + timedelta(days=3)
        request_1 = ReservationCreateRequest(
            id_traveler=traveler_id,
            id_property=property_id,
            id_room=room_id,
            check_in_date=check_in_1,
            check_out_date=check_out_1,
            number_of_guests=2,
            currency="COP",
        )
        reservation_repository.add(request_1, total_price)

        # Intentar verificar disponibilidad para fechas solapadas
        check_in_2 = check_in_1 + timedelta(days=1)
        check_out_2 = check_out_1 + timedelta(days=1)

        is_available = reservation_repository.check_room_availability(
            room_id, check_in_2, check_out_2
        )

        assert is_available is False

    def test_check_room_availability_ignores_cancelled_reservations(
        self, reservation_repository, traveler_id, property_id, room_id
    ):
        """Test that cancelled reservations don't block availability."""
        total_price = Decimal("348.00")

        # Crear y cancelar una reserva
        check_in = datetime.now(UTC) + timedelta(days=5)
        check_out = check_in + timedelta(days=3)
        request = ReservationCreateRequest(
            id_traveler=traveler_id,
            id_property=property_id,
            id_room=room_id,
            check_in_date=check_in,
            check_out_date=check_out,
            number_of_guests=2,
            currency="COP",
        )
        created = reservation_repository.add(request, total_price)
        reservation_repository.update_status(created.id, "cancelled")

        # La habitación ya debería estar disponible
        is_available = reservation_repository.check_room_availability(
            room_id, check_in, check_out
        )

        assert is_available is True

    def test_update_status_changes_reservation_status(
        self, reservation_repository, valid_create_request
    ):
        """Test that update_status changes the reservation status."""
        total_price = Decimal("348.00")
        created = reservation_repository.add(valid_create_request, total_price)

        result = reservation_repository.update_status(created.id, "paid")

        assert result.status == "paid"

    def test_add_raises_error_if_room_not_available(
        self, reservation_repository, traveler_id, property_id, room_id
    ):
        """Test that adding a reservation fails if room is not available."""
        total_price = Decimal("348.00")

        # Crear la primera reserva
        check_in_1 = datetime.now(UTC) + timedelta(days=5)
        check_out_1 = check_in_1 + timedelta(days=3)
        request_1 = ReservationCreateRequest(
            id_traveler=traveler_id,
            id_property=property_id,
            id_room=room_id,
            check_in_date=check_in_1,
            check_out_date=check_out_1,
            number_of_guests=2,
            currency="COP",
        )
        reservation_repository.add(request_1, total_price)

        # Intentar crear una reserva solapada
        check_in_2 = check_in_1 + timedelta(days=1)
        check_out_2 = check_out_1 + timedelta(days=1)
        request_2 = ReservationCreateRequest(
            id_traveler=uuid4(),
            id_property=property_id,
            id_room=room_id,
            check_in_date=check_in_2,
            check_out_date=check_out_2,
            number_of_guests=2,
            currency="COP",
        )

        with pytest.raises(RoomNotAvailableError):
            reservation_repository.add(request_2, total_price)
