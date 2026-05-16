import base64
import json
import os
from hashlib import sha256

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from domain.schemas.reservation import CheckInQrPayload

_CHECKIN_QR_PREFIX = "thci1"
_IV_SIZE_BYTES = 12


def encode_checkin_qr_payload(payload: CheckInQrPayload, secret: str) -> str:
    nonce = os.urandom(_IV_SIZE_BYTES)
    cipher = AESGCM(_derive_key(secret))
    plaintext = json.dumps(
        payload.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    ciphertext = cipher.encrypt(nonce, plaintext, None)
    encoded = base64.urlsafe_b64encode(nonce + ciphertext).decode("utf-8")
    return f"{_CHECKIN_QR_PREFIX}.{encoded}"


def decode_checkin_qr_payload_for_test(encoded: str, secret: str) -> CheckInQrPayload:
    prefix_removed = encoded.removeprefix(f"{_CHECKIN_QR_PREFIX}.")
    raw = base64.urlsafe_b64decode(prefix_removed.encode("utf-8"))
    nonce, ciphertext = raw[:_IV_SIZE_BYTES], raw[_IV_SIZE_BYTES:]
    plaintext = AESGCM(_derive_key(secret)).decrypt(nonce, ciphertext, None)
    return CheckInQrPayload.model_validate_json(plaintext.decode("utf-8"))


def build_checkin_qr_fingerprint(
    *,
    status: str,
    check_in_date,
    check_out_date,
    number_of_guests: int,
) -> str:
    canonical = "|".join(
        [
            status,
            check_in_date.date().isoformat() if hasattr(check_in_date, "date") else str(check_in_date),
            check_out_date.date().isoformat() if hasattr(check_out_date, "date") else str(check_out_date),
            str(number_of_guests),
        ]
    )
    return sha256(canonical.encode("utf-8")).hexdigest()


def _derive_key(secret: str) -> bytes:
    return sha256(secret.encode("utf-8")).digest()
