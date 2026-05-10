"""
Tests for cache invalidation functionality on seasonal pricing updates.
"""

from unittest.mock import Mock
from uuid import uuid4

import pytest

from adapters.repositories.cached_property_repository import CachedPropertyRepository


class TestCacheInvalidation:
    """Test cache invalidation on seasonal pricing operations."""

    def test_invalidate_property_caches_exists(self):
        """Verify invalidate_property_caches method exists on cached repository."""
        base_repo = Mock()
        mock_cache = Mock()
        cached_repo = CachedPropertyRepository(base_repo, cache=mock_cache)
        
        # Verify method exists
        assert hasattr(cached_repo, 'invalidate_property_caches')
        assert callable(cached_repo.invalidate_property_caches)

    def test_invalidate_property_caches_no_cache(self):
        """Should handle gracefully when no cache is configured."""
        base_repo = Mock()
        cached_repo = CachedPropertyRepository(base_repo, cache=None)
        
        property_id = uuid4()
        # Should not raise exception
        cached_repo.invalidate_property_caches(property_id)

    def test_invalidate_property_caches_with_cache(self):
        """Should delete detail and list caches for property."""
        base_repo = Mock()
        mock_cache = Mock()
        cached_repo = CachedPropertyRepository(base_repo, cache=mock_cache)
        
        property_id = uuid4()
        cached_repo.invalidate_property_caches(property_id)
        
        # Verify cache.delete was called
        assert mock_cache.delete.called
        
        # Verify the right keys were invalidated
        calls = mock_cache.delete.call_args_list
        called_keys = [call[0][0] for call in calls]
        
        assert f"properties:detail:{property_id}" in called_keys
        assert "properties:list:all" in called_keys

    def test_invalidate_multiple_properties(self):
        """Should independently handle multiple property cache invalidations."""
        base_repo = Mock()
        mock_cache = Mock()
        cached_repo = CachedPropertyRepository(base_repo, cache=mock_cache)
        
        property_id_1 = uuid4()
        property_id_2 = uuid4()
        
        cached_repo.invalidate_property_caches(property_id_1)
        cached_repo.invalidate_property_caches(property_id_2)
        
        # Verify both properties were processed
        calls = mock_cache.delete.call_args_list
        assert len(calls) >= 4  # 2 calls per property (detail + list)
        
        called_keys = [call[0][0] for call in calls]
        assert f"properties:detail:{property_id_1}" in called_keys
        assert f"properties:detail:{property_id_2}" in called_keys
