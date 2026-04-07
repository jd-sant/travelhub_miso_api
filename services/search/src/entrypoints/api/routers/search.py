from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, select

from assembly import get_search_properties_use_case
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
from domain.schemas import EmptyStateSuggestion
from domain.schemas import SearchPagination
from domain.schemas import SearchQuery
from domain.schemas import SearchResponse
from domain.use_cases import SearchPropertiesUseCase
from errors import InvalidSearchRuleError

router = APIRouter(prefix="/search", tags=["search"])


@router.get("/status")
def search_status() -> dict[str, str]:
    return {"service": "search", "status": "ok"}


@router.get(
    "",
    response_model=SearchResponse,
    responses={
        400: {"description": "Invalid search business rules"},
        422: {"description": "Invalid or missing request fields"},
    },
)
def search_properties(
    ciudad: str = Query(min_length=2, max_length=120),
    check_in: date = Query(),
    check_out: date = Query(),
    huespedes: int = Query(ge=1),
    amenidades: list[str] = Query(default=[]),
    precio_min: Decimal | None = Query(default=None, ge=0),
    precio_max: Decimal | None = Query(default=None, ge=0),
    order_by: str = Query(default="price"),
    order_dir: str = Query(default="asc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    session: Session = Depends(get_session),
) -> SearchResponse:
    use_case: SearchPropertiesUseCase = get_search_properties_use_case(session)

    try:
        query = SearchQuery(
            ciudad=ciudad,
            check_in=check_in,
            check_out=check_out,
            huespedes=huespedes,
            amenidades=amenidades,
            precio_min=precio_min,
            precio_max=precio_max,
            order_by=order_by,
            order_dir=order_dir,
            page=page,
            page_size=page_size,
        )
        _validate_search_rules(query)
        result = use_case.execute(query)
        total_pages = _calculate_total_pages(result.total, result.page_size)

        empty_state = []
        if result.total == 0:
            empty_state = [
                EmptyStateSuggestion(
                    code="TRY_OTHER_CITY",
                    message="No encontramos resultados en esa ciudad. Intenta otra ciudad cercana.",
                ),
                EmptyStateSuggestion(
                    code="TRY_OTHER_DATES",
                    message="Prueba con fechas diferentes para encontrar mayor disponibilidad.",
                ),
            ]

        return SearchResponse(
            items=result.items,
            pagination=SearchPagination(
                total=result.total,
                page=result.page,
                page_size=result.page_size,
                total_pages=total_pages,
            ),
            empty_state=empty_state,
        )
    except InvalidSearchRuleError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


def _validate_search_rules(query: SearchQuery) -> None:
    if query.check_out <= query.check_in:
        raise InvalidSearchRuleError(
            "check_out must be greater than check_in"
        )

    if (
        query.precio_min is not None
        and query.precio_max is not None
        and query.precio_min > query.precio_max
    ):
        raise InvalidSearchRuleError(
            "precio_min cannot be greater than precio_max"
        )

    valid_order_fields = {"price", "rating", "name"}
    if query.order_by.lower() not in valid_order_fields:
        raise InvalidSearchRuleError(
            "order_by must be one of: price, rating, name"
        )

    valid_order_direction = {"asc", "desc"}
    if query.order_dir.lower() not in valid_order_direction:
        raise InvalidSearchRuleError(
            "order_dir must be asc or desc"
        )


def _calculate_total_pages(total: int, page_size: int) -> int:
    if total == 0:
        return 0
    return (total + page_size - 1) // page_size


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