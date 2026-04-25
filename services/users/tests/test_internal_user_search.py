from helpers import INTERNAL_API_KEY, seed_user_with_role


def test_search_by_name_matches_substring(client, session):
    seed_user_with_role(session, email="ana@example.com", full_name="Ana García")
    seed_user_with_role(session, email="diana@example.com", full_name="Diana López")
    seed_user_with_role(session, email="other@example.com", full_name="Pedro Solano")

    response = client.post(
        "/api/v1/internal/users/search-by-name",
        json={"query": "ana"},
        headers={"X-Internal-Api-Key": INTERNAL_API_KEY},
    )

    assert response.status_code == 200
    body = response.json()
    matched_emails = {item["email"] for item in body}
    assert matched_emails == {"ana@example.com", "diana@example.com"}


def test_search_by_name_requires_api_key(client, session):
    seed_user_with_role(session)
    response = client.post(
        "/api/v1/internal/users/search-by-name",
        json={"query": "ana"},
    )
    assert response.status_code == 403


def test_search_by_name_validates_query(client, session):
    response = client.post(
        "/api/v1/internal/users/search-by-name",
        json={"query": ""},
        headers={"X-Internal-Api-Key": INTERNAL_API_KEY},
    )
    assert response.status_code == 422


def test_list_by_ids_returns_only_matching_users(client, session):
    user_a = seed_user_with_role(session, email="a@example.com", full_name="User A")
    user_b = seed_user_with_role(session, email="b@example.com", full_name="User B")
    seed_user_with_role(session, email="c@example.com", full_name="User C")

    response = client.post(
        "/api/v1/internal/users/by-ids",
        json={"ids": [str(user_a.id), str(user_b.id)]},
        headers={"X-Internal-Api-Key": INTERNAL_API_KEY},
    )

    assert response.status_code == 200
    body = response.json()
    assert {item["email"] for item in body} == {"a@example.com", "b@example.com"}


def test_list_by_ids_empty_input(client, session):
    seed_user_with_role(session)
    response = client.post(
        "/api/v1/internal/users/by-ids",
        json={"ids": []},
        headers={"X-Internal-Api-Key": INTERNAL_API_KEY},
    )
    assert response.status_code == 200
    assert response.json() == []
