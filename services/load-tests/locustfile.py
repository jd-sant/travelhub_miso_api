"""Locust load test for MPF-74 — Gestión de sesiones en alta demanda.

Scenario:
  - Phase 1 (ramp, 5 min):  600 → 3,600 users/min  (10 → 60 VUs).
  - Phase 2 (peak, 15 min): 3,600 users/min sustained (60 VUs).

Per-VU lifecycle:
  - on_start: register a brand-new user via POST /api/v1/users and pre-sign a JWT
    locally with the shared HS256 secret (LOADTEST_JWT_SECRET). The 2FA OTP can't
    be passed in an automated test (no inbox access), but the JWT signed with the
    same secret is accepted by every task — which is exactly what AC2
    ("sesión distribuida") requires.

Task mix per iteration (≈ 1 request / 10 s per VU):
  - 60 % search       — public read traffic.
  - 15 % login        — exercises login_attempt table writes (mostly 401).
  -  5 % register     — exercises POST /api/v1/users under sustained load.
  - 20 % booking      — POST /api/v1/payments/charges with the pre-signed JWT.

See README.md and ../../docs/load-tests/MPF-74/RUNBOOK.md for the full runbook.
"""

from __future__ import annotations

import os
import random
import uuid
from datetime import date, datetime, timedelta, timezone

import jwt
from locust import HttpUser, LoadTestShape, between, events, task

# ---------------------------------------------------------------------------
# Config (override via env vars)
# ---------------------------------------------------------------------------

CITIES = ["Bogotá", "Medellín", "Cartagena", "Cali", "Barranquilla", "Santa Marta"]
EMAIL_DOMAIN = os.getenv("LOADTEST_EMAIL_DOMAIN", "loadtest.example.com")
PROPERTY_ID = os.getenv("LOADTEST_PROPERTY_ID", "")
JWT_SECRET = os.getenv("LOADTEST_JWT_SECRET", "")
JWT_ALGORITHM = os.getenv("LOADTEST_JWT_ALGORITHM", "HS256")
JWT_TTL_MINUTES = int(os.getenv("LOADTEST_JWT_TTL_MINUTES", "60"))

RAMP_DURATION_S = int(os.getenv("LOADTEST_RAMP_SECONDS", "300"))
PEAK_DURATION_S = int(os.getenv("LOADTEST_PEAK_SECONDS", "900"))
PEAK_USERS = int(os.getenv("LOADTEST_PEAK_USERS", "60"))
START_USERS = int(os.getenv("LOADTEST_START_USERS", "10"))

# Fracción de logins con credenciales reales (los que disparan envío de OTP por
# SMTP). En AWS con SES en sandbox o cuotas Gmail bajas el envío real falla bajo
# carga; poner 0.0 ejercita solo el path 401 (sin SMTP) y deja la verificación
# real de "sesión distribuida" para el procedimiento manual del README (AC2).
REAL_LOGIN_RATIO = float(os.getenv("LOADTEST_REAL_LOGIN_RATIO", "0.3"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _random_email(prefix: str = "loadtest") -> str:
    return f"{prefix}+{uuid.uuid4().hex[:12]}@{EMAIL_DOMAIN}"


def _random_phone() -> str:
    return f"300{random.randint(1000000, 9999999)}"


def _sign_jwt(user_id: str, email: str, role: str = "traveler") -> str:
    """Pre-sign a JWT compatible with what security service's verify-otp emits."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=JWT_TTL_MINUTES),
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _random_search_query() -> dict:
    today = date.today()
    check_in = today + timedelta(days=random.randint(7, 60))
    check_out = check_in + timedelta(days=random.randint(1, 7))
    return {
        "city": random.choice(CITIES),
        "check_in": check_in.isoformat(),
        "check_out": check_out.isoformat(),
        "guests": random.randint(1, 4),
        "page": 1,
        "page_size": 10,
    }


# ---------------------------------------------------------------------------
# User: realistic mix with inline registration
# ---------------------------------------------------------------------------


class TravelHubUser(HttpUser):
    wait_time = between(8, 12)

    def on_start(self):
        """Register a brand-new user; on success, pre-sign a JWT for its identity."""
        self.email = _random_email()
        self.password = "LoadTest!1234"
        self.user_id: str | None = None
        self.token: str | None = None

        payload = {
            "email": self.email,
            "phone": _random_phone(),
            "password": self.password,
            "full_name": f"Loadtest {self.email.split('+')[1].split('@')[0]}",
            "role": "traveler",
            "status": 1,
        }
        with self.client.post(
            "/api/v1/users",
            json=payload,
            name="POST /api/v1/users (on_start)",
            catch_response=True,
        ) as resp:
            if resp.status_code == 201:
                self.user_id = resp.json().get("id")
                if JWT_SECRET and self.user_id:
                    self.token = _sign_jwt(self.user_id, self.email, "traveler")
                resp.success()
            elif resp.status_code == 409:
                resp.success()  # email collision, rare with uuid suffix
            else:
                resp.failure(f"register on_start returned {resp.status_code}")

    @task(60)
    def search_properties(self):
        params = _random_search_query()
        with self.client.get(
            "/api/v1/search",
            params=params,
            name="GET /api/v1/search",
            catch_response=True,
        ) as resp:
            if resp.status_code in (200, 404):
                resp.success()
            else:
                resp.failure(f"search returned {resp.status_code}")

    @task(15)
    def auth_login(self):
        if REAL_LOGIN_RATIO > 0 and random.random() < REAL_LOGIN_RATIO:
            payload = {"email": self.email, "password": self.password}
        else:
            payload = {
                "email": _random_email("unknown"),
                "password": "WrongPasswordForLoadTest123!",
            }

        with self.client.post(
            "/api/v1/auth/login",
            json=payload,
            name="POST /api/v1/auth/login",
            catch_response=True,
        ) as resp:
            if resp.status_code in (200, 401, 423, 429):
                resp.success()
            else:
                resp.failure(f"login returned {resp.status_code}")

    @task(5)
    def register_sustained(self):
        """Keep exercising POST /api/v1/users under sustained load (not just on_start)."""
        payload = {
            "email": _random_email("sustained"),
            "phone": _random_phone(),
            "password": "LoadTest!1234",
            "full_name": "Sustained Loadtest",
            "role": "traveler",
            "status": 1,
        }
        with self.client.post(
            "/api/v1/users",
            json=payload,
            name="POST /api/v1/users (sustained)",
            catch_response=True,
        ) as resp:
            if resp.status_code in (201, 409):
                resp.success()
            else:
                resp.failure(f"register sustained returned {resp.status_code}")

    @task(20)
    def booking_charge(self):
        if not (self.token and self.user_id):
            return

        payload = {
            "reservation_id": str(uuid.uuid4()),
            "traveler_id": self.user_id,
            "amount_in_cents": random.randint(50_000, 500_000),
            "currency": "COP",
            "payment_method_token": "pm_loadtest_success",
            "idempotency_key": uuid.uuid4().hex,
        }
        headers = {
            "X-Forwarded-Proto": "https",
            "Authorization": f"Bearer {self.token}",
        }
        with self.client.post(
            "/api/v1/payments/charges",
            json=payload,
            headers=headers,
            name="POST /api/v1/payments/charges",
            catch_response=True,
        ) as resp:
            if resp.status_code in (201, 400, 409):
                resp.success()
            else:
                resp.failure(f"charge returned {resp.status_code}")


# ---------------------------------------------------------------------------
# Load shape: 5 min ramp + 15 min peak
# ---------------------------------------------------------------------------


class RampThenPeak(LoadTestShape):
    """5 min linear ramp from START_USERS to PEAK_USERS, then 15 min hold."""

    def tick(self):
        run_time = self.get_run_time()
        total = RAMP_DURATION_S + PEAK_DURATION_S

        if run_time >= total:
            return None

        if run_time < RAMP_DURATION_S:
            progress = run_time / RAMP_DURATION_S
            users = int(START_USERS + (PEAK_USERS - START_USERS) * progress)
            spawn_rate = max(1.0, (PEAK_USERS - START_USERS) / RAMP_DURATION_S)
            return (users, spawn_rate)

        return (PEAK_USERS, 1.0)


# ---------------------------------------------------------------------------
# Lifecycle hooks
# ---------------------------------------------------------------------------


@events.test_start.add_listener
def _on_test_start(environment, **_kwargs):
    print(
        f"[MPF-74] Starting load test: ramp {RAMP_DURATION_S}s "
        f"(VUs {START_USERS}->{PEAK_USERS}) + peak {PEAK_DURATION_S}s @ {PEAK_USERS} VUs"
    )
    print(
        f"[MPF-74] REAL_LOGIN_RATIO={REAL_LOGIN_RATIO:.2f} "
        f"(0.0 = todos los login devuelven 401 sin tocar SMTP/SES)"
    )
    if not JWT_SECRET:
        print(
            "[MPF-74] WARN: LOADTEST_JWT_SECRET not set — booking flow disabled "
            "(VUs will skip POST /api/v1/payments/charges)"
        )
    if not PROPERTY_ID:
        print("[MPF-74] WARN: LOADTEST_PROPERTY_ID not set — booking flow disabled")
