import base64
import json
import os
from hashlib import sha256
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_ENCRYPTED_VALUE_PREFIX = "enc:v1:"
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
    if value is None or value.startswith(_ENCRYPTED_VALUE_PREFIX):
        return value
    nonce = os.urandom(12)
    ciphertext = AESGCM(_derive_encryption_key(secret)).encrypt(
        nonce,
        value.encode("utf-8"),
        None,
    )
    encoded = base64.urlsafe_b64encode(nonce + ciphertext).decode("utf-8")
    return f"{_ENCRYPTED_VALUE_PREFIX}{encoded}"


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


def build_entry_hash(
    *,
    previous_hash: str | None,
    actor_user_id: str | None,
    action: str,
    resource_type: str,
    resource_id: str | None,
    pii_fields: list[str],
    source_ip: str,
    country_code: str | None,
    data_region: str,
    metadata: dict[str, Any],
    created_at_iso: str,
) -> str:
    canonical_payload = {
        "action": action,
        "actor_user_id": actor_user_id,
        "country_code": country_code,
        "created_at": created_at_iso,
        "data_region": data_region,
        "metadata": metadata,
        "pii_fields": sorted({field.strip().lower() for field in pii_fields if field.strip()}),
        "previous_hash": previous_hash,
        "resource_id": resource_id,
        "resource_type": resource_type,
        "source_ip": source_ip,
    }
    serialized = json.dumps(canonical_payload, sort_keys=True, separators=(",", ":"))
    return sha256(serialized.encode("utf-8")).hexdigest()


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
    normalized = (country_code or "").strip().upper()
    if not normalized:
        return default_region
    return policies.get(normalized, default_region)


def _derive_encryption_key(secret: str) -> bytes:
    return sha256(secret.encode("utf-8")).digest()
