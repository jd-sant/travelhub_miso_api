import re
from typing import Any

_PAN_CANDIDATE_RE = re.compile(r"(?:\d[ -]?){13,19}")
_SENSITIVE_KEYS = {
    "authorization",
    "body",
    "card",
    "card_number",
    "client_secret",
    "confirmation_token",
    "confirmation_token_id",
    "cvv",
    "expiration",
    "expiration_date",
    "pan",
    "payment_method_data",
    "payment_method_token",
    "secret",
    "stripe_secret_key",
    "token",
    "x-internal-api-key",
}


def sanitize_sensitive_data(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: (
                "[REDACTED]"
                if _is_sensitive_key(key)
                else sanitize_sensitive_data(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [sanitize_sensitive_data(item) for item in value]
    if isinstance(value, tuple):
        return [sanitize_sensitive_data(item) for item in value]
    if isinstance(value, str) and _looks_like_pan(value):
        return "[REDACTED]"
    return value


def mask_email(value: str) -> str:
    if "@" not in value:
        return "***"
    local_part, domain = value.split("@", 1)
    if len(local_part) <= 2:
        masked_local = "*" * len(local_part)
    else:
        masked_local = f"{local_part[0]}***{local_part[-1]}"
    return f"{masked_local}@{domain}"


def _is_sensitive_key(key: str) -> bool:
    normalized = key.strip().lower().replace("-", "_")
    return normalized in _SENSITIVE_KEYS


def _looks_like_pan(value: str) -> bool:
    candidate = re.sub(r"\D", "", value)
    if len(candidate) < 13 or len(candidate) > 19:
        return False
    if not _PAN_CANDIDATE_RE.fullmatch(value.strip()):
        return False
    return _passes_luhn(candidate)


def _passes_luhn(value: str) -> bool:
    checksum = 0
    parity = len(value) % 2
    for index, digit in enumerate(value):
        number = int(digit)
        if index % 2 == parity:
            number *= 2
            if number > 9:
                number -= 9
        checksum += number
    return checksum % 10 == 0
