from uuid import UUID
from datetime import datetime, UTC

from sqlmodel import Session

from adapters.models.property_seasonal_price import PropertySeasonalPrice
from adapters.models.property_pricing_audit_log import PropertyPricingAuditLog
from core.config import settings
from core.security import (
    canonicalize_pricing_payload,
    verify_pricing_signature,
)
from domain.schemas.property import SeasonalPricingResponse, SeasonalPricingListResponse
from domain.use_cases.base import BaseUseCase
from errors import SeasonalPricingNotFoundError


def _to_response(model: PropertySeasonalPrice, integrity_valid: bool = True) -> SeasonalPricingResponse:
    return SeasonalPricingResponse(
        id=model.id,
        property_id=model.property_id,
        season_start=model.season_start,
        season_end=model.season_end,
        price_per_night=model.price_per_night,
        currency=model.currency,
        tax_rate=model.tax_rate,
        cleaning_fee=model.cleaning_fee,
        signature_hash=model.signature_hash,
        signature_algo=model.signature_algo,
        integrity_locked=model.integrity_locked,
        integrity_checked_at=model.integrity_checked_at.isoformat() if model.integrity_checked_at else None,
        created_at=model.created_at.isoformat(),
        updated_at=model.updated_at.isoformat(),
        integrity_valid=integrity_valid,
    )


class GetSeasonalPricingUseCase(BaseUseCase):
    """
    Retrieve seasonal pricing for a property.
    
    Validates signature on every read (100% coverage) and locks record if tampering detected.
    """
    
    def __init__(self, session: Session):
        self.session = session

    def execute(self, property_id: UUID, seasonal_price_id: UUID | None = None) -> SeasonalPricingResponse | SeasonalPricingListResponse:
        """
        Get seasonal pricing by ID or list all for property.
        
        Validates integrity on read-path and locks if signature mismatch.
        """
        if seasonal_price_id:
            return self._get_single(property_id, seasonal_price_id)
        else:
            return self._get_list(property_id)

    def _get_single(self, property_id: UUID, seasonal_price_id: UUID) -> SeasonalPricingResponse:
        """Get single seasonal price with integrity check"""
        model = self.session.query(PropertySeasonalPrice).filter(
            PropertySeasonalPrice.id == seasonal_price_id,
            PropertySeasonalPrice.property_id == property_id,
        ).first()
        
        if not model:
            raise SeasonalPricingNotFoundError(f"Seasonal pricing {seasonal_price_id} not found")
        
        # Validate integrity (100% of reads)
        integrity_valid, was_locked = self._validate_and_lock_if_tampered(model)
        
        return _to_response(model, integrity_valid)

    def _get_list(self, property_id: UUID) -> SeasonalPricingListResponse:
        """List all seasonal prices for property with integrity checks"""
        models = self.session.query(PropertySeasonalPrice).filter(
            PropertySeasonalPrice.property_id == property_id
        ).all()
        
        items = []
        for model in models:
            # Validate integrity on each read (100%)
            integrity_valid, was_locked = self._validate_and_lock_if_tampered(model)
            items.append(_to_response(model, integrity_valid))
        
        return SeasonalPricingListResponse(items=items, total=len(items))

    def _validate_and_lock_if_tampered(self, model: PropertySeasonalPrice) -> tuple[bool, bool]:
        """
        Validate signature and lock if tampering detected.
        
        Returns (is_valid, was_locked)
        """
        # Build canonical payload from current state
        canonical = canonicalize_pricing_payload(
            property_id=str(model.property_id),
            season_start=model.season_start,
            season_end=model.season_end,
            price_per_night=model.price_per_night,
            currency=model.currency,
            tax_rate=model.tax_rate,
            cleaning_fee=model.cleaning_fee,
        )
        
        # Verify against stored signature
        is_valid = verify_pricing_signature(
            canonical,
            model.signature_hash,
            settings.pricing_integrity_secret,
            model.signature_algo,
        )
        
        was_locked = False
        if not is_valid and not model.integrity_locked:
            # Lock the record and create audit event
            model.integrity_locked = True
            model.integrity_checked_at = datetime.now(UTC)
            
            import json
            audit_log = PropertyPricingAuditLog(
                property_id=model.property_id,
                seasonal_price_id=model.id,
                action="integrity_failed",
                signature_hash=model.signature_hash,
                signature_algo=model.signature_algo,
                payload_snapshot_json=json.dumps({
                    "property_id": str(model.property_id),
                    "season_start": model.season_start,
                    "season_end": model.season_end,
                    "price_per_night": model.price_per_night,
                }),
            )
            self.session.add(audit_log)
            self.session.commit()
            was_locked = True
        elif is_valid:
            # Update check timestamp even if valid
            model.integrity_checked_at = datetime.now(UTC)
            self.session.commit()
        
        return is_valid, was_locked
