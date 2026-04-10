from decimal import Decimal

from sqlalchemy import and_, asc, desc, func
from sqlmodel import Session, select

from adapters.models import Amenity
from adapters.models import InventoryCalendar
from adapters.models import Property
from adapters.models import PropertyAmenity
from adapters.models import RateCalendar
from adapters.models import RatePlan
from adapters.models import RoomType
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

        amenities = [a.strip().lower() for a in query.amenities if a.strip()]
        city = query.city.strip().lower()

        available_room_type_subq = (
            select(InventoryCalendar.room_type_id)
            .where(
                and_(
                    InventoryCalendar.fecha >= query.check_in,
                    InventoryCalendar.fecha < query.check_out,
                    InventoryCalendar.unidades_disponibles
                    > InventoryCalendar.unidades_bloqueadas,
                )
            )
            .group_by(InventoryCalendar.room_type_id)
            .having(func.count(func.distinct(InventoryCalendar.fecha)) == nights)
        )

        avg_calendar_price_subq = (
            select(func.avg(RateCalendar.precio))
            .where(
                and_(
                    RateCalendar.rate_plan_id == RatePlan.id,
                    RateCalendar.fecha >= query.check_in,
                    RateCalendar.fecha < query.check_out,
                )
            )
            .correlate(RatePlan)
            .scalar_subquery()
        )

        effective_price_expr = func.coalesce(avg_calendar_price_subq, RatePlan.precio_base)
        min_price_expr = func.min(effective_price_expr)

        base_stmt = (
            select(
                Property.id,
                Property.nombre,
                Property.ciudad,
                Property.pais,
                Property.capacidad_maxima,
                Property.imagen_principal_url,
                Property.rating,
                min_price_expr.label("precio_desde"),
                func.min(RatePlan.moneda).label("moneda"),
            )
            .join(RoomType, RoomType.property_id == Property.id)
            .join(RatePlan, RatePlan.room_type_id == RoomType.id)
            .where(
                and_(
                    func.lower(Property.ciudad) == city,
                    Property.estado_activo.is_(True),
                    RoomType.estado_activo.is_(True),
                    RatePlan.estado_activo.is_(True),
                    RoomType.capacidad >= query.guests,
                    RoomType.id.in_(available_room_type_subq),
                )
            )
        )

        if amenities:
            amenity_match_subq = (
                select(PropertyAmenity.property_id)
                .join(Amenity, Amenity.id == PropertyAmenity.amenity_id)
                .where(func.lower(Amenity.nombre).in_(amenities))
                .group_by(PropertyAmenity.property_id)
                .having(func.count(func.distinct(func.lower(Amenity.nombre))) == len(set(amenities)))
            )
            base_stmt = base_stmt.where(Property.id.in_(amenity_match_subq))

        grouped_stmt = base_stmt.group_by(
            Property.id,
            Property.nombre,
            Property.ciudad,
            Property.pais,
            Property.capacidad_maxima,
            Property.imagen_principal_url,
            Property.rating,
        )

        if query.min_price is not None:
            grouped_stmt = grouped_stmt.having(min_price_expr >= query.min_price)
        if query.max_price is not None:
            grouped_stmt = grouped_stmt.having(min_price_expr <= query.max_price)

        total_stmt = select(func.count()).select_from(grouped_stmt.subquery())
        total = self.session.exec(total_stmt).one()

        sort_map = {
            "price": min_price_expr,
            "rating": func.coalesce(Property.rating, 0),
            "name": Property.nombre,
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
                select(PropertyAmenity.property_id, Amenity.nombre)
                .join(Amenity, Amenity.id == PropertyAmenity.amenity_id)
                .where(PropertyAmenity.property_id.in_(property_ids))
                .order_by(Amenity.nombre)
            ).all()
            for property_id, amenity_name in amenity_rows:
                amenities_by_property.setdefault(property_id, []).append(amenity_name)

        items = [
            PropertySearchItem(
                id=row.id,
                name=row.nombre,
                city=row.ciudad,
                country=row.pais,
                max_capacity=row.capacidad_maxima,
                main_image_url=row.imagen_principal_url,
                rating=row.rating,
                price_from=Decimal(str(row.precio_desde)),
                currency=row.moneda,
                amenities=amenities_by_property.get(row.id, []),
            )
            for row in rows
        ]

        return SearchResult(
            items=items,
            total=total,
            page=query.page,
            page_size=query.page_size,
        )
