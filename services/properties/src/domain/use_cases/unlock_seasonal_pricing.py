import json
from datetime import UTC, datetime
from uuid import UUID

from sqlmodel import Session, select

from adapters.models.property_pricing_audit_log import PropertyPricingAuditLog
from adapters.models.property_seasonal_price import PropertySeasonalPrice
from core.config import settings
from core.security import (
    SIGNATURE_ALGO,
    build_pricing_signature,
    canonicalize_pricing_payload,
)
from domain.ports.property_repository import PropertyRepository
from domain.schemas.property import SeasonalPricingResponse
from errors import (
    PricingOwnershipError,
    PropertyNotFoundError,
    SeasonalPricingNotFoundError,
)


def _to_response(model: PropertySeasonalPrice) -> SeasonalPricingResponse:
    return SeasonalPricingResponse(
        id=model.id,
        property_id=model.property_id,
        season_start=model.season_start.isoformat(),
        season_end=model.season_end.isoformat(),
        price_per_night=model.price_per_night,
        currency=model.currency,
        tax_rate=model.tax_rate,
        cleaning_fee=model.cleaning_fee,
        signature_hash=model.signature_hash,
        signature_algo=model.signature_algo,
        integrity_locked=model.integrity_locked,
        integrity_checked_at=(
            model.integrity_checked_at.isoformat()
            if model.integrity_checked_at
            else None
        ),
        created_at=model.created_at.isoformat(),
        updated_at=model.updated_at.isoformat(),
        integrity_valid=True,
    )


class UnlockSeasonalPricingUseCase:
    """Admin recovery action for a locked seasonal pricing record.

    Re-signs the record's current state (the locked signature is by definition
    stale or tampered) and emits an audit event with the operator-supplied
    reason. Ownership is enforced.
    """

    def __init__(self, session: Session, property_repository: PropertyRepository):
        self.session = session
        self.property_repository = property_repository

    def execute(
        self,
        property_id: UUID,
        seasonal_price_id: UUID,
        admin_id: str,
        source_ip: str | None,
        reason: str,
    ) -> SeasonalPricingResponse:
        prop = self.property_repository.get_by_id(property_id)
        if prop is None:
            raise PropertyNotFoundError(f"Property {property_id} not found")
        if not admin_id or str(prop.id_owner) != admin_id:
            raise PricingOwnershipError(
                f"Admin {admin_id or 'unknown'} does not own property {property_id}"
            )

        model = self.session.exec(
            select(PropertySeasonalPrice)
            .where(PropertySeasonalPrice.id == seasonal_price_id)
            .where(PropertySeasonalPrice.property_id == property_id)
        ).first()
        if model is None:
            raise SeasonalPricingNotFoundError(
                f"Seasonal pricing {seasonal_price_id} not found"
            )

        canonical = canonicalize_pricing_payload(
            property_id=str(model.property_id),
            season_start=model.season_start.isoformat(),
            season_end=model.season_end.isoformat(),
            price_per_night=model.price_per_night,
            currency=model.currency,
            tax_rate=model.tax_rate,
            cleaning_fee=model.cleaning_fee,
        )
        model.signature_hash = build_pricing_signature(
            canonical, settings.pricing_integrity_secret
        )
        model.signature_algo = SIGNATURE_ALGO
        model.integrity_locked = False
        model.integrity_checked_at = datetime.now(UTC)
        model.updated_at = datetime.now(UTC)
        self.session.add(model)

        audit_log = PropertyPricingAuditLog(
            property_id=model.property_id,
            seasonal_price_id=model.id,
            action="pricing_unlocked",
            signature_hash=model.signature_hash,
            signature_algo=model.signature_algo,
            actor_admin_id=admin_id,
            source_ip=source_ip,
            payload_snapshot_json=json.dumps(
                {
                    "reason": reason,
                    "property_id": str(model.property_id),
                    "season_start": model.season_start.isoformat(),
                    "season_end": model.season_end.isoformat(),
                    "price_per_night": model.price_per_night,
                }
            ),
        )
        self.session.add(audit_log)
        self.session.commit()
        self.property_repository.invalidate_property_caches(property_id)
        return _to_response(model)
