import base64
import binascii
import json
import os
from hashlib import sha256
from hmac import new as hmac_new

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag

ENCRYPTED_VALUE_PREFIX = "enc:v1:"
_DEFAULT_RESIDENCY_POLICIES = {
    "CO": "aws-us-east-1",
    "US": "aws-us-east-1",
    "BR": "aws-sa-east-1",
    "MX": "aws-us-east-1",
    "PE": "aws-us-east-1",
    "CL": "aws-sa-east-1",
    "AR": "aws-sa-east-1",
    "ES": "aws-eu-west-1",
    "PT": "aws-eu-west-1",
}


def encrypt_sensitive_value(value: str | None, secret: str) -> str | None:
    if value is None or value.startswith(ENCRYPTED_VALUE_PREFIX):
        return value
    nonce = os.urandom(12)
    ciphertext = AESGCM(_derive_encryption_key(secret)).encrypt(
        nonce,
        value.encode("utf-8"),
        None,
    )
    encoded = base64.urlsafe_b64encode(nonce + ciphertext).decode("utf-8")
    return f"{ENCRYPTED_VALUE_PREFIX}{encoded}"


def decrypt_sensitive_value(value: str | None, secret: str) -> str | None:
    if value is None or not value.startswith(ENCRYPTED_VALUE_PREFIX):
        return value
    encoded = value[len(ENCRYPTED_VALUE_PREFIX) :]
    try:
        raw = base64.urlsafe_b64decode(encoded.encode("utf-8"))
        nonce, ciphertext = raw[:12], raw[12:]
        plaintext = AESGCM(_derive_encryption_key(secret)).decrypt(
            nonce,
            ciphertext,
            None,
        )
        return plaintext.decode("utf-8")
    except (binascii.Error, ValueError, TypeError, InvalidTag):
        return None


def build_lookup_hash(value: str, secret: str) -> str:
    normalized = value.strip().lower()
    return hmac_new(
        secret.encode("utf-8"),
        normalized.encode("utf-8"),
        sha256,
    ).hexdigest()


def is_encrypted_sensitive_value(value: str | None) -> bool:
    return bool(value and value.startswith(ENCRYPTED_VALUE_PREFIX))


def normalize_country_code(value: str | None) -> str:
    normalized = (value or "CO").strip().upper()
    return normalized[:2] if len(normalized) >= 2 else "CO"


def load_residency_policies(raw_value: str | None) -> dict[str, str]:
    if not raw_value:
        return dict(_DEFAULT_RESIDENCY_POLICIES)
    try:
        decoded = json.loads(raw_value)
    except json.JSONDecodeError as exc:
        raise RuntimeError("DATA_RESIDENCY_POLICIES must be valid JSON") from exc
    if not isinstance(decoded, dict):
        raise RuntimeError("DATA_RESIDENCY_POLICIES must be a JSON object")
    return {
        str(country).strip().upper(): str(region).strip()
        for country, region in decoded.items()
        if str(country).strip() and str(region).strip()
    }


def resolve_data_region(
    country_code: str | None,
    *,
    policies: dict[str, str],
    default_region: str,
) -> str:
    normalized = normalize_country_code(country_code)
    return policies.get(normalized, default_region)


def _derive_encryption_key(secret: str) -> bytes:
    return sha256(secret.encode("utf-8")).digest()
