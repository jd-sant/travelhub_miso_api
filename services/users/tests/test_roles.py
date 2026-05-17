import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from adapters.models.role import Role
from adapters.models.user import User
from adapters.models.user_role import UserRole
from core.security import hash_password


def test_role_model_persists(session):
    role = Role(name="traveler")
    session.add(role)
    session.commit()
    session.refresh(role)

    assert role.id is not None
    assert role.name == "traveler"


def test_role_name_is_unique(session):
    role1 = Role(name="hotel_admin")
    session.add(role1)
    session.commit()

    role2 = Role(name="hotel_admin")
    session.add(role2)
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_user_role_association(session):
    role = Role(name="traveler")
    session.add(role)
    session.commit()
    session.refresh(role)

    user = User(
        email="test@example.com",
        phone="3001234567",
        password=hash_password("securePassword1"),
        full_name="Test User",
        status=1,
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    user_role = UserRole(user_id=user.id, role_id=role.id)
    session.add(user_role)
    session.commit()

    associations = session.exec(
        select(UserRole).where(UserRole.user_id == user.id)
    ).all()
    assert len(associations) == 1
    assert associations[0].role_id == role.id
