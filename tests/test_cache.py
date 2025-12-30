"""Tests for the caching service."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from linkedin_mcp.services.cache import (
    CacheEntry,
    CacheService,
    cached,
    set_cache,
)


class TestCacheEntry:
    """Tests for CacheEntry."""

    def test_entry_creation(self) -> None:
        """Test creating a cache entry."""
        entry = CacheEntry("test_value", ttl_seconds=60)

        assert entry.value == "test_value"
        assert entry.hits == 0
        assert not entry.is_expired

    def test_entry_expiration(self) -> None:
        """Test cache entry expiration."""
        # Create entry with 0 TTL (immediately expired)
        entry = CacheEntry("test_value", ttl_seconds=0)

        # Should be expired
        assert entry.is_expired

    def test_entry_access_increments_hits(self) -> None:
        """Test that accessing an entry increments hits."""
        entry = CacheEntry("test_value", ttl_seconds=60)

        assert entry.hits == 0
        entry.access()
        assert entry.hits == 1
        entry.access()
        assert entry.hits == 2


class TestCacheService:
    """Tests for CacheService."""

    @pytest.fixture
    def cache(self) -> CacheService:
        """Create a fresh cache instance."""
        return CacheService(default_ttl=300, max_size=100)

    @pytest.mark.asyncio
    async def test_set_and_get(self, cache: CacheService) -> None:
        """Test basic set and get operations."""
        await cache.set("key1", "value1")
        result = await cache.get("key1")

        assert result == "value1"

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, cache: CacheService) -> None:
        """Test getting a nonexistent key."""
        result = await cache.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_expired(self, cache: CacheService) -> None:
        """Test getting an expired entry."""
        # Use TTL of 1 second and wait longer to ensure expiration
        await cache.set("key1", "value1", ttl=1)

        # Wait for entry to expire
        await asyncio.sleep(1.1)

        result = await cache.get("key1")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete(self, cache: CacheService) -> None:
        """Test deleting a cache entry."""
        await cache.set("key1", "value1")

        deleted = await cache.delete("key1")
        assert deleted is True

        result = await cache.get("key1")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, cache: CacheService) -> None:
        """Test deleting a nonexistent key."""
        deleted = await cache.delete("nonexistent")
        assert deleted is False

    @pytest.mark.asyncio
    async def test_clear(self, cache: CacheService) -> None:
        """Test clearing all cache entries."""
        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        await cache.set("key3", "value3")

        count = await cache.clear()
        assert count == 3

        assert await cache.get("key1") is None
        assert await cache.get("key2") is None
        assert await cache.get("key3") is None

    @pytest.mark.asyncio
    async def test_clear_pattern(self, cache: CacheService) -> None:
        """Test clearing entries by pattern."""
        await cache.set("user:1", "data1")
        await cache.set("user:2", "data2")
        await cache.set("post:1", "data3")

        count = await cache.clear_pattern("user:")
        assert count == 2

        assert await cache.get("user:1") is None
        assert await cache.get("user:2") is None
        assert await cache.get("post:1") == "data3"

    @pytest.mark.asyncio
    async def test_max_size_eviction(self) -> None:
        """Test that cache evicts entries when max size is reached."""
        cache = CacheService(default_ttl=300, max_size=3)

        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        await cache.set("key3", "value3")
        await cache.set("key4", "value4")

        # First key should be evicted
        assert await cache.get("key1") is None
        assert await cache.get("key4") == "value4"

    def test_stats(self, cache: CacheService) -> None:
        """Test cache statistics."""
        stats = cache.stats

        assert stats["size"] == 0
        assert stats["max_size"] == 100
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["hit_rate"] == 0
        assert stats["default_ttl"] == 300

    @pytest.mark.asyncio
    async def test_stats_tracking(self, cache: CacheService) -> None:
        """Test that stats are tracked correctly."""
        await cache.set("key1", "value1")

        # Hit
        await cache.get("key1")

        # Miss
        await cache.get("nonexistent")

        stats = cache.stats
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 50.0

    def test_make_key(self, cache: CacheService) -> None:
        """Test cache key generation."""
        key = cache.make_key("profile", "user123", "posts")
        assert key == "profile:user123:posts"


class TestCachedFunction:
    """Tests for the cached() helper function."""

    @pytest.fixture(autouse=True)
    def setup_cache(self) -> None:
        """Set up a fresh cache for each test."""
        set_cache(CacheService(default_ttl=300, max_size=100))

    @pytest.mark.asyncio
    async def test_cached_returns_fresh_value(self) -> None:
        """Test that cached() fetches and caches a value."""
        fetch_fn = AsyncMock(return_value="fetched_value")

        result = await cached("test_key", fetch_fn)

        assert result == "fetched_value"
        fetch_fn.assert_called_once()

    @pytest.mark.asyncio
    async def test_cached_returns_cached_value(self) -> None:
        """Test that cached() returns cached value on second call."""
        call_count = 0

        async def fetch_fn() -> str:
            nonlocal call_count
            call_count += 1
            return "fetched_value"

        # First call - fetches
        result1 = await cached("test_key", fetch_fn)
        assert result1 == "fetched_value"
        assert call_count == 1

        # Second call - uses cache
        result2 = await cached("test_key", fetch_fn)
        assert result2 == "fetched_value"
        assert call_count == 1  # Still 1, didn't fetch again


class TestTTLConstants:
    """Tests for TTL constant values."""

    def test_ttl_values(self) -> None:
        """Test that TTL constants are defined correctly."""
        assert CacheService.TTL_PROFILE == 3600
        assert CacheService.TTL_FEED == 300
        assert CacheService.TTL_POSTS == 600
        assert CacheService.TTL_CONNECTIONS == 1800
        assert CacheService.TTL_SEARCH == 900
        assert CacheService.TTL_ANALYTICS == 120
