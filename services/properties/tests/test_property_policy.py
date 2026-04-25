from uuid import uuid4

from adapters.repositories.property_repository import SQLModelPropertyRepository
from core.config import settings
from db.seed import BEACHFRONT_PENTHOUSE_ID, RENAISSANCE_ESTATE_ID


def test_repository_returns_seeded_cancellation_policy(session):
    repository = SQLModelPropertyRepository(session)

    policy = repository.get_cancellation_policy(RENAISSANCE_ESTATE_ID)

    assert policy is not None
    assert policy.property_id == RENAISSANCE_ESTATE_ID
    assert policy.policy_type == "full_refund"
    assert policy.minimum_notice_hours == 48
    assert policy.is_active is True


def test_repository_returns_none_for_unknown_property_policy(session):
    repository = SQLModelPropertyRepository(session)

    assert repository.get_cancellation_policy(uuid4()) is None


def test_internal_policy_endpoint_returns_policy(client):
    response = client.get(
        f"/api/v1/internal/properties/{BEACHFRONT_PENTHOUSE_ID}/cancellation-policy",
        headers={"X-Internal-Api-Key": settings.internal_api_key},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["property_id"] == str(BEACHFRONT_PENTHOUSE_ID)
    assert body["policy_type"] == "partial_refund"
    assert body["minimum_notice_hours"] == 24
    assert body["penalty_percentage"] == 25
    assert body["timezone"] == "America/New_York"


def test_internal_policy_endpoint_forbids_invalid_key(client):
    response = client.get(
        f"/api/v1/internal/properties/{BEACHFRONT_PENTHOUSE_ID}/cancellation-policy",
        headers={"X-Internal-Api-Key": "wrong-key"},
    )

    assert response.status_code == 403
