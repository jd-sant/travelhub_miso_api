from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class PropertySeasonalPrice(SQLModel, table=True):
    __tablename__ = "property_seasonal_prices"

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    property_id: UUID = Field(index=True)
    season_start: str = Field(index=True)  # ISO format YYYY-MM-DD
    season_end: str = Field(index=True)    # ISO format YYYY-MM-DD
    price_per_night: float = Field(ge=0)
    currency: str = Field(max_length=3, default="COP")
    tax_rate: float = Field(default=0.0, ge=0.0)
    cleaning_fee: float = Field(default=0.0, ge=0.0)
    
    # Firma y estado de integridad
    signature_hash: str = Field(index=True)
    signature_algo: str = Field(default="HMAC-SHA256")
    integrity_locked: bool = Field(default=False, index=True)
    integrity_checked_at: datetime | None = Field(default=None)
    
    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
