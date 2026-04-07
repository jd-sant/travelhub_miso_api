from decimal import Decimal

from sqlalchemy import and_, asc, desc, func
from sqlmodel import Session, select

from adapters.models import Amenidad
from adapters.models import CalendarioInventario
from adapters.models import CalendarioTarifas
from adapters.models import PlanTarifa
from adapters.models import Propiedad
from adapters.models import PropiedadAmenidad
from adapters.models import TipoHabitacion
from domain.ports.search_repository import SearchRepository
from domain.schemas.search import PropertySearchItem, SearchQuery, SearchResult


class SQLModelSearchRepository(SearchRepository):
    def __init__(self, session: Session):
        self.session = session

    def search(self, query: SearchQuery) -> SearchResult:
        nights = (query.check_out - query.check_in).days
        if nights <= 0:
            return SearchResult(
                items=[],
                total=0,
                page=query.page,
                page_size=query.page_size,
            )

        amenidades = [a.strip().lower() for a in query.amenidades if a.strip()]
        ciudad = query.ciudad.strip().lower()

        available_room_type_subq = (
            select(CalendarioInventario.tipo_habitacion_id)
            .where(
                and_(
                    CalendarioInventario.fecha >= query.check_in,
                    CalendarioInventario.fecha < query.check_out,
                    CalendarioInventario.unidades_disponibles
                    > CalendarioInventario.unidades_bloqueadas,
                )
            )
            .group_by(CalendarioInventario.tipo_habitacion_id)
            .having(func.count(func.distinct(CalendarioInventario.fecha)) == nights)
        )

        avg_calendar_price_subq = (
            select(func.avg(CalendarioTarifas.precio))
            .where(
                and_(
                    CalendarioTarifas.plan_tarifa_id == PlanTarifa.id,
                    CalendarioTarifas.fecha >= query.check_in,
                    CalendarioTarifas.fecha < query.check_out,
                )
            )
            .correlate(PlanTarifa)
            .scalar_subquery()
        )

        effective_price_expr = func.coalesce(avg_calendar_price_subq, PlanTarifa.precio_base)
        min_price_expr = func.min(effective_price_expr)

        base_stmt = (
            select(
                Propiedad.id,
                Propiedad.nombre,
                Propiedad.ciudad,
                Propiedad.pais,
                Propiedad.capacidad_maxima,
                Propiedad.imagen_principal_url,
                Propiedad.rating,
                min_price_expr.label("precio_desde"),
                func.min(PlanTarifa.moneda).label("moneda"),
            )
            .join(TipoHabitacion, TipoHabitacion.propiedad_id == Propiedad.id)
            .join(PlanTarifa, PlanTarifa.tipo_habitacion_id == TipoHabitacion.id)
            .where(
                and_(
                    func.lower(Propiedad.ciudad) == ciudad,
                    Propiedad.estado_activo.is_(True),
                    TipoHabitacion.estado_activo.is_(True),
                    PlanTarifa.estado_activo.is_(True),
                    TipoHabitacion.capacidad >= query.huespedes,
                    TipoHabitacion.id.in_(available_room_type_subq),
                )
            )
        )

        if query.precio_min is not None:
            base_stmt = base_stmt.where(effective_price_expr >= query.precio_min)
        if query.precio_max is not None:
            base_stmt = base_stmt.where(effective_price_expr <= query.precio_max)

        if amenidades:
            amenity_match_subq = (
                select(PropiedadAmenidad.propiedad_id)
                .join(Amenidad, Amenidad.id == PropiedadAmenidad.amenidad_id)
                .where(func.lower(Amenidad.nombre).in_(amenidades))
                .group_by(PropiedadAmenidad.propiedad_id)
                .having(func.count(func.distinct(func.lower(Amenidad.nombre))) == len(set(amenidades)))
            )
            base_stmt = base_stmt.where(Propiedad.id.in_(amenity_match_subq))

        grouped_stmt = base_stmt.group_by(
            Propiedad.id,
            Propiedad.nombre,
            Propiedad.ciudad,
            Propiedad.pais,
            Propiedad.capacidad_maxima,
            Propiedad.imagen_principal_url,
            Propiedad.rating,
        )

        total_stmt = select(func.count()).select_from(grouped_stmt.subquery())
        total = self.session.exec(total_stmt).one()

        sort_map = {
            "price": min_price_expr,
            "rating": func.coalesce(Propiedad.rating, 0),
            "name": Propiedad.nombre,
        }
        sort_expr = sort_map.get(query.order_by.lower(), min_price_expr)
        sort_fn = desc if query.order_dir.lower() == "desc" else asc

        paged_stmt = (
            grouped_stmt.order_by(sort_fn(sort_expr))
            .offset((query.page - 1) * query.page_size)
            .limit(query.page_size)
        )

        rows = self.session.exec(paged_stmt).all()
        property_ids = [row.id for row in rows]

        amenities_by_property: dict = {}
        if property_ids:
            amenity_rows = self.session.exec(
                select(PropiedadAmenidad.propiedad_id, Amenidad.nombre)
                .join(Amenidad, Amenidad.id == PropiedadAmenidad.amenidad_id)
                .where(PropiedadAmenidad.propiedad_id.in_(property_ids))
                .order_by(Amenidad.nombre)
            ).all()
            for property_id, amenity_name in amenity_rows:
                amenities_by_property.setdefault(property_id, []).append(amenity_name)

        items = [
            PropertySearchItem(
                id=row.id,
                nombre=row.nombre,
                ciudad=row.ciudad,
                pais=row.pais,
                capacidad_maxima=row.capacidad_maxima,
                imagen_principal_url=row.imagen_principal_url,
                rating=row.rating,
                precio_desde=Decimal(str(row.precio_desde)),
                moneda=row.moneda,
                amenidades=amenities_by_property.get(row.id, []),
            )
            for row in rows
        ]

        return SearchResult(
            items=items,
            total=total,
            page=query.page,
            page_size=query.page_size,
        )
