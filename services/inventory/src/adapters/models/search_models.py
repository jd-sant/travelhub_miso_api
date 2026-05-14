from datetime import UTC, date as dt_date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Index, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel


class PropertyAmenity(SQLModel, table=True):
    __tablename__ = "property_amenity"
    __table_args__ = (
        Index(
            "ix_property_amenity_amenity_id",
            "amenity_id",
        ),
        Index(
            "ix_property_amenity_amenity_property",
            "amenity_id",
            "property_id",
        ),
    )

    property_id: UUID = Field(
        foreign_key="properties.id", primary_key=True
    )
    amenity_id: UUID = Field(
        foreign_key="amenities.id", primary_key=True
    )


class Property(SQLModel, table=True):
    __tablename__ = "properties"
    __table_args__ = (
        Index(
            "ix_properties_city_active",
            "city",
            "is_active",
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    name: str = Field(max_length=160, index=True)
    city: str = Field(max_length=120, index=True)
    country: str = Field(max_length=120)
    address: Optional[str] = Field(default=None, max_length=250)
    description: Optional[str] = Field(default=None)
    is_active: bool = Field(default=True, index=True)
    max_capacity: int = Field(ge=1, index=True)
    main_image_url: Optional[str] = Field(default=None, max_length=500)
    rating: Optional[float] = Field(default=None, ge=0, le=5, index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    room_types: list["RoomType"] = Relationship(
        back_populates="property"
    )
    services: list["Service"] = Relationship(back_populates="property")
    amenities: list["Amenity"] = Relationship(
        back_populates="properties", link_model=PropertyAmenity
    )


class RoomType(SQLModel, table=True):
    __tablename__ = "room_types"
    __table_args__ = (
        Index(
            "ix_room_types_property_active_capacity",
            "property_id",
            "is_active",
            "capacity",
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    property_id: UUID = Field(foreign_key="properties.id", index=True)
    name: str = Field(max_length=140)
    description: Optional[str] = Field(default=None)
    capacity: int = Field(ge=1, index=True)
    is_active: bool = Field(default=True, index=True)

    property: Property = Relationship(back_populates="room_types")
    rate_plans: list["RatePlan"] = Relationship(
        back_populates="room_type"
    )
    inventory_calendar: list["InventoryCalendar"] = Relationship(
        back_populates="room_type"
    )


class RatePlan(SQLModel, table=True):
    __tablename__ = "rate_plans"
    __table_args__ = (
        Index(
            "ix_rate_plans_room_type_active_base_price",
            "room_type_id",
            "is_active",
            "base_price",
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    room_type_id: UUID = Field(
        foreign_key="room_types.id", index=True
    )
    name: str = Field(max_length=140)
    description: Optional[str] = Field(default=None)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    base_price: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=12, decimal_places=2)
    is_active: bool = Field(default=True, index=True)

    room_type: RoomType = Relationship(
        back_populates="rate_plans"
    )
    rate_calendar: list["RateCalendar"] = Relationship(
        back_populates="rate_plan"
    )


class InventoryCalendar(SQLModel, table=True):
    __tablename__ = "inventory_calendar"
    __table_args__ = (
        UniqueConstraint(
            "room_type_id",
            "date",
            name="uq_inventory_calendar_room_type_date",
        ),
        Index(
            "ix_inventory_calendar_room_type_date_availability",
            "room_type_id",
            "date",
            "available_units",
            "blocked_units",
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    room_type_id: UUID = Field(
        foreign_key="room_types.id", index=True
    )
    date: dt_date = Field(index=True)
    available_units: int = Field(default=0, ge=0)
    blocked_units: int = Field(default=0, ge=0)

    room_type: RoomType = Relationship(
        back_populates="inventory_calendar"
    )


class RateCalendar(SQLModel, table=True):
    __tablename__ = "rate_calendar"
    __table_args__ = (
        UniqueConstraint(
            "rate_plan_id",
            "date",
            name="uq_rate_calendar_rate_plan_date",
        ),
        Index(
            "ix_rate_calendar_rate_plan_date_price",
            "rate_plan_id",
            "date",
            "price",
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    rate_plan_id: UUID = Field(foreign_key="rate_plans.id", index=True)
    date: dt_date = Field(index=True)
    price: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=12, decimal_places=2)

    rate_plan: RatePlan = Relationship(back_populates="rate_calendar")


class Service(SQLModel, table=True):
    __tablename__ = "services"
    __table_args__ = (
        UniqueConstraint(
            "property_id",
            "name",
            name="uq_services_property_name",
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    property_id: UUID = Field(foreign_key="properties.id", index=True)
    name: str = Field(max_length=120)
    description: Optional[str] = Field(default=None)
    is_active: bool = Field(default=True, index=True)

    property: Property = Relationship(back_populates="services")


class Amenity(SQLModel, table=True):
    __tablename__ = "amenities"

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    name: str = Field(max_length=120, index=True, unique=True)
    category: Optional[str] = Field(default=None, max_length=120)

    properties: list["Property"] = Relationship(
        back_populates="amenities", link_model=PropertyAmenity
    )
