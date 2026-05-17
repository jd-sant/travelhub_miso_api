"""Tests del template payment_confirmation.html con desglose canónico (4 líneas)."""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape


_TEMPLATES_DIR = (
    Path(__file__).resolve().parents[1] / "src" / "adapters" / "templates"
)
_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES_DIR)),
    autoescape=select_autoescape(["html"]),
)


def _base_context() -> dict:
    return {
        "recipient_name": "Viajero Demo",
        "reservation_id": "abc-123",
        "receipt_number": "RC-001",
        "property_name": "Hotel Demo",
        "property_address": "Bogotá",
        "check_in_date": "2026-05-01",
        "check_out_date": "2026-05-03",
        "guests_count": 2,
        "nights": 2,
        "currency": "USD",
        "total": "1005.40",
        "cancellation_policy": "Cancelación gratuita 48h antes.",
    }


def test_template_renderiza_las_cuatro_lineas_del_breakdown_canonico():
    context = {
        **_base_context(),
        "accommodation": "800.00",
        "cleaning_fee": "50.00",
        "service_fee": "64.00",
        "taxes": "91.40",
    }
    html = _env.get_template("payment_confirmation.html").render(**context)

    assert "Alojamiento" in html
    assert "(2 noches)" in html
    assert "800.00 USD" in html
    assert "Tarifa de limpieza" in html
    assert "50.00 USD" in html
    assert "Cargo de servicio TravelHub" in html
    assert "64.00 USD" in html
    assert "Impuestos" in html
    assert "91.40 USD" in html
    assert "Total pagado" in html
    assert "1005.40 USD" in html
    # No debe usar el path legacy si ya viene accommodation
    assert "Tarifa por noche" not in html


def test_template_cae_en_legacy_nightly_rate_si_falta_accommodation():
    context = {
        **_base_context(),
        "nightly_rate": "100.00",
        "taxes": "91.40",
    }
    html = _env.get_template("payment_confirmation.html").render(**context)

    assert "Tarifa por noche" in html
    assert "100.00 USD" in html
    assert "Alojamiento" not in html
    assert "Tarifa de limpieza" not in html
    assert "Cargo de servicio TravelHub" not in html


def test_template_omite_lineas_opcionales_cuando_son_cero_o_ausentes():
    context = {
        **_base_context(),
        "accommodation": "800.00",
        # Sin cleaning_fee ni service_fee → no deben aparecer
        "taxes": "91.40",
    }
    html = _env.get_template("payment_confirmation.html").render(**context)

    assert "Alojamiento" in html
    assert "Tarifa de limpieza" not in html
    assert "Cargo de servicio TravelHub" not in html
    assert "Impuestos" in html
