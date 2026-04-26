from datetime import date

from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

from adapters.models.property import Property
from adapters.models.property_cancellation_policy import PropertyCancellationPolicy
from adapters.models.property_image import PropertyImage
from adapters.models.property_review import PropertyReview
from db.seed import (
    CIKOS_EXECUTIVE_SUITES_ID,
    DEMO_HOTEL_A_OWNER_ID,
    RENAISSANCE_ESTATE_ID,
    sync_demo_properties_seed,
)


def _engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


def test_seed_includes_cikos_property_for_demo_hotel_a():
    engine = _engine()

    with Session(engine) as session:
        sync_demo_properties_seed(session)

        property_row = session.get(Property, CIKOS_EXECUTIVE_SUITES_ID)
        assert property_row is not None
        assert property_row.id_owner == DEMO_HOTEL_A_OWNER_ID
        assert property_row.name == "Hotel Cikos Executive Suites"

        images = session.exec(
            select(PropertyImage).where(PropertyImage.property_id == CIKOS_EXECUTIVE_SUITES_ID)
        ).all()
        reviews = session.exec(
            select(PropertyReview).where(PropertyReview.property_id == CIKOS_EXECUTIVE_SUITES_ID)
        ).all()
        policy = session.exec(
            select(PropertyCancellationPolicy).where(
                PropertyCancellationPolicy.property_id == CIKOS_EXECUTIVE_SUITES_ID
            )
        ).first()

        assert len(images) == 5
        assert len(reviews) == 2
        assert policy is not None
        assert policy.timezone == "America/Bogota"


def test_seed_adds_missing_demo_property_even_when_database_is_not_empty():
    engine = _engine()

    with Session(engine) as session:
        session.add(
            Property(
                id=RENAISSANCE_ESTATE_ID,
                id_owner=DEMO_HOTEL_A_OWNER_ID,
                name="Placeholder",
                description="Placeholder",
                location="Placeholder",
                latitude=0,
                longitude=0,
                price_per_night=1,
                currency="COP",
                rating=1,
                review_count=0,
                bedrooms=1,
                bathrooms=1,
                max_guests=1,
                amenities="[]",
                status=1,
                cancellation_policy="Placeholder",
                tax_rate=0,
                cleaning_fee=0,
            )
        )
        session.commit()

        sync_demo_properties_seed(session)

        property_row = session.get(Property, CIKOS_EXECUTIVE_SUITES_ID)
        assert property_row is not None
        assert property_row.id_owner == DEMO_HOTEL_A_OWNER_ID


def test_seed_updates_existing_demo_review_and_image_text():
    engine = _engine()

    with Session(engine) as session:
        sync_demo_properties_seed(session)

        review = session.exec(
            select(PropertyReview).where(
                PropertyReview.property_id == CIKOS_EXECUTIVE_SUITES_ID,
                PropertyReview.review_date == date(2024, 9, 18),
            )
        ).first()
        image = session.exec(
            select(PropertyImage).where(
                PropertyImage.property_id == CIKOS_EXECUTIVE_SUITES_ID,
                PropertyImage.position == 3,
            )
        ).first()

        assert review is not None
        assert image is not None

        review.author = "Laura SÃ¡nchez"
        review.comment = "Excelente opciÃ³n en BogotÃ¡"
        image.alt_text = "Lobby y recepciÃ³n"
        session.add(review)
        session.add(image)
        session.commit()

        sync_demo_properties_seed(session)

        updated_review = session.exec(
            select(PropertyReview).where(
                PropertyReview.property_id == CIKOS_EXECUTIVE_SUITES_ID,
                PropertyReview.review_date == date(2024, 9, 18),
            )
        ).first()
        updated_image = session.exec(
            select(PropertyImage).where(
                PropertyImage.property_id == CIKOS_EXECUTIVE_SUITES_ID,
                PropertyImage.position == 3,
            )
        ).first()

        assert updated_review is not None
        assert updated_review.author == "Laura Sánchez"
        assert "Bogotá" in updated_review.comment
        assert updated_image is not None
        assert updated_image.alt_text == "Lobby y recepción"
