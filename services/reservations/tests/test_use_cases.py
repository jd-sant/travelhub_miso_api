import pytest
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from domain.use_cases.check_reservation_status import CheckReservationStatusUseCase
from domain.use_cases.create_reservation import CreateReservationUseCase
from domain.use_cases.update_reservation import UpdateReservationStatusUseCase
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
        # Sin property_client => fallback (price=100, cleaning=0, tax_rate=0.16,
        # service_fee_rate=0.08). Para 3 noches y 2 huéspedes:
        #   accommodation = 100*3*2 = 600
        #   service       = 600*0.08 = 48
        #   subtotal      = 648
        #   taxes         = 648*0.16 = 103.68
        #   total         = 751.68
        expected_price = Decimal("751.68")
        assert result.total_price == expected_price
        breakdown = result.price_breakdown
        assert breakdown is not None
        assert breakdown.accommodation_in_cents == 60000
        assert breakdown.service_fee_in_cents == 4800
        assert breakdown.taxes_in_cents == 10368
        assert breakdown.total_in_cents == 75168
        assert breakdown.nights == 3

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

        # 1 noche, 1 huésped (fallback price=100, cleaning=0, tax_rate=0.16,
        # service_fee=0.08): accommodation=100; service=8; subtotal=108;
        # taxes=17.28; total=125.28
        expected_price = Decimal("125.28")
        assert result.total_price == expected_price

    def test_execute_preserves_currency_for_each_supported_code(
        self, create_reservation_use_case, traveler_id, property_id
    ):
        """El tax_rate proviene de la propiedad; sin property_client mockeado el
        fallback (0.16) aplica a todas las monedas. Solo verificamos que la
        moneda se preserva y el total cuadra con la fórmula canónica.
        """
        check_in = datetime.now(UTC) + timedelta(days=5)
        check_out = check_in + timedelta(days=2)  # 2 noches

        # 2 noches * 2 huéspedes * 100 = 400 acomodación;
        # service = 32; subtotal = 432; taxes = 69.12; total = 501.12
        expected_price = Decimal("501.12")

        for currency in ("COP", "USD", "ARS", "CLP", "PEN", "MXN"):
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
            assert result.currency == currency
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

        # 1 noche * 2 huéspedes con fallback (price=100, cleaning=0,
        # tax_rate=0.16, service=0.08): accommodation=200; service=16;
        # subtotal=216; taxes=34.56; total=250.56
        expected_price = Decimal("250.56")
        assert result.total_price == expected_price

    def test_execute_handles_timezone_aware_datetimes(
        self, create_reservation_use_case, traveler_id, property_id, room_id
    ):
        """Test that Zulu/aware datetimes from API clients are normalized correctly."""
        check_in = datetime.now(UTC) + timedelta(days=5)
        check_out = check_in + timedelta(days=2)

        request = ReservationCreateRequest(
            id_traveler=traveler_id,
            id_property=property_id,
            id_room=room_id,
            check_in_date=check_in,
            check_out_date=check_out,
            number_of_guests=2,
            currency="USD",
        )

        result = create_reservation_use_case.execute(request)

        assert result.status == "pending_payment"
        assert result.check_in_date.tzinfo == UTC
        assert result.check_out_date.tzinfo == UTC

    def test_execute_uses_property_pricing_for_canonical_breakdown(
        self, reservation_repository, traveler_id, property_id, room_id
    ):
        """Cuando hay property_client el breakdown se construye con los datos
        reales de la propiedad (price/cleaning/tax_rate)."""
        from uuid import UUID
        from domain.ports.property_service_client import PropertyServiceClient
        from domain.schemas.property_service import PropertyDetailResponse

        class StubPropertyClient(PropertyServiceClient):
            def get_property(self, property_id: UUID) -> PropertyDetailResponse:
                return PropertyDetailResponse(
                    id=property_id,
                    max_guests=4,
                    price_per_night=Decimal("200"),
                    cleaning_fee=Decimal("50"),
                    tax_rate=Decimal("0.10"),
                )

            def get_cancellation_policy(self, property_id: UUID):  # pragma: no cover
                raise NotImplementedError

        use_case = CreateReservationUseCase(
            reservation_repository,
            scheduler=None,
            properties_client=None,
            property_client=StubPropertyClient(),
        )

        check_in = datetime.now(UTC) + timedelta(days=5)
        check_out = check_in + timedelta(days=2)
        result = use_case.execute(
            ReservationCreateRequest(
                id_traveler=traveler_id,
                id_property=property_id,
                id_room=room_id,
                check_in_date=check_in,
                check_out_date=check_out,
                number_of_guests=2,
                currency="USD",
            )
        )

        # 2 noches * 2 huéspedes * 200 = 800 (accommodation)
        # cleaning = 50; service = 800*0.08 = 64; subtotal = 914
        # taxes = 914*0.10 = 91.40; total = 1005.40
        breakdown = result.price_breakdown
        assert breakdown is not None
        assert breakdown.accommodation_in_cents == 80000
        assert breakdown.cleaning_fee_in_cents == 5000
        assert breakdown.service_fee_in_cents == 6400
        assert breakdown.taxes_in_cents == 9140
        assert breakdown.total_in_cents == 100540
        assert breakdown.nights == 2
        assert breakdown.nightly_rate_in_cents == 40000
        assert result.total_price == Decimal("1005.40")

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


class TestCheckReservationStatusUseCase:
    def test_execute_cancels_pending_payment_reservation(
        self, reservation_repository, valid_create_request
    ):
        created = reservation_repository.add(valid_create_request, Decimal("357.00"))
        updater = UpdateReservationStatusUseCase(reservation_repository)
        use_case = CheckReservationStatusUseCase(updater)

        result = use_case.execute(created.id)

        assert result.status_before == "pending_payment"
        assert result.status_after == "cancelled"
        assert result.action_applied == "cancelled"
        assert result.reservation.status == "cancelled"

    def test_execute_keeps_non_pending_payment_reservation(
        self, reservation_repository, valid_create_request
    ):
        created = reservation_repository.add(valid_create_request, Decimal("357.00"))
        reservation_repository.update_status(created.id, "confirmed")
        updater = UpdateReservationStatusUseCase(reservation_repository)
        use_case = CheckReservationStatusUseCase(updater)

        result = use_case.execute(created.id)

        assert result.status_before == "confirmed"
        assert result.status_after == "confirmed"
        assert result.action_applied == "none"


class TestUpdateReservationStatusUseCase:
    def test_execute_updates_status_and_returns_transition(
        self, reservation_repository, valid_create_request
    ):
        created = reservation_repository.add(valid_create_request, Decimal("357.00"))
        use_case = UpdateReservationStatusUseCase(reservation_repository)

        result = use_case.execute(created.id, "cancelled")

        assert result.status_before == "pending_payment"
        assert result.status_after == "cancelled"
        assert result.action_applied == "cancelled"
        assert result.reservation.status == "cancelled"
