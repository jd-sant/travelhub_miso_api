import hashlib
import hmac

from core.config import settings


SIGNATURE_ALGO = "HMAC-SHA256"


def canonicalize_pricing_payload(
    property_id: str,
    season_start: str,
    season_end: str,
    price_per_night: float,
    currency: str,
    tax_rate: float,
    cleaning_fee: float,
) -> str:
    """Build deterministic canonical payload for pricing signature.

    Format: property_id|season_start|season_end|price|currency|tax|fee
    Numerics fixed to 2 decimals; currency uppercased; dates as ISO YYYY-MM-DD.
    """
    parts = [
        str(property_id),
        str(season_start),
        str(season_end),
        f"{float(price_per_night):.2f}",
        currency.upper(),
        f"{float(tax_rate):.2f}",
        f"{float(cleaning_fee):.2f}",
    ]
    return "|".join(parts)


def build_pricing_signature(
    canonical_payload: str,
    secret: str,
    algo: str = SIGNATURE_ALGO,
) -> str:
    """Generate hex-encoded HMAC-SHA256 signature for canonical payload."""
    if algo != SIGNATURE_ALGO:
        raise ValueError(f"Unsupported algorithm: {algo}")
    return hmac.new(
        secret.encode(),
        canonical_payload.encode(),
        hashlib.sha256,
    ).hexdigest()


def verify_pricing_signature(
    canonical_payload: str,
    expected_signature: str,
    secret: str,
    algo: str = SIGNATURE_ALGO,
) -> bool:
    """Verify signature with constant-time comparison."""
    computed = build_pricing_signature(canonical_payload, secret, algo)
    return hmac.compare_digest(computed, expected_signature)


def sign_pricing_payload(
    property_id: str,
    season_start: str,
    season_end: str,
    price_per_night: float,
    currency: str,
    tax_rate: float,
    cleaning_fee: float,
) -> str:
    """Convenience wrapper: canonicalize + sign with the configured secret."""
    canonical = canonicalize_pricing_payload(
        property_id=property_id,
        season_start=season_start,
        season_end=season_end,
        price_per_night=price_per_night,
        currency=currency,
        tax_rate=tax_rate,
        cleaning_fee=cleaning_fee,
    )
    return build_pricing_signature(canonical, settings.pricing_integrity_secret)
