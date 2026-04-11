from hashlib import sha256
from hmac import compare_digest, new


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
