"""Demo data seeding for the users service.

The demo hotel UUIDs intentionally match the `id_owner` values used in the
properties service (`services/properties/src/db/seed.py`). Keep them in sync
so the host dashboard demo works end-to-end without manual UUID juggling.
"""
from uuid import UUID

from sqlmodel import Session, select

from adapters.models.role import Role
from adapters.models.user import User
from adapters.models.user_role import UserRole
from core.security import hash_password


DEMO_HOTEL_A_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
DEMO_HOTEL_B_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
DEMO_HOTEL_PASSWORD = "HotelDemo123"

DEMO_HOTELS = [
    {
        "id": DEMO_HOTEL_A_ID,
        "email": "hotel-a@travelhub.demo",
        "full_name": "Grand Plaza Hotel",
        "hotel_name": "Grand Plaza Hotel",
        "phone": "3000000001",
    },
    {
        "id": DEMO_HOTEL_B_ID,
        "email": "hotel-b@travelhub.demo",
        "full_name": "Mountain Resort",
        "hotel_name": "Mountain Resort",
        "phone": "3000000002",
    },
]


def seed_demo_hotels_if_empty(session: Session) -> None:
    """Insert the demo hotel users + role assignment if they do not exist yet."""
    role = session.exec(select(Role).where(Role.name == "hotel")).first()
    if role is None:
        role = Role(name="hotel")
        session.add(role)
        session.commit()
        session.refresh(role)

    hashed_password = hash_password(DEMO_HOTEL_PASSWORD)

    for hotel in DEMO_HOTELS:
        existing = session.exec(select(User).where(User.id == hotel["id"])).first()
        if existing is not None:
            continue

        user = User(
            id=hotel["id"],
            email=hotel["email"],
            phone=hotel["phone"],
            password=hashed_password,
            full_name=hotel["full_name"],
            hotel_name=hotel["hotel_name"],
            status=1,
        )
        session.add(user)
        session.commit()
        session.refresh(user)

        already_has_role = session.exec(
            select(UserRole).where(
                UserRole.user_id == user.id, UserRole.role_id == role.id
            )
        ).first()
        if already_has_role is None:
            session.add(UserRole(user_id=user.id, role_id=role.id))
            session.commit()
