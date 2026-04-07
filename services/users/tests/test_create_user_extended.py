from sqlmodel import Session, select

from adapters.models.role import Role
from adapters.models.user import User
from adapters.models.user_role import UserRole


def test_create_traveler_user_with_full_name(client, test_engine):
    payload = {
        "email": "traveler@example.com",
        "phone": "3001234567",
        "password": "miPasswordSegura123",
        "full_name": "Juan Traveler",
        "role": "traveler",
        "status": 1,
    }

    response = client.post("/api/v1/users", json=payload)

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == payload["email"]
    assert body["full_name"] == payload["full_name"]
    assert body["hotel_name"] is None

    with Session(test_engine) as session:
        user = session.exec(
            select(User).where(User.email == payload["email"])
        ).first()
        assert user is not None
        assert user.full_name == "Juan Traveler"
        assert user.hotel_name is None

        user_roles = session.exec(
            select(UserRole, Role).join(Role).where(UserRole.user_id == user.id)
        ).all()
        assert len(user_roles) == 1
        role_name = user_roles[0][1].name
        assert role_name == "traveler"


def test_create_hotel_partner_with_hotel_name(client, test_engine):
    payload = {
        "email": "hotel@example.com",
        "phone": "3007654321",
        "password": "passwordHotel123",
        "full_name": "Carlos Hotel Manager",
        "hotel_name": "Grand Hotel",
        "role": "hotel_partner",
        "status": 1,
    }

    response = client.post("/api/v1/users", json=payload)

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == payload["email"]
    assert body["full_name"] == payload["full_name"]
    assert body["hotel_name"] == payload["hotel_name"]

    with Session(test_engine) as session:
        user = session.exec(
            select(User).where(User.email == payload["email"])
        ).first()
        assert user is not None
        assert user.full_name == "Carlos Hotel Manager"
        assert user.hotel_name == "Grand Hotel"

        user_roles = session.exec(
            select(UserRole, Role).join(Role).where(UserRole.user_id == user.id)
        ).all()
        assert len(user_roles) == 1
        role_name = user_roles[0][1].name
        assert role_name == "hotel_partner"


def test_create_user_defaults_to_traveler_role(client, test_engine):
    payload = {
        "email": "default@example.com",
        "phone": "3009876543",
        "password": "passwordDefault123",
        "full_name": "Default User",
    }

    response = client.post("/api/v1/users", json=payload)

    assert response.status_code == 201

    with Session(test_engine) as session:
        user = session.exec(
            select(User).where(User.email == payload["email"])
        ).first()
        assert user is not None

        user_roles = session.exec(
            select(UserRole, Role).join(Role).where(UserRole.user_id == user.id)
        ).all()
        assert len(user_roles) == 1
        role_name = user_roles[0][1].name
        assert role_name == "traveler"


def test_create_user_without_full_name_returns_422(client):
    payload = {
        "email": "nofullname@example.com",
        "phone": "3001234567",
        "password": "miPasswordSegura123",
        "status": 1,
    }

    response = client.post("/api/v1/users", json=payload)

    assert response.status_code == 422
    errors = response.json()["detail"]
    assert any("full_name" in str(error) for error in errors)
