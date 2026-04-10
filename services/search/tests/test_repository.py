from datetime import date
from decimal import Decimal
from uuid import uuid4

from adapters.models import Property
from adapters.models import InventoryCalendar
from adapters.models import RateCalendar
from adapters.models import RatePlan
from adapters.models import RoomType
from domain.schemas import SearchQuery


class TestSearchRepository:
    def test_search_success_with_pagination(self, search_repository):
        page_1 = search_repository.search(
            SearchQuery(
                city="Bogota",
                check_in=date(2026, 4, 10),
                check_out=date(2026, 4, 12),
                guests=2,
                page=1,
                page_size=5,
            )
        )
        page_2 = search_repository.search(
            SearchQuery(
                city="Bogota",
                check_in=date(2026, 4, 10),
                check_out=date(2026, 4, 12),
                guests=2,
                page=2,
                page_size=5,
            )
        )

        assert page_1.total >= len(page_1.items)
        assert len(page_1.items) <= 5
        assert page_1.page == 1
        assert page_2.page == 2
        assert page_1.total == page_2.total

    def test_search_filters_by_amenities(self, search_repository):
        result = search_repository.search(
            SearchQuery(
                city="Bogota",
                check_in=date(2026, 4, 10),
                check_out=date(2026, 4, 12),
                guests=2,
                amenities=["wifi", "piscina"],
                page=1,
                page_size=10,
            )
        )

        assert result.total >= 1
        for item in result.items:
            assert "wifi" in item.amenities
            assert "piscina" in item.amenities

    def test_search_filters_by_price(self, search_repository):
        result = search_repository.search(
            SearchQuery(
                city="Bogota",
                check_in=date(2026, 4, 10),
                check_out=date(2026, 4, 12),
                guests=2,
                min_price=90,
                max_price=200,
                page=1,
                page_size=20,
            )
        )

        for item in result.items:
            assert item.price_from >= 90
            assert item.price_from <= 200

    def test_search_returns_empty_for_unknown_city(self, search_repository):
        result = search_repository.search(
            SearchQuery(
                city="CiudadInexistente",
                check_in=date(2026, 4, 10),
                check_out=date(2026, 4, 12),
                guests=2,
                page=1,
                page_size=10,
            )
        )

        assert result.total == 0
        assert result.items == []

    def test_search_returns_empty_for_invalid_date_range(self, search_repository):
        result = search_repository.search(
            SearchQuery(
                city="Bogota",
                check_in=date(2026, 4, 12),
                check_out=date(2026, 4, 12),
                guests=2,
                page=1,
                page_size=10,
            )
        )

        assert result.total == 0
        assert result.items == []

    def test_search_price_filter_uses_aggregated_min_price(self, db_session, search_repository):
        property_id = uuid4()
        room_type_id = uuid4()
        cheap_rate_plan_id = uuid4()
        expensive_rate_plan_id = uuid4()

        db_session.add(
            Property(
                id=property_id,
                nombre="Hotel Precio Agregado",
                ciudad="Bogota",
                pais="Colombia",
                descripcion="Regresion para filtro por precio agregado",
                estado_activo=True,
                capacidad_maxima=2,
                imagen_principal_url="https://cdn.example.com/aggregate-price.jpg",
                rating=4.5,
            )
        )
        db_session.add(
            RoomType(
                id=room_type_id,
                property_id=property_id,
                nombre="Habitacion Agregada",
                capacidad=2,
                estado_activo=True,
            )
        )
        for day in (date(2026, 4, 10), date(2026, 4, 11)):
            db_session.add(
                InventoryCalendar(
                    room_type_id=room_type_id,
                    fecha=day,
                    unidades_disponibles=3,
                    unidades_bloqueadas=0,
                )
            )
        db_session.add(
            RatePlan(
                id=cheap_rate_plan_id,
                room_type_id=room_type_id,
                nombre="Tarifa Basica",
                moneda="USD",
                precio_base=Decimal("50.00"),
                estado_activo=True,
            )
        )
        db_session.add(
            RatePlan(
                id=expensive_rate_plan_id,
                room_type_id=room_type_id,
                nombre="Tarifa Premium",
                moneda="USD",
                precio_base=Decimal("150.00"),
                estado_activo=True,
            )
        )
        for rate_plan_id in (cheap_rate_plan_id, expensive_rate_plan_id):
            db_session.add(
                RateCalendar(
                    rate_plan_id=rate_plan_id,
                    fecha=date(2026, 4, 10),
                    precio=Decimal("50.00") if rate_plan_id == cheap_rate_plan_id else Decimal("150.00"),
                )
            )
            db_session.add(
                RateCalendar(
                    rate_plan_id=rate_plan_id,
                    fecha=date(2026, 4, 11),
                    precio=Decimal("50.00") if rate_plan_id == cheap_rate_plan_id else Decimal("150.00"),
                )
            )

        db_session.commit()

        result = search_repository.search(
            SearchQuery(
                city="Bogota",
                check_in=date(2026, 4, 10),
                check_out=date(2026, 4, 12),
                guests=2,
                min_price=100,
                page=1,
                page_size=10,
            )
        )

        assert all(item.id != property_id for item in result.items)
