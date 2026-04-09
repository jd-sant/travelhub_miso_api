from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class Property(SQLModel, table=True):
    __tablename__ = "properties"

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    name: str = Field(index=True)
    description: str
    location: str = Field(index=True)
    latitude: float | None = None
    longitude: float | None = None
    price_per_night: float
    currency: str = Field(max_length=3, default="COP")
    rating: float = Field(default=0.0, ge=0.0, le=5.0)
    review_count: int = Field(default=0, ge=0)
    bedrooms: int = Field(default=0, ge=0)
    bathrooms: float = Field(default=0.0, ge=0.0)
    max_guests: int = Field(default=0, ge=0)
    amenities: str = Field(default="[]")  # JSON array as string
    status: int = Field(default=1, ge=0, le=1)
