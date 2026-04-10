from uuid import UUID

import httpx

from core.config import settings
from domain.ports.traveler_profile_source import TravelerProfileSource
from domain.schemas.notification import TravelerProfileRecord
from errors import PaymentConfirmationUnavailableError, TravelerProfileNotFoundError


class HttpTravelerProfileClient(TravelerProfileSource):
    def get_traveler(self, traveler_id: UUID) -> TravelerProfileRecord:
        url = f"{settings.users_service_url}/api/v1/users"
        try:
            response = httpx.get(url, timeout=5.0)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise PaymentConfirmationUnavailableError(
                "No fue posible consultar la informacion del viajero."
            ) from exc

        users = response.json()
        traveler = next(
            (user for user in users if str(user.get("id")) == str(traveler_id)),
            None,
        )
        if traveler is None:
            raise TravelerProfileNotFoundError(
                f"No se encontro informacion del viajero {traveler_id}."
            )

        return TravelerProfileRecord(
            traveler_id=traveler["id"],
            email=traveler["email"],
            full_name=traveler["full_name"],
        )
