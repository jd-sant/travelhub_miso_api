from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import jwt

from core.checkin_qr import decode_checkin_qr_payload_for_test
from core.config import settings
from domain.schemas.property_service import PropertyDetailResponse
from domain.use_cases.generate_checkin_qr import GenerateCheckInQrUseCase
from assembly import get_generate_checkin_qr_use_case


class StubUsersClient:
    def __init__(self, traveler_id: UUID):
        self.traveler_id = traveler_id

    def list_by_ids(self, ids: list[UUID]) -> list[dict]:
        if self.traveler_id not in ids:
            return []
        return [
            {
                "id": str(self.traveler_id),
                "full_name": "Ada Lovelace",
                "email": "ada@example.com",
            }
        ]


class StubPropertyClient:
    def get_property(self, property_id: UUID) -> PropertyDetailResponse:
        return PropertyDetailResponse(
            id=property_id,
            name="Grand Hotel Riviera",
            max_guests=4,
            price_per_night=Decimal("200"),
            cover_image_url="https://example.com/hotel.jpg",
            cleaning_fee=Decimal("50"),
            tax_rate=Decimal("0.10"),
        )

    def get_cancellation_policy(self, property_id: UUID):  # pragma: no cover
        raise NotImplementedError


def _confirmed_reservation(reservation_repository, valid_create_request):
    created = reservation_repository.add(valid_create_request, Decimal("357.00"))
    reservation_repository.update_status(created.id, "confirmed")
    return reservation_repository.get_by_id(created.id)


def test_generate_checkin_qr_use_case_encrypts_payload_and_includes_metadata(
    reservation_repository,
    traveler_id,
    valid_create_request,
):
    reservation = _confirmed_reservation(reservation_repository, valid_create_request)
    assert reservation is not None

    use_case = GenerateCheckInQrUseCase(
        reservation_repository,
        StubUsersClient(traveler_id),
        StubPropertyClient(),
    )

    result = use_case.execute(reservation.id, actor_user_id=traveler_id)

    assert result.reservation_id == reservation.id
    assert result.reservation_status == "confirmed"
    assert result.property_name == "Grand Hotel Riviera"
    assert result.property_cover_image_url == "https://example.com/hotel.jpg"
    assert result.holder_email == "ada@example.com"
    assert result.holder_full_name == "Ada Lovelace"
    assert result.encrypted_payload.startswith("thci1.")

    decoded = decode_checkin_qr_payload_for_test(
        result.encrypted_payload,
        settings.checkin_qr_secret_key,
    )
    assert decoded.reservation_id == reservation.id
    assert decoded.traveler_id == traveler_id
    assert decoded.holder_email == "ada@example.com"
    assert decoded.holder_full_name == "Ada Lovelace"


def test_get_checkin_qr_route_returns_payload_for_authenticated_traveler(
    client,
    reservation_repository,
    traveler_id,
    valid_create_request,
):
    reservation = _confirmed_reservation(reservation_repository, valid_create_request)
    assert reservation is not None

    from domain.schemas.reservation import CheckInQrResponse

    response_model = CheckInQrResponse(
        reservation_id=reservation.id,
        reservation_status="confirmed",
        reservation_fingerprint="fingerprint",
        property_name="Grand Hotel Riviera",
        property_cover_image_url="https://example.com/hotel.jpg",
        check_in_date=reservation.check_in_date,
        check_out_date=reservation.check_out_date,
        number_of_guests=reservation.number_of_guests,
        holder_email="ada@example.com",
        holder_full_name="Ada Lovelace",
        traveler_id=traveler_id,
        encrypted_payload="thci1.fake",
        issued_at_epoch_ms=123,
    )

    class TypedStubUseCase:
        def execute(self, reservation_id, *, actor_user_id):
            return response_model

    app_override = TypedStubUseCase()
    from entrypoints.api.main import app

    app.dependency_overrides[get_generate_checkin_qr_use_case] = lambda: app_override
    token = jwt.encode(
        {
            "sub": str(traveler_id),
            "email": "ada@example.com",
            "role": "traveler",
            "iat": int(datetime.now(UTC).timestamp()),
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    try:
        response = client.get(
            f"/api/v1/reservations/{reservation.id}/checkin-qr",
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["reservation_id"] == str(reservation.id)
    assert body["holder_email"] == "ada@example.com"
    assert body["encrypted_payload"] == "thci1.fake"
