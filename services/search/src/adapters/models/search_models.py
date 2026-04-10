from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Index, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel


class PropertyAmenity(SQLModel, table=True):
    __tablename__ = "propiedad_amenidad"
    __table_args__ = (
        Index(
            "ix_propiedad_amenidad_amenidad_id",
            "amenity_id",
        ),
        Index(
            "ix_propiedad_amenidad_amenidad_propiedad",
            "amenity_id",
            "property_id",
        ),
    )

    property_id: UUID = Field(
        foreign_key="propiedades.id", primary_key=True
    )
    amenity_id: UUID = Field(
        foreign_key="amenidades.id", primary_key=True
    )


class Property(SQLModel, table=True):
    __tablename__ = "propiedades"
    __table_args__ = (
        Index(
            "ix_propiedades_ciudad_estado",
            "ciudad",
            "estado_activo",
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    nombre: str = Field(max_length=160, index=True)
    ciudad: str = Field(max_length=120, index=True)
    pais: str = Field(max_length=120)
    direccion: Optional[str] = Field(default=None, max_length=250)
    descripcion: Optional[str] = Field(default=None)
    estado_activo: bool = Field(default=True, index=True)
    capacidad_maxima: int = Field(ge=1, index=True)
    imagen_principal_url: Optional[str] = Field(default=None, max_length=500)
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
    __tablename__ = "tipos_habitacion"
    __table_args__ = (
        Index(
            "ix_tipos_habitacion_propiedad_estado_capacidad",
            "property_id",
            "estado_activo",
            "capacidad",
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    property_id: UUID = Field(foreign_key="propiedades.id", index=True)
    nombre: str = Field(max_length=140)
    descripcion: Optional[str] = Field(default=None)
    capacidad: int = Field(ge=1, index=True)
    estado_activo: bool = Field(default=True, index=True)

    property: Property = Relationship(back_populates="room_types")
    rate_plans: list["RatePlan"] = Relationship(
        back_populates="room_type"
    )
    inventory_calendar: list["InventoryCalendar"] = Relationship(
        back_populates="room_type"
    )


class RatePlan(SQLModel, table=True):
    __tablename__ = "planes_tarifa"
    __table_args__ = (
        Index(
            "ix_planes_tarifa_tipo_estado_precio",
            "room_type_id",
            "estado_activo",
            "precio_base",
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    room_type_id: UUID = Field(
        foreign_key="tipos_habitacion.id", index=True
    )
    nombre: str = Field(max_length=140)
    descripcion: Optional[str] = Field(default=None)
    moneda: str = Field(default="USD", min_length=3, max_length=3)
    precio_base: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=12, decimal_places=2)
    estado_activo: bool = Field(default=True, index=True)

    room_type: RoomType = Relationship(
        back_populates="rate_plans"
    )
    rate_calendar: list["RateCalendar"] = Relationship(
        back_populates="rate_plan"
    )


class InventoryCalendar(SQLModel, table=True):
    __tablename__ = "calendario_inventario"
    __table_args__ = (
        UniqueConstraint(
            "room_type_id",
            "fecha",
            name="uq_calendario_inventario_tipo_habitacion_fecha",
        ),
        Index(
            "ix_calendario_inventario_tipo_fecha_disponibilidad",
            "room_type_id",
            "fecha",
            "unidades_disponibles",
            "unidades_bloqueadas",
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    room_type_id: UUID = Field(
        foreign_key="tipos_habitacion.id", index=True
    )
    fecha: date = Field(index=True)
    unidades_disponibles: int = Field(default=0, ge=0)
    unidades_bloqueadas: int = Field(default=0, ge=0)

    room_type: RoomType = Relationship(
        back_populates="inventory_calendar"
    )


class RateCalendar(SQLModel, table=True):
    __tablename__ = "calendario_tarifas"
    __table_args__ = (
        UniqueConstraint(
            "rate_plan_id",
            "fecha",
            name="uq_calendario_tarifas_plan_tarifa_fecha",
        ),
        Index(
            "ix_calendario_tarifas_plan_fecha_precio",
            "rate_plan_id",
            "fecha",
            "precio",
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    rate_plan_id: UUID = Field(foreign_key="planes_tarifa.id", index=True)
    fecha: date = Field(index=True)
    precio: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=12, decimal_places=2)

    rate_plan: RatePlan = Relationship(back_populates="rate_calendar")


class Service(SQLModel, table=True):
    __tablename__ = "servicios"
    __table_args__ = (
        UniqueConstraint(
            "property_id",
            "nombre",
            name="uq_servicios_propiedad_nombre",
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    property_id: UUID = Field(foreign_key="propiedades.id", index=True)
    nombre: str = Field(max_length=120)
    descripcion: Optional[str] = Field(default=None)
    estado_activo: bool = Field(default=True, index=True)

    property: Property = Relationship(back_populates="services")


class Amenity(SQLModel, table=True):
    __tablename__ = "amenidades"

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    nombre: str = Field(max_length=120, index=True, unique=True)
    categoria: Optional[str] = Field(default=None, max_length=120)

    properties: list["Property"] = Relationship(
        back_populates="amenities", link_model=PropertyAmenity
    )
