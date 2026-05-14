from uuid import UUID

from adapters.services.properties_client import PropertiesOwnershipClient
from core.auth import AuthenticatedUser
from domain.schemas.pricing import (
    PricingApplyRequest,
    PricingApplyResponse,
    PricingHistoryItem,
    PricingPreviewRequest,
    PricingPreviewResponse,
    PricingRevertResponse,
    PricingTargetOption,
)
from errors import PricingAuthorizationError


class PricingManagementUseCase:
    def __init__(self, repository, ownership_client: PropertiesOwnershipClient):
        self.repository = repository
        self.ownership_client = ownership_client

    def list_targets(self, user: AuthenticatedUser) -> list[PricingTargetOption]:
        owned_property_ids = self.ownership_client.list_owned_property_ids(user.id)
        return self.repository.list_targets(owned_property_ids)

    def preview(self, user: AuthenticatedUser, payload: PricingPreviewRequest) -> PricingPreviewResponse:
        owned_property_ids = self.ownership_client.list_owned_property_ids(user.id)
        if not owned_property_ids:
            raise PricingAuthorizationError("No tienes propiedades para gestionar")
        return self.repository.build_preview(payload, owned_property_ids)

    def apply(
        self,
        user: AuthenticatedUser,
        payload: PricingApplyRequest,
        actor_ip: str | None = None,
        request_checksum: str | None = None,
    ) -> PricingApplyResponse:
        owned_property_ids = self.ownership_client.list_owned_property_ids(user.id)
        preview, history = self.repository.apply_pricing(
            payload,
            owned_property_ids,
            actor_user_id=user.id,
            actor_email=user.email,
            actor_ip=actor_ip,
            request_checksum=request_checksum,
        )
        return PricingApplyResponse(preview=preview, history_entry=history)

    def history(self, user: AuthenticatedUser) -> list[PricingHistoryItem]:
        owned_property_ids = self.ownership_client.list_owned_property_ids(user.id)
        return self.repository.list_history(owned_property_ids)

    def revert(self, user: AuthenticatedUser, change_id: UUID) -> PricingRevertResponse:
        owned_property_ids = self.ownership_client.list_owned_property_ids(user.id)
        history = self.repository.revert_change(change_id, owned_property_ids)
        return PricingRevertResponse(
            reverted_change_id=history.id,
            reverted_at=history.reverted_at,
        )
