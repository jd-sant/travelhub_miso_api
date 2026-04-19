from typing import Any

_SENSITIVE_KEYS = {
    "authorization",
    "payment_method_token",
    "x_internal_api_key",
    "x-internal-api-key",
    "token",
    "secret",
}


def sanitize_sensitive_data(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if _is_sensitive_key(key) else sanitize_sensitive_data(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [sanitize_sensitive_data(item) for item in value]
    if isinstance(value, tuple):
        return tuple(sanitize_sensitive_data(item) for item in value)
    return value


def _is_sensitive_key(key: str) -> bool:
    return key.strip().lower().replace("-", "_") in _SENSITIVE_KEYS
