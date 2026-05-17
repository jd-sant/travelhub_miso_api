"""Tests del contrato canónico de price_breakdown end-to-end (HU desglose).

Se valida que el cliente HTTP a `reservations` parsea correctamente el
`price_breakdown`, que el `ConfirmationEnrichmentService` lo propaga, y que
`GetPaymentConfirmationSummaryUseCase` antepone el breakdown de la reserva
al cálculo derivado del total cobrado.
"""

from datetime import date
from uuid import UUID, uuid4

import pytest

from adapters.services.reservation_details_client import (
    PropertyDetails,
    ReservationDetails,
    ReservationPriceBreakdown,
    _parse_breakdown,
)
from adapters.services.confirmation_enrichment import ConfirmationEnrichmentService
from domain.use_cases.get_payment_confirmation_summary import (
    GetPaymentConfirmationSummaryUseCase,
)


def test_parse_breakdown_acepta_todos_los_campos():
    breakdown = _parse_breakdown(
        {
            "accommodation_in_cents": 80000,
            "cleaning_fee_in_cents": 5000,
            "service_fee_in_cents": 6400,
            "taxes_in_cents": 9140,
            "total_in_cents": 100540,
            "currency": "USD",
            "nights": 2,
            "nightly_rate_in_cents": 40000,
        }
    )
    assert breakdown is not None
    assert breakdown.accommodation_in_cents == 80000
    assert breakdown.cleaning_fee_in_cents == 5000
    assert breakdown.service_fee_in_cents == 6400
    assert breakdown.taxes_in_cents == 9140
    assert breakdown.total_in_cents == 100540
    assert breakdown.nights == 2
    assert breakdown.nightly_rate_in_cents == 40000
    assert breakdown.currency == "USD"


def test_parse_breakdown_devuelve_none_si_payload_invalido():
    assert _parse_breakdown(None) is None
    assert _parse_breakdown([]) is None
    assert _parse_breakdown("not-a-dict") is None


def test_parse_breakdown_tolera_campos_faltantes_con_zero_default():
    breakdown = _parse_breakdown({"currency": "USD"})
    assert breakdown is not None
    assert breakdown.accommodation_in_cents == 0
    assert breakdown.taxes_in_cents == 0
    assert breakdown.total_in_cents == 0


class _StubReservationsClient:
    def __init__(self, breakdown: ReservationPriceBreakdown | None):
        self._breakdown = breakdown

    def fetch(self, reservation_id: UUID) -> ReservationDetails:
        return ReservationDetails(
            guests_count=2,
            property_id=uuid4(),
            check_in_date=date(2026, 5, 1),
            check_out_date=date(2026, 5, 3),
            price_breakdown=self._breakdown,
        )


class _StubPropertiesClient:
    def fetch(self, property_id: UUID) -> PropertyDetails:
        return PropertyDetails(name="Stub Hotel", address="Stub City")


def test_enrichment_service_propaga_el_breakdown_canonico():
    canonical = ReservationPriceBreakdown(
        accommodation_in_cents=80000,
        cleaning_fee_in_cents=5000,
        service_fee_in_cents=6400,
        taxes_in_cents=9140,
        total_in_cents=100540,
        nights=2,
        nightly_rate_in_cents=40000,
        currency="USD",
    )
    service = ConfirmationEnrichmentService(
        reservation_details_client=_StubReservationsClient(canonical),
        property_details_client=_StubPropertiesClient(),
    )

    enrichment = service.enrich(uuid4())

    assert enrichment.price_breakdown is canonical
    assert enrichment.guests_count == 2
    assert enrichment.property_name == "Stub Hotel"


class _FakePayment:
    def __init__(self):
        self.payment_id = uuid4()
        self.reservation_id = uuid4()
        self.traveler_id = uuid4()
        self.amount_in_cents = 100540
        self.currency = "USD"
        self.receipt_id = None
        self.receipt_number = "RC-001"
        # PaymentStatus.confirmed.value
        from domain.schemas.payment import PaymentStatus

        self.status = PaymentStatus.confirmed


class _FakePaymentRepo:
    def __init__(self, payment):
        self._payment = payment

    def get_by_id(self, payment_id):
        return self._payment


class _FakeCheckoutRepo:
    def get_session_by_payment_id(self, payment_id):
        return None


def test_summary_use_case_prefiere_breakdown_canonico_sobre_calculo_derivado():
    payment = _FakePayment()
    canonical = ReservationPriceBreakdown(
        accommodation_in_cents=80000,
        cleaning_fee_in_cents=5000,
        service_fee_in_cents=6400,
        taxes_in_cents=9140,
        total_in_cents=100540,
        nights=2,
        nightly_rate_in_cents=40000,
        currency="USD",
    )

    use_case = GetPaymentConfirmationSummaryUseCase(
        payment_repository=_FakePaymentRepo(payment),
        checkout_repository=_FakeCheckoutRepo(),
        enrichment_service=ConfirmationEnrichmentService(
            reservation_details_client=_StubReservationsClient(canonical),
            property_details_client=_StubPropertiesClient(),
        ),
    )

    response = use_case.execute(payment.payment_id)

    assert response.accommodation_in_cents == 80000
    assert response.cleaning_fee_in_cents == 5000
    assert response.service_fee_in_cents == 6400
    assert response.taxes_in_cents == 9140
    assert response.total_in_cents == 100540
    assert response.nights == 2
    assert response.nightly_rate_in_cents == 40000


def test_summary_use_case_cae_en_calculo_derivado_si_reservation_no_trae_breakdown():
    payment = _FakePayment()

    use_case = GetPaymentConfirmationSummaryUseCase(
        payment_repository=_FakePaymentRepo(payment),
        checkout_repository=_FakeCheckoutRepo(),
        enrichment_service=ConfirmationEnrichmentService(
            reservation_details_client=_StubReservationsClient(None),
            property_details_client=_StubPropertiesClient(),
        ),
    )

    response = use_case.execute(payment.payment_id)

    # El cálculo derivado no expone accommodation/cleaning/service_fee
    assert response.accommodation_in_cents is None
    assert response.cleaning_fee_in_cents is None
    assert response.service_fee_in_cents is None
    # Pero sí preserva el total y deriva taxes/noches del calculator estándar
    assert response.total_in_cents == 100540
    assert response.nights == 2
