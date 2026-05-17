from helpers import INTERNAL_API_KEY, seed_user_with_role


def test_verify_credentials_returns_user_with_roles(client, session):
    seed_user_with_role(session)
    response = client.post(
        "/api/v1/internal/verify-credentials",
        json={"email": "ana@example.com", "password": "securePassword1"},
        headers={"X-Internal-Api-Key": INTERNAL_API_KEY},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "ana@example.com"
    assert "id" in body
    assert body["status"] == 1
    assert "traveler" in body["roles"]
    assert "password" not in body


def test_verify_credentials_wrong_password_returns_401(client, session):
    seed_user_with_role(session)
    response = client.post(
        "/api/v1/internal/verify-credentials",
        json={"email": "ana@example.com", "password": "wrongPassword1"},
        headers={"X-Internal-Api-Key": INTERNAL_API_KEY},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Credenciales inválidas"


def test_verify_credentials_unknown_email_returns_401(client):
    response = client.post(
        "/api/v1/internal/verify-credentials",
        json={"email": "noexiste@example.com", "password": "securePassword1"},
        headers={"X-Internal-Api-Key": INTERNAL_API_KEY},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Credenciales inválidas"


def test_verify_credentials_no_api_key_returns_403(client, session):
    seed_user_with_role(session)
    response = client.post(
        "/api/v1/internal/verify-credentials",
        json={"email": "ana@example.com", "password": "securePassword1"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Forbidden"


def test_verify_credentials_wrong_api_key_returns_403(client, session):
    seed_user_with_role(session)
    response = client.post(
        "/api/v1/internal/verify-credentials",
        json={"email": "ana@example.com", "password": "securePassword1"},
        headers={"X-Internal-Api-Key": "wrong-key"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Forbidden"


def test_verify_credentials_generic_message_no_user_enumeration(client, session):
    seed_user_with_role(session)
    resp_wrong_email = client.post(
        "/api/v1/internal/verify-credentials",
        json={"email": "noexiste@example.com", "password": "whatever123"},
        headers={"X-Internal-Api-Key": INTERNAL_API_KEY},
    )
    resp_wrong_pass = client.post(
        "/api/v1/internal/verify-credentials",
        json={"email": "ana@example.com", "password": "wrongPassword1"},
        headers={"X-Internal-Api-Key": INTERNAL_API_KEY},
    )
    assert resp_wrong_email.status_code == resp_wrong_pass.status_code == 401
    assert resp_wrong_email.json() == resp_wrong_pass.json()
