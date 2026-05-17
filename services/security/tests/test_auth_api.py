from core.jwt_handler import decode_token


def test_login_valid_credentials_returns_otp_message(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "ana@example.com", "password": "correctPassword"},
    )
    assert response.status_code == 200
    assert response.json()["message"] == "OTP enviado al correo registrado"


def test_login_valid_credentials_sends_otp(client, fake_otp_sender):
    client.post(
        "/api/v1/auth/login",
        json={"email": "ana@example.com", "password": "correctPassword"},
    )
    assert len(fake_otp_sender.sent) == 1
    email, code = fake_otp_sender.sent[0]
    assert email == "ana@example.com"
    assert len(code) == 6
    assert code.isdigit()


def test_login_wrong_password_returns_401(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "ana@example.com", "password": "wrongPassword"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Credenciales inválidas"


def test_login_unknown_email_returns_401(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "unknown@example.com", "password": "correctPassword"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Credenciales inválidas"


def test_login_generic_message_no_user_enumeration(client):
    resp_bad_email = client.post(
        "/api/v1/auth/login",
        json={"email": "noexiste@x.com", "password": "whatever"},
    )
    resp_bad_pass = client.post(
        "/api/v1/auth/login",
        json={"email": "ana@example.com", "password": "wrongPassword"},
    )
    assert resp_bad_email.status_code == resp_bad_pass.status_code == 401
    assert resp_bad_email.json() == resp_bad_pass.json()


def test_verify_otp_correct_code_returns_jwt(client, fake_otp_sender):
    client.post(
        "/api/v1/auth/login",
        json={"email": "ana@example.com", "password": "correctPassword"},
    )
    _, otp_code = fake_otp_sender.sent[0]

    response = client.post(
        "/api/v1/auth/verify-otp",
        json={"email": "ana@example.com", "otp_code": otp_code},
    )
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"
    assert body["role"] == "traveler"

    payload = decode_token(body["access_token"])
    assert payload["email"] == "ana@example.com"
    assert payload["role"] == "traveler"


def test_verify_otp_wrong_code_returns_401(client, fake_otp_sender):
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


def test_verify_otp_three_failures_locks_account(client, fake_otp_sender):
    client.post(
        "/api/v1/auth/login",
        json={"email": "ana@example.com", "password": "correctPassword"},
    )

    for _ in range(3):
        client.post(
            "/api/v1/auth/verify-otp",
            json={"email": "ana@example.com", "otp_code": "000000"},
        )

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "ana@example.com", "password": "correctPassword"},
    )
    assert response.status_code == 423
    assert response.json()["detail"] == "Cuenta bloqueada temporalmente"


def test_verify_otp_no_active_otp_returns_401(client):
    response = client.post(
        "/api/v1/auth/verify-otp",
        json={"email": "ana@example.com", "otp_code": "123456"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "OTP expirado"


def test_ip_blocked_after_10_failed_attempts(client):
    for _ in range(10):
        client.post(
            "/api/v1/auth/login",
            json={"email": "wrong@x.com", "password": "wrong"},
        )

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "ana@example.com", "password": "correctPassword"},
    )
    assert response.status_code == 429
    assert response.json()["detail"] == "IP bloqueada por múltiples intentos fallidos"


def test_validate_token_valid(client, fake_otp_sender):
    client.post(
        "/api/v1/auth/login",
        json={"email": "ana@example.com", "password": "correctPassword"},
    )
    _, otp_code = fake_otp_sender.sent[0]

    otp_resp = client.post(
        "/api/v1/auth/verify-otp",
        json={"email": "ana@example.com", "otp_code": otp_code},
    )
    token = otp_resp.json()["access_token"]

    response = client.post(
        "/api/v1/auth/validate-token",
        json={"token": token},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "ana@example.com"
    assert body["role"] == "traveler"
    assert body["valid"] is True


def test_validate_token_invalid_returns_401(client):
    response = client.post(
        "/api/v1/auth/validate-token",
        json={"token": "invalid.token.here"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Token inválido"
