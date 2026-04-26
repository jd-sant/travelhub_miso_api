from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape


_TEMPLATES_DIR = (
    Path(__file__).resolve().parents[1] / "src" / "adapters" / "templates"
)
_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES_DIR)),
    autoescape=select_autoescape(["html"]),
)


def test_cancellation_template_uses_card_layout_and_refund_block_in_spanish():
    html = _env.get_template("reservation_update.html").render(
        recipient_name="Sarah Mitchell",
        reservation_id="RES-9421",
        status="cancelada",
        reason="overbooking",
        description="Se presentó una indisponibilidad operativa de última hora.",
        refund_requested=True,
        refund_amount="4284.00",
        language_tag="es",
        is_cancelled=True,
        translations={
            "greeting": "Hola",
            "title_cancelled": "Reserva cancelada por el hotel",
            "title_confirmed": "Reserva confirmada",
            "subtitle_cancelled": "Te compartimos el detalle de esta actualización sobre tu reserva.",
            "subtitle_confirmed": "Tu reserva fue actualizada correctamente.",
            "reservation_details": "Detalle de la reserva",
            "reservation_label": "Reserva",
            "status_label": "Estado",
            "reason_label": "Motivo",
            "description_label": "Descripción",
            "refund_title": "Proceso de reembolso",
            "refund_description": "El sistema inició automáticamente el reembolso según la política de cancelación vigente.",
            "refund_amount_label": "Monto estimado",
            "help_text": "Si necesitas ayuda adicional, revisa tu panel de reservas o contacta al hotel.",
            "footer": "Gracias por usar TravelHub.",
        },
    )

    assert "Reserva cancelada por el hotel" in html
    assert "Hola Sarah Mitchell" in html
    assert "Reserva RES-9421" in html
    assert "Motivo" in html
    assert "overbooking" in html
    assert "Descripción" in html
    assert "Proceso de reembolso" in html
    assert "Monto estimado:" in html
    assert "4284.00" in html
    assert "#dc2626" in html


def test_confirmation_template_keeps_same_visual_language_without_refund():
    html = _env.get_template("reservation_update.html").render(
        recipient_name="John Doe",
        reservation_id="RES-1111",
        status="confirmed",
        reason=None,
        description=None,
        refund_requested=False,
        refund_amount=None,
        language_tag="en",
        is_cancelled=False,
        translations={
            "greeting": "Hello",
            "title_cancelled": "Reservation cancelled by the hotel",
            "title_confirmed": "Reservation confirmed",
            "subtitle_cancelled": "Here are the details of this reservation update.",
            "subtitle_confirmed": "Your reservation was updated successfully.",
            "reservation_details": "Reservation details",
            "reservation_label": "Reservation",
            "status_label": "Status",
            "reason_label": "Reason",
            "description_label": "Description",
            "refund_title": "Refund process",
            "refund_description": "The system automatically started the refund according to the active cancellation policy.",
            "refund_amount_label": "Estimated amount",
            "help_text": "If you need additional help, review your reservations panel or contact the hotel.",
            "footer": "Thanks for using TravelHub.",
        },
    )

    assert "Reservation confirmed" in html
    assert "Hello John Doe" in html
    assert "Refund process" not in html
    assert "#135bec" in html
