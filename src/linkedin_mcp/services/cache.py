"""
In-memory caching service for LinkedIn MCP Server.

Provides TTL-based caching to reduce API calls and improve response times.
"""

import asyncio
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any, ParamSpec, TypeVar

from linkedin_mcp.core.logging import get_logger

logger = get_logger(__name__)

P = ParamSpec("P")
R = TypeVar("R")


class CacheEntry:
    """Single cache entry with TTL."""

    __slots__ = ("value", "expires_at", "hits")

    def __init__(self, value: Any, ttl_seconds: int) -> None:
        self.value = value
        self.expires_at = datetime.now() + timedelta(seconds=ttl_seconds)
        self.hits = 0

    @property
    def is_expired(self) -> bool:
        return datetime.now() > self.expires_at

    def access(self) -> Any:
        self.hits += 1
        return self.value


class CacheService:
    """
    In-memory cache with TTL support.

    Features:
    - Configurable TTL per entry
    - Automatic expiration cleanup
    - Hit tracking for analytics
    - Thread-safe operations
    """

    # Default TTL values by category (in seconds)
    TTL_PROFILE = 3600  # 1 hour
    TTL_FEED = 300  # 5 minutes
    TTL_POSTS = 600  # 10 minutes
    TTL_CONNECTIONS = 1800  # 30 minutes
    TTL_SEARCH = 900  # 15 minutes
    TTL_ANALYTICS = 120  # 2 minutes
    TTL_COMPANY = 7200  # 2 hours
    TTL_ARTICLES = 3600  # 1 hour

    def __init__(self, default_ttl: int = 300, max_size: int = 1000) -> None:
        self._cache: dict[str, CacheEntry] = {}
        self._default_ttl = default_ttl
        self._max_size = max_size
        self._lock = asyncio.Lock()
        self._total_hits = 0
        self._total_misses = 0

    async def get(self, key: str) -> Any | None:
        """
        Get a value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        async with self._lock:
            entry = self._cache.get(key)

            if entry is None:
                self._total_misses += 1
                return None

            if entry.is_expired:
                del self._cache[key]
                self._total_misses += 1
                return None

            self._total_hits += 1
            return entry.access()

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
    ) -> None:
        """
        Set a value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (uses default if not specified)
        """
        async with self._lock:
            # Evict if at capacity
            if len(self._cache) >= self._max_size:
                await self._evict_expired()

                # If still at capacity, remove oldest
                if len(self._cache) >= self._max_size:
                    oldest_key = next(iter(self._cache))
                    del self._cache[oldest_key]

            self._cache[key] = CacheEntry(value, ttl or self._default_ttl)

    async def delete(self, key: str) -> bool:
        """
        Delete a cache entry.

        Args:
            key: Cache key

        Returns:
            True if deleted, False if not found
        """
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    async def clear(self) -> int:
        """
        Clear all cache entries.

        Returns:
            Number of entries cleared
        """
        async with self._lock:
            count = len(self._cache)
            self._cache.clear()
            return count

    async def clear_pattern(self, pattern: str) -> int:
        """
        Clear cache entries matching a pattern.

        Args:
            pattern: Key prefix to match

        Returns:
            Number of entries cleared
        """
        async with self._lock:
            keys_to_delete = [k for k in self._cache if k.startswith(pattern)]
            for key in keys_to_delete:
                del self._cache[key]
            return len(keys_to_delete)

    async def _evict_expired(self) -> int:
        """Remove all expired entries."""
        expired = [k for k, v in self._cache.items() if v.is_expired]
        for key in expired:
            del self._cache[key]
        return len(expired)

    @property
    def stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        total_requests = self._total_hits + self._total_misses
        hit_rate = (self._total_hits / total_requests * 100) if total_requests > 0 else 0

        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "hits": self._total_hits,
            "misses": self._total_misses,
            "hit_rate": round(hit_rate, 2),
            "default_ttl": self._default_ttl,
        }

    def make_key(self, *parts: str) -> str:
        """
        Create a cache key from parts.

        Args:
            *parts: Key components

        Returns:
            Joined cache key
        """
        return ":".join(str(p) for p in parts)


# Global cache instance
_cache: CacheService | None = None


def get_cache() -> CacheService:
    """Get the global cache instance."""
    global _cache
    if _cache is None:
        _cache = CacheService()
    return _cache


def set_cache(cache: CacheService) -> None:
    """Set the global cache instance."""
    global _cache
    _cache = cache


async def cached(
    key: str,
    fetch_fn: Callable[[], Any],
    ttl: int | None = None,
) -> Any:
    """
    Get a value from cache or fetch and cache it.

    Args:
        key: Cache key
        fetch_fn: Async function to fetch value if not cached
        ttl: Optional TTL override

    Returns:
        Cached or freshly fetched value
    """
    cache = get_cache()

    # Try cache first
    value = await cache.get(key)
    if value is not None:
        logger.debug("Cache hit", key=key)
        return value

    # Fetch and cache
    logger.debug("Cache miss", key=key)
    value = await fetch_fn()
    await cache.set(key, value, ttl)
    return value
