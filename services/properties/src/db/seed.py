"""Database initialization utilities for properties service"""
import os
import json
from uuid import UUID
from sqlmodel import Session, select

from adapters.models.property import Property
from adapters.models.property_image import PropertyImage
from adapters.models.property_review import PropertyReview


# Property IDs (using fixed UUIDs for frontend to use)
RENAISSANCE_ESTATE_ID = UUID("11111111-1111-1111-1111-111111111111")
BEACHFRONT_PENTHOUSE_ID = UUID("22222222-2222-2222-2222-222222222222")
ALPINE_LODGE_ID = UUID("33333333-3333-3333-3333-333333333333")
TROPICAL_VILLA_ID = UUID("44444444-4444-4444-4444-444444444444")


PROPERTIES_DATA = [
    {
        "id": RENAISSANCE_ESTATE_ID,
        "name": "Renaissance Estate & Private Vineyard",
        "description": "Experience the timeless elegance of this 18th-century Renaissance estate, nestled in the heart of scenic working vineyard just outside Florence. The villa has been meticulously restored to blend historic character with ultra-modern luxury. This historic property boasts 4 luxurious bedrooms with en-suite bathrooms, each decorated with period furnishings and modern amenities.",
        "location": "Fiesole, Florence",
        "latitude": 43.8047,
        "longitude": 11.2844,
        "price_per_night": 1240.0,
        "currency": "COP",
        "rating": 4.98,
        "review_count": 54,
        "bedrooms": 4,
        "bathrooms": 4.5,
        "max_guests": 12,
        "amenities": [
            "Private Infinity Pool",
            "High-speed Fiber WiFi",
            "Private Vineyard Access",
            "Professional Kitchen",
            "Free Valet Parking",
            "Climate Control",
            "Smart Home System",
            "Wine Cellar"
        ],
        "images": [
            ("1", "/mock/property-1.svg", "Renaissance Estate Main View", 0),
            ("2", "/mock/property-2.svg", "Bedroom", 1),
            ("3", "/mock/property-3.svg", "Bathroom", 2),
            ("4", "/mock/property-4.svg", "Dining Room", 3),
            ("5", "/mock/property-5.svg", "Living Area", 4),
        ],
        "reviews": [
            ("Sarah Holkins", 5, "September 2024", "This was the highlight of my entire vacation! Amazing property with incredible attention to detail. Highly recommend!"),
            ("Marc Thompson", 5, "August 2024", "Stunning location and exceptional service. The host went above and beyond to make our stay perfect. Will definitely return!"),
        ],
    },
    {
        "id": BEACHFRONT_PENTHOUSE_ID,
        "name": "Modern Beachfront Penthouse",
        "description": "Stunning contemporary penthouse with direct beach access and panoramic ocean views. This ultra-modern property features floor-to-ceiling windows, minimalist design, and state-of-the-art technology. Wake up to the sound of waves while enjoying your morning coffee on the spacious terrace.",
        "location": "Miami Beach, Florida",
        "latitude": 25.7907,
        "longitude": -80.1300,
        "price_per_night": 2150.0,
        "currency": "USD",
        "rating": 4.87,
        "review_count": 42,
        "bedrooms": 3,
        "bathrooms": 3.0,
        "max_guests": 8,
        "amenities": [
            "Private Beach Access",
            "360° Panoramic Views",
            "Smart Home Automation",
            "Chef Kitchen",
            "Wine Cooler",
            "Sauna & Steam Room",
            "Concierge Service",
            "Rooftop Terrace"
        ],
        "images": [
            ("1", "/mock/property-2.svg", "Beachfront View", 0),
            ("2", "/mock/property-1.svg", "Master Bedroom", 1),
            ("3", "/mock/property-4.svg", "Modern Bathroom", 2),
            ("4", "/mock/property-3.svg", "Living Room", 3),
            ("5", "/mock/property-5.svg", "Terrace View", 4),
        ],
        "reviews": [
            ("Sarah Holkins", 5, "September 2024", "This was the highlight of my entire vacation! Amazing property with incredible attention to detail. Highly recommend!"),
            ("Marc Thompson", 5, "August 2024", "Stunning location and exceptional service. The host went above and beyond to make our stay perfect. Will definitely return!"),
        ],
    },
    {
        "id": ALPINE_LODGE_ID,
        "name": "Alpine Mountain Lodge",
        "description": "Cozy luxury mountain lodge surrounded by pristine alpine scenery and snow-capped peaks. Perfect retreat for hiking, skiing, or simply relaxing by the fireplace. This incredible property is surrounded by lush alpine views and offers direct access to mountain activities.",
        "location": "Chamonix, French Alps",
        "latitude": 45.9237,
        "longitude": 6.8694,
        "price_per_night": 890.0,
        "currency": "EUR",
        "rating": 4.92,
        "review_count": 67,
        "bedrooms": 5,
        "bathrooms": 4.0,
        "max_guests": 14,
        "amenities": [
            "Stone Fireplace",
            "Mountain Views",
            "Ski Storage",
            "Heated Sauna",
            "Ski In/Out Access",
            "Game Room",
            "Wine Cellar",
            "Library"
        ],
        "images": [
            ("1", "/mock/property-5.svg", "Mountain Lodge Exterior", 0),
            ("2", "/mock/property-3.svg", "Cozy Living Room", 1),
            ("3", "/mock/property-2.svg", "Luxury Bathroom", 2),
            ("4", "/mock/property-4.svg", "Dining Area", 3),
            ("5", "/mock/property-1.svg", "Mountain View", 4),
        ],
        "reviews": [
            ("Emily Rodriguez", 5, "July 2024", "Perfect mountain retreat! The fireplace and views are absolutely stunning. Perfect for a winter getaway."),
            ("James Chen", 5, "June 2024", "Best ski-in/ski-out experience I've had. The lodge is cozy and the service is impeccable."),
        ],
    },
    {
        "id": TROPICAL_VILLA_ID,
        "name": "Tropical Paradise Villa",
        "description": "Exotic beach villa with direct access to white sand beaches and turquoise waters. This incredible property is surrounded by lush tropical gardens, palm trees, and exotic flowers. Wake up to the sounds of nature and enjoy the perfect tropical escape.",
        "location": "Bora Bora, French Polynesia",
        "latitude": -16.5004,
        "longitude": -151.7415,
        "price_per_night": 1650.0,
        "currency": "USD",
        "rating": 4.99,
        "review_count": 89,
        "bedrooms": 4,
        "bathrooms": 4.0,
        "max_guests": 10,
        "amenities": [
            "Beach Front",
            "Infinity Pool",
            "Outdoor Shower",
            "Water Sports Equipment",
            "Tropical Gardens",
            "Tiki Bar",
            "Aerial Pavilion",
            "Snorkel Access"
        ],
        "images": [
            ("1", "/mock/property-4.svg", "Tropical Beach", 0),
            ("2", "/mock/property-2.svg", "Bedroom Bungalow", 1),
            ("3", "/mock/property-1.svg", "Outdoor Bathroom", 2),
            ("4", "/mock/property-5.svg", "Infinity Pool", 3),
            ("5", "/mock/property-3.svg", "Sunset View", 4),
        ],
        "reviews": [
            ("Sarah Holkins", 5, "September 2024", "Paradise found! This villa exceeded all my expectations. The beach access is incredible!"),
            ("Marc Thompson", 5, "August 2024", "Best vacation ever! The tropical setting and amenities are world-class. Definitely coming back!"),
        ],
    },
]


def seed_properties_if_empty(session: Session) -> None:
    """Seed database with sample properties if empty"""
    # Check if properties already exist
    existing = session.exec(select(Property).limit(1)).first()
    if existing:
        return

    try:
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

    except Exception as e:
        session.rollback()
        raise
