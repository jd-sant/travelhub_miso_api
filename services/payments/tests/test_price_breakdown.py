from datetime import date

from domain.services.price_breakdown import PriceBreakdownCalculator


def test_calculate_con_iva_y_noches():
    calc = PriceBreakdownCalculator({"COP": 0.19})
    breakdown = calc.calculate(
        total_in_cents=119_000,
        currency="COP",
        check_in=date(2026, 5, 10),
        check_out=date(2026, 5, 15),  # 5 noches
    )
    assert breakdown.total_in_cents == 119_000
    assert breakdown.taxes_in_cents == 19_000
    assert breakdown.nights == 5
    assert breakdown.nightly_rate_in_cents == 20_000


def test_calculate_sin_fechas_devuelve_nights_none():
    calc = PriceBreakdownCalculator({"USD": 0.08})
    breakdown = calc.calculate(
        total_in_cents=10_800,
        currency="USD",
        check_in=None,
        check_out=None,
    )
    assert breakdown.nights is None
    assert breakdown.nightly_rate_in_cents is None
    assert breakdown.taxes_in_cents == 800


def test_calculate_currency_desconocida_usa_cero_impuestos():
    calc = PriceBreakdownCalculator({"COP": 0.19})
    breakdown = calc.calculate(
        total_in_cents=50_000,
        currency="JPY",
        check_in=date(2026, 5, 10),
        check_out=date(2026, 5, 12),
    )
    assert breakdown.taxes_in_cents == 0
    assert breakdown.nightly_rate_in_cents == 25_000


def test_calculate_checkout_anterior_a_checkin_ignora_noches():
    calc = PriceBreakdownCalculator({"USD": 0.08})
    breakdown = calc.calculate(
        total_in_cents=10_800,
        currency="USD",
        check_in=date(2026, 5, 15),
        check_out=date(2026, 5, 10),
    )
    assert breakdown.nights is None
    assert breakdown.nightly_rate_in_cents is None
