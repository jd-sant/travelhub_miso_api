import pytest
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from domain.use_cases.create_reservation import CreateReservationUseCase
from domain.schemas.reservation import ReservationCreateRequest
from errors import InvalidReservationDateError, RoomNotAvailableError


class TestCreateReservationUseCase:
    """Tests for CreateReservationUseCase."""

    def test_execute_creates_reservation_with_calculated_price(
        self, create_reservation_use_case, valid_create_request
    ):
        """Test that execute creates reservation with calculated price including taxes."""
        result = create_reservation_use_case.execute(valid_create_request)

        assert result.id is not None
        assert result.id_traveler == valid_create_request.id_traveler
        assert result.status == "pending_payment"
        # 3 noches * 100 * (1 + 0.19 de impuesto para COP) = 357.00
        expected_price = Decimal("357.00")
        assert result.total_price == expected_price

    def test_execute_validates_dates(self, create_reservation_use_case):
        """Test that execute raises error if check_out is before check_in."""
        check_in = datetime.now(UTC) + timedelta(days=5)
        check_out = check_in - timedelta(days=1)  # Inválido: antes de la fecha de ingreso

        invalid_request = ReservationCreateRequest(
            id_traveler=uuid4(),
            id_property=uuid4(),
            id_room=uuid4(),
            check_in_date=check_in,
            check_out_date=check_out,
            number_of_guests=2,
            currency="COP",
        )

        with pytest.raises(InvalidReservationDateError):
            create_reservation_use_case.execute(invalid_request)

    def test_execute_raises_error_if_dates_are_equal(
        self, create_reservation_use_case
    ):
        """Test that execute raises error if check_in equals check_out."""
        same_date = datetime.now(UTC) + timedelta(days=5)

        invalid_request = ReservationCreateRequest(
            id_traveler=uuid4(),
            id_property=uuid4(),
            id_room=uuid4(),
            check_in_date=same_date,
            check_out_date=same_date,
            number_of_guests=2,
            currency="COP",
        )

        with pytest.raises(InvalidReservationDateError):
            create_reservation_use_case.execute(invalid_request)

    def test_execute_calculates_correct_price_for_single_night(
        self, create_reservation_use_case, traveler_id, property_id, room_id
    ):
        """Test price calculation for single night reservation."""
        check_in = datetime.now(UTC) + timedelta(days=5)
        check_out = check_in + timedelta(days=1)  # 1 noche

        request = ReservationCreateRequest(
            id_traveler=traveler_id,
            id_property=property_id,
            id_room=room_id,
            check_in_date=check_in,
            check_out_date=check_out,
            number_of_guests=1,
            currency="COP",
        )

        result = create_reservation_use_case.execute(request)

        # 1 noche * 100 * (1 + 0.19 de impuesto) = 119.00
        expected_price = Decimal("119.00")
        assert result.total_price == expected_price

    def test_execute_applies_correct_tax_rate_for_each_currency(
        self, create_reservation_use_case, traveler_id, property_id
    ):
        """Test that correct tax rates are applied for different currencies."""
        check_in = datetime.now(UTC) + timedelta(days=5)
        check_out = check_in + timedelta(days=2)  # 2 noches
        base_price = Decimal(100) * 2  # 200

        tax_rates = {
            "COP": Decimal("0.19"),  # 200 * 1.19 = 238.00
            "USD": Decimal("0.08"),  # 200 * 1.08 = 216.00
            "ARS": Decimal("0.21"),  # 200 * 1.21 = 242.00
            "CLP": Decimal("0.19"),  # 200 * 1.19 = 238.00
            "PEN": Decimal("0.18"),  # 200 * 1.18 = 236.00
            "MXN": Decimal("0.16"),  # 200 * 1.16 = 232.00
        }

        expected_prices = {
            "COP": Decimal("238.00"),
            "USD": Decimal("216.00"),
            "ARS": Decimal("242.00"),
            "CLP": Decimal("238.00"),
            "PEN": Decimal("236.00"),
            "MXN": Decimal("232.00"),
        }

        for currency, expected_price in expected_prices.items():
            request = ReservationCreateRequest(
                id_traveler=traveler_id,
                id_property=property_id,
                id_room=uuid4(),
                check_in_date=check_in,
                check_out_date=check_out,
                number_of_guests=2,
                currency=currency,
            )
            result = create_reservation_use_case.execute(request)
            assert result.total_price == expected_price

    def test_execute_uses_unknown_currency_tax_rate(
        self, create_reservation_use_case, traveler_id, property_id, room_id
    ):
        """Test that unknown currency defaults to 16% tax."""
        check_in = datetime.now(UTC) + timedelta(days=5)
        check_out = check_in + timedelta(days=1)  # 1 noche

        request = ReservationCreateRequest(
            id_traveler=traveler_id,
            id_property=property_id,
            id_room=room_id,
            check_in_date=check_in,
            check_out_date=check_out,
            number_of_guests=2,
            currency="XXX",  # Moneda desconocida
        )

        result = create_reservation_use_case.execute(request)

        # 100 * (1 + 0.16) = 116.00
        expected_price = Decimal("116.00")
        assert result.total_price == expected_price

    def test_execute_checks_room_availability(
        self, create_reservation_use_case, reservation_repository, valid_create_request
    ):
        """Test that execute checks room availability before creating."""
        total_price = Decimal("357.00")

        # Crear la primera reserva
        create_reservation_use_case.execute(valid_create_request)

        # Intentar crear una reserva solapada
        overlapping_request = ReservationCreateRequest(
            id_traveler=uuid4(),
            id_property=valid_create_request.id_property,
            id_room=valid_create_request.id_room,
            check_in_date=valid_create_request.check_in_date + timedelta(days=1),
            check_out_date=valid_create_request.check_out_date + timedelta(days=1),
            number_of_guests=2,
            currency="USD",
        )

        with pytest.raises(RoomNotAvailableError):
            create_reservation_use_case.execute(overlapping_request)
