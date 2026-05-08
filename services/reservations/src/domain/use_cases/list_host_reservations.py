from datetime import datetime
from uuid import UUID

from adapters.services.properties_client import PropertiesServiceClient
from adapters.services.users_client import UsersServiceClient
from domain.ports.reservation_repository import ReservationRepository
from domain.schemas.reservation import (
    HostReservationItem,
    HostReservationsPage,
    compute_available_actions,
)


class ListHostReservationsUseCase:
    def __init__(
        self,
        repository: ReservationRepository,
        properties_client: PropertiesServiceClient,
        users_client: UsersServiceClient,
    ):
        self.repository = repository
        self.properties_client = properties_client
        self.users_client = users_client

    def execute(
        self,
        *,
        owner_id: UUID,
        statuses: list[str] | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        guest_name: str | None = None,
        sort_by: str = "check_in_date",
        sort_dir: str = "desc",
        page: int = 1,
        page_size: int = 10,
    ) -> HostReservationsPage:
        properties = self.properties_client.list_by_owner(owner_id)
        property_ids = [UUID(p["id"]) for p in properties]
        if not property_ids:
            return HostReservationsPage(items=[], total=0, page=page, page_size=page_size)

        guest_ids: list[UUID] | None = None
        if guest_name and guest_name.strip():
            matches = self.users_client.search_by_name(guest_name)
            guest_ids = [UUID(m["id"]) for m in matches]
            if not guest_ids:
                return HostReservationsPage(
                    items=[], total=0, page=page, page_size=page_size
                )

        reservations, total = self.repository.list_by_properties(
            property_ids,
            statuses=statuses,
            start_date=start_date,
            end_date=end_date,
            guest_ids=guest_ids,
            sort_by=sort_by,
            sort_dir=sort_dir,
            page=page,
            page_size=page_size,
        )

        property_lookup = {UUID(p["id"]): p for p in properties}
        traveler_ids = list({r.id_traveler for r in reservations})
        users = self.users_client.list_by_ids(traveler_ids) if traveler_ids else []
        user_lookup = {UUID(u["id"]): u for u in users}

        items = [
            HostReservationItem(
                id=r.id,
                reservation_number=_short_number(r.id),
                id_property=r.id_property,
                id_room=r.id_room,
                id_traveler=r.id_traveler,
                guest_full_name=(user_lookup.get(r.id_traveler) or {}).get("full_name"),
                room_type=(property_lookup.get(r.id_property) or {}).get("name"),
                check_in_date=r.check_in_date,
                check_out_date=r.check_out_date,
                number_of_guests=r.number_of_guests,
                total_price=r.total_price,
                currency=r.currency,
                status=r.status,
                created_at=r.created_at,
                available_actions=compute_available_actions(r.status),
            )
            for r in reservations
        ]
        return HostReservationsPage(
            items=items, total=total, page=page, page_size=page_size
        )


def _short_number(reservation_id: UUID) -> str:
    return f"RES-{str(reservation_id)[:8].upper()}"
