from uuid import uuid4

import pytest
from sqlmodel import Session

from adapters.models.property import Property
from adapters.models.property_image import PropertyImage
from adapters.models.property_review import PropertyReview
from adapters.repositories.property_repository import (
    SQLModelPropertyRepository,
)
from domain.use_cases.get_property_detail import (
    GetPropertyDetailUseCase,
)
from domain.use_cases.get_properties_list import (
    GetPropertiesListUseCase,
)
from errors import PropertyNotFoundError


def test_list_properties_success(session: Session):
    """Test listing all properties - should have 5 seeded properties"""
    repository = SQLModelPropertyRepository(session)
    use_case = GetPropertiesListUseCase(repository)

    result = use_case.execute()

    # Should have 5 seeded properties
    assert len(result) == 5
    names = {prop.name for prop in result}
    assert "Mansión Renacentista & Viñedo Privado" in names
    assert "Penthouse Moderno Frente a la Playa" in names
    assert "Refugio Alpino de Montaña" in names
    assert "Villa Paraíso Tropical" in names


def test_get_property_detail_with_images_and_reviews(session: Session):
    """Test getting property detail with images and reviews"""
    # Get first property from seeded data
    repository = SQLModelPropertyRepository(session)
    
    # List to get a property ID
    properties = repository.list_all()
    assert len(properties) > 0
    
    first_prop = properties[0]
    
    # Get detail
    detail = repository.get_by_id(first_prop.id)
    assert detail is not None
    assert detail.id == first_prop.id
    
    # Check that images are loaded
    assert len(detail.images) > 0
    # Images should be ordered by position
    for i, img in enumerate(detail.images[:-1]):
        assert img.position <= detail.images[i + 1].position
    
    # Check that reviews are loaded
    assert len(detail.reviews) > 0


def test_get_property_detail_not_found(session: Session):
    """Test getting property detail when not found"""
    repository = SQLModelPropertyRepository(session)
    use_case = GetPropertyDetailUseCase(repository)

    non_existent_id = uuid4()

    with pytest.raises(PropertyNotFoundError):
        use_case.execute(non_existent_id)


def test_property_detail_has_all_fields(session: Session):
    """Test that property detail response has all required fields"""
    repository = SQLModelPropertyRepository(session)
    properties = repository.list_all()
    
    assert len(properties) > 0
    prop = properties[0]
    
    # Check all required fields
    assert prop.id is not None
    assert prop.name is not None
    assert prop.description is not None
    assert prop.location is not None
    assert prop.price_per_night is not None
    assert prop.currency is not None
    assert prop.rating is not None
    assert prop.review_count >= 0
    assert prop.bedrooms >= 0
    assert prop.bathrooms >= 0
    assert prop.max_guests >= 0
    assert isinstance(prop.amenities, list)
    assert len(prop.amenities) > 0
