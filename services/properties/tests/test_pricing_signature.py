"""Unit tests for pricing signature and canonicalization"""
import pytest
from core.security import (
    canonicalize_pricing_payload,
    build_pricing_signature,
    verify_pricing_signature,
)
from uuid import uuid4


class TestCanonicalPayload:
    """Tests for deterministic payload canonicalization"""
    
    def test_deterministic_payload(self):
        """Same inputs produce same canonical output"""
        prop_id = str(uuid4())
        canonical_1 = canonicalize_pricing_payload(
            property_id=prop_id,
            season_start="2026-06-01",
            season_end="2026-08-31",
            price_per_night=100.0,
            currency="COP",
            tax_rate=0.19,
            cleaning_fee=50.0,
        )
        canonical_2 = canonicalize_pricing_payload(
            property_id=prop_id,
            season_start="2026-06-01",
            season_end="2026-08-31",
            price_per_night=100.0,
            currency="COP",
            tax_rate=0.19,
            cleaning_fee=50.0,
        )
        assert canonical_1 == canonical_2
    
    def test_canonical_format(self):
        """Canonical payload follows expected format with pipe delimiter"""
        prop_id = str(uuid4())
        canonical = canonicalize_pricing_payload(
            property_id=prop_id,
            season_start="2026-06-01",
            season_end="2026-08-31",
            price_per_night=100.0,
            currency="COP",
            tax_rate=0.19,
            cleaning_fee=50.0,
        )
        parts = canonical.split("|")
        assert len(parts) == 7
        assert parts[0] == prop_id
        assert parts[1] == "2026-06-01"
        assert parts[2] == "2026-08-31"
        assert parts[3] == "100.00"
        assert parts[4] == "COP"
        assert parts[5] == "0.19"
        assert parts[6] == "50.00"
    
    def test_currency_normalized_to_uppercase(self):
        """Currency is normalized to uppercase"""
        prop_id = str(uuid4())
        canonical_lower = canonicalize_pricing_payload(
            property_id=prop_id,
            season_start="2026-06-01",
            season_end="2026-08-31",
            price_per_night=100.0,
            currency="cop",
            tax_rate=0.19,
            cleaning_fee=50.0,
        )
        canonical_upper = canonicalize_pricing_payload(
            property_id=prop_id,
            season_start="2026-06-01",
            season_end="2026-08-31",
            price_per_night=100.0,
            currency="COP",
            tax_rate=0.19,
            cleaning_fee=50.0,
        )
        assert canonical_lower == canonical_upper
    
    def test_numeric_normalization(self):
        """Numerics normalized to 2 decimal places"""
        prop_id = str(uuid4())
        canonical_1 = canonicalize_pricing_payload(
            property_id=prop_id,
            season_start="2026-06-01",
            season_end="2026-08-31",
            price_per_night=100,  # int
            currency="COP",
            tax_rate=0.19,
            cleaning_fee=50,  # int
        )
        canonical_2 = canonicalize_pricing_payload(
            property_id=prop_id,
            season_start="2026-06-01",
            season_end="2026-08-31",
            price_per_night=100.00,  # float
            currency="COP",
            tax_rate=0.19,
            cleaning_fee=50.00,  # float
        )
        assert canonical_1 == canonical_2


class TestSignatureGeneration:
    """Tests for HMAC-SHA256 signature generation"""
    
    def test_build_pricing_signature(self):
        """Signature can be generated for canonical payload"""
        canonical = "test-payload|123|456"
        secret = "test-secret"
        signature = build_pricing_signature(canonical, secret, "HMAC-SHA256")
        assert signature is not None
        assert len(signature) == 64  # SHA256 hex = 64 chars
        assert all(c in "0123456789abcdef" for c in signature)
    
    def test_signature_deterministic(self):
        """Same canonical and secret produce same signature"""
        canonical = "test-payload|123|456"
        secret = "test-secret"
        sig_1 = build_pricing_signature(canonical, secret, "HMAC-SHA256")
        sig_2 = build_pricing_signature(canonical, secret, "HMAC-SHA256")
        assert sig_1 == sig_2
    
    def test_signature_changes_with_payload(self):
        """Different payload produces different signature"""
        secret = "test-secret"
        sig_1 = build_pricing_signature("payload-1", secret, "HMAC-SHA256")
        sig_2 = build_pricing_signature("payload-2", secret, "HMAC-SHA256")
        assert sig_1 != sig_2
    
    def test_signature_changes_with_secret(self):
        """Different secret produces different signature"""
        payload = "test-payload"
        sig_1 = build_pricing_signature(payload, "secret-1", "HMAC-SHA256")
        sig_2 = build_pricing_signature(payload, "secret-2", "HMAC-SHA256")
        assert sig_1 != sig_2
    
    def test_unsupported_algorithm(self):
        """Unsupported algorithm raises ValueError"""
        canonical = "test-payload"
        secret = "test-secret"
        with pytest.raises(ValueError, match="Unsupported algorithm"):
            build_pricing_signature(canonical, secret, "SHA1")


class TestSignatureVerification:
    """Tests for signature verification with constant-time comparison"""
    
    def test_verify_valid_signature(self):
        """Valid signature verifies successfully"""
        canonical = "test-payload|100|50"
        secret = "test-secret"
        signature = build_pricing_signature(canonical, secret, "HMAC-SHA256")
        assert verify_pricing_signature(canonical, signature, secret, "HMAC-SHA256") is True
    
    def test_verify_invalid_signature(self):
        """Invalid signature fails verification"""
        canonical = "test-payload|100|50"
        secret = "test-secret"
        wrong_signature = "0" * 64  # Invalid signature
        assert verify_pricing_signature(canonical, wrong_signature, secret, "HMAC-SHA256") is False
    
    def test_verify_signature_wrong_secret(self):
        """Signature fails if secret differs"""
        canonical = "test-payload|100|50"
        secret_1 = "secret-1"
        secret_2 = "secret-2"
        signature = build_pricing_signature(canonical, secret_1, "HMAC-SHA256")
        assert verify_pricing_signature(canonical, signature, secret_2, "HMAC-SHA256") is False
    
    def test_verify_signature_tampered_payload(self):
        """Signature fails if payload is tampered"""
        canonical_1 = "property-123|2026-06-01|2026-08-31|100.00|COP|0.19|50.00"
        canonical_2 = "property-123|2026-06-01|2026-08-31|101.00|COP|0.19|50.00"  # Tampered price
        secret = "test-secret"
        signature = build_pricing_signature(canonical_1, secret, "HMAC-SHA256")
        assert verify_pricing_signature(canonical_2, signature, secret, "HMAC-SHA256") is False
    
    def test_verify_uses_constant_time_comparison(self):
        """
        Verification uses hmac.compare_digest for constant-time comparison.
        We can't directly test timing, but we verify it rejects tampering.
        """
        canonical = "test-payload"
        secret = "secret"
        correct_sig = build_pricing_signature(canonical, secret, "HMAC-SHA256")
        
        # Tamper with single char
        tampered_sig = correct_sig[:-1] + ("a" if correct_sig[-1] != "a" else "b")
        assert verify_pricing_signature(canonical, tampered_sig, secret, "HMAC-SHA256") is False


class TestIntegrationPayloadToSignature:
    """Integration tests for full canonicalization -> signature flow"""
    
    def test_full_flow_success(self):
        """Full pricing signature flow from canonical payload"""
        prop_id = str(uuid4())
        canonical = canonicalize_pricing_payload(
            property_id=prop_id,
            season_start="2026-06-01",
            season_end="2026-08-31",
            price_per_night=150.50,
            currency="USD",
            tax_rate=0.08,
            cleaning_fee=25.00,
        )
        
        secret = "production-secret-key"
        signature = build_pricing_signature(canonical, secret, "HMAC-SHA256")
        is_valid = verify_pricing_signature(canonical, signature, secret, "HMAC-SHA256")
        
        assert is_valid is True
    
    def test_full_flow_with_tampering(self):
        """Detect tampering in full flow"""
        prop_id = str(uuid4())
        
        # Original
        canonical_original = canonicalize_pricing_payload(
            property_id=prop_id,
            season_start="2026-06-01",
            season_end="2026-08-31",
            price_per_night=150.50,
            currency="USD",
            tax_rate=0.08,
            cleaning_fee=25.00,
        )
        secret = "production-secret-key"
        signature = build_pricing_signature(canonical_original, secret, "HMAC-SHA256")
        
        # Tampering: price changed
        canonical_tampered = canonicalize_pricing_payload(
            property_id=prop_id,
            season_start="2026-06-01",
            season_end="2026-08-31",
            price_per_night=200.00,  # Changed!
            currency="USD",
            tax_rate=0.08,
            cleaning_fee=25.00,
        )
        
        is_valid = verify_pricing_signature(canonical_tampered, signature, secret, "HMAC-SHA256")
        assert is_valid is False
