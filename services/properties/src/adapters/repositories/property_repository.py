import json
from typing import Optional
from uuid import UUID

from sqlmodel import Session, select

from adapters.models.property import Property
from adapters.models.property_cancellation_policy import PropertyCancellationPolicy
from adapters.models.property_image import PropertyImage
from adapters.models.property_review import PropertyReview
from domain.ports.property_repository import PropertyRepository
from domain.schemas.property import (
    PropertyResponse,
    PropertyImage as PropertyImageSchema,
    PropertyReview as PropertyReviewSchema,
    PropertyListResponse,
)
from domain.schemas.property_policy import (
    PropertyCancellationPolicyResponse,
    CancellationPolicyType,
)


def _to_response(
    model: Property,
    images: list[PropertyImage] | None = None,
    reviews: list[PropertyReview] | None = None,
) -> PropertyResponse:
    """Convert Property model to PropertyResponse"""
    # Parse amenities from JSON string
    amenities = []
    try:
        amenities = json.loads(model.amenities) if model.amenities else []
    except json.JSONDecodeError:
        amenities = []

    # Convert images
    image_list = [
        PropertyImageSchema(
            id=str(img.id),
            url=img.url,
            alt_text=img.alt_text,
            position=img.position,
            url_hires=img.url_hires,
            is_cover=img.is_cover,
        )
        for img in (images or [])
    ]

    # Convert reviews
    review_list = [
        PropertyReviewSchema(
            id=str(rev.id),
            author=rev.author,
            rating=rev.rating,
            review_date=rev.review_date,
            comment=rev.comment,
            verified_stay=rev.verified_stay,
        )
        for rev in (reviews or [])
    ]

    return PropertyResponse(
        id=model.id,
        name=model.name,
        description=model.description,
        location=model.location,
        latitude=model.latitude,
        longitude=model.longitude,
        price_per_night=model.price_per_night,
        currency=model.currency,
        rating=model.rating,
        review_count=model.review_count,
        bedrooms=model.bedrooms,
        bathrooms=model.bathrooms,
        max_guests=model.max_guests,
        amenities=amenities,
        cancellation_policy=model.cancellation_policy,
        tax_rate=model.tax_rate,
        cleaning_fee=model.cleaning_fee,
        status=model.status,
        images=image_list,
        reviews=review_list,
    )


def _to_list_response(
    model: Property,
    images: list[PropertyImage] | None = None,
) -> PropertyListResponse:
    """Convert Property model to PropertyListResponse (without reviews)"""
    # Parse amenities from JSON string
    amenities = []
    try:
        amenities = json.loads(model.amenities) if model.amenities else []
    except json.JSONDecodeError:
        amenities = []

    # Convert images
    image_list = [
        PropertyImageSchema(
            id=str(img.id),
            url=img.url,
            alt_text=img.alt_text,
            position=img.position,
            url_hires=img.url_hires,
            is_cover=img.is_cover,
        )
        for img in (images or [])
    ]

    return PropertyListResponse(
        id=model.id,
        name=model.name,
        description=model.description,
        location=model.location,
        latitude=model.latitude,
        longitude=model.longitude,
        price_per_night=model.price_per_night,
        currency=model.currency,
        rating=model.rating,
        review_count=model.review_count,
        bedrooms=model.bedrooms,
        bathrooms=model.bathrooms,
        max_guests=model.max_guests,
        amenities=amenities,
        cancellation_policy=model.cancellation_policy,
        tax_rate=model.tax_rate,
        cleaning_fee=model.cleaning_fee,
        status=model.status,
        images=image_list,
    )


def _to_policy_response(model: PropertyCancellationPolicy) -> PropertyCancellationPolicyResponse:
    return PropertyCancellationPolicyResponse(
        property_id=model.property_id,
        policy_type=CancellationPolicyType(model.policy_type),
        minimum_notice_hours=model.minimum_notice_hours,
        penalty_percentage=model.penalty_percentage,
        timezone=model.timezone,
        is_active=model.is_active,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class SQLModelPropertyRepository(PropertyRepository):
    def __init__(self, session: Session):
        self.session = session

    def get_by_id(self, property_id: UUID) -> Optional[PropertyResponse]:
        """Get property with all related data (images and reviews)"""
        model = self.session.exec(
            select(Property).where(Property.id == property_id)
        ).first()
        
        if not model:
            return None

        # Load related images
        images = self.session.exec(
            select(PropertyImage)
            .where(PropertyImage.property_id == property_id)
            .order_by(PropertyImage.position)
        ).all()

        # Load related reviews
        reviews = self.session.exec(
            select(PropertyReview).where(PropertyReview.property_id == property_id)
        ).all()

        return _to_response(model, images, reviews)

    def list_all(self) -> list[PropertyListResponse]:
        """List all properties with their images"""
        models = self.session.exec(select(Property)).all()
        
        result = []
        for model in models:
            # Load related images for each property
            images = self.session.exec(
                select(PropertyImage)
                .where(PropertyImage.property_id == model.id)
                .order_by(PropertyImage.position)
            ).all()
            result.append(_to_list_response(model, images))
        
        return result

    def get_cancellation_policy(
        self, property_id: UUID
    ) -> Optional[PropertyCancellationPolicyResponse]:
        model = self.session.exec(
            select(PropertyCancellationPolicy)
            .where(PropertyCancellationPolicy.property_id == property_id)
            .where(PropertyCancellationPolicy.is_active.is_(True))
        ).first()
        return _to_policy_response(model) if model else None
