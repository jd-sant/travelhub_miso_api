from datetime import date

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
