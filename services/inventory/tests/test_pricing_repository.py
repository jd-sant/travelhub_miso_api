from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from adapters.models import PricingChangeLog, Property, RateCalendar, RatePlan, RoomType
from adapters.repositories.pricing_management_repository import (
    SQLModelPricingManagementRepository,
)
from errors import PricingConflictError


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as db:
        yield db


def test_revert_change_rejects_when_newer_active_overlapping_change_exists(session: Session):
    property_id = uuid4()
    room_type_id = uuid4()
    rate_plan_id = uuid4()

    session.add(
        Property(
            id=property_id,
            name="Hotel Test",
            city="Bogota",
            country="Colombia",
            max_capacity=2,
        )
    )
    session.add(
        RoomType(
            id=room_type_id,
            property_id=property_id,
            name="Standard",
            capacity=2,
        )
    )
    session.add(
        RatePlan(
            id=rate_plan_id,
            room_type_id=room_type_id,
            name="Standard",
            currency="COP",
            base_price=Decimal("180000.00"),
        )
    )
    session.add(
        RateCalendar(
            rate_plan_id=rate_plan_id,
            date=date(2026, 5, 10),
            price=Decimal("175000.00"),
        )
    )
    older = PricingChangeLog(
        property_id=property_id,
        property_name="Hotel Test",
        room_type_id=room_type_id,
        room_type_name="Standard",
        rate_plan_id=rate_plan_id,
        rate_plan_name="Standard",
        currency="COP",
        start_date=date(2026, 5, 9),
        end_date=date(2026, 5, 12),
        previous_base_price="180000.00",
        new_base_price="175000.00",
        final_price="175000.00",
        projected_revenue_before="100.00",
        projected_revenue_after="90.00",
        actor_user_id=uuid4(),
        actor_email="hotel-a@travelhub.demo",
        previous_calendar_snapshot='[{"date":"2026-05-10","existed":true,"price":"180000.00"}]',
        created_at=datetime(2026, 5, 9, 14, 48, 45, tzinfo=UTC),
    )
    newer = PricingChangeLog(
        property_id=property_id,
        property_name="Hotel Test",
        room_type_id=room_type_id,
        room_type_name="Standard",
        rate_plan_id=rate_plan_id,
        rate_plan_name="Standard",
        currency="COP",
        start_date=date(2026, 5, 9),
        end_date=date(2026, 5, 12),
        previous_base_price="175000.00",
        new_base_price="170000.00",
        final_price="170000.00",
        projected_revenue_before="90.00",
        projected_revenue_after="80.00",
        actor_user_id=uuid4(),
        actor_email="hotel-a@travelhub.demo",
        previous_calendar_snapshot='[{"date":"2026-05-10","existed":true,"price":"175000.00"}]',
        created_at=datetime(2026, 5, 9, 14, 48, 47, tzinfo=UTC),
    )
    session.add(older)
    session.add(newer)
    session.commit()

    repository = SQLModelPricingManagementRepository(session)

    with pytest.raises(PricingConflictError):
        repository.revert_change(older.id, {property_id})
