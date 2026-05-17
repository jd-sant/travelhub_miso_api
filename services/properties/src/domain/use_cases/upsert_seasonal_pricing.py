import json
import logging
from datetime import UTC, date, datetime
from uuid import UUID

from sqlmodel import Session, select

from adapters.models.property_pricing_audit_log import PropertyPricingAuditLog
from adapters.models.property_seasonal_price import PropertySeasonalPrice
from core.config import settings
from core.security import (
    SIGNATURE_ALGO,
    build_pricing_signature,
    canonicalize_pricing_payload,
    verify_pricing_signature,
)
from domain.ports.property_repository import PropertyRepository
from domain.schemas.property import (
    SeasonalPricingCreateRequest,
    SeasonalPricingResponse,
    SeasonalPricingUpdateRequest,
)
from errors import (
    PricingIntegrityLockedError,
    PricingOwnershipError,
    PricingSignatureVerificationError,
    PropertyNotFoundError,
    SeasonalPricingNotFoundError,
)

logger = logging.getLogger(__name__)


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
        integrity_valid=not model.integrity_locked,
    )


def _audit_payload_snapshot(
    *,
    property_id: UUID,
    season_start: date,
    season_end: date,
    price_per_night: float,
    currency: str,
    tax_rate: float,
    cleaning_fee: float,
) -> str:
    return json.dumps(
        {
            "property_id": str(property_id),
            "season_start": season_start.isoformat(),
            "season_end": season_end.isoformat(),
            "price_per_night": price_per_night,
            "currency": currency,
            "tax_rate": tax_rate,
            "cleaning_fee": cleaning_fee,
        }
    )


class UpsertSeasonalPricingUseCase:
    def __init__(self, session: Session, property_repository: PropertyRepository):
        self.session = session
        self.property_repository = property_repository

    def execute_create(
        self,
        property_id: UUID,
        admin_id: str,
        source_ip: str | None,
        request: SeasonalPricingCreateRequest,
    ) -> SeasonalPricingResponse:
        self._assert_owner(property_id, admin_id)

        signature = self._sign(
            property_id=property_id,
            season_start=request.season_start,
            season_end=request.season_end,
            price_per_night=request.price_per_night,
            currency=request.currency,
            tax_rate=request.tax_rate,
            cleaning_fee=request.cleaning_fee,
        )

        model = PropertySeasonalPrice(
            property_id=property_id,
            season_start=request.season_start,
            season_end=request.season_end,
            price_per_night=request.price_per_night,
            currency=request.currency,
            tax_rate=request.tax_rate,
            cleaning_fee=request.cleaning_fee,
            signature_hash=signature,
            signature_algo=SIGNATURE_ALGO,
        )
        self.session.add(model)
        self.session.flush()

        self._record_audit(
            model=model,
            action="pricing_created",
            admin_id=admin_id,
            source_ip=source_ip,
            season_start=request.season_start,
            season_end=request.season_end,
            price_per_night=request.price_per_night,
            currency=request.currency,
            tax_rate=request.tax_rate,
            cleaning_fee=request.cleaning_fee,
        )
        self.session.commit()
        self.property_repository.invalidate_property_caches(property_id)
        return _to_response(model)

    def execute_update(
        self,
        property_id: UUID,
        seasonal_price_id: UUID,
        admin_id: str,
        source_ip: str | None,
        request: SeasonalPricingUpdateRequest,
    ) -> SeasonalPricingResponse:
        self._assert_owner(property_id, admin_id)

        existing = self.session.exec(
            select(PropertySeasonalPrice)
            .where(PropertySeasonalPrice.id == seasonal_price_id)
            .where(PropertySeasonalPrice.property_id == property_id)
        ).first()
        if existing is None:
            raise SeasonalPricingNotFoundError(
                f"Seasonal pricing {seasonal_price_id} not found"
            )
        if existing.integrity_locked:
            raise PricingIntegrityLockedError(
                "Pricing record is locked due to integrity failure"
            )

        # Merge: aplicar solo los campos provistos sobre el modelo persistido.
        updates = request.model_dump(exclude_unset=True)
        for field, value in updates.items():
            setattr(existing, field, value)

        signature = self._sign(
            property_id=property_id,
            season_start=existing.season_start,
            season_end=existing.season_end,
            price_per_night=existing.price_per_night,
            currency=existing.currency,
            tax_rate=existing.tax_rate,
            cleaning_fee=existing.cleaning_fee,
        )
        existing.signature_hash = signature
        existing.updated_at = datetime.now(UTC)
        self.session.add(existing)
        self.session.flush()

        self._record_audit(
            model=existing,
            action="pricing_updated",
            admin_id=admin_id,
            source_ip=source_ip,
            season_start=existing.season_start,
            season_end=existing.season_end,
            price_per_night=existing.price_per_night,
            currency=existing.currency,
            tax_rate=existing.tax_rate,
            cleaning_fee=existing.cleaning_fee,
        )
        self.session.commit()
        self.property_repository.invalidate_property_caches(property_id)
        return _to_response(existing)

    # ----- helpers -----

    def _assert_owner(self, property_id: UUID, admin_id: str) -> None:
        prop = self.property_repository.get_by_id(property_id)
        if prop is None:
            raise PropertyNotFoundError(f"Property {property_id} not found")
        if not admin_id or str(prop.id_owner) != admin_id:
            raise PricingOwnershipError(
                f"Admin {admin_id or 'unknown'} does not own property {property_id}"
            )

    def _sign(
        self,
        *,
        property_id: UUID,
        season_start: date,
        season_end: date,
        price_per_night: float,
        currency: str,
        tax_rate: float,
        cleaning_fee: float,
    ) -> str:
        canonical = canonicalize_pricing_payload(
            property_id=str(property_id),
            season_start=season_start.isoformat(),
            season_end=season_end.isoformat(),
            price_per_night=price_per_night,
            currency=currency,
            tax_rate=tax_rate,
            cleaning_fee=cleaning_fee,
        )
        signature = build_pricing_signature(canonical, settings.pricing_integrity_secret)
        # Defensa en profundidad: HU-ARQ-06 exige verificación inmediata post-firma.
        # Matemáticamente no puede fallar con el mismo secret, pero el AC lo pide explícito.
        if not verify_pricing_signature(canonical, signature, settings.pricing_integrity_secret):
            raise PricingSignatureVerificationError(
                "Signature verification failed before commit"
            )
        return signature

    def _record_audit(
        self,
        *,
        model: PropertySeasonalPrice,
        action: str,
        admin_id: str,
        source_ip: str | None,
        season_start: date,
        season_end: date,
        price_per_night: float,
        currency: str,
        tax_rate: float,
        cleaning_fee: float,
    ) -> None:
        audit_log = PropertyPricingAuditLog(
            property_id=model.property_id,
            seasonal_price_id=model.id,
            action=action,
            signature_hash=model.signature_hash,
            signature_algo=model.signature_algo,
            actor_admin_id=admin_id,
            source_ip=source_ip,
            payload_snapshot_json=_audit_payload_snapshot(
                property_id=model.property_id,
                season_start=season_start,
                season_end=season_end,
                price_per_night=price_per_night,
                currency=currency,
                tax_rate=tax_rate,
                cleaning_fee=cleaning_fee,
            ),
        )
        self.session.add(audit_log)
