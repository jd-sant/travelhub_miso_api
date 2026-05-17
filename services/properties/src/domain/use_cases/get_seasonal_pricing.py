import json
from datetime import UTC, datetime
from uuid import UUID

from sqlmodel import Session, select

from adapters.models.property_pricing_audit_log import PropertyPricingAuditLog
from adapters.models.property_seasonal_price import PropertySeasonalPrice
from core.config import settings
from core.security import (
    canonicalize_pricing_payload,
    verify_pricing_signature,
)
from domain.schemas.property import (
    SeasonalPricingListResponse,
    SeasonalPricingResponse,
)
from domain.use_cases.base import BaseUseCase
from errors import SeasonalPricingNotFoundError


def _to_response(
    model: PropertySeasonalPrice, integrity_valid: bool
) -> SeasonalPricingResponse:
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
        integrity_valid=integrity_valid,
    )


class GetSeasonalPricingUseCase(BaseUseCase):
    """Retrieve seasonal pricing for a property.

    Validates signature on every read (100% coverage, HU-ARQ-06) and locks the
    record if tampering is detected. Reads that pass integrity do not write to
    the DB so GETs remain side-effect-free in the happy path.
    """

    def __init__(self, session: Session):
        self.session = session

    def execute(
        self, property_id: UUID, seasonal_price_id: UUID | None = None
    ) -> SeasonalPricingResponse | SeasonalPricingListResponse:
        if seasonal_price_id is not None:
            return self._get_single(property_id, seasonal_price_id)
        return self._get_list(property_id)

    def _get_single(
        self, property_id: UUID, seasonal_price_id: UUID
    ) -> SeasonalPricingResponse:
        model = self.session.exec(
            select(PropertySeasonalPrice)
            .where(PropertySeasonalPrice.id == seasonal_price_id)
            .where(PropertySeasonalPrice.property_id == property_id)
        ).first()
        if model is None:
            raise SeasonalPricingNotFoundError(
                f"Seasonal pricing {seasonal_price_id} not found"
            )
        integrity_valid = self._check_integrity(model)
        return _to_response(model, integrity_valid)

    def _get_list(self, property_id: UUID) -> SeasonalPricingListResponse:
        models = self.session.exec(
            select(PropertySeasonalPrice).where(
                PropertySeasonalPrice.property_id == property_id
            )
        ).all()
        items = [
            _to_response(model, self._check_integrity(model)) for model in models
        ]
        return SeasonalPricingListResponse(items=items, total=len(items))

    def _check_integrity(self, model: PropertySeasonalPrice) -> bool:
        """Verify signature; lock the record (+ audit) if tampering is detected.

        Returns whether the current signature is valid. Only writes to DB when
        a new lock is being applied — happy path is purely read.
        """
        canonical = canonicalize_pricing_payload(
            property_id=str(model.property_id),
            season_start=model.season_start.isoformat(),
            season_end=model.season_end.isoformat(),
            price_per_night=model.price_per_night,
            currency=model.currency,
            tax_rate=model.tax_rate,
            cleaning_fee=model.cleaning_fee,
        )
        is_valid = verify_pricing_signature(
            canonical,
            model.signature_hash,
            settings.pricing_integrity_secret,
            model.signature_algo,
        )

        if is_valid or model.integrity_locked:
            return is_valid

        model.integrity_locked = True
        model.integrity_checked_at = datetime.now(UTC)
        audit_log = PropertyPricingAuditLog(
            property_id=model.property_id,
            seasonal_price_id=model.id,
            action="integrity_failed",
            signature_hash=model.signature_hash,
            signature_algo=model.signature_algo,
            payload_snapshot_json=json.dumps(
                {
                    "property_id": str(model.property_id),
                    "season_start": model.season_start.isoformat(),
                    "season_end": model.season_end.isoformat(),
                    "price_per_night": model.price_per_night,
                }
            ),
        )
        self.session.add(audit_log)
        self.session.commit()
        return False
