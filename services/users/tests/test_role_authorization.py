"""
Tests para validar la funcionalidad de control de accesos por rol.

Casos de prueba:
1. Un usuario con rol "viajero" que intenta acceder a endpoints admin recibe 403
2. Un usuario con rol "admin" puede acceder a endpoints admin
3. Un usuario sin autenticación recibe 401
4. Un token JWT manipulado es rechazado
"""

import jwt

from adapters.models.role import Role


def test_traveler_cannot_create_user_403(client, traveler_token, session):
    """
    Un usuario con rol "viajero" que intenta crear usuarios
    recibe un 403 Forbidden.
    """
    # Crear rol traveler en BD
    traveler_role = Role(name="traveler")
    session.add(traveler_role)
    session.commit()
    
    response = client.post(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {traveler_token}"},
        json={
            "email": "newuser@example.com",
            "phone": "1234567890",
            "password": "pass123",
        },
    )
    
    assert response.status_code == 403
    assert "Se requiere rol 'admin'" in response.json()["detail"]


def test_traveler_cannot_list_users_403(client, traveler_token, session):
    """
    Un usuario con rol "viajero" que intenta listar usuarios
    recibe un 403 Forbidden.
    """
    # Crear rol traveler en BD
    traveler_role = Role(name="traveler")
    session.add(traveler_role)
    session.commit()
    
    response = client.get(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {traveler_token}"},
    )
    
    assert response.status_code == 403
    assert "Se requiere rol 'admin'" in response.json()["detail"]


def test_admin_can_create_user_201(client, admin_token, session):
    """
    Un usuario con rol "admin" puede crear nuevos usuarios.
    """
    # Crear roles en BD
    admin_role = Role(name="admin")
    traveler_role = Role(name="traveler")
    session.add(admin_role)
    session.add(traveler_role)
    session.commit()
    
    response = client.post(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "email": "newuser@example.com",
            "phone": "1234567890",
            "password": "pass123",
        },
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "newuser@example.com"


def test_admin_can_list_users_200(client, admin_token, session):
    """
    Un usuario con rol "admin" puede listar todos los usuarios.
    """
    # Crear rol admin en BD
    admin_role = Role(name="admin")
    session.add(admin_role)
    session.commit()
    
    response = client.get(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_missing_token_returns_401(client):
    """
    Un usuario sin token JWT recibe 401 Unauthorized.
    """
    response = client.get("/api/v1/users")
    
    assert response.status_code == 401
    assert "No autorizado" in response.json()["detail"]


def test_invalid_jwt_token_returns_401(client):
    """
    Un token JWT inválido o manipulado es rechazado con 401.
    """
    response = client.get(
        "/api/v1/users",
        headers={"Authorization": "Bearer invalid-token-xyz"},
    )
    
    assert response.status_code == 401
    assert "No autorizado" in response.json()["detail"]


def test_manipulated_jwt_token_rejected_401(client):
    """
    Si un JWT token contiene un rol manipulado, el middleware lo valida
    y rechaza con 401 si la firma es inválida.
    """
    # Token con firma incorrecta
    fake_payload = {
        "sub": "user-id",
        "email": "hacker@example.com",
        "role": "admin",
    }
    fake_token = jwt.encode(fake_payload, "wrong-secret-key", algorithm="HS256")
    
    response = client.get(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {fake_token}"},
    )
    
    # Debe rechazar porque la firma no coincide
    assert response.status_code == 401
    assert "No autorizado" in response.json()["detail"]


def test_hotel_role_receives_403_on_admin_endpoints(client, hotel_token, session):
    """
    Un usuario con rol "hotel" que intenta acceder a endpoints admin
    recibe 403 Forbidden.
    """
    # Crear rol hotel en BD
    hotel_role = Role(name="hotel")
    session.add(hotel_role)
    session.commit()
    
    response = client.get(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {hotel_token}"},
    )
    
    assert response.status_code == 403
    assert "Se requiere rol 'admin'" in response.json()["detail"]


def test_no_token_on_protected_endpoint_401(client, session):
    """
    Un endpoint protegido sin token de autenticación retorna 401.
    """
    # Crear rol traveler para que se asigne al nuevo usuario
    traveler_role = Role(name="traveler")
    session.add(traveler_role)
    session.commit()
    
    response = client.post(
        "/api/v1/users",
        json={
            "email": "test@example.com",
            "phone": "1234567890",
            "password": "pass123",
        },
    )
    
    assert response.status_code == 401
    assert "No autorizado" in response.json()["detail"]
