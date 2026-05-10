import hmac
import hashlib
from typing import Any


def canonicalize_pricing_payload(
    property_id: str,
    season_start: str,
    season_end: str,
    price_per_night: float,
    currency: str,
    tax_rate: float,
    cleaning_fee: float,
) -> str:
    """
    Build deterministic canonical payload for pricing signature.
    
    Format: property_id|season_start|season_end|price_per_night|currency|tax_rate|cleaning_fee
    
    All fields normalized:
    - Dates as ISO string (YYYY-MM-DD)
    - Numerics with fixed decimal places
    - Currency uppercase
    """
    price_str = f"{float(price_per_night):.2f}"
    tax_str = f"{float(tax_rate):.2f}"
    fee_str = f"{float(cleaning_fee):.2f}"
    
    parts = [
        str(property_id),
        str(season_start),
        str(season_end),
        price_str,
        currency.upper(),
        tax_str,
        fee_str,
    ]
    
    return "|".join(parts)


def build_pricing_signature(
    canonical_payload: str,
    secret: str,
    algo: str = "HMAC-SHA256"
) -> str:
    """
    Generate HMAC-SHA256 signature for pricing payload.
    
    Returns hex-encoded signature.
    """
    if algo != "HMAC-SHA256":
        raise ValueError(f"Unsupported algorithm: {algo}")
    
    signature = hmac.new(
        secret.encode(),
        canonical_payload.encode(),
        hashlib.sha256
    ).hexdigest()
    
    return signature


def verify_pricing_signature(
    canonical_payload: str,
    expected_signature: str,
    secret: str,
    algo: str = "HMAC-SHA256"
) -> bool:
    """
    Verify pricing signature with constant-time comparison.
    
    Returns True if signature is valid, False otherwise.
    """
    computed_signature = build_pricing_signature(canonical_payload, secret, algo)
    return hmac.compare_digest(computed_signature, expected_signature)
