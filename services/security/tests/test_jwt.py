import os
import time
from uuid import uuid4

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-jwt")

from core.jwt_handler import create_token, decode_token
from errors import TokenExpiredError, InvalidTokenError


def test_create_token_returns_string():
    token = create_token(user_id=uuid4(), email="a@b.com", role="traveler")
    assert isinstance(token, str)
    assert len(token) > 0


def test_decode_token_returns_correct_claims():
    uid = uuid4()
    token = create_token(user_id=uid, email="a@b.com", role="traveler")
    payload = decode_token(token)

    assert payload["sub"] == str(uid)
    assert payload["email"] == "a@b.com"
    assert payload["role"] == "traveler"
    assert "exp" in payload
    assert "iat" in payload
    assert "jti" in payload


def test_decode_expired_token_raises_error():
    os.environ["JWT_EXPIRATION_MINUTES"] = "0"
    # Force re-import to pick up new config
    from core import config
    config.get_settings.cache_clear()

    uid = uuid4()
    token = create_token(user_id=uid, email="a@b.com", role="traveler")
    time.sleep(1)

    with pytest.raises(TokenExpiredError):
        decode_token(token)

    # Restore
    os.environ["JWT_EXPIRATION_MINUTES"] = "30"
    config.get_settings.cache_clear()


def test_decode_tampered_token_raises_error():
    token = create_token(user_id=uuid4(), email="a@b.com", role="traveler")
    tampered = token[:-5] + "XXXXX"

    with pytest.raises(InvalidTokenError):
        decode_token(tampered)


def test_decode_garbage_raises_error():
    with pytest.raises(InvalidTokenError):
        decode_token("not.a.real.token")
