from uuid import UUID

import httpx

from core.config import settings
from domain.ports.traveler_profile_source import TravelerProfileSource
from domain.schemas.notification import TravelerProfileRecord
from errors import PaymentConfirmationUnavailableError, TravelerProfileNotFoundError


class HttpTravelerProfileClient(TravelerProfileSource):
    def get_traveler(self, traveler_id: UUID) -> TravelerProfileRecord:
        url = f"{settings.users_service_url}/api/v1/internal/users/{traveler_id}"
        try:
            response = httpx.get(
                url,
                headers={"X-Internal-Api-Key": settings.internal_api_key},
                timeout=5.0,
            )
            if response.status_code == 404:
                raise TravelerProfileNotFoundError(
                    f"No se encontro informacion del viajero {traveler_id}."
                )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise PaymentConfirmationUnavailableError(
                "No fue posible consultar la informacion del viajero."
            ) from exc

        traveler = response.json()
        return TravelerProfileRecord(
            traveler_id=traveler["id"],
            email=traveler["email"],
            full_name=traveler["full_name"],
        )
