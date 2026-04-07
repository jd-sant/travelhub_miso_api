from datetime import date

from domain.schemas import SearchQuery


class TestSearchUseCase:
    def test_execute_returns_results(self, search_use_case):
        result = search_use_case.execute(
            SearchQuery(
                ciudad="Bogota",
                check_in=date(2026, 4, 10),
                check_out=date(2026, 4, 12),
                huespedes=2,
                page=1,
                page_size=10,
            )
        )

        assert result.total >= 1
        assert len(result.items) >= 1

    def test_execute_returns_empty_when_no_results(self, search_use_case):
        result = search_use_case.execute(
            SearchQuery(
                ciudad="CiudadInexistente",
                check_in=date(2026, 4, 10),
                check_out=date(2026, 4, 12),
                huespedes=2,
                page=1,
                page_size=10,
            )
        )

        assert result.total == 0
        assert result.items == []
