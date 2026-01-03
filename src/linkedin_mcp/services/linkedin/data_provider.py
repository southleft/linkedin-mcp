"""
Unified LinkedIn data provider with intelligent fallback.

Orchestrates between multiple data sources to provide reliable
LinkedIn data access. Sources are ordered by RELIABILITY:

1. PND API: Professional Network Data API (RapidAPI) - MOST RELIABLE, 55 endpoints
2. Fresh Data API: RapidAPI Fresh LinkedIn Profile Data (profile/company search)
3. Marketing API: LinkedIn Official Marketing/Community Management API (organizations)
4. Enhanced: HTTP client with curl_cffi (anti-detection)
5. Headless: Browser scraper (slowest but reliable)
6. Primary: tomquirk/linkedin-api (LEAST RELIABLE - cookie-based, prone to blocking)

The unofficial LinkedIn API (Primary) is placed LAST because it's the most
brittle - it relies on session cookies that expire and is prone to bot detection.

All operations happen in the background without any visible UI.
"""

import asyncio
from typing import TYPE_CHECKING, Any

from linkedin_mcp.core.exceptions import (
    LinkedInAPIError,
    LinkedInAuthError,
    format_error_response,
)
from linkedin_mcp.core.logging import get_logger

if TYPE_CHECKING:
    from linkedin_mcp.services.linkedin.fresh_data_client import FreshLinkedInDataClient
    from linkedin_mcp.services.linkedin.marketing_client import LinkedInMarketingClient
    from linkedin_mcp.services.linkedin.professional_network_data_client import (
        ProfessionalNetworkDataClient,
    )

logger = get_logger(__name__)


class LinkedInDataProvider:
    """
    Unified LinkedIn data provider with automatic fallback.

    This provider tries multiple data sources in order of RELIABILITY,
    automatically falling back when one source fails due to blocking.

    Fallback order (most reliable first):
    1. PND API - Professional Network Data (paid, 55 endpoints)
    2. Fresh Data API - RapidAPI (paid)
    3. Enhanced - curl_cffi with anti-detection
    4. Headless - browser scraper
    5. Primary - tomquirk/linkedin-api (LAST - most brittle, cookie-based)

    The unofficial LinkedIn API (Primary) is tried LAST because it's the
    most prone to failures due to expired cookies and bot detection.

    All operations happen in the background - no visible browser windows.

    Usage:
        provider = LinkedInDataProvider(
            pnd_client=pnd_client,  # Professional Network Data API (most reliable)
            primary_client=linkedin_client,  # tomquirk/linkedin-api (fallback only)
            cookies={"li_at": "...", "JSESSIONID": "..."},
        )
        await provider.initialize()

        # Will try pnd → fresh_data → enhanced → headless → primary
        profile = await provider.get_profile("johndoe")
    """

    def __init__(
        self,
        primary_client: Any | None = None,
        marketing_client: "LinkedInMarketingClient | None" = None,
        fresh_data_client: "FreshLinkedInDataClient | None" = None,
        pnd_client: "ProfessionalNetworkDataClient | None" = None,
        cookies: dict[str, str] | None = None,
        enable_enhanced: bool = True,
        enable_headless: bool = True,
    ):
        """
        Initialize the data provider.

        Data sources are ordered by RELIABILITY (most reliable first):
        1. PND API (Professional Network Data) - paid, 55 endpoints, most reliable
        2. Fresh Data API - paid, reliable
        3. Marketing API - official LinkedIn API for organizations
        4. Enhanced - curl_cffi with anti-detection
        5. Headless - browser scraper
        6. Primary - tomquirk/linkedin-api (LAST - most brittle, cookie-based)

        Args:
            primary_client: tomquirk/linkedin-api client instance (LEAST reliable)
            marketing_client: LinkedIn Marketing API client (Community Management)
            fresh_data_client: Fresh LinkedIn Data API client (RapidAPI)
            pnd_client: Professional Network Data API client (MOST reliable)
            cookies: LinkedIn cookies for fallback clients
            enable_enhanced: Enable enhanced HTTP client with curl_cffi
            enable_headless: Enable headless browser scraper
        """
        self._primary = primary_client
        self._marketing = marketing_client
        self._fresh_data = fresh_data_client
        self._pnd = pnd_client
        self._cookies = cookies or {}
        self._enable_enhanced = enable_enhanced
        self._enable_headless = enable_headless

        self._enhanced = None
        self._headless = None
        self._initialized = False

        # Track which sources are working
        self._source_status = {
            "pnd": True,
            "fresh_data": True,
            "marketing": True,
            "enhanced": True,
            "headless": True,
            "primary": True,
        }

        # Failure counts for adaptive fallback
        self._failure_counts = {
            "pnd": 0,
            "fresh_data": 0,
            "marketing": 0,
            "enhanced": 0,
            "headless": 0,
            "primary": 0,
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

    async def _try_pnd(self, method_name: str, *args, **kwargs) -> dict | None:
        """Try Professional Network Data API (RapidAPI) - MOST RELIABLE."""
        if not self._pnd or self._should_skip_source("pnd"):
            return None

        try:
            method = getattr(self._pnd, method_name, None)
            if method is None:
                return None

            result = await method(*args, **kwargs)
            # Return None for empty results so fallback chain continues
            if result is None:
                return None
            # Handle error responses from PND API
            if isinstance(result, dict) and result.get("error"):
                logger.info("PND API returned error, trying next source", error=result.get("error"))
                return None
            self._record_success("pnd")
            return {"data": result, "source": "pnd_api"}
        except Exception as e:
            self._record_failure("pnd", e)
            return None

    async def _try_primary(self, method_name: str, *args, **kwargs) -> dict | None:
        """Try primary client (tomquirk/linkedin-api) - LEAST RELIABLE, try last."""
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

    async def _try_marketing(self, method_name: str, *args, **kwargs) -> dict | None:
        """Try LinkedIn Marketing API client (Community Management)."""
        if not self._marketing or self._should_skip_source("marketing"):
            return None

        try:
            method = getattr(self._marketing, method_name, None)
            if method is None:
                return None

            result = await method(*args, **kwargs)
            if result is None:
                return None
            self._record_success("marketing")
            return {"data": result, "source": "marketing_api"}
        except Exception as e:
            self._record_failure("marketing", e)
            return None

    async def _try_fresh_data(self, method_name: str, *args, **kwargs) -> dict | None:
        """Try Fresh LinkedIn Data API (RapidAPI)."""
        if not self._fresh_data or self._should_skip_source("fresh_data"):
            return None

        try:
            method = getattr(self._fresh_data, method_name, None)
            if method is None:
                return None

            result = await method(*args, **kwargs)
            # Return None for empty results so fallback chain continues
            if result is None or (isinstance(result, list) and len(result) == 0):
                logger.info("Fresh Data API returned empty results, trying next source")
                return None
            self._record_success("fresh_data")
            return {"data": result, "source": "fresh_data_api"}
        except Exception as e:
            self._record_failure("fresh_data", e)
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

        Sources are ordered by RELIABILITY (most reliable first):
        1. PND API - Professional Network Data (paid, 55 endpoints)
        2. Fresh Data API - RapidAPI (paid)
        3. Enhanced - curl_cffi with anti-detection
        4. Headless - browser scraper
        5. Primary - tomquirk/linkedin-api (LAST - most brittle, cookie-based)

        The unofficial LinkedIn API (Primary) is tried LAST because it's the
        most prone to failures due to expired cookies and bot detection.

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

        # 1. Try PND API first (Professional Network Data - MOST RELIABLE)
        result = await self._try_pnd(method_name, *args, **kwargs)
        if result:
            return result

        # 2. Try Fresh Data API (RapidAPI - reliable when subscribed)
        result = await self._try_fresh_data(method_name, *args, **kwargs)
        if result:
            return result

        # 3. Try enhanced (curl_cffi with anti-detection)
        result = await self._try_enhanced(method_name, *args, **kwargs)
        if result:
            logger.info(f"Falling back to enhanced client for {method_name}")
            return result

        # 4. Try headless (browser scraper)
        result = await self._try_headless(method_name, *args, **kwargs)
        if result:
            logger.info(f"Falling back to headless scraper for {method_name}")
            return result

        # 5. Try primary (tomquirk/linkedin-api) - LAST, most brittle
        result = await self._try_primary(method_name, *args, **kwargs)
        if result:
            logger.info(f"Falling back to unofficial API for {method_name}")
            return result

        # All sources failed
        raise LinkedInAPIError(
            f"All data sources failed for {method_name}",
            details={
                "method": method_name,
                "sources_tried": ["pnd", "fresh_data", "enhanced", "headless", "primary"],
                "suggestion": "Check API keys or try refreshing cookies: linkedin-mcp-auth extract-cookies",
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
        return await self._execute_with_fallback("get_profile", public_id=public_id)

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
    # Engagement Methods (Reactions, Comments)
    # =========================================================================

    async def get_post_reactions(
        self,
        post_urn: str,
    ) -> dict[str, Any]:
        """
        Get reactions on a LinkedIn post.

        Falls back through: PND → Fresh Data → Primary

        Args:
            post_urn: LinkedIn post URN (e.g., "urn:li:activity:123456")

        Returns:
            Reactions data with source information
        """
        return await self._execute_with_fallback(
            "get_post_reactions",
            post_urn,
        )

    async def get_post_comments(
        self,
        post_urn: str,
        limit: int = 50,
    ) -> dict[str, Any]:
        """
        Get comments on a LinkedIn post.

        Falls back through: PND → Fresh Data → Primary

        Args:
            post_urn: LinkedIn post URN (e.g., "urn:li:activity:123456")
            limit: Maximum comments to return

        Returns:
            Comments data with source information
        """
        return await self._execute_with_fallback(
            "get_post_comments",
            post_urn,
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
    # Organization/Company Methods (Marketing API + Fresh Data API)
    # =========================================================================

    async def get_organization(
        self,
        organization_id: int | str | None = None,
        vanity_name: str | None = None,
    ) -> dict[str, Any]:
        """
        Get organization/company data.

        Tries Marketing API first (official), then Fresh Data API.

        Args:
            organization_id: LinkedIn organization numeric ID
            vanity_name: Organization vanity name (URL slug, e.g., "microsoft")

        Returns:
            Organization data with source information
        """
        errors = []

        # Try Marketing API (official Community Management API)
        if organization_id:
            result = await self._try_marketing("get_organization", organization_id)
            if result:
                return result

        if vanity_name:
            result = await self._try_marketing("get_organization_by_vanity_name", vanity_name)
            if result:
                return result

        # Try Fresh Data API (RapidAPI)
        result = await self._try_fresh_data(
            "get_company",
            company_id=organization_id,
            vanity_name=vanity_name,
        )
        if result:
            return result

        # Try primary client if available
        result = await self._try_primary("get_company", vanity_name or str(organization_id))
        if result:
            return result

        raise LinkedInAPIError(
            "Failed to get organization data from all sources",
            details={
                "organization_id": organization_id,
                "vanity_name": vanity_name,
                "sources_tried": ["marketing_api", "fresh_data_api", "primary"],
            },
        )

    async def get_organization_follower_count(
        self,
        organization_id: int | str,
    ) -> dict[str, Any]:
        """
        Get follower count for an organization.

        Uses Marketing API (official LinkedIn API).

        Args:
            organization_id: LinkedIn organization numeric ID

        Returns:
            Follower count with source information
        """
        result = await self._try_marketing("get_organization_follower_count", organization_id)
        if result:
            return result

        raise LinkedInAPIError(
            "Failed to get organization follower count",
            details={"organization_id": organization_id},
        )

    async def search_companies(
        self,
        query: str,
        limit: int = 25,
    ) -> dict[str, Any]:
        """
        Search for companies on LinkedIn.

        Uses Fresh Data API (RapidAPI) for comprehensive search.

        Args:
            query: Search query (company name or keywords)
            limit: Maximum results to return

        Returns:
            Company search results with source information
        """
        # Try Fresh Data API first (most comprehensive search)
        result = await self._try_fresh_data("search_companies", query, limit=limit)
        if result:
            return result

        # Fall back to primary client
        result = await self._try_primary("search_companies", query, limit=limit)
        if result:
            return result

        raise LinkedInAPIError(
            "Failed to search companies from all sources",
            details={"query": query},
        )

    async def get_company_posts(
        self,
        company_id: str,
        limit: int = 10,
    ) -> dict[str, Any]:
        """
        Get posts/updates from a company page.

        Falls back through: PND → Fresh Data → Primary

        Args:
            company_id: Company's public identifier (URL slug, e.g., 'microsoft')
            limit: Maximum posts to return

        Returns:
            Company posts with source information
        """
        return await self._execute_with_fallback(
            "get_company_posts",
            company_id,
            limit=limit,
        )

    async def get_company_employees(
        self,
        company_id: int | str | None = None,
        company_name: str | None = None,
        title_keywords: list[str] | None = None,
        limit: int = 25,
    ) -> dict[str, Any]:
        """
        Get employees of a company.

        Uses Fresh Data API for employee search.

        Args:
            company_id: LinkedIn company ID
            company_name: Company name to search
            title_keywords: Filter by job title keywords
            limit: Maximum results to return

        Returns:
            Employee profiles with source information
        """
        result = await self._try_fresh_data(
            "get_company_employees",
            company_id=company_id,
            company_name=company_name,
            title_keywords=title_keywords,
            limit=limit,
        )
        if result:
            return result

        raise LinkedInAPIError(
            "Failed to get company employees",
            details={"company_id": company_id, "company_name": company_name},
        )

    # =========================================================================
    # Enhanced Profile Search (Fresh Data API)
    # =========================================================================

    async def search_profiles(
        self,
        query: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        title_keywords: list[str] | None = None,
        company_names: list[str] | None = None,
        locations: list[str] | None = None,
        limit: int = 25,
    ) -> dict[str, Any]:
        """
        Advanced profile search with multiple filters.

        Uses Fresh Data API for comprehensive search capabilities.

        Args:
            query: General search keywords
            first_name: Filter by first name
            last_name: Filter by last name
            title_keywords: Filter by job title keywords
            company_names: Filter by current company names
            locations: Filter by location names
            limit: Maximum results to return

        Returns:
            Profile search results with source information
        """
        sources_tried = []

        # Try Fresh Data API first (most comprehensive)
        result = await self._try_fresh_data(
            "search_profiles",
            query=query,
            first_name=first_name,
            last_name=last_name,
            title_keywords=title_keywords,
            company_names=company_names,
            locations=locations,
            limit=limit,
        )
        if result:
            return result
        sources_tried.append("fresh_data_api")

        # Build search kwargs for simplified clients
        search_kwargs = {"limit": limit}
        if query:
            search_kwargs["keywords"] = query
        if title_keywords and len(title_keywords) > 0:
            search_kwargs["keyword_title"] = title_keywords[0]
        if company_names and len(company_names) > 0:
            search_kwargs["keyword_company"] = company_names[0]

        # Fall back to primary client
        if query:
            result = await self._try_primary("search_people", **search_kwargs)
            if result:
                return result
            sources_tried.append("primary")

        # Fall back to enhanced client
        result = await self._try_enhanced("search_people", **search_kwargs)
        if result:
            return result
        sources_tried.append("enhanced")

        # Fall back to headless browser
        result = await self._try_headless("search_people", **search_kwargs)
        if result:
            return result
        sources_tried.append("headless")

        raise LinkedInAPIError(
            "Failed to search profiles from all sources",
            details={
                "query": query,
                "filters": {"first_name": first_name, "last_name": last_name},
                "sources_tried": sources_tried,
                "suggestion": "Fresh Data API requires subscription: https://rapidapi.com/rockapis-rockapis-default/api/fresh-linkedin-profile-data",
            },
        )

    # =========================================================================
    # Status and Control
    # =========================================================================

    def get_source_status(self) -> dict[str, Any]:
        """Get status of all data sources (ordered by reliability)."""
        return {
            "sources": {
                "pnd": {
                    "available": self._pnd is not None,
                    "enabled": self._source_status.get("pnd", False),
                    "failures": self._failure_counts.get("pnd", 0),
                    "type": "Professional Network Data API (RapidAPI) - PRIMARY",
                    "priority": 1,
                },
                "fresh_data": {
                    "available": self._fresh_data is not None,
                    "enabled": self._source_status.get("fresh_data", False),
                    "failures": self._failure_counts.get("fresh_data", 0),
                    "type": "Fresh LinkedIn Data API (RapidAPI)",
                    "priority": 2,
                },
                "marketing": {
                    "available": self._marketing is not None,
                    "enabled": self._source_status.get("marketing", False),
                    "failures": self._failure_counts.get("marketing", 0),
                    "type": "LinkedIn Marketing API (Community Management)",
                    "priority": 3,
                },
                "enhanced": {
                    "available": self._enhanced is not None,
                    "enabled": self._source_status.get("enhanced", False),
                    "failures": self._failure_counts.get("enhanced", 0),
                    "type": "curl_cffi HTTP client",
                    "priority": 4,
                },
                "headless": {
                    "available": self._headless is not None,
                    "enabled": self._source_status.get("headless", False),
                    "failures": self._failure_counts.get("headless", 0),
                    "type": "Patchright/Playwright browser",
                    "priority": 5,
                },
                "primary": {
                    "available": self._primary is not None,
                    "enabled": self._source_status.get("primary", False),
                    "failures": self._failure_counts.get("primary", 0),
                    "type": "linkedin-api (unofficial) - FALLBACK ONLY",
                    "priority": 6,
                },
            },
            "failure_threshold": self._failure_threshold,
            "fallback_order": ["pnd", "fresh_data", "enhanced", "headless", "primary"],
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
        for source in ["pnd", "fresh_data", "marketing", "enhanced", "headless", "primary"]:
            self.reset_source(source)

    async def close(self) -> None:
        """Close all data sources."""
        if self._pnd:
            try:
                await self._pnd.close()
            except Exception:
                pass

        if self._marketing:
            try:
                await self._marketing.close()
            except Exception:
                pass

        if self._fresh_data:
            try:
                await self._fresh_data.close()
            except Exception:
                pass

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
    marketing_client: "LinkedInMarketingClient | None" = None,
    fresh_data_client: "FreshLinkedInDataClient | None" = None,
    pnd_client: "ProfessionalNetworkDataClient | None" = None,
    li_at: str | None = None,
    jsessionid: str | None = None,
    enable_enhanced: bool = True,
    enable_headless: bool = True,
) -> LinkedInDataProvider:
    """
    Factory function to create an initialized data provider.

    Data sources are ordered by RELIABILITY (most reliable first):
    1. PND API - Professional Network Data (paid, 55 endpoints)
    2. Fresh Data API - RapidAPI (paid)
    3. Enhanced - curl_cffi with anti-detection
    4. Headless - browser scraper
    5. Primary - tomquirk/linkedin-api (LAST - most brittle)

    Args:
        primary_client: Optional tomquirk/linkedin-api client (LEAST reliable)
        marketing_client: LinkedIn Marketing API client (Community Management)
        fresh_data_client: Fresh LinkedIn Data API client (RapidAPI)
        pnd_client: Professional Network Data API client (MOST reliable)
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
        marketing_client=marketing_client,
        fresh_data_client=fresh_data_client,
        pnd_client=pnd_client,
        cookies=cookies,
        enable_enhanced=enable_enhanced,
        enable_headless=enable_headless,
    )

    await provider.initialize()
    return provider
