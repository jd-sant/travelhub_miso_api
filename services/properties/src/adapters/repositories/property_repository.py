import json
import math
from typing import Optional
from urllib.parse import urlparse, urlunparse
from uuid import UUID

from sqlalchemy import func
from sqlmodel import Session, select

from adapters.models.property import Property
from adapters.models.property_cancellation_policy import PropertyCancellationPolicy
from adapters.models.property_image import PropertyImage
from adapters.models.property_review import PropertyReview
from adapters.models.property_seasonal_price import PropertySeasonalPrice
from domain.ports.property_repository import PropertyRepository
from domain.schemas.property import (
    PaginationMeta,
    PropertyFilters,
    PropertyResponse,
    PropertyImage as PropertyImageSchema,
    PropertyReview as PropertyReviewSchema,
    PropertyListResponse,
    PropertySearchResponse,
    PropertySortBy,
    PropertySortDir,
)
from domain.schemas.property_policy import (
    PropertyCancellationPolicyResponse,
    CancellationPolicyType,
)
from core.config import settings


def _rewrite_asset_url(url: str | None) -> str | None:
    if not url or not settings.asset_cdn_enabled:
        return url

    original = urlparse(url)
    cdn = urlparse(settings.asset_cdn_base_url or "")
    if not original.scheme or not original.netloc or not cdn.scheme or not cdn.netloc:
        return url

    return urlunparse(
        (
            cdn.scheme,
            cdn.netloc,
            original.path,
            original.params,
            original.query,
            original.fragment,
        )
    )


def _to_response(
    model: Property,
    images: list[PropertyImage] | None = None,
    reviews: list[PropertyReview] | None = None,
    price_override: float | None = None,
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
            url=_rewrite_asset_url(img.url) or img.url,
            alt_text=img.alt_text,
            position=img.position,
            url_hires=_rewrite_asset_url(img.url_hires),
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

    has_discount = price_override is not None and price_override < model.price_per_night
    effective_price = (
        price_override if price_override is not None else model.price_per_night
    )

    return PropertyResponse(
        id=model.id,
        id_owner=model.id_owner,
        name=model.name,
        description=model.description,
        location=model.location,
        latitude=model.latitude,
        longitude=model.longitude,
        price_per_night=effective_price,
        base_price_per_night=model.price_per_night if has_discount else None,
        has_seasonal_discount=has_discount,
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
    price_override: float | None = None,
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
            url=_rewrite_asset_url(img.url) or img.url,
            alt_text=img.alt_text,
            position=img.position,
            url_hires=_rewrite_asset_url(img.url_hires),
            is_cover=img.is_cover,
        )
        for img in (images or [])
    ]

    has_discount = price_override is not None and price_override < model.price_per_night
    effective_price = price_override if price_override is not None else model.price_per_night

    return PropertyListResponse(
        id=model.id,
        id_owner=model.id_owner,
        name=model.name,
        description=model.description,
        location=model.location,
        latitude=model.latitude,
        longitude=model.longitude,
        price_per_night=effective_price,
        base_price_per_night=model.price_per_night if has_discount else None,
        has_seasonal_discount=has_discount,
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

    def _resolve_seasonal_overrides(
        self,
        property_ids: list[UUID],
        check_in,  # date | None
        check_out,  # date | None
    ) -> dict[UUID, float]:
        """Return {property_id -> overridden price_per_night} for the given range.

        Hierarchy: when several non-locked rules cover the range,
        the cheapest one wins (best for the customer). Locked rules are skipped.
        """
        if check_in is None or check_out is None or not property_ids:
            return {}
        rows = self.session.exec(
            select(PropertySeasonalPrice)
            .where(PropertySeasonalPrice.property_id.in_(property_ids))
            .where(PropertySeasonalPrice.season_start <= check_in)
            .where(PropertySeasonalPrice.season_end >= check_out)
            .where(PropertySeasonalPrice.integrity_locked == False)  # noqa: E712
        ).all()
        overrides: dict[UUID, float] = {}
        for row in rows:
            current = overrides.get(row.property_id)
            if current is None or row.price_per_night < current:
                overrides[row.property_id] = row.price_per_night
        return overrides

    def get_by_id(
        self,
        property_id: UUID,
        check_in=None,  # date | None
        check_out=None,  # date | None
    ) -> Optional[PropertyResponse]:
        """Get property with all related data. When `check_in`/`check_out` are
        provided, applies the same seasonal override logic as `search()` so the
        detail page reflects the price the customer would actually be charged.
        """
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

        override = self._resolve_seasonal_overrides(
            [property_id], check_in, check_out
        ).get(property_id)
        return _to_response(model, images, reviews, price_override=override)

    def list_all(
        self, owner_id: UUID | None = None
    ) -> list[PropertyListResponse]:
        """List properties with their images, optionally filtered by owner."""
        statement = select(Property)
        if owner_id is not None:
            statement = statement.where(Property.id_owner == owner_id)
        models = self.session.exec(statement).all()

        result = []
        for model in models:
            images = self.session.exec(
                select(PropertyImage)
                .where(PropertyImage.property_id == model.id)
                .order_by(PropertyImage.position)
            ).all()
            result.append(_to_list_response(model, images))

        return result

    def search(self, filters: PropertyFilters) -> PropertySearchResponse:
        """Search properties with filters, sort and pagination."""
        statement = select(Property)
        count_statement = select(func.count()).select_from(Property)

        conditions = []
        if filters.status is not None:
            conditions.append(Property.status == filters.status)
        if filters.city:
            pattern = f"%{filters.city.lower()}%"
            dialect = self.session.bind.dialect.name if self.session.bind else ""
            if dialect == "postgresql":
                # Accent-insensitive: needs the `unaccent` extension (see init-schemas.sql).
                conditions.append(
                    func.lower(func.unaccent(Property.location)).like(
                        func.lower(func.unaccent(pattern))
                    )
                )
            else:
                conditions.append(func.lower(Property.location).like(pattern))
        if filters.min_price is not None:
            conditions.append(Property.price_per_night >= filters.min_price)
        if filters.max_price is not None:
            conditions.append(Property.price_per_night <= filters.max_price)
        if filters.min_guests is not None:
            conditions.append(Property.max_guests >= filters.min_guests)
        if filters.ids:
            conditions.append(Property.id.in_(filters.ids))
        if filters.min_lat is not None:
            conditions.append(Property.latitude >= filters.min_lat)
        if filters.max_lat is not None:
            conditions.append(Property.latitude <= filters.max_lat)
        if filters.min_lng is not None:
            conditions.append(Property.longitude >= filters.min_lng)
        if filters.max_lng is not None:
            conditions.append(Property.longitude <= filters.max_lng)
        for amenity in filters.amenities:
            pattern = f"%{amenity.lower()}%"
            conditions.append(func.lower(Property.amenities).like(pattern))

        for cond in conditions:
            statement = statement.where(cond)
            count_statement = count_statement.where(cond)

        sort_column = {
            PropertySortBy.PRICE: Property.price_per_night,
            PropertySortBy.RATING: Property.rating,
            PropertySortBy.NAME: Property.name,
        }[filters.sort_by]
        statement = statement.order_by(
            sort_column.desc() if filters.sort_dir == PropertySortDir.DESC else sort_column.asc()
        )

        offset = (filters.page - 1) * filters.page_size
        statement = statement.offset(offset).limit(filters.page_size)

        total = self.session.exec(count_statement).one()
        if isinstance(total, tuple):
            total = total[0]

        models = self.session.exec(statement).all()
        items: list[PropertyListResponse] = []

        seasonal_override = self._resolve_seasonal_overrides(
            [m.id for m in models], filters.check_in, filters.check_out
        )

        for model in models:
            images = self.session.exec(
                select(PropertyImage)
                .where(PropertyImage.property_id == model.id)
                .order_by(PropertyImage.position)
            ).all()
            items.append(
                _to_list_response(
                    model, images,
                    price_override=seasonal_override.get(model.id),
                )
            )

        total_pages = max(1, math.ceil(total / filters.page_size)) if total > 0 else 0
        return PropertySearchResponse(
            items=items,
            pagination=PaginationMeta(
                total=total,
                page=filters.page,
                page_size=filters.page_size,
                total_pages=total_pages,
            ),
        )

    def get_cancellation_policy(
        self, property_id: UUID
    ) -> Optional[PropertyCancellationPolicyResponse]:
        model = self.session.exec(
            select(PropertyCancellationPolicy)
            .where(PropertyCancellationPolicy.property_id == property_id)
            .where(PropertyCancellationPolicy.is_active.is_(True))
        ).first()
        return _to_policy_response(model) if model else None
