"""
Unified LinkedIn data provider with intelligent fallback.

Orchestrates between multiple data sources to provide reliable
LinkedIn data access:

1. Primary: tomquirk/linkedin-api (fastest, most features)
2. Secondary: Enhanced HTTP client with curl_cffi (anti-detection)
3. Tertiary: Headless browser scraper (most reliable, slowest)

All operations happen in the background without any visible UI.
"""

import asyncio
from typing import Any

from linkedin_mcp.core.exceptions import (
    LinkedInAPIError,
    LinkedInAuthError,
    format_error_response,
)
from linkedin_mcp.core.logging import get_logger

logger = get_logger(__name__)


class LinkedInDataProvider:
    """
    Unified LinkedIn data provider with automatic fallback.

    This provider tries multiple data sources in order of speed,
    automatically falling back when one source fails due to blocking.

    All operations happen in the background - no visible browser windows.

    Usage:
        provider = LinkedInDataProvider(
            primary_client=linkedin_client,  # tomquirk/linkedin-api
            cookies={"li_at": "...", "JSESSIONID": "..."},
        )
        await provider.initialize()

        # Will try primary, then enhanced, then headless
        profile = await provider.get_profile("johndoe")
    """

    def __init__(
        self,
        primary_client: Any | None = None,
        cookies: dict[str, str] | None = None,
        enable_enhanced: bool = True,
        enable_headless: bool = True,
    ):
        """
        Initialize the data provider.

        Args:
            primary_client: tomquirk/linkedin-api client instance
            cookies: LinkedIn cookies for fallback clients
            enable_enhanced: Enable enhanced HTTP client with curl_cffi
            enable_headless: Enable headless browser scraper
        """
        self._primary = primary_client
        self._cookies = cookies or {}
        self._enable_enhanced = enable_enhanced
        self._enable_headless = enable_headless

        self._enhanced = None
        self._headless = None
        self._initialized = False

        # Track which sources are working
        self._source_status = {
            "primary": True,
            "enhanced": True,
            "headless": True,
        }

        # Failure counts for adaptive fallback
        self._failure_counts = {
            "primary": 0,
            "enhanced": 0,
            "headless": 0,
        }
        self._failure_threshold = 3  # Skip source after this many consecutive failures

    async def initialize(self) -> None:
        """Initialize all data sources."""
        if self._initialized:
            return

        # Initialize enhanced client if enabled and cookies available
        if self._enable_enhanced and self._cookies.get("li_at"):
            try:
                from linkedin_mcp.services.linkedin.enhanced_client import (
                    EnhancedLinkedInClient,
                )

                self._enhanced = EnhancedLinkedInClient(
                    cookies=self._cookies,
                    use_curl_cffi=True,
                )
                await self._enhanced.initialize()
                logger.info("Enhanced LinkedIn client initialized")
            except Exception as e:
                logger.warning("Failed to initialize enhanced client", error=str(e))
                self._source_status["enhanced"] = False

        # Note: Headless scraper is initialized lazily to save resources

        self._initialized = True
        logger.info(
            "LinkedIn data provider initialized",
            primary=self._primary is not None,
            enhanced=self._enhanced is not None,
            headless_enabled=self._enable_headless,
        )

    async def _init_headless_if_needed(self) -> bool:
        """Lazily initialize headless scraper when needed."""
        if self._headless is not None:
            return True

        if not self._enable_headless:
            return False

        if not self._cookies.get("li_at"):
            logger.warning("Cannot initialize headless scraper without cookies")
            return False

        try:
            from linkedin_mcp.services.linkedin.headless_scraper import (
                HeadlessLinkedInScraper,
            )

            self._headless = HeadlessLinkedInScraper(headless=True)
            await self._headless.initialize()
            await self._headless.set_cookies(
                li_at=self._cookies.get("li_at", ""),
                jsessionid=self._cookies.get("JSESSIONID"),
            )
            logger.info("Headless scraper initialized on demand")
            return True
        except Exception as e:
            logger.warning("Failed to initialize headless scraper", error=str(e))
            self._source_status["headless"] = False
            return False

    def _should_skip_source(self, source: str) -> bool:
        """Check if a source should be skipped due to repeated failures."""
        if not self._source_status.get(source, False):
            return True
        return self._failure_counts.get(source, 0) >= self._failure_threshold

    def _record_success(self, source: str) -> None:
        """Record successful request from source."""
        self._failure_counts[source] = 0
        self._source_status[source] = True

    def _record_failure(self, source: str, error: Exception) -> None:
        """Record failed request from source."""
        self._failure_counts[source] = self._failure_counts.get(source, 0) + 1
        logger.warning(
            f"Data source {source} failed",
            error=str(error),
            failure_count=self._failure_counts[source],
        )

        # Disable source if threshold reached
        if self._failure_counts[source] >= self._failure_threshold:
            logger.warning(f"Disabling {source} due to repeated failures")
            self._source_status[source] = False

    async def _try_primary(self, method_name: str, *args, **kwargs) -> dict | None:
        """Try primary client (tomquirk/linkedin-api)."""
        if not self._primary or self._should_skip_source("primary"):
            return None

        try:
            method = getattr(self._primary, method_name, None)
            if method is None:
                return None

            result = await method(*args, **kwargs)
            self._record_success("primary")
            return {"data": result, "source": "linkedin_api"}
        except Exception as e:
            self._record_failure("primary", e)
            return None

    async def _try_enhanced(self, method_name: str, *args, **kwargs) -> dict | None:
        """Try enhanced HTTP client."""
        if not self._enhanced or self._should_skip_source("enhanced"):
            return None

        try:
            method = getattr(self._enhanced, method_name, None)
            if method is None:
                return None

            result = await method(*args, **kwargs)
            self._record_success("enhanced")
            return {"data": result, "source": "enhanced_client"}
        except Exception as e:
            self._record_failure("enhanced", e)
            return None

    async def _try_headless(self, method_name: str, *args, **kwargs) -> dict | None:
        """Try headless browser scraper."""
        if self._should_skip_source("headless"):
            return None

        # Initialize lazily
        if not await self._init_headless_if_needed():
            return None

        try:
            method = getattr(self._headless, method_name, None)
            if method is None:
                return None

            result = await method(*args, **kwargs)
            self._record_success("headless")
            return {"data": result, "source": "headless_scraper"}
        except Exception as e:
            self._record_failure("headless", e)
            return None

    async def _execute_with_fallback(
        self,
        method_name: str,
        *args,
        **kwargs,
    ) -> dict[str, Any]:
        """
        Execute method with automatic fallback through data sources.

        Args:
            method_name: Name of the method to call on each source
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Result dict with 'data' and 'source' keys

        Raises:
            LinkedInAPIError: If all sources fail
        """
        errors = []

        # Try primary (tomquirk/linkedin-api)
        result = await self._try_primary(method_name, *args, **kwargs)
        if result:
            return result

        # Try enhanced (curl_cffi)
        result = await self._try_enhanced(method_name, *args, **kwargs)
        if result:
            logger.info(f"Falling back to enhanced client for {method_name}")
            return result

        # Try headless (browser scraper)
        result = await self._try_headless(method_name, *args, **kwargs)
        if result:
            logger.info(f"Falling back to headless scraper for {method_name}")
            return result

        # All sources failed
        raise LinkedInAPIError(
            f"All data sources failed for {method_name}",
            details={
                "method": method_name,
                "sources_tried": ["primary", "enhanced", "headless"],
                "suggestion": "Try refreshing cookies: linkedin-mcp-auth extract-cookies",
            },
        )

    # =========================================================================
    # Profile Methods
    # =========================================================================

    async def get_profile(self, public_id: str) -> dict[str, Any]:
        """
        Get a LinkedIn profile by public ID.

        Automatically falls back through data sources if one fails.

        Args:
            public_id: LinkedIn public ID (e.g., "johndoe")

        Returns:
            Profile data with source information
        """
        return await self._execute_with_fallback("get_profile", public_id)

    async def get_own_profile(self) -> dict[str, Any]:
        """Get the authenticated user's profile."""
        return await self._execute_with_fallback("get_own_profile")

    # =========================================================================
    # Search Methods
    # =========================================================================

    async def search_people(
        self,
        keywords: str | None = None,
        limit: int = 10,
        keyword_title: str | None = None,
        keyword_company: str | None = None,
    ) -> dict[str, Any]:
        """
        Search for people on LinkedIn.

        Args:
            keywords: Search keywords
            limit: Maximum results
            keyword_title: Filter by job title
            keyword_company: Filter by company

        Returns:
            Search results with source information
        """
        return await self._execute_with_fallback(
            "search_people",
            keywords=keywords,
            limit=limit,
            keyword_title=keyword_title,
            keyword_company=keyword_company,
        )

    # =========================================================================
    # Feed Methods
    # =========================================================================

    async def get_feed(self, limit: int = 10) -> dict[str, Any]:
        """
        Get the user's LinkedIn feed.

        Args:
            limit: Maximum posts to return

        Returns:
            Feed posts with source information
        """
        return await self._execute_with_fallback("get_feed", limit=limit)

    async def get_profile_posts(
        self,
        public_id: str,
        limit: int = 10,
    ) -> dict[str, Any]:
        """Get posts from a specific profile."""
        return await self._execute_with_fallback(
            "get_profile_posts",
            public_id,
            limit=limit,
        )

    # =========================================================================
    # Connection Methods
    # =========================================================================

    async def get_connections(self, limit: int = 50) -> dict[str, Any]:
        """
        Get user's LinkedIn connections.

        Args:
            limit: Maximum connections to return

        Returns:
            Connections list with source information
        """
        return await self._execute_with_fallback(
            "get_connections" if self._primary else "get_connections",
            limit=limit,
        )

    # =========================================================================
    # Status and Control
    # =========================================================================

    def get_source_status(self) -> dict[str, Any]:
        """Get status of all data sources."""
        return {
            "sources": {
                "primary": {
                    "available": self._primary is not None,
                    "enabled": self._source_status.get("primary", False),
                    "failures": self._failure_counts.get("primary", 0),
                    "type": "linkedin-api",
                },
                "enhanced": {
                    "available": self._enhanced is not None,
                    "enabled": self._source_status.get("enhanced", False),
                    "failures": self._failure_counts.get("enhanced", 0),
                    "type": "curl_cffi HTTP client",
                },
                "headless": {
                    "available": self._headless is not None,
                    "enabled": self._source_status.get("headless", False),
                    "failures": self._failure_counts.get("headless", 0),
                    "type": "Patchright/Playwright browser",
                },
            },
            "failure_threshold": self._failure_threshold,
        }

    def reset_source(self, source: str) -> None:
        """
        Reset a source to try it again.

        Args:
            source: Source name ("primary", "enhanced", "headless")
        """
        if source in self._failure_counts:
            self._failure_counts[source] = 0
            self._source_status[source] = True
            logger.info(f"Reset source: {source}")

    def reset_all_sources(self) -> None:
        """Reset all sources to try them again."""
        for source in ["primary", "enhanced", "headless"]:
            self.reset_source(source)

    async def close(self) -> None:
        """Close all data sources."""
        if self._enhanced:
            try:
                await self._enhanced.close()
            except Exception:
                pass

        if self._headless:
            try:
                await self._headless.close()
            except Exception:
                pass

        logger.info("LinkedIn data provider closed")


# =============================================================================
# Factory function
# =============================================================================

async def create_data_provider(
    primary_client: Any | None = None,
    li_at: str | None = None,
    jsessionid: str | None = None,
    enable_enhanced: bool = True,
    enable_headless: bool = True,
) -> LinkedInDataProvider:
    """
    Factory function to create an initialized data provider.

    Args:
        primary_client: Optional tomquirk/linkedin-api client
        li_at: LinkedIn session cookie
        jsessionid: JSESSIONID cookie
        enable_enhanced: Enable enhanced HTTP client
        enable_headless: Enable headless browser scraper

    Returns:
        Initialized LinkedInDataProvider
    """
    cookies = {}
    if li_at:
        cookies["li_at"] = li_at
    if jsessionid:
        cookies["JSESSIONID"] = jsessionid

    provider = LinkedInDataProvider(
        primary_client=primary_client,
        cookies=cookies,
        enable_enhanced=enable_enhanced,
        enable_headless=enable_headless,
    )

    await provider.initialize()
    return provider
