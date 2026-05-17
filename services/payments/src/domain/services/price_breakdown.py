"""Cálculo puro del desglose de precio para la confirmación de reserva (HU022)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class PriceBreakdown:
    total_in_cents: int
    taxes_in_cents: int
    nights: int | None
    nightly_rate_in_cents: int | None


class PriceBreakdownCalculator:
    """Desagrega un total (IVA incluido) en impuestos, tarifa/noche y número de noches.

    La fórmula asume que el total facturado ya incluye IVA:
        subtotal = total / (1 + tax_rate)
        taxes    = total - subtotal
        nightly  = subtotal / nights
    """

    def __init__(self, tax_rates_by_currency: dict[str, float]):
        self._tax_rates = {k.upper(): v for k, v in tax_rates_by_currency.items()}

    def calculate(
        self,
        *,
        total_in_cents: int,
        currency: str,
        check_in: date | None,
        check_out: date | None,
    ) -> PriceBreakdown:
        nights = self._compute_nights(check_in, check_out)
        taxes = self._compute_taxes(total_in_cents, currency)
        nightly = self._compute_nightly(total_in_cents, taxes, nights)
        return PriceBreakdown(
            total_in_cents=total_in_cents,
            taxes_in_cents=taxes,
            nights=nights,
            nightly_rate_in_cents=nightly,
        )

    @staticmethod
    def _compute_nights(check_in: date | None, check_out: date | None) -> int | None:
        if check_in is None or check_out is None:
            return None
        delta = (check_out - check_in).days
        return delta if delta > 0 else None

    def _compute_taxes(self, total_in_cents: int, currency: str) -> int:
        tax_rate = self._tax_rates.get(currency.upper(), 0.0)
        if tax_rate <= 0:
            return 0
        subtotal = round(total_in_cents / (1 + tax_rate))
        return total_in_cents - subtotal

    @staticmethod
    def _compute_nightly(
        total_in_cents: int, taxes_in_cents: int, nights: int | None
    ) -> int | None:
        if not nights or nights <= 0:
            return None
        return round((total_in_cents - taxes_in_cents) / nights)
