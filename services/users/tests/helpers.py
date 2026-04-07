from sqlmodel import Session, select

from adapters.models.role import Role
from adapters.models.user import User
from adapters.models.user_role import UserRole
from core.security import hash_password

INTERNAL_API_KEY = "test-internal-key-12345"


def seed_user_with_role(
    session: Session,
    email: str = "ana@example.com",
    password: str = "securePassword1",
    role_name: str = "traveler",
    full_name: str = "Ana García",
    hotel_name: str = None,
) -> User:
    role = session.exec(select(Role).where(Role.name == role_name)).first()
    if not role:
        role = Role(name=role_name)
        session.add(role)
        session.commit()
        session.refresh(role)

    user = User(
        email=email,
        phone="3001234567",
        password=hash_password(password),
        full_name=full_name,
        hotel_name=hotel_name,
        status=1,
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    user_role = UserRole(user_id=user.id, role_id=role.id)
    session.add(user_role)
    session.commit()
    return user
