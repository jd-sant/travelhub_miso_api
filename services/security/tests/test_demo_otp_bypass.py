import os
from uuid import UUID

import pytest

from core.config import settings


DEMO_HOTEL_EMAIL = "hotel-a@travelhub.demo"
DEMO_HOTEL_USER_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


@pytest.fixture
def demo_seed_enabled(monkeypatch):
    monkeypatch.setenv("DEMO_SEED_ENABLED", "true")
    yield


@pytest.fixture
def fake_auth_repo_with_hotel(fake_auth_repo):
    fake_auth_repo.add_user(
        email=DEMO_HOTEL_EMAIL,
        user_id=DEMO_HOTEL_USER_ID,
        status=1,
        roles=["hotel"],
    )
    return fake_auth_repo


@pytest.fixture
def hotel_client(client, fake_auth_repo_with_hotel):
    return client


def test_demo_otp_bypass_returns_jwt_with_hotel_role(
    hotel_client, demo_seed_enabled, fake_otp_sender
):
    hotel_client.post(
        "/api/v1/auth/login",
        json={"email": DEMO_HOTEL_EMAIL, "password": "correctPassword"},
    )

    response = hotel_client.post(
        "/api/v1/auth/verify-otp",
        json={"email": DEMO_HOTEL_EMAIL, "otp_code": "000000"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["role"] == "hotel"
    assert body["access_token"]


def test_demo_otp_bypass_only_works_for_demo_emails(
    client, demo_seed_enabled, fake_otp_sender
):
    client.post(
        "/api/v1/auth/login",
        json={"email": "ana@example.com", "password": "correctPassword"},
    )

    response = client.post(
        "/api/v1/auth/verify-otp",
        json={"email": "ana@example.com", "otp_code": "000000"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Código OTP inválido"


def test_demo_otp_bypass_disabled_when_flag_off(
    hotel_client, monkeypatch, fake_otp_sender
):
    monkeypatch.setenv("DEMO_SEED_ENABLED", "false")
    monkeypatch.setenv("ENV", "production")

    hotel_client.post(
        "/api/v1/auth/login",
        json={"email": DEMO_HOTEL_EMAIL, "password": "correctPassword"},
    )

    response = hotel_client.post(
        "/api/v1/auth/verify-otp",
        json={"email": DEMO_HOTEL_EMAIL, "otp_code": "000000"},
    )

    assert response.status_code == 401


def test_demo_otp_bypass_requires_active_otp(
    hotel_client, demo_seed_enabled
):
    response = hotel_client.post(
        "/api/v1/auth/verify-otp",
        json={"email": DEMO_HOTEL_EMAIL, "otp_code": "000000"},
    )
    assert response.status_code == 401
