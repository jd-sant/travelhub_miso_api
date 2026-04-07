from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel


class PropiedadAmenidad(SQLModel, table=True):
    __tablename__ = "propiedad_amenidad"

    propiedad_id: UUID = Field(
        foreign_key="propiedades.id", primary_key=True
    )
    amenidad_id: UUID = Field(
        foreign_key="amenidades.id", primary_key=True
    )


class Propiedad(SQLModel, table=True):
    __tablename__ = "propiedades"

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

    tipos_habitacion: list["TipoHabitacion"] = Relationship(
        back_populates="propiedad"
    )
    servicios: list["Servicio"] = Relationship(back_populates="propiedad")
    amenidades: list["Amenidad"] = Relationship(
        back_populates="propiedades", link_model=PropiedadAmenidad
    )


class TipoHabitacion(SQLModel, table=True):
    __tablename__ = "tipos_habitacion"

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    propiedad_id: UUID = Field(foreign_key="propiedades.id", index=True)
    nombre: str = Field(max_length=140)
    descripcion: Optional[str] = Field(default=None)
    capacidad: int = Field(ge=1, index=True)
    estado_activo: bool = Field(default=True, index=True)

    propiedad: Propiedad = Relationship(back_populates="tipos_habitacion")
    planes_tarifa: list["PlanTarifa"] = Relationship(
        back_populates="tipo_habitacion"
    )
    calendario_inventario: list["CalendarioInventario"] = Relationship(
        back_populates="tipo_habitacion"
    )


class PlanTarifa(SQLModel, table=True):
    __tablename__ = "planes_tarifa"

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    tipo_habitacion_id: UUID = Field(
        foreign_key="tipos_habitacion.id", index=True
    )
    nombre: str = Field(max_length=140)
    descripcion: Optional[str] = Field(default=None)
    moneda: str = Field(default="USD", min_length=3, max_length=3)
    precio_base: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=12, decimal_places=2)
    estado_activo: bool = Field(default=True, index=True)

    tipo_habitacion: TipoHabitacion = Relationship(
        back_populates="planes_tarifa"
    )
    calendario_tarifas: list["CalendarioTarifas"] = Relationship(
        back_populates="plan_tarifa"
    )


class CalendarioInventario(SQLModel, table=True):
    __tablename__ = "calendario_inventario"
    __table_args__ = (
        UniqueConstraint(
            "tipo_habitacion_id",
            "fecha",
            name="uq_calendario_inventario_tipo_habitacion_fecha",
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    tipo_habitacion_id: UUID = Field(
        foreign_key="tipos_habitacion.id", index=True
    )
    fecha: date = Field(index=True)
    unidades_disponibles: int = Field(default=0, ge=0)
    unidades_bloqueadas: int = Field(default=0, ge=0)

    tipo_habitacion: TipoHabitacion = Relationship(
        back_populates="calendario_inventario"
    )


class CalendarioTarifas(SQLModel, table=True):
    __tablename__ = "calendario_tarifas"
    __table_args__ = (
        UniqueConstraint(
            "plan_tarifa_id",
            "fecha",
            name="uq_calendario_tarifas_plan_tarifa_fecha",
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    plan_tarifa_id: UUID = Field(foreign_key="planes_tarifa.id", index=True)
    fecha: date = Field(index=True)
    precio: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=12, decimal_places=2)

    plan_tarifa: PlanTarifa = Relationship(back_populates="calendario_tarifas")


class Servicio(SQLModel, table=True):
    __tablename__ = "servicios"
    __table_args__ = (
        UniqueConstraint(
            "propiedad_id",
            "nombre",
            name="uq_servicios_propiedad_nombre",
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    propiedad_id: UUID = Field(foreign_key="propiedades.id", index=True)
    nombre: str = Field(max_length=120)
    descripcion: Optional[str] = Field(default=None)
    estado_activo: bool = Field(default=True, index=True)

    propiedad: Propiedad = Relationship(back_populates="servicios")


class Amenidad(SQLModel, table=True):
    __tablename__ = "amenidades"

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    nombre: str = Field(max_length=120, index=True, unique=True)
    categoria: Optional[str] = Field(default=None, max_length=120)

    propiedades: list["Propiedad"] = Relationship(
        back_populates="amenidades", link_model=PropiedadAmenidad
    )
