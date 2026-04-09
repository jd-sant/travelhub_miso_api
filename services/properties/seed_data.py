"""
Seed script for properties service.
Run this after database initialization to populate with sample data.

Usage:
    PYTHONPATH=src python seed_data.py
"""
import json
from sqlmodel import Session, create_engine
from sqlalchemy.orm import sessionmaker

from adapters.models.property import Property
from adapters.models.property_image import PropertyImage
from adapters.models.property_review import PropertyReview
from core.config import settings
from db.seed import PROPERTIES_DATA

# Use the configured database URL
engine = create_engine(settings.database_url, echo=False)
SessionLocal = sessionmaker(bind=engine, class_=Session)


def seed_properties():
    """Seed the database with sample properties"""
    session = SessionLocal()
    
    try:
        # Check if data already exists
        existing = session.query(Property).first()
        if existing:
            print("Properties already exist in database. Skipping seed.")
            return

        # Add all properties
        for prop_data in PROPERTIES_DATA:
            property_obj = Property(
                id=prop_data["id"],
                name=prop_data["name"],
                description=prop_data["description"],
                location=prop_data["location"],
                latitude=prop_data["latitude"],
                longitude=prop_data["longitude"],
                price_per_night=prop_data["price_per_night"],
                currency=prop_data["currency"],
                rating=prop_data["rating"],
                review_count=prop_data["review_count"],
                bedrooms=prop_data["bedrooms"],
                bathrooms=prop_data["bathrooms"],
                max_guests=prop_data["max_guests"],
                amenities=json.dumps(prop_data["amenities"]),
                status=1,
            )
            session.add(property_obj)

        session.commit()

        # Add images
        for prop_data in PROPERTIES_DATA:
            for img_id, url, alt_text, position in prop_data["images"]:
                image = PropertyImage(
                    property_id=prop_data["id"],
                    url=url,
                    alt_text=alt_text,
                    position=position,
                )
                session.add(image)

        session.commit()

        # Add reviews
        for prop_data in PROPERTIES_DATA:
            for author, rating, date, comment in prop_data["reviews"]:
                review = PropertyReview(
                    property_id=prop_data["id"],
                    author=author,
                    rating=rating,
                    date=date,
                    comment=comment,
                    verified_stay=True,
                )
                session.add(review)

        session.commit()
        print("✓ Properties seeded successfully!")

    except Exception as e:
        session.rollback()
        print(f"✗ Error seeding properties: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    seed_properties()
