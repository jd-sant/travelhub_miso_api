from uuid import UUID, uuid4
from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


class PropertyImage(SQLModel, table=True):
    __tablename__ = "property_images"

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    property_id: UUID = Field(foreign_key="property.id", index=True)
    url: str
    alt_text: str | None = None
    position: int = Field(default=0, ge=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PropertyReview(SQLModel, table=True):
    __tablename__ = "property_reviews"

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    property_id: UUID = Field(foreign_key="property.id", index=True)
    author: str
    rating: int = Field(ge=1, le=5)
    comment: str
    verified_stay: bool = Field(default=True)
    date: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
