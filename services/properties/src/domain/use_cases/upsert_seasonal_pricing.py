from uuid import UUID
from datetime import datetime, UTC

from sqlmodel import Session

from adapters.models.property_seasonal_price import PropertySeasonalPrice
from adapters.models.property_pricing_audit_log import PropertyPricingAuditLog
from core.config import settings
from core.security import (
    canonicalize_pricing_payload,
    build_pricing_signature,
    verify_pricing_signature,
)
from domain.schemas.property import SeasonalPricingCreateRequest, SeasonalPricingResponse
from domain.use_cases.base import BaseUseCase
from errors import PricingSignatureVerificationError, PricingOwnershipError, PropertyNotFoundError


def _to_response(model: PropertySeasonalPrice) -> SeasonalPricingResponse:
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
        integrity_valid=not model.integrity_locked,
    )


class UpsertSeasonalPricingUseCase(BaseUseCase):
    def __init__(self, session: Session, property_repository):
        self.session = session
        self.property_repository = property_repository

    def execute(
        self,
        property_id: UUID,
        admin_id: str | None,
        source_ip: str | None,
        request: SeasonalPricingCreateRequest,
        seasonal_price_id: UUID | None = None,  # Si viene, es update; sino, create
    ) -> SeasonalPricingResponse:
        """
        Create or update seasonal pricing with signature verification.
        
        1. Validate ownership via property repository.
        2. Build canonical payload.
        3. Generate signature.
        4. Verify before commit.
        5. Persist + audit log.
        """
        
        # Verificar que la propiedad existe
        prop = self.property_repository.get_by_id(property_id)
        if prop is None:
            raise PropertyNotFoundError(f"Property {property_id} not found")
        
        # Verificar ownership si existe admin_id
        if admin_id:
            if str(prop.id_owner) != admin_id:
                raise PricingOwnershipError(f"Admin {admin_id} does not own property {property_id}")
        
        # Build canonical payload
        canonical = canonicalize_pricing_payload(
            property_id=str(property_id),
            season_start=request.season_start,
            season_end=request.season_end,
            price_per_night=request.price_per_night,
            currency=request.currency,
            tax_rate=request.tax_rate,
            cleaning_fee=request.cleaning_fee,
        )
        
        # Generate signature
        signature = build_pricing_signature(
            canonical,
            settings.pricing_integrity_secret,
            settings.pricing_signature_algo,
        )
        
        # Verify signature before committing (security check)
        if not verify_pricing_signature(canonical, signature, settings.pricing_integrity_secret):
            raise PricingSignatureVerificationError("Signature verification failed before commit")
        
        # Create or update model
        if seasonal_price_id:
            # Update existing
            existing = self.session.query(PropertySeasonalPrice).filter(
                PropertySeasonalPrice.id == seasonal_price_id
            ).first()
            if not existing:
                raise PropertyNotFoundError(f"Seasonal pricing {seasonal_price_id} not found")
            
            if existing.integrity_locked:
                raise PricingSignatureVerificationError("Pricing record is locked due to integrity failure")
            
            existing.season_start = request.season_start
            existing.season_end = request.season_end
            existing.price_per_night = request.price_per_night
            existing.currency = request.currency
            existing.tax_rate = request.tax_rate
            existing.cleaning_fee = request.cleaning_fee
            existing.signature_hash = signature
            existing.updated_at = datetime.now(UTC)
            model = existing
            action = "pricing_updated"
        else:
            # Create new
            model = PropertySeasonalPrice(
                property_id=property_id,
                season_start=request.season_start,
                season_end=request.season_end,
                price_per_night=request.price_per_night,
                currency=request.currency,
                tax_rate=request.tax_rate,
                cleaning_fee=request.cleaning_fee,
                signature_hash=signature,
                signature_algo=settings.pricing_signature_algo,
            )
            action = "pricing_created"
        
        # Persist
        self.session.add(model)
        self.session.flush()
        
        # Create audit log
        import json
        payload_snapshot = {
            "property_id": str(property_id),
            "season_start": request.season_start,
            "season_end": request.season_end,
            "price_per_night": request.price_per_night,
            "currency": request.currency,
            "tax_rate": request.tax_rate,
            "cleaning_fee": request.cleaning_fee,
        }
        
        audit_log = PropertyPricingAuditLog(
            property_id=property_id,
            seasonal_price_id=model.id,
            action=action,
            signature_hash=signature,
            signature_algo=settings.pricing_signature_algo,
            actor_admin_id=admin_id,
            source_ip=source_ip,
            payload_snapshot_json=json.dumps(payload_snapshot),
        )
        self.session.add(audit_log)
        self.session.commit()
        
        # Invalidate property cache after successful write
        if hasattr(self.property_repository, 'invalidate_property_caches'):
            self.property_repository.invalidate_property_caches(property_id)
        
        return _to_response(model)
