from datetime import UTC, datetime
from uuid import UUID

from adapters.services.property_service_client import HttpPropertyServiceClient
from adapters.services.users_client import UsersServiceClient
from core.checkin_qr import build_checkin_qr_fingerprint, encode_checkin_qr_payload
from core.config import settings
from domain.ports.property_service_client import PropertyServiceClient
from domain.ports.reservation_repository import ReservationRepository
from domain.schemas.reservation import CheckInQrPayload, CheckInQrResponse
from errors import (
    InvalidReservationOperationError,
    ReservationNotFoundError,
    ReservationOwnershipError,
    ServiceUnavailableError,
)


class GenerateCheckInQrUseCase:
    def __init__(
        self,
        reservation_repository: ReservationRepository,
        users_client: UsersServiceClient,
        property_client: PropertyServiceClient | None = None,
    ):
        self.reservation_repository = reservation_repository
        self.users_client = users_client
        self.property_client = property_client or HttpPropertyServiceClient()

    def execute(self, reservation_id: UUID, *, actor_user_id: UUID) -> CheckInQrResponse:
        reservation = self.reservation_repository.get_by_id(reservation_id)
        if reservation is None:
            raise ReservationNotFoundError("Reservation not found")
        if reservation.id_traveler != actor_user_id:
            raise ReservationOwnershipError("Reservation does not belong to traveler")
        if reservation.status not in ("confirmed", "modification_confirmed"):
            raise InvalidReservationOperationError(
                "La reserva no tiene check-in disponible"
            )

        holder = self._resolve_holder(reservation.id_traveler)
        property_detail = self._resolve_property_details(reservation.id_property)
        issued_at = datetime.now(UTC)
        payload = CheckInQrPayload(
            reservation_id=reservation.id,
            traveler_id=reservation.id_traveler,
            holder_email=holder["email"],
            holder_full_name=holder.get("full_name"),
            issued_at_epoch_ms=int(issued_at.timestamp() * 1000),
        )
        encrypted_payload = encode_checkin_qr_payload(
            payload,
            settings.checkin_qr_secret_key,
        )
        return CheckInQrResponse(
            reservation_id=reservation.id,
            reservation_status=reservation.status,
            reservation_fingerprint=_build_fingerprint(reservation.status, reservation.check_in_date, reservation.check_out_date, reservation.number_of_guests),
            property_name=property_detail.get("name"),
            property_cover_image_url=property_detail.get("cover_image_url"),
            check_in_date=reservation.check_in_date,
            check_out_date=reservation.check_out_date,
            number_of_guests=reservation.number_of_guests,
            holder_email=holder["email"],
            holder_full_name=holder.get("full_name"),
            traveler_id=reservation.id_traveler,
            encrypted_payload=encrypted_payload,
            issued_at_epoch_ms=payload.issued_at_epoch_ms,
        )

    def _resolve_holder(self, traveler_id: UUID) -> dict:
        try:
            users = self.users_client.list_by_ids([traveler_id])
        except Exception as exc:  # noqa: BLE001
            raise ServiceUnavailableError(
                "No se pudo consultar el titular de la reserva"
            ) from exc
        holder = next((user for user in users if str(user.get("id")) == str(traveler_id)), None)
        if holder is None or not holder.get("email"):
            raise ServiceUnavailableError(
                "No se pudo resolver la información del titular"
            )
        return holder

    def _resolve_property_details(self, property_id: UUID) -> dict:
        try:
            prop = self.property_client.get_property(property_id)
        except Exception:
            return {}
        return {
            "name": getattr(prop, "name", None),
            "cover_image_url": getattr(prop, "cover_image_url", None),
        }


def _build_fingerprint(
    status: str,
    check_in_date: datetime,
    check_out_date: datetime,
    number_of_guests: int,
) -> str:
    return build_checkin_qr_fingerprint(
        status=status,
        check_in_date=check_in_date,
        check_out_date=check_out_date,
        number_of_guests=number_of_guests,
    )
