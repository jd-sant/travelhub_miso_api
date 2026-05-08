from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from assembly import get_pricing_management_use_case
from core.auth import AuthenticatedUser, get_current_hotel_user
from domain.schemas.pricing import (
    PricingApplyResponse,
    PricingHistoryItem,
    PricingPreviewResponse,
    PricingRevertResponse,
    PricingTargetOption,
)
from entrypoints.api.main import app
from errors import PricingConflictError, PricingValidationError


class _FakePricingUseCase:
    def __init__(self):
        self.preview_payload = None
        self.apply_payload = None
        self.last_change_id = None

    def list_targets(self, user):
        return [
            PricingTargetOption(
                property_id=UUID("11111111-1111-1111-1111-111111111111"),
                property_name="Hotel Riviera",
                room_type_id=UUID("22222222-2222-2222-2222-222222222222"),
                room_type_name="Suite Presidencial",
                rate_plan_id=UUID("33333333-3333-3333-3333-333333333333"),
                rate_plan_name="Torre A",
                currency="USD",
                base_price=Decimal("245.00"),
            )
        ]

    def preview(self, user, payload):
        self.preview_payload = payload
        if payload.rule_name == "bad-rule":
            raise PricingValidationError("regla inválida")
        return PricingPreviewResponse(
            property_id=payload.property_id,
            property_name="Hotel Riviera",
            room_type_id=UUID("22222222-2222-2222-2222-222222222222"),
            room_type_name="Suite Presidencial",
            rate_plan_id=payload.rate_plan_id,
            rate_plan_name="Torre A",
            currency="USD",
            start_date=payload.start_date,
            end_date=payload.end_date,
            days_affected=3,
            current_base_price=Decimal("245.00"),
            proposed_base_price=payload.proposed_base_price or Decimal("245.00"),
            discount_type=payload.discount_type,
            discount_value=payload.discount_value,
            final_price=Decimal("196.00"),
            projected_revenue_before=Decimal("2205.00"),
            projected_revenue_after=Decimal("1764.00"),
            projected_revenue_delta=Decimal("-441.00"),
            sellable_units=3,
            requires_confirmation=True,
            impact_summary="Se afectarán 3 noches con un descuento promocional.",
        )

    def apply(self, user, payload):
        self.apply_payload = payload
        if not payload.confirmation_acknowledged:
            raise PricingConflictError("se requiere confirmación")
        preview = self.preview(user, payload)
        return PricingApplyResponse(
            preview=preview,
            history_entry=PricingHistoryItem(
                id=uuid4(),
                property_id=payload.property_id,
                property_name="Hotel Riviera",
                room_type_name="Suite Presidencial",
                rate_plan_name="Torre A",
                currency="USD",
                rule_name=payload.rule_name,
                start_date=payload.start_date,
                end_date=payload.end_date,
                previous_base_price=Decimal("245.00"),
                new_base_price=payload.proposed_base_price or Decimal("245.00"),
                discount_type=payload.discount_type,
                discount_value=payload.discount_value,
                final_price=Decimal("196.00"),
                projected_revenue_before=Decimal("2205.00"),
                projected_revenue_after=Decimal("1764.00"),
                actor_user_id=user.id,
                actor_email=user.email,
                device_label=payload.device_label,
                device_platform=payload.device_platform,
                created_at=datetime(2026, 5, 6, 12, 0, tzinfo=timezone.utc),
                reverted_at=None,
                can_revert=True,
            ),
        )

    def history(self, user):
        return [
            PricingHistoryItem(
                id=uuid4(),
                property_id=UUID("11111111-1111-1111-1111-111111111111"),
                property_name="Hotel Riviera",
                room_type_name="Suite Presidencial",
                rate_plan_name="Torre A",
                currency="USD",
                rule_name="Black Friday",
                start_date=date(2026, 11, 24),
                end_date=date(2026, 11, 30),
                previous_base_price=Decimal("245.00"),
                new_base_price=Decimal("230.00"),
                discount_type="percentage",
                discount_value=Decimal("20"),
                final_price=Decimal("184.00"),
                projected_revenue_before=Decimal("2205.00"),
                projected_revenue_after=Decimal("1656.00"),
                actor_user_id=user.id,
                actor_email=user.email,
                device_label="Pixel 9",
                device_platform="Android API 36",
                created_at=datetime(2026, 5, 6, 12, 0, tzinfo=timezone.utc),
                reverted_at=None,
                can_revert=True,
            )
        ]

    def revert(self, user, change_id):
        self.last_change_id = change_id
        if str(change_id).startswith("00000000"):
            raise PricingConflictError("ya fue revertido")
        return PricingRevertResponse(
            reverted_change_id=change_id,
            reverted_at=datetime(2026, 5, 6, 13, 0, tzinfo=timezone.utc),
        )


def _hotel_user():
    return AuthenticatedUser(
        id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        email="hotel-a@travelhub.demo",
        role="hotel_partner",
        raw_claims={},
    )


def test_list_pricing_targets_returns_options(client):
    fake = _FakePricingUseCase()
    app.dependency_overrides[get_current_hotel_user] = _hotel_user
    app.dependency_overrides[get_pricing_management_use_case] = lambda: fake
    try:
        response = client.get("/api/v1/search/hotel/pricing/targets")
        assert response.status_code == 200
        payload = response.json()
        assert payload[0]["property_name"] == "Hotel Riviera"
        assert payload[0]["rate_plan_name"] == "Torre A"
    finally:
        app.dependency_overrides.clear()


def test_preview_pricing_change_maps_validation_errors(client):
    fake = _FakePricingUseCase()
    app.dependency_overrides[get_current_hotel_user] = _hotel_user
    app.dependency_overrides[get_pricing_management_use_case] = lambda: fake
    try:
        response = client.post(
            "/api/v1/search/hotel/pricing/preview",
            json={
                "property_id": "11111111-1111-1111-1111-111111111111",
                "rate_plan_id": "33333333-3333-3333-3333-333333333333",
                "start_date": "2026-11-24",
                "end_date": "2026-11-30",
                "proposed_base_price": 245,
                "discount_type": "percentage",
                "discount_value": 20,
                "rule_name": "bad-rule",
            },
        )
        assert response.status_code == 400
        assert "inválida" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_apply_pricing_change_returns_history_entry(client):
    fake = _FakePricingUseCase()
    app.dependency_overrides[get_current_hotel_user] = _hotel_user
    app.dependency_overrides[get_pricing_management_use_case] = lambda: fake
    try:
        response = client.post(
            "/api/v1/search/hotel/pricing/apply",
            json={
                "property_id": "11111111-1111-1111-1111-111111111111",
                "rate_plan_id": "33333333-3333-3333-3333-333333333333",
                "start_date": "2026-11-24",
                "end_date": "2026-11-30",
                "proposed_base_price": 230,
                "discount_type": "percentage",
                "discount_value": 20,
                "rule_name": "Black Friday",
                "confirmation_acknowledged": True,
                "device_label": "Pixel 9",
                "device_platform": "Android API 36",
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["preview"]["requires_confirmation"] is True
        assert payload["history_entry"]["device_label"] == "Pixel 9"
    finally:
        app.dependency_overrides.clear()


def test_revert_pricing_change_maps_conflict(client):
    fake = _FakePricingUseCase()
    app.dependency_overrides[get_current_hotel_user] = _hotel_user
    app.dependency_overrides[get_pricing_management_use_case] = lambda: fake
    try:
        response = client.post(
            "/api/v1/search/hotel/pricing/history/00000000-0000-0000-0000-000000000001/revert"
        )
        assert response.status_code == 409
        assert "revertido" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()
