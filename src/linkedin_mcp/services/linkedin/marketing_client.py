"""
LinkedIn Marketing API Client for Community Management.

Provides access to LinkedIn's official Marketing API including:
- Organization lookup (company information)
- Organization follower counts
- Page analytics (for admins)

Requires Community Management API approval from LinkedIn Developer Portal.
"""

import time
from pathlib import Path
from typing import Any

import httpx
import structlog

logger = structlog.get_logger(__name__)


class LinkedInMarketingClient:
    """
    LinkedIn Marketing API Client for Community Management.

    This client provides access to LinkedIn's official Marketing APIs
    for organization/company data lookup and management.

    API Documentation:
    https://learn.microsoft.com/en-us/linkedin/marketing/community-management/organizations

    Required Product: Community Management API
    """

    # API endpoints
    API_BASE = "https://api.linkedin.com"
    REST_BASE = f"{API_BASE}/rest"
    V2_BASE = f"{API_BASE}/v2"

    # Current API version (YYYYMM format)
    API_VERSION = "202501"

    def __init__(
        self,
        access_token: str,
        api_version: str | None = None,
    ):
        """
        Initialize the Marketing API client.

        Args:
            access_token: OAuth 2.0 access token with appropriate scopes
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
    # Organization Lookup APIs
    # =========================================================================

    async def get_organization(self, organization_id: int | str) -> dict[str, Any] | None:
        """
        Get organization details by ID.

        For non-administered organizations, returns limited fields:
        - id, name, localizedName, vanityName, logoV2, locations, primaryOrganizationType

        For administered organizations (user is admin), returns full details.

        Args:
            organization_id: LinkedIn organization ID (numeric)

        Returns:
            Organization data dict or None on error
        """
        client = await self._get_client()

        try:
            # Use the REST API endpoint for single org lookup
            response = await client.get(
                f"{self.REST_BASE}/organizations/{organization_id}",
            )

            if response.status_code == 200:
                data = response.json()
                logger.info("Organization lookup successful", org_id=organization_id)
                return self._normalize_organization(data)
            elif response.status_code == 404:
                logger.warning("Organization not found", org_id=organization_id)
                return None
            else:
                logger.error(
                    "Organization lookup failed",
                    org_id=organization_id,
                    status=response.status_code,
                    error=response.text[:500],
                )
                return None

        except Exception as e:
            logger.error("Organization lookup error", org_id=organization_id, error=str(e))
            return None

    async def get_organization_by_vanity_name(self, vanity_name: str) -> dict[str, Any] | None:
        """
        Get organization by vanity name (URL slug).

        Example: "microsoft" from linkedin.com/company/microsoft

        Args:
            vanity_name: Organization's vanity name (URL slug)

        Returns:
            Organization data dict or None on error
        """
        client = await self._get_client()

        try:
            response = await client.get(
                f"{self.REST_BASE}/organizations",
                params={
                    "q": "vanityName",
                    "vanityName": vanity_name,
                },
            )

            if response.status_code == 200:
                data = response.json()
                elements = data.get("elements", [])
                if elements:
                    org = elements[0]
                    logger.info("Organization found by vanity name", vanity_name=vanity_name)
                    return self._normalize_organization(org)
                else:
                    logger.warning("Organization not found", vanity_name=vanity_name)
                    return None
            else:
                logger.error(
                    "Organization vanity lookup failed",
                    vanity_name=vanity_name,
                    status=response.status_code,
                    error=response.text[:500],
                )
                return None

        except Exception as e:
            logger.error("Organization vanity lookup error", vanity_name=vanity_name, error=str(e))
            return None

    async def batch_get_organizations(
        self, organization_ids: list[int | str]
    ) -> dict[str, dict[str, Any]]:
        """
        Batch lookup multiple organizations by ID.

        Args:
            organization_ids: List of organization IDs (max 50)

        Returns:
            Dict mapping organization ID to organization data
        """
        if not organization_ids:
            return {}

        # LinkedIn has a limit on batch size
        organization_ids = organization_ids[:50]
        client = await self._get_client()

        try:
            # Format IDs as List() parameter
            ids_param = ",".join(str(id) for id in organization_ids)

            response = await client.get(
                f"{self.REST_BASE}/organizationsLookup",
                params={
                    "ids": f"List({ids_param})",
                },
            )

            if response.status_code == 200:
                data = response.json()
                results = {}
                for element in data.get("results", {}).values():
                    if element:
                        normalized = self._normalize_organization(element)
                        if normalized and normalized.get("id"):
                            results[str(normalized["id"])] = normalized
                logger.info("Batch organization lookup successful", count=len(results))
                return results
            else:
                logger.error(
                    "Batch organization lookup failed",
                    status=response.status_code,
                    error=response.text[:500],
                )
                return {}

        except Exception as e:
            logger.error("Batch organization lookup error", error=str(e))
            return {}

    async def get_organization_follower_count(
        self, organization_id: int | str
    ) -> int | None:
        """
        Get the follower count for an organization.

        Args:
            organization_id: LinkedIn organization ID

        Returns:
            Follower count or None on error
        """
        client = await self._get_client()

        try:
            org_urn = f"urn:li:organization:{organization_id}"
            response = await client.get(
                f"{self.REST_BASE}/networkSizes/{org_urn}",
                params={
                    "edgeType": "COMPANY_FOLLOWED_BY_MEMBER",
                },
            )

            if response.status_code == 200:
                data = response.json()
                count = data.get("firstDegreeSize", 0)
                logger.info("Follower count retrieved", org_id=organization_id, count=count)
                return count
            else:
                logger.warning(
                    "Follower count lookup failed",
                    org_id=organization_id,
                    status=response.status_code,
                )
                return None

        except Exception as e:
            logger.error("Follower count error", org_id=organization_id, error=str(e))
            return None

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _normalize_organization(self, data: dict) -> dict[str, Any]:
        """
        Normalize organization data to a consistent format.

        Args:
            data: Raw organization data from API

        Returns:
            Normalized organization dict
        """
        # Handle both REST and v2 API response formats
        return {
            "id": data.get("id") or data.get("$URN", "").split(":")[-1],
            "name": data.get("name") or data.get("localizedName"),
            "localized_name": data.get("localizedName"),
            "vanity_name": data.get("vanityName"),
            "description": data.get("description") or data.get("localizedDescription"),
            "website": data.get("website") or data.get("localizedWebsite"),
            "industry": data.get("industries", []),
            "company_size": data.get("staffCountRange"),
            "headquarters": self._extract_headquarters(data),
            "logo_url": self._extract_logo_url(data),
            "organization_type": data.get("primaryOrganizationType") or data.get("organizationType"),
            "founded_year": data.get("foundedOn", {}).get("year") if isinstance(data.get("foundedOn"), dict) else None,
            "specialties": data.get("specialties") or data.get("localizedSpecialties", []),
            "source": "marketing_api",
        }

    def _extract_headquarters(self, data: dict) -> dict[str, Any] | None:
        """Extract headquarters location from organization data."""
        locations = data.get("locations", [])
        if not locations:
            return None

        # Find headquarters location
        for loc in locations:
            if loc.get("locationType") == "HEADQUARTERS":
                address = loc.get("address", {})
                return {
                    "city": address.get("city"),
                    "country": address.get("country"),
                    "region": address.get("geographicArea"),
                    "postal_code": address.get("postalCode"),
                }

        # Fallback to first location
        if locations:
            address = locations[0].get("address", {})
            return {
                "city": address.get("city"),
                "country": address.get("country"),
                "region": address.get("geographicArea"),
                "postal_code": address.get("postalCode"),
            }

        return None

    def _extract_logo_url(self, data: dict) -> str | None:
        """Extract logo URL from organization data."""
        logo_v2 = data.get("logoV2")
        if not logo_v2:
            return None

        # Try to get the original/cropped square logo
        if "original~" in logo_v2:
            elements = logo_v2.get("original~", {}).get("elements", [])
            if elements:
                # Get the largest image
                largest = max(elements, key=lambda x: x.get("data", {}).get("width", 0))
                return largest.get("identifiers", [{}])[0].get("identifier")

        if "cropped~" in logo_v2:
            elements = logo_v2.get("cropped~", {}).get("elements", [])
            if elements:
                largest = max(elements, key=lambda x: x.get("data", {}).get("width", 0))
                return largest.get("identifiers", [{}])[0].get("identifier")

        return None

    # =========================================================================
    # Debug/Status Methods
    # =========================================================================

    def get_status(self) -> dict[str, Any]:
        """Get client status information."""
        return {
            "client_type": "marketing_api",
            "api_version": self._api_version,
            "has_token": bool(self._access_token),
            "available_features": [
                "get_organization",
                "get_organization_by_vanity_name",
                "batch_get_organizations",
                "get_organization_follower_count",
            ],
            "documentation": "https://learn.microsoft.com/en-us/linkedin/marketing/community-management/organizations",
        }
