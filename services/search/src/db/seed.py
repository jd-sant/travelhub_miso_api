from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import func
from sqlmodel import Session, delete, select

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

# Keep Search seeded property IDs aligned with Properties service.
PROPERTY_SEED_SPECS = (
    {
        "id": UUID("11111111-1111-1111-1111-111111111111"),
        "name": "Mansion Renacentista E2E",
        "city": "Bogota",
        "capacity": 4,
        "rating": 4.9,
        "base_price": Decimal("125.00"),
        "amenities": ("wifi", "pool", "gym", "spa"),
    },
    {
        "id": UUID("22222222-2222-2222-2222-222222222222"),
        "name": "Penthouse Playa E2E",
        "city": "Cartagena",
        "capacity": 3,
        "rating": 4.8,
        "base_price": Decimal("145.00"),
        "amenities": ("wifi", "pool", "parking", "air_conditioning"),
    },
    {
        "id": UUID("33333333-3333-3333-3333-333333333333"),
        "name": "Refugio Alpino E2E",
        "city": "Cali",
        "capacity": 5,
        "rating": 4.7,
        "base_price": Decimal("110.00"),
        "amenities": ("wifi", "gym", "pet_friendly", "breakfast_included"),
    },
    {
        "id": UUID("44444444-4444-4444-4444-444444444444"),
        "name": "Villa Tropical E2E",
        "city": "Santa Marta",
        "capacity": 6,
        "rating": 4.6,
        "base_price": Decimal("135.00"),
        "amenities": ("wifi", "pool", "breakfast_included", "air_conditioning"),
    },
)

TARGET_PROPERTY_COUNT = len(PROPERTY_SEED_SPECS)


def _build_seed_dates() -> tuple[date, ...]:
    """
    Build contiguous availability windows across the year.
    We seed days 10-16 for every month in 2026 so short stays
    (e.g. 10->12) work consistently in E2E tests.
    """
    days: list[date] = []
    for month in range(1, 13):
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


def _build_seed_price(base_price: Decimal, seed_day: date) -> Decimal:
    # Keep prices in a practical E2E range for filters (e.g. max_price=200).
    seasonality = Decimal((seed_day.month % 4) * 3)  # 0..9
    intra_window = Decimal((seed_day.day - 10) * 2)  # 0..12 for days 10..16
    return base_price + seasonality + intra_window


def _clear_search_dataset(session: Session) -> None:
    """Clear search data in FK-safe order for local self-healing reseed."""
    session.exec(delete(PropertyAmenity))
    session.exec(delete(Service))
    session.exec(delete(RateCalendar))
    session.exec(delete(InventoryCalendar))
    session.exec(delete(RatePlan))
    session.exec(delete(RoomType))
    session.exec(delete(Property))
    session.exec(delete(Amenity))
    session.commit()


def seed_dummy_data_if_needed() -> None:
    if not _is_seed_enabled():
        return

    with Session(engine) as session:
        current_count = session.exec(select(func.count()).select_from(Property)).one()

        if current_count:
            existing_ids = set(session.exec(select(Property.id)).all())
            fixed_ids = {spec["id"] for spec in PROPERTY_SEED_SPECS}
            inventory_rows = session.exec(select(func.count()).select_from(InventoryCalendar)).one()
            rate_rows = session.exec(select(func.count()).select_from(RateCalendar)).one()
            expected_rows = TARGET_PROPERTY_COUNT * len(SEED_DATES)

            # If existing local data does not match canonical IDs or date coverage, reset and reseed.
            if existing_ids != fixed_ids or inventory_rows != expected_rows or rate_rows != expected_rows:
                _clear_search_dataset(session)
                current_count = 0

        if current_count >= TARGET_PROPERTY_COUNT:
            return

        amenity_id_by_name = _ensure_amenity_catalog(session)

        existing_ids = set(session.exec(select(Property.id)).all()) if current_count else set()

        for idx, spec in enumerate(PROPERTY_SEED_SPECS, start=1):
            property_id = spec["id"]
            if property_id in existing_ids:
                continue

            room_type_id = uuid4()
            rate_plan_id = uuid4()

            city = spec["city"]
            capacity = spec["capacity"]
            rating = spec["rating"]
            base_price = spec["base_price"]

            session.add(
                Property(
                    id=property_id,
                    name=spec["name"],
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
                        available_units=6 + (idx % 3),
                        blocked_units=0,
                    )
                )
                session.add(
                    RateCalendar(
                        rate_plan_id=rate_plan_id,
                        date=seed_day,
                        price=_build_seed_price(base_price, seed_day),
                    )
                )

            selected_amenities = spec["amenities"]
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
