from uuid import UUID, uuid4
from datetime import UTC, datetime, date as date_type

from sqlmodel import Field, SQLModel


class PropertyReview(SQLModel, table=True):
    __tablename__ = "property_reviews"

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    property_id: UUID = Field(foreign_key="properties.id", index=True)
    author: str
    rating: int = Field(ge=1, le=5)
    comment: str
    verified_stay: bool = Field(default=True)
    review_date: date_type
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
