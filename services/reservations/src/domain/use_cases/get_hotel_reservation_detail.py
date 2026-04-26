from uuid import UUID

from adapters.services.properties_client import PropertiesServiceClient
from adapters.services.users_client import UsersServiceClient
from domain.ports.reservation_repository import ReservationRepository
from domain.schemas.reservation import (
    GuestInfo,
    HotelReservationDetailResponse,
    compute_available_actions,
)
from errors import ReservationAuthorizationError, ReservationNotFoundError


class GetHotelReservationDetailUseCase:
    def __init__(
        self,
        repository: ReservationRepository,
        users_client: UsersServiceClient,
        properties_client: PropertiesServiceClient,
    ):
        self.repository = repository
        self.users_client = users_client
        self.properties_client = properties_client

    def execute(self, reservation_id: UUID, *, owner_hotel_id: UUID) -> HotelReservationDetailResponse:
        reservation = self.repository.get_by_id(reservation_id)
        if reservation is None:
            raise ReservationNotFoundError("Reservation not found")

        owned_ids = self.properties_client.get_owned_property_ids(owner_hotel_id)
        if reservation.id_property not in owned_ids:
            raise ReservationAuthorizationError(
                "No tienes permiso para acceder a esta reserva."
            )

        change_history = self.repository.list_changes(reservation_id)
        internal_notes = self.repository.list_notes(reservation_id)
        available_actions = compute_available_actions(reservation.status)

        guest: GuestInfo | None = None
        try:
            users = self.users_client.list_by_ids([reservation.id_traveler])
            if users:
                u = users[0]
                guest = GuestInfo(
                    id=reservation.id_traveler,
                    full_name=u.get("full_name"),
                    email=u.get("email"),
                    phone=u.get("phone"),
                )
        except Exception:  # noqa: BLE001
            pass

        return HotelReservationDetailResponse(
            reservation=reservation,
            guest=guest,
            change_history=change_history,
            internal_notes=internal_notes,
            available_actions=available_actions,
        )
