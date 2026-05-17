import hashlib
import hmac
import secrets

from core.config import settings


def generate_otp(length: int = 6) -> str:
    max_val = 10**length
    return str(secrets.randbelow(max_val)).zfill(length)


def hash_otp(code: str) -> str:
    return hmac.new(
        settings.jwt_secret_key.encode(),
        code.encode(),
        hashlib.sha256,
    ).hexdigest()
