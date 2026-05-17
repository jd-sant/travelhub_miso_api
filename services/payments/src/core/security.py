import base64
import os
import re
from hashlib import sha256
from hmac import compare_digest, new
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_ENCRYPTED_VALUE_PREFIX = "enc:v1:"
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
    "x_internal_api_key",
}
_PAN_CANDIDATE_RE = re.compile(r"(?:\d[ -]?){13,19}")


def hash_token(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


def build_payment_fingerprint(
    *,
    reservation_id: str,
    traveler_id: str,
    amount_in_cents: int,
    currency: str,
    token_hash: str,
) -> str:
    raw_value = "|".join(
        [
            reservation_id,
            traveler_id,
            str(amount_in_cents),
            currency.upper(),
            token_hash,
        ]
    )
    return sha256(raw_value.encode("utf-8")).hexdigest()


def build_request_checksum(payload: str, secret: str) -> str:
    return new(secret.encode("utf-8"), payload.encode("utf-8"), "sha256").hexdigest()


def build_duplicate_guard_key(
    *,
    request_fingerprint: str,
    bucket: int,
) -> str:
    raw_value = f"{request_fingerprint}|{bucket}"
    return sha256(raw_value.encode("utf-8")).hexdigest()


def verify_checksum(*, payload: str, expected_checksum: str, secret: str) -> bool:
    calculated_checksum = build_request_checksum(payload, secret)
    return compare_digest(calculated_checksum, expected_checksum)


def encrypt_sensitive_value(value: str | None, secret: str) -> str | None:
    if value is None or value.startswith(_ENCRYPTED_VALUE_PREFIX):
        return value
    nonce = os.urandom(12)
    ciphertext = AESGCM(_derive_encryption_key(secret)).encrypt(
        nonce,
        value.encode("utf-8"),
        None,
    )
    token = base64.urlsafe_b64encode(nonce + ciphertext).decode("utf-8")
    return f"{_ENCRYPTED_VALUE_PREFIX}{token}"


def decrypt_sensitive_value(value: str | None, secret: str) -> str | None:
    if value is None or not value.startswith(_ENCRYPTED_VALUE_PREFIX):
        return value
    encoded = value[len(_ENCRYPTED_VALUE_PREFIX) :]
    raw = base64.urlsafe_b64decode(encoded.encode("utf-8"))
    nonce, ciphertext = raw[:12], raw[12:]
    plaintext = AESGCM(_derive_encryption_key(secret)).decrypt(
        nonce,
        ciphertext,
        None,
    )
    return plaintext.decode("utf-8")


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
        return tuple(sanitize_sensitive_data(item) for item in value)
    if isinstance(value, str) and _looks_like_pan(value):
        return "[REDACTED]"
    return value


def _derive_encryption_key(secret: str) -> bytes:
    return sha256(secret.encode("utf-8")).digest()


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
