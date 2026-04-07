from datetime import date
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import func
from sqlmodel import Session, select

from adapters.models import Amenidad
from adapters.models import CalendarioInventario
from adapters.models import CalendarioTarifas
from adapters.models import PlanTarifa
from adapters.models import Propiedad
from adapters.models import PropiedadAmenidad
from adapters.models import Servicio
from adapters.models import TipoHabitacion
from core.config import settings
from db.session import engine

TARGET_PROPERTY_COUNT = 1000
SEED_DATES = (date(2026, 4, 10), date(2026, 4, 11))

AMENITY_CATALOG = [
    ("wifi", "conectividad"),
    ("piscina", "recreacion"),
    ("gimnasio", "bienestar"),
    ("parqueadero", "comodidad"),
    ("pet_friendly", "mascotas"),
    ("aire_acondicionado", "comodidad"),
    ("desayuno_incluido", "gastronomia"),
    ("spa", "bienestar"),
]

CITIES = [
    "Bogota",
    "Cali",
    "Cartagena",
    "Barranquilla",
    "Santa Marta",
    "Bucaramanga",
]


def _is_seed_enabled() -> bool:
    db_url = str(engine.url)
    if db_url.startswith("sqlite"):
        return True
    if db_url.startswith("postgresql") and settings.is_development:
        return True
    return False


def seed_dummy_data_if_needed() -> None:
    if not _is_seed_enabled():
        return

    with Session(engine) as session:
        current_count = session.exec(select(func.count()).select_from(Propiedad)).one()
        if current_count >= TARGET_PROPERTY_COUNT:
            return

        amenity_id_by_name = _ensure_amenity_catalog(session)

        for idx in range(current_count + 1, TARGET_PROPERTY_COUNT + 1):
            property_id = uuid4()
            room_type_id = uuid4()
            rate_plan_id = uuid4()

            city = CITIES[(idx - 1) % len(CITIES)]
            capacity = 2 + (idx % 5)
            rating = min(5.0, round(3.4 + ((idx % 16) * 0.1), 1))
            base_price = Decimal(80 + idx * 3)

            session.add(
                Propiedad(
                    id=property_id,
                    nombre=f"Hotel Demo Search {idx:02d}",
                    ciudad=city,
                    pais="Colombia",
                    direccion=f"Carrera {20 + idx} #10-{40 + idx}",
                    descripcion="Propiedad dummy para pruebas locales en Postman.",
                    estado_activo=True,
                    capacidad_maxima=capacity,
                    imagen_principal_url=f"https://cdn.example.com/hotel-{idx:02d}.jpg",
                    rating=rating,
                )
            )

            session.add(
                TipoHabitacion(
                    id=room_type_id,
                    propiedad_id=property_id,
                    nombre="Habitacion Estandar",
                    descripcion="Habitacion base del dataset dummy",
                    capacidad=capacity,
                    estado_activo=True,
                )
            )

            session.add(
                PlanTarifa(
                    id=rate_plan_id,
                    tipo_habitacion_id=room_type_id,
                    nombre="Tarifa Flexible",
                    descripcion="Cancelable hasta 24h antes",
                    moneda="USD",
                    precio_base=base_price,
                    estado_activo=True,
                )
            )

            for day_offset, seed_day in enumerate(SEED_DATES):
                session.add(
                    CalendarioInventario(
                        tipo_habitacion_id=room_type_id,
                        fecha=seed_day,
                        unidades_disponibles=5 + (idx % 3),
                        unidades_bloqueadas=0,
                    )
                )
                session.add(
                    CalendarioTarifas(
                        plan_tarifa_id=rate_plan_id,
                        fecha=seed_day,
                        precio=base_price + Decimal(5 * day_offset),
                    )
                )

            selected_amenities = [
                AMENITY_CATALOG[(idx - 1) % len(AMENITY_CATALOG)][0],
                AMENITY_CATALOG[idx % len(AMENITY_CATALOG)][0],
                AMENITY_CATALOG[(idx + 1) % len(AMENITY_CATALOG)][0],
            ]
            for amenity_name in selected_amenities:
                session.add(
                    PropiedadAmenidad(
                        propiedad_id=property_id,
                        amenidad_id=amenity_id_by_name[amenity_name],
                    )
                )

            session.add(
                Servicio(
                    id=uuid4(),
                    propiedad_id=property_id,
                    nombre="desayuno",
                    descripcion="Servicio de desayuno incluido",
                    estado_activo=True,
                )
            )
            session.add(
                Servicio(
                    id=uuid4(),
                    propiedad_id=property_id,
                    nombre="recepcion_24h",
                    descripcion="Atencion 24 horas",
                    estado_activo=True,
                )
            )

        session.commit()


def _ensure_amenity_catalog(session: Session) -> dict[str, object]:
    amenity_id_by_name: dict[str, object] = {}
    existing_amenities = session.exec(select(Amenidad)).all()
    for amenity in existing_amenities:
        amenity_id_by_name[amenity.nombre] = amenity.id

    for name, category in AMENITY_CATALOG:
        if name in amenity_id_by_name:
            continue

        amenity = Amenidad(id=uuid4(), nombre=name, categoria=category)
        session.add(amenity)
        session.flush()
        amenity_id_by_name[name] = amenity.id

    return amenity_id_by_name
