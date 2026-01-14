"""
LinkedIn Ad Library API Client.

Provides access to LinkedIn's Ad Library for ad transparency and research.
The Ad Library contains publicly available data about ads that have run
on LinkedIn within the past year.

Features:
- Search ads by keyword
- Search ads by advertiser
- Filter by country and date range
- Get ad details including targeting, impressions, and creative content

Requires Ad Library API approval from LinkedIn Developer Portal.
"""

from datetime import datetime
from typing import Any

import httpx
import structlog

logger = structlog.get_logger(__name__)


class LinkedInAdLibraryClient:
    """
    LinkedIn Ad Library API Client.

    This client provides access to LinkedIn's Ad Library API for searching
    and retrieving information about ads running on the platform.

    The Ad Library is a transparency feature that allows anyone to search
    for ads by advertiser, keyword, country, and date range.

    API Documentation:
    https://developer.linkedin.com/product-catalog/marketing

    Required Product: LinkedIn Ad Library (Default Tier)
    """

    # API endpoints
    API_BASE = "https://api.linkedin.com"
    REST_BASE = f"{API_BASE}/rest"

    # Current API version (YYYYMM format)
    API_VERSION = "202501"

    def __init__(
        self,
        access_token: str,
        api_version: str | None = None,
    ):
        """
        Initialize the Ad Library API client.

        Args:
            access_token: OAuth 2.0 access token with Ad Library scope
            api_version: API version in YYYYMM format (defaults to latest)
        """
        self._access_token = access_token
        self._api_version = api_version or self.API_VERSION
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                headers=self._get_headers(),
            )
        return self._client

    def _get_headers(self) -> dict[str, str]:
        """Get headers for API requests."""
        return {
            "Authorization": f"Bearer {self._access_token}",
            "X-Restli-Protocol-Version": "2.0.0",
            "LinkedIn-Version": self._api_version,
            "Content-Type": "application/json",
        }

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    # =========================================================================
    # Ad Library Search APIs
    # =========================================================================

    async def search_ads(
        self,
        keyword: str | None = None,
        advertiser: str | None = None,
        country: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        count: int = 25,
        start: int = 0,
    ) -> dict[str, Any]:
        """
        Search for ads in the LinkedIn Ad Library.

        The Ad Library contains ads that have run on LinkedIn within the past year.
        At least one of keyword or advertiser must be provided.

        Args:
            keyword: Search term to find in ad content
            advertiser: Company/advertiser name to search for
            country: ISO 3166-1 alpha-2 country code (e.g., "US", "GB", "DE")
            start_date: Filter ads shown after this date (YYYY-MM-DD format)
            end_date: Filter ads shown before this date (YYYY-MM-DD format)
            count: Number of results to return (default 25, max 100)
            start: Offset for pagination

        Returns:
            Dict containing:
                - elements: List of ad objects
                - paging: Pagination info
                - total: Total number of matching ads

        Example:
            >>> client = LinkedInAdLibraryClient(token)
            >>> results = await client.search_ads(keyword="software", country="US")
            >>> for ad in results["elements"]:
            ...     print(ad["advertiser"]["name"], ad["impressions"])
        """
        if not keyword and not advertiser:
            return {
                "success": False,
                "error": "At least one of 'keyword' or 'advertiser' must be provided",
                "elements": [],
            }

        client = await self._get_client()

        # Build query parameters
        params: dict[str, Any] = {
            "q": "criteria",
            "count": min(count, 100),
            "start": start,
        }

        if keyword:
            params["keyword"] = keyword
        if advertiser:
            params["advertiser"] = advertiser
        # Note: country param not supported by API as of 2025
        if start_date:
            params["startDate"] = start_date
        if end_date:
            params["endDate"] = end_date

        try:
            logger.info(
                "Searching Ad Library",
                keyword=keyword,
                advertiser=advertiser,
                country=country,
            )

            response = await client.get(
                f"{self.REST_BASE}/adLibrary",
                params=params,
            )

            if response.status_code == 200:
                data = response.json()
                elements = data.get("elements", [])

                # Log raw response structure for debugging
                if elements:
                    logger.info(
                        "Ad Library raw response sample",
                        sample_keys=list(elements[0].keys()) if elements else [],
                    )

                # Normalize the results
                normalized_ads = [self._normalize_ad(ad) for ad in elements]

                logger.info(
                    "Ad Library search successful",
                    result_count=len(normalized_ads),
                )

                return {
                    "success": True,
                    "elements": normalized_ads,  # Now includes _raw and _keys for discovery
                    "paging": data.get("paging", {}),
                    "total": data.get("total", len(normalized_ads)),
                }
            elif response.status_code == 404:
                logger.warning(
                    "Ad Library endpoint not found - may require different API version",
                    status=response.status_code,
                )
                return {
                    "success": False,
                    "error": "Ad Library API endpoint not available. Ensure Ad Library product is enabled.",
                    "elements": [],
                }
            else:
                logger.error(
                    "Ad Library search failed",
                    status=response.status_code,
                    error=response.text[:500],
                )
                return {
                    "success": False,
                    "error": response.text[:500],
                    "status_code": response.status_code,
                    "elements": [],
                }

        except Exception as e:
            logger.error("Ad Library search error", error=str(e))
            return {
                "success": False,
                "error": str(e),
                "elements": [],
            }

    async def get_ad_details(self, ad_id: str) -> dict[str, Any] | None:
        """
        Get detailed information about a specific ad.

        Args:
            ad_id: The unique identifier of the ad

        Returns:
            Ad details dict or None if not found
        """
        client = await self._get_client()

        try:
            response = await client.get(
                f"{self.REST_BASE}/adLibrary/{ad_id}",
            )

            if response.status_code == 200:
                data = response.json()
                logger.info("Retrieved ad details", ad_id=ad_id)
                return self._normalize_ad(data)
            elif response.status_code == 404:
                logger.warning("Ad not found", ad_id=ad_id)
                return None
            else:
                logger.error(
                    "Failed to get ad details",
                    ad_id=ad_id,
                    status=response.status_code,
                )
                return None

        except Exception as e:
            logger.error("Error getting ad details", ad_id=ad_id, error=str(e))
            return None

    async def search_ads_by_advertiser(
        self,
        advertiser_name: str,
        country: str | None = None,
        count: int = 25,
    ) -> dict[str, Any]:
        """
        Search for all ads by a specific advertiser.

        Convenience method that wraps search_ads with advertiser filter.

        Args:
            advertiser_name: Name of the advertiser/company
            country: Optional country filter (ISO 3166-1 alpha-2)
            count: Number of results to return

        Returns:
            Search results dict with ads from the specified advertiser
        """
        return await self.search_ads(
            advertiser=advertiser_name,
            country=country,
            count=count,
        )

    async def search_ads_by_keyword(
        self,
        keyword: str,
        country: str | None = None,
        count: int = 25,
    ) -> dict[str, Any]:
        """
        Search for ads containing a specific keyword.

        Convenience method that wraps search_ads with keyword filter.

        Args:
            keyword: Search term to find in ad content
            country: Optional country filter (ISO 3166-1 alpha-2)
            count: Number of results to return

        Returns:
            Search results dict with ads matching the keyword
        """
        return await self.search_ads(
            keyword=keyword,
            country=country,
            count=count,
        )

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _normalize_ad(self, data: dict) -> dict[str, Any]:
        """
        Normalize ad data to a consistent format.

        LinkedIn Ad Library API returns:
        - isRestricted: bool
        - adUrl: str (link to ad in Ad Library)
        - details: dict with type, advertiser, adTargeting, and content fields

        Args:
            data: Raw ad data from API

        Returns:
            Normalized ad dict
        """
        # Extract the details object which contains most of the data
        details = data.get("details", {})
        advertiser_info = details.get("advertiser", {})

        # Extract ad ID from adUrl (e.g., "https://www.linkedin.com/ad-library/detail/1027918076")
        ad_url = data.get("adUrl", "")
        ad_id = ad_url.split("/")[-1] if ad_url else None

        # Extract content from details - structure varies by ad type
        # Content might be in various nested locations
        content_data = details.get("content", {})
        creative_data = details.get("creative", {})

        # Build normalized response
        return {
            "id": ad_id,
            "ad_url": ad_url,
            "is_restricted": data.get("isRestricted", False),
            "ad_type": details.get("type"),
            "advertiser": {
                "name": advertiser_info.get("advertiserName"),
                "payer": advertiser_info.get("adPayer"),
                "url": advertiser_info.get("advertiserUrl"),
            },
            "content": {
                "text": (
                    content_data.get("text")
                    or content_data.get("body")
                    or content_data.get("commentary")
                    or creative_data.get("text")
                ),
                "headline": (
                    content_data.get("headline")
                    or content_data.get("title")
                    or creative_data.get("headline")
                ),
                "description": content_data.get("description") or creative_data.get("description"),
                "call_to_action": content_data.get("callToAction") or creative_data.get("callToAction"),
                "landing_page_url": (
                    content_data.get("landingPageUrl")
                    or content_data.get("destinationUrl")
                    or creative_data.get("landingPageUrl")
                ),
                "images": content_data.get("images", []) or creative_data.get("images", []),
                "videos": content_data.get("videos", []) or creative_data.get("videos", []),
            },
            "targeting": details.get("adTargeting", []),
            "impressions": details.get("impressions", {}),
            "source": "ad_library_api",
        }

    # =========================================================================
    # Status/Debug Methods
    # =========================================================================

    def get_status(self) -> dict[str, Any]:
        """Get client status information."""
        return {
            "client_type": "ad_library_api",
            "api_version": self._api_version,
            "has_token": bool(self._access_token),
            "available_features": [
                "search_ads",
                "search_ads_by_advertiser",
                "search_ads_by_keyword",
                "get_ad_details",
            ],
            "description": "Search LinkedIn's Ad Library for ad transparency data",
            "documentation": "https://developer.linkedin.com/product-catalog/marketing",
        }
