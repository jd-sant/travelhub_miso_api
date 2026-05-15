from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class PropertyPricingAuditLog(SQLModel, table=True):
    __tablename__ = "property_pricing_audit_logs"

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    property_id: UUID = Field(index=True)
    seasonal_price_id: UUID | None = Field(default=None, index=True)
    
    # Accion y firma
    action: str = Field(index=True)  # pricing_created, pricing_updated, integrity_failed, pricing_locked
    signature_hash: str
    signature_algo: str = Field(default="HMAC-SHA256")
    
    # Actor y fuente
    actor_admin_id: str | None = Field(default=None, index=True)
    source_ip: str | None = Field(default=None, index=True)
    
    # Snapshot del payload sanitizado
    payload_snapshot_json: str | None = Field(default=None)
    
    # Timestamp
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)
