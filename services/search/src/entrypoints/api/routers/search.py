from fastapi import APIRouter, Depends, HTTPException, status
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
from db.session import get_session
from db.session import engine

router = APIRouter(prefix="/search", tags=["search"])


@router.get("/status")
def search_status() -> dict[str, str]:
    return {"service": "search", "status": "ok"}


if settings.is_development:

    @router.get("/test-dataset")
    def list_test_dataset(
        session: Session = Depends(get_session),
    ) -> dict:
        db_url = str(engine.url)
        enabled = db_url.startswith("sqlite") or db_url.startswith("postgresql")
        if not enabled:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Endpoint available only for local development test data",
            )

        propiedades = session.exec(select(Propiedad)).all()
        tipos_habitacion = session.exec(select(TipoHabitacion)).all()
        planes_tarifa = session.exec(select(PlanTarifa)).all()
        inventario = session.exec(select(CalendarioInventario)).all()
        tarifas = session.exec(select(CalendarioTarifas)).all()
        amenidades = session.exec(select(Amenidad)).all()
        servicios = session.exec(select(Servicio)).all()
        propiedad_amenidad = session.exec(select(PropiedadAmenidad)).all()

        return {
            "counts": {
                "propiedades": len(propiedades),
                "tipos_habitacion": len(tipos_habitacion),
                "planes_tarifa": len(planes_tarifa),
                "calendario_inventario": len(inventario),
                "calendario_tarifas": len(tarifas),
                "amenidades": len(amenidades),
                "servicios": len(servicios),
                "propiedad_amenidad": len(propiedad_amenidad),
            },
            "propiedades": [
                {
                    "id": str(p.id),
                    "nombre": p.nombre,
                    "ciudad": p.ciudad,
                    "pais": p.pais,
                    "capacidad_maxima": p.capacidad_maxima,
                    "imagen_principal_url": p.imagen_principal_url,
                    "rating": p.rating,
                }
                for p in propiedades
            ],
        }