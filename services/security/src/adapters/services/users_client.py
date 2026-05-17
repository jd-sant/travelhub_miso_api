from typing import Optional

import httpx

from core.config import settings
from domain.ports.auth_repository import AuthRepository
from domain.schemas.auth import UserCredentials
from errors import ServiceUnavailableError


class UsersServiceClient(AuthRepository):
    def verify_credentials(
        self, email: str, password: str
    ) -> Optional[UserCredentials]:
        url = f"{settings.users_service_url}/api/v1/internal/verify-credentials"
        try:
            response = httpx.post(
                url,
                json={"email": email, "password": password},
                headers={"X-Internal-Api-Key": settings.internal_api_key},
                timeout=10.0,
            )
        except httpx.RequestError as exc:
            raise ServiceUnavailableError(
                "No se pudo conectar al servicio de usuarios"
            ) from exc

        if response.status_code == 200:
            data = response.json()
            return UserCredentials(**data)
        return None
