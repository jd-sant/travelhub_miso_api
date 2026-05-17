from helpers import INTERNAL_API_KEY, seed_user_with_role


def test_internal_get_user_by_id_returns_public_profile(client, session):
    user = seed_user_with_role(session, email="lookup@example.com", full_name="Lookup User")

    response = client.get(
        f"/api/v1/internal/users/{user.id}",
        headers={"X-Internal-Api-Key": INTERNAL_API_KEY},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(user.id)
    assert body["email"] == "lookup@example.com"
    assert body["full_name"] == "Lookup User"
    assert "password" not in body


def test_internal_get_user_by_id_requires_api_key(client, session):
    user = seed_user_with_role(session)

    response = client.get(f"/api/v1/internal/users/{user.id}")

    assert response.status_code == 403
