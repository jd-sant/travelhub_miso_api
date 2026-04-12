from datetime import date
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import func
from sqlmodel import Session, select

from adapters.models import Amenity
from adapters.models import InventoryCalendar
from adapters.models import Property
from adapters.models import PropertyAmenity
from adapters.models import RateCalendar
from adapters.models import RatePlan
from adapters.models import RoomType
from adapters.models import Service
from core.config import settings
from db.session import engine

TARGET_PROPERTY_COUNT = 1000


def _build_seed_dates() -> tuple[date, ...]:
    """
    Build contiguous availability windows across several months.
    We seed days 10-16 for each month from April to December 2026 so
    short stays (e.g. 10->12) work consistently in each month.
    """
    days: list[date] = []
    for month in range(4, 13):
        for day in range(10, 17):
            days.append(date(2026, month, day))
    return tuple(days)


SEED_DATES = _build_seed_dates()

AMENITY_CATALOG = [
    ("wifi", "connectivity"),
    ("pool", "recreation"),
    ("gym", "wellness"),
    ("parking", "comfort"),
    ("pet_friendly", "pets"),
    ("air_conditioning", "comfort"),
    ("breakfast_included", "gastronomy"),
    ("spa", "wellness"),
]

CITIES = [
    "Bogota",
    "Cali",
    "Cartagena",
    "Barranquilla",
    "Santa Marta",
    "Bucaramanga",
]


def _is_seed_enabled() -> bool:
    db_url = str(engine.url)
    if db_url.startswith("sqlite"):
        return True
    if db_url.startswith("postgresql") and settings.is_local_dev:
        return True
    return False


def _build_local_seed_image_url(idx: int) -> str:
    # Local generic image path to avoid external URL dependency.
    variant = ((idx - 1) % 24) + 1
    return f"/assets/seed-images/hotel-{variant:02d}.jpg"


def seed_dummy_data_if_needed() -> None:
    if not _is_seed_enabled():
        return

    with Session(engine) as session:
        current_count = session.exec(select(func.count()).select_from(Property)).one()
        if current_count >= TARGET_PROPERTY_COUNT:
            return

        amenity_id_by_name = _ensure_amenity_catalog(session)

        for idx in range(current_count + 1, TARGET_PROPERTY_COUNT + 1):
            property_id = uuid4()
            room_type_id = uuid4()
            rate_plan_id = uuid4()

            city = CITIES[(idx - 1) % len(CITIES)]
            capacity = 2 + (idx % 5)
            rating = min(5.0, round(3.4 + ((idx % 16) * 0.1), 1))
            base_price = Decimal(80 + idx * 3)

            session.add(
                Property(
                    id=property_id,
                    name=f"Hotel Demo Search {idx:02d}",
                    city=city,
                    country="Colombia",
                    address=f"Carrera {20 + idx} #10-{40 + idx}",
                    description="Dummy property for local Postman and API tests.",
                    is_active=True,
                    max_capacity=capacity,
                    main_image_url=_build_local_seed_image_url(idx),
                    rating=rating,
                )
            )

            session.add(
                RoomType(
                    id=room_type_id,
                    property_id=property_id,
                    name="Standard Room",
                    description="Base room type for dummy dataset",
                    capacity=capacity,
                    is_active=True,
                )
            )

            session.add(
                RatePlan(
                    id=rate_plan_id,
                    room_type_id=room_type_id,
                    name="Flexible Rate",
                    description="Cancelable up to 24h before check-in",
                    currency="USD",
                    base_price=base_price,
                    is_active=True,
                )
            )

            for day_offset, seed_day in enumerate(SEED_DATES):
                session.add(
                    InventoryCalendar(
                        room_type_id=room_type_id,
                        date=seed_day,
                        available_units=5 + (idx % 3),
                        blocked_units=0,
                    )
                )
                session.add(
                    RateCalendar(
                        rate_plan_id=rate_plan_id,
                        date=seed_day,
                        price=base_price + Decimal(5 * day_offset),
                    )
                )

            selected_amenities = [
                AMENITY_CATALOG[(idx - 1) % len(AMENITY_CATALOG)][0],
                AMENITY_CATALOG[idx % len(AMENITY_CATALOG)][0],
                AMENITY_CATALOG[(idx + 1) % len(AMENITY_CATALOG)][0],
            ]
            for amenity_name in selected_amenities:
                session.add(
                    PropertyAmenity(
                        property_id=property_id,
                        amenity_id=amenity_id_by_name[amenity_name],
                    )
                )

            session.add(
                Service(
                    id=uuid4(),
                    property_id=property_id,
                    name="breakfast",
                    description="Breakfast service included",
                    is_active=True,
                )
            )
            session.add(
                Service(
                    id=uuid4(),
                    property_id=property_id,
                    name="front_desk_24h",
                    description="24-hour front desk service",
                    is_active=True,
                )
            )

        session.commit()


def _ensure_amenity_catalog(session: Session) -> dict[str, object]:
    amenity_id_by_name: dict[str, object] = {}
    existing_amenities = session.exec(select(Amenity)).all()
    for amenity in existing_amenities:
        amenity_id_by_name[amenity.name] = amenity.id

    for name, category in AMENITY_CATALOG:
        if name in amenity_id_by_name:
            continue

        amenity = Amenity(id=uuid4(), name=name, category=category)
        session.add(amenity)
        session.flush()
        amenity_id_by_name[name] = amenity.id

    return amenity_id_by_name
