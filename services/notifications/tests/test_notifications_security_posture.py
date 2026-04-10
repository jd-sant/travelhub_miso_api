from pathlib import Path

import pytest

from core.config import Settings
from core.privacy import mask_email, sanitize_sensitive_data


def test_mask_email_obfuscates_local_part() -> None:
    assert mask_email("traveler@example.com") == "t***r@example.com"


def test_sanitize_sensitive_data_redacts_known_financial_fields() -> None:
    payload = {
        "body": "sensitive body",
        "nested": {
            "confirmation_token_id": "ctoken_123",
            "card_number": "4242424242424242",
        },
    }

    assert sanitize_sensitive_data(payload) == {
        "body": "[REDACTED]",
        "nested": {
            "confirmation_token_id": "[REDACTED]",
            "card_number": "[REDACTED]",
        },
    }


def test_settings_require_https_internal_urls_in_non_dev(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("PAYMENTS_SERVICE_URL", "http://payments.internal")

    with pytest.raises(RuntimeError, match="https"):
        Settings().payments_service_url


def test_backend_source_has_no_hardcoded_pan_literals() -> None:
    service_root = Path(__file__).resolve().parents[1]
    repo_root = Path(__file__).resolve().parents[3]
    target_files = list((service_root / "src").rglob("*.py"))
    target_files.append(repo_root / ".env.example")
    known_pan_literals = {
        "4242 4242 4242 4242",
        "4000 0000 0000 9995",
        "4000 0000 0000 0002",
        "4242424242424242",
        "4000000000009995",
        "4000000000000002",
    }

    offending = []
    for path in target_files:
        content = path.read_text(encoding="utf-8")
        if any(literal in content for literal in known_pan_literals):
            offending.append(str(path))

    assert offending == []
