from datetime import date
from uuid import UUID

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
        existing_property = session.exec(select(Propiedad.id).limit(1)).first()
        if existing_property:
            return

        propiedad_id = UUID("10000000-0000-0000-0000-000000000001")
        tipo_habitacion_id = UUID("20000000-0000-0000-0000-000000000001")
        plan_tarifa_id = UUID("30000000-0000-0000-0000-000000000001")
        amenidad_id = UUID("40000000-0000-0000-0000-000000000001")
        servicio_id = UUID("50000000-0000-0000-0000-000000000001")

        session.add(
            Propiedad(
                id=propiedad_id,
                nombre="Hotel Demo Search",
                ciudad="Bogota",
                pais="Colombia",
                direccion="Calle 123 #45-67",
                descripcion="Propiedad dummy para pruebas API.",
                estado_activo=True,
                capacidad_maxima=4,
                imagen_principal_url="https://cdn.example.com/demo-hotel.jpg",
                rating=4.5,
            )
        )

        session.add(
            TipoHabitacion(
                id=tipo_habitacion_id,
                propiedad_id=propiedad_id,
                nombre="Habitacion Estandar",
                descripcion="Habitacion de prueba",
                capacidad=2,
                estado_activo=True,
            )
        )

        session.add(
            PlanTarifa(
                id=plan_tarifa_id,
                tipo_habitacion_id=tipo_habitacion_id,
                nombre="Tarifa Flexible",
                descripcion="Cancelable hasta 24h antes",
                moneda="USD",
                precio_base=120,
                estado_activo=True,
            )
        )

        session.add(
            CalendarioInventario(
                tipo_habitacion_id=tipo_habitacion_id,
                fecha=date(2026, 4, 10),
                unidades_disponibles=5,
                unidades_bloqueadas=0,
            )
        )
        session.add(
            CalendarioInventario(
                tipo_habitacion_id=tipo_habitacion_id,
                fecha=date(2026, 4, 11),
                unidades_disponibles=5,
                unidades_bloqueadas=0,
            )
        )

        session.add(
            CalendarioTarifas(
                plan_tarifa_id=plan_tarifa_id,
                fecha=date(2026, 4, 10),
                precio=125,
            )
        )
        session.add(
            CalendarioTarifas(
                plan_tarifa_id=plan_tarifa_id,
                fecha=date(2026, 4, 11),
                precio=130,
            )
        )

        session.add(
            Amenidad(
                id=amenidad_id,
                nombre="wifi",
                categoria="conectividad",
            )
        )
        session.add(
            PropiedadAmenidad(
                propiedad_id=propiedad_id,
                amenidad_id=amenidad_id,
            )
        )

        session.add(
            Servicio(
                id=servicio_id,
                propiedad_id=propiedad_id,
                nombre="desayuno",
                descripcion="Servicio de desayuno incluido",
                estado_activo=True,
            )
        )

        session.commit()
