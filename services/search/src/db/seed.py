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
        "name": "Mansión Renacentista & Viñedo Privado",
        "city": "Fiesole",
        "country": "Italia",
        "capacity": 12,
        "rating": 4.98,
        "base_price": Decimal("1240.00"),
        "currency": "COP",
        "amenities": ("wifi", "pool", "gym", "spa"),
    },
    {
        "id": UUID("22222222-2222-2222-2222-222222222222"),
        "name": "Penthouse Moderno Frente a la Playa",
        "city": "Miami",
        "country": "Estados Unidos",
        "capacity": 8,
        "rating": 4.87,
        "base_price": Decimal("2150.00"),
        "currency": "USD",
        "amenities": ("wifi", "pool", "parking", "air_conditioning"),
    },
    {
        "id": UUID("33333333-3333-3333-3333-333333333333"),
        "name": "Refugio Alpino de Montaña",
        "city": "Chamonix",
        "country": "Francia",
        "capacity": 14,
        "rating": 4.92,
        "base_price": Decimal("890.00"),
        "currency": "EUR",
        "amenities": ("wifi", "gym", "pet_friendly", "breakfast_included"),
    },
    {
        "id": UUID("44444444-4444-4444-4444-444444444444"),
        "name": "Villa Paraíso Tropical",
        "city": "Bora Bora",
        "country": "Polinesia Francesa",
        "capacity": 10,
        "rating": 4.99,
        "base_price": Decimal("1650.00"),
        "currency": "USD",
        "amenities": ("wifi", "pool", "breakfast_included", "air_conditioning"),
    },
    {
        "id": UUID("55555555-5555-5555-5555-555555555555"),
        "name": "Hotel Cikos Executive Suites",
        "city": "Bogota",
        "country": "Colombia",
        "capacity": 24,
        "rating": 4.84,
        "base_price": Decimal("180000.00"),
        "currency": "COP",
        "amenities": ("wifi", "breakfast_included", "air_conditioning"),
    },
    {
        "id": UUID("66666666-6666-6666-6666-666666666666"),
        "name": "Hostal Boutique La Candelaria",
        "city": "Bogota",
        "country": "Colombia",
        "capacity": 8,
        "rating": 4.55,
        "base_price": Decimal("95000.00"),
        "currency": "COP",
        "amenities": ("wifi", "breakfast_included", "parking"),
    },
    {
        "id": UUID("77777777-7777-7777-7777-777777777777"),
        "name": "Aparthotel Andino Premium",
        "city": "Bogota",
        "country": "Colombia",
        "capacity": 6,
        "rating": 4.95,
        "base_price": Decimal("320000.00"),
        "currency": "COP",
        "amenities": ("wifi", "gym", "parking", "spa"),
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
    "Fiesole",
    "Miami",
    "Chamonix",
    "Bora Bora",
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
    # Keep nightly price consistent with Properties service for E2E checks.
    _ = seed_day
    return base_price


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


def _has_seed_metadata_drift(session: Session) -> bool:
    properties = session.exec(select(Property)).all()
    property_by_id = {prop.id: prop for prop in properties}

    room_types = session.exec(select(RoomType)).all()
    room_type_by_property = {rt.property_id: rt for rt in room_types}

    rate_plans = session.exec(select(RatePlan)).all()
    rate_plan_by_room_type = {rp.room_type_id: rp for rp in rate_plans}

    for spec in PROPERTY_SEED_SPECS:
        prop = property_by_id.get(spec["id"])
        if prop is None:
            return True

        if prop.name != spec["name"]:
            return True
        if prop.city != spec["city"]:
            return True
        if prop.country != spec["country"]:
            return True
        if int(prop.max_capacity) != int(spec["capacity"]):
            return True
        if abs(float(prop.rating or 0.0) - float(spec["rating"])) > 1e-9:
            return True

        room_type = room_type_by_property.get(spec["id"])
        if room_type is None:
            return True

        rate_plan = rate_plan_by_room_type.get(room_type.id)
        if rate_plan is None:
            return True

        if rate_plan.currency != spec["currency"]:
            return True
        if Decimal(rate_plan.base_price) != Decimal(spec["base_price"]):
            return True

    return False


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
            metadata_drift = _has_seed_metadata_drift(session)

            # If existing local data does not match canonical IDs or date coverage, reset and reseed.
            if (
                existing_ids != fixed_ids
                or inventory_rows != expected_rows
                or rate_rows != expected_rows
                or metadata_drift
            ):
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
                    country=spec["country"],
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
                    currency=spec["currency"],
                    base_price=base_price,
                    is_active=True,
                )
            )

            for seed_day in SEED_DATES:
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




