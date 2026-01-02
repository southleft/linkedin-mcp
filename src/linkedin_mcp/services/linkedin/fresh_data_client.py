"""
Fresh LinkedIn Data API Client.

Third-party API for comprehensive LinkedIn data access including:
- Profile search and lookup
- Company/organization data
- Employee search at scale
- Job search

API Provider: RapidAPI (web-scraping-api2 by freshdata)
Documentation: https://fdocs.info/api-reference/quickstart

IMPORTANT: RapidAPI Provider Status (as of January 2026):
- web-scraping-api2.p.rapidapi.com (freshdata) - ACTIVE, requires subscription
- fresh-linkedin-profile-data.p.rapidapi.com (freshdata) - DEPRECATED, endpoints don't exist
- linkedin-api8.p.rapidapi.com (rockapis) - DISCONTINUED
- linkedin-data-api.p.rapidapi.com (rockapis) - DISCONTINUED
- fresh-linkedin-scraper-api.p.rapidapi.com (saleleadsdotai) - Requires separate subscription

Subscribe to web-scraping-api2:
https://rapidapi.com/freshdata-freshdata-default/api/web-scraping-api2
"""

import asyncio
from typing import Any

import httpx
import structlog

logger = structlog.get_logger(__name__)


class FreshLinkedInDataClient:
    """
    Fresh LinkedIn Data API Client via RapidAPI.

    This client provides access to comprehensive LinkedIn data through
    the Fresh LinkedIn Profile Data API on RapidAPI.

    Features:
    - Profile lookup by URL or public ID
    - Company/organization data
    - People search with filters
    - Employee search by company
    - Job search

    Pricing: Pay-per-request via RapidAPI
    Documentation: https://fdocs.info/api-reference/quickstart
    """

    # API endpoints - Using web-scraping-api2 (freshdata provider)
    # Note: fresh-linkedin-profile-data.p.rapidapi.com endpoints no longer exist
    # rockapis providers (linkedin-api8, linkedin-data-api) are discontinued
    API_HOST = "web-scraping-api2.p.rapidapi.com"
    API_BASE = f"https://{API_HOST}"

    def __init__(
        self,
        rapidapi_key: str,
        timeout: float = 30.0,
    ):
        """
        Initialize the Fresh Data API client.

        Args:
            rapidapi_key: RapidAPI key for authentication
            timeout: Request timeout in seconds
        """
        self._api_key = rapidapi_key
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self._timeout,
                headers=self._get_headers(),
            )
        return self._client

    def _get_headers(self) -> dict[str, str]:
        """Get headers for API requests."""
        return {
            "x-rapidapi-key": self._api_key,
            "x-rapidapi-host": self.API_HOST,
            "Content-Type": "application/json",
        }

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    # =========================================================================
    # Profile APIs
    # =========================================================================

    async def get_profile(
        self,
        linkedin_url: str | None = None,
        public_id: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Get a LinkedIn profile by URL or public ID.

        Args:
            linkedin_url: Full LinkedIn profile URL
            public_id: LinkedIn public ID (e.g., "williamhgates")

        Returns:
            Profile data dict or None on error
        """
        if not linkedin_url and not public_id:
            logger.error("Must provide either linkedin_url or public_id")
            return None

        # Construct URL if only public_id provided
        if not linkedin_url and public_id:
            linkedin_url = f"https://www.linkedin.com/in/{public_id}"

        client = await self._get_client()

        try:
            response = await client.get(
                f"{self.API_BASE}/get-personal-profile",
                params={"linkedin_url": linkedin_url},
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("data"):
                    logger.info("Profile lookup successful", url=linkedin_url)
                    return self._normalize_profile(data["data"])
                else:
                    logger.warning("Profile not found", url=linkedin_url)
                    return None
            elif response.status_code == 403:
                error_msg = response.json().get("message", "Access denied")
                logger.error(
                    "Fresh Data API subscription required",
                    status=response.status_code,
                    error=error_msg,
                )
                raise PermissionError(f"Fresh Data API: {error_msg}. Subscribe at: https://rapidapi.com/freshdata-freshdata-default/api/web-scraping-api2")
            elif response.status_code == 429:
                error_msg = response.json().get("message", "Rate limited")
                logger.warning("Fresh Data API rate limited", error=error_msg)
                raise RuntimeError(f"Fresh Data API rate limited: {error_msg}")
            elif response.status_code == 404:
                # API endpoint doesn't exist - provider may have changed or deprecated
                error_data = response.json() if response.text else {}
                error_msg = error_data.get("message", "Endpoint not found")
                logger.error(
                    "Fresh Data API endpoint not found (API may be deprecated)",
                    status=response.status_code,
                    error=error_msg,
                    url=linkedin_url,
                )
                raise RuntimeError(f"Fresh Data API endpoint not found: {error_msg}. The API provider may have changed or deprecated this endpoint.")
            else:
                logger.error(
                    "Profile lookup failed",
                    url=linkedin_url,
                    status=response.status_code,
                    error=response.text[:500],
                )
                return None

        except (PermissionError, RuntimeError):
            raise
        except Exception as e:
            logger.error("Profile lookup error", url=linkedin_url, error=str(e))
            raise RuntimeError(f"Fresh Data API error: {str(e)}")

    async def search_profiles(
        self,
        query: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        title_keywords: list[str] | None = None,
        company_names: list[str] | None = None,
        company_ids: list[int] | None = None,
        locations: list[str] | None = None,
        geo_codes: list[int] | None = None,
        industries: list[int] | None = None,
        seniority_levels: list[str] | None = None,
        functions: list[str] | None = None,
        limit: int = 25,
    ) -> list[dict[str, Any]]:
        """
        Search for LinkedIn profiles with various filters.

        Args:
            query: General search query
            first_name: Filter by first name
            last_name: Filter by last name
            title_keywords: Filter by job title keywords
            company_names: Filter by current company names
            company_ids: Filter by LinkedIn company IDs
            locations: Filter by location names
            geo_codes: Filter by LinkedIn geo codes
            industries: Filter by industry codes
            seniority_levels: Filter by seniority (e.g., "Director", "VP")
            functions: Filter by function (e.g., "Engineering", "Sales")
            limit: Maximum results to return (default 25)

        Returns:
            List of profile dicts
        """
        client = await self._get_client()

        # Build search parameters
        search_params = {}
        if query:
            search_params["keywords"] = query
        if first_name:
            search_params["first_name"] = first_name
        if last_name:
            search_params["last_name"] = last_name
        if title_keywords:
            search_params["title_keywords"] = title_keywords
        if company_names:
            search_params["current_company_names"] = company_names
        if company_ids:
            search_params["current_company_ids"] = company_ids
        if geo_codes:
            search_params["geo_codes"] = geo_codes
        if industries:
            search_params["industry_codes"] = industries
        if seniority_levels:
            search_params["seniority_levels"] = seniority_levels
        if functions:
            search_params["functions"] = functions

        try:
            # Use the search-leads endpoint for comprehensive results
            response = await client.post(
                f"{self.API_BASE}/search-leads",
                json=search_params,
            )

            if response.status_code == 200:
                data = response.json()
                request_id = data.get("request_id")
                total_count = data.get("total_count", 0)

                if request_id:
                    # Need to poll for results
                    results = await self._poll_search_results(request_id, limit)
                    logger.info("Profile search completed", count=len(results), total=total_count)
                    return results
                else:
                    # Direct results
                    leads = data.get("leads", data.get("data", []))
                    results = [self._normalize_profile(p) for p in leads[:limit]]
                    logger.info("Profile search completed", count=len(results))
                    return results
            elif response.status_code == 403:
                error_msg = response.json().get("message", "Access denied")
                logger.error(
                    "Fresh Data API subscription required",
                    status=response.status_code,
                    error=error_msg,
                )
                raise PermissionError(f"Fresh Data API: {error_msg}. Subscribe at: https://rapidapi.com/freshdata-freshdata-default/api/web-scraping-api2")
            elif response.status_code == 429:
                error_msg = response.json().get("message", "Rate limited")
                logger.warning(
                    "Fresh Data API rate limited",
                    status=response.status_code,
                    error=error_msg,
                )
                raise RuntimeError(f"Fresh Data API rate limited: {error_msg}")
            elif response.status_code == 404:
                # API endpoint doesn't exist - provider may have changed or deprecated
                error_data = response.json() if response.text else {}
                error_msg = error_data.get("message", "Endpoint not found")
                logger.error(
                    "Fresh Data API search endpoint not found (API may be deprecated)",
                    status=response.status_code,
                    error=error_msg,
                )
                raise RuntimeError(f"Fresh Data API endpoint not found: {error_msg}. The API provider may have changed or deprecated this endpoint.")
            else:
                logger.error(
                    "Profile search failed",
                    status=response.status_code,
                    error=response.text[:500],
                )
                raise RuntimeError(f"Fresh Data API error: {response.status_code}")

        except (PermissionError, RuntimeError):
            raise  # Re-raise API-specific errors for fallback handling
        except Exception as e:
            logger.error("Profile search error", error=str(e))
            raise

    async def _poll_search_results(
        self,
        request_id: str,
        limit: int,
        max_attempts: int = 10,
        delay: float = 2.0,
    ) -> list[dict[str, Any]]:
        """
        Poll for search results by request ID.

        Args:
            request_id: Search request ID
            limit: Maximum results to return
            max_attempts: Maximum polling attempts
            delay: Delay between attempts in seconds

        Returns:
            List of result dicts
        """
        client = await self._get_client()

        for attempt in range(max_attempts):
            try:
                # First check status
                response = await client.get(
                    f"{self.API_BASE}/check-search-status",
                    params={"request_id": request_id},
                )

                if response.status_code == 200:
                    data = response.json()
                    status = data.get("status", "").lower()

                    if status == "completed" or "data" in data:
                        # If data is included in status response, use it
                        results = data.get("data", [])
                        if results:
                            return [self._normalize_profile(p) for p in results[:limit]]

                        # Otherwise fetch results separately
                        results_response = await client.get(
                            f"{self.API_BASE}/get-search-results",
                            params={"request_id": request_id},
                        )
                        if results_response.status_code == 200:
                            results_data = results_response.json()
                            results = results_data.get("data", results_data.get("leads", []))
                            return [self._normalize_profile(p) for p in results[:limit]]
                        return []
                    elif status in ("pending", "processing", "in_progress"):
                        await asyncio.sleep(delay)
                        continue
                    elif status == "failed":
                        logger.error("Search request failed", request_id=request_id)
                        return []
                else:
                    logger.warning(
                        "Search status check failed",
                        request_id=request_id,
                        status=response.status_code,
                    )

            except Exception as e:
                logger.warning("Search status poll error", attempt=attempt, error=str(e))

            await asyncio.sleep(delay)

        logger.warning("Search polling timed out", request_id=request_id)
        return []

    # =========================================================================
    # Company APIs
    # =========================================================================

    async def get_company(
        self,
        linkedin_url: str | None = None,
        company_id: int | str | None = None,
        vanity_name: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Get company/organization data.

        Args:
            linkedin_url: Full LinkedIn company URL
            company_id: LinkedIn company ID
            vanity_name: Company vanity name (URL slug)

        Returns:
            Company data dict or None on error
        """
        # Construct URL if needed
        if not linkedin_url:
            if vanity_name:
                linkedin_url = f"https://www.linkedin.com/company/{vanity_name}"
            elif company_id:
                linkedin_url = f"https://www.linkedin.com/company/{company_id}"
            else:
                logger.error("Must provide linkedin_url, company_id, or vanity_name")
                return None

        client = await self._get_client()

        try:
            response = await client.get(
                f"{self.API_BASE}/get-company-by-linkedinurl",
                params={"linkedin_url": linkedin_url},
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("data"):
                    logger.info("Company lookup successful", url=linkedin_url)
                    return self._normalize_company(data["data"])
                else:
                    logger.warning("Company not found", url=linkedin_url)
                    return None
            elif response.status_code == 403:
                error_msg = response.json().get("message", "Access denied")
                logger.error("Fresh Data API subscription required", error=error_msg)
                raise PermissionError(f"Fresh Data API: {error_msg}. Subscribe at: https://rapidapi.com/freshdata-freshdata-default/api/web-scraping-api2")
            elif response.status_code == 429:
                error_msg = response.json().get("message", "Rate limited")
                logger.warning("Fresh Data API rate limited", error=error_msg)
                raise RuntimeError(f"Fresh Data API rate limited: {error_msg}")
            else:
                logger.error(
                    "Company lookup failed",
                    url=linkedin_url,
                    status=response.status_code,
                    error=response.text[:500],
                )
                return None

        except (PermissionError, RuntimeError):
            raise
        except Exception as e:
            logger.error("Company lookup error", url=linkedin_url, error=str(e))
            return None

    async def search_companies(
        self,
        query: str,
        industries: list[int] | None = None,
        company_sizes: list[str] | None = None,
        locations: list[int] | None = None,
        limit: int = 25,
    ) -> list[dict[str, Any]]:
        """
        Search for companies.

        Args:
            query: Search query (company name or keywords)
            industries: Filter by industry codes
            company_sizes: Filter by size ranges (e.g., "51-200", "1001-5000")
            locations: Filter by geo codes
            limit: Maximum results

        Returns:
            List of company dicts
        """
        client = await self._get_client()

        search_params = {"query": query}
        if industries:
            search_params["industry_codes"] = industries
        if company_sizes:
            search_params["company_headcounts"] = company_sizes
        if locations:
            search_params["geo_codes"] = locations

        try:
            response = await client.post(
                f"{self.API_BASE}/search-companies",
                json=search_params,
            )

            if response.status_code == 200:
                data = response.json()
                companies = data.get("data", data.get("companies", []))
                results = [self._normalize_company(c) for c in companies[:limit]]
                logger.info("Company search completed", count=len(results))
                return results
            elif response.status_code == 403:
                error_msg = response.json().get("message", "Access denied")
                logger.error("Fresh Data API subscription required", error=error_msg)
                raise PermissionError(f"Fresh Data API: {error_msg}. Subscribe at: https://rapidapi.com/freshdata-freshdata-default/api/web-scraping-api2")
            elif response.status_code == 429:
                error_msg = response.json().get("message", "Rate limited")
                logger.warning("Fresh Data API rate limited", error=error_msg)
                raise RuntimeError(f"Fresh Data API rate limited: {error_msg}")
            else:
                logger.error(
                    "Company search failed",
                    status=response.status_code,
                    error=response.text[:500],
                )
                raise RuntimeError(f"Fresh Data API error: {response.status_code}")

        except (PermissionError, RuntimeError):
            raise
        except Exception as e:
            logger.error("Company search error", error=str(e))
            raise

    async def get_company_employees(
        self,
        company_id: int | str | None = None,
        company_name: str | None = None,
        title_keywords: list[str] | None = None,
        limit: int = 25,
    ) -> list[dict[str, Any]]:
        """
        Get employees of a company.

        Args:
            company_id: LinkedIn company ID
            company_name: Company name to search
            title_keywords: Filter by job title keywords
            limit: Maximum results

        Returns:
            List of employee profile dicts
        """
        search_params = {}
        if company_id:
            search_params["current_company_ids"] = [int(company_id)]
        if company_name:
            search_params["current_company_names"] = [company_name]
        if title_keywords:
            search_params["title_keywords"] = title_keywords

        return await self.search_profiles(**search_params, limit=limit)

    # =========================================================================
    # Normalization Methods
    # =========================================================================

    def _normalize_profile(self, data: dict) -> dict[str, Any]:
        """Normalize profile data to consistent format."""
        return {
            "id": data.get("profile_id") or data.get("public_id") or data.get("urn", "").split(":")[-1],
            "public_id": data.get("public_id"),
            "first_name": data.get("first_name"),
            "last_name": data.get("last_name"),
            "full_name": f"{data.get('first_name', '')} {data.get('last_name', '')}".strip() or data.get("name"),
            "headline": data.get("headline"),
            "summary": data.get("about") or data.get("summary"),
            "location": data.get("location"),
            "city": data.get("city"),
            "country": data.get("country"),
            "profile_url": data.get("linkedin_url") or data.get("redirected_url"),
            "profile_image_url": data.get("profile_image_url"),
            "connection_count": data.get("connection_count"),
            "current_company": data.get("company"),
            "current_title": data.get("job_title") or data.get("headline"),
            "email": data.get("email"),
            "phone": data.get("phone"),
            "experiences": self._normalize_experiences(data.get("experiences", [])),
            "education": self._normalize_education(data.get("educations", [])),
            "skills": data.get("skills", []),
            "languages": data.get("languages"),
            "source": "fresh_data_api",
        }

    def _normalize_experiences(self, experiences: list) -> list[dict]:
        """Normalize experience data."""
        normalized = []
        for exp in experiences:
            normalized.append({
                "company": exp.get("company"),
                "company_id": exp.get("company_id"),
                "company_url": exp.get("company_linkedin_url"),
                "company_logo": exp.get("company_logo_url"),
                "title": exp.get("title"),
                "date_range": exp.get("date_range"),
                "description": exp.get("description"),
                "location": exp.get("location"),
            })
        return normalized

    def _normalize_education(self, education: list) -> list[dict]:
        """Normalize education data."""
        normalized = []
        for edu in education:
            normalized.append({
                "school": edu.get("school"),
                "school_id": edu.get("school_id"),
                "school_url": edu.get("school_linkedin_url"),
                "degree": edu.get("degree"),
                "field_of_study": edu.get("field_of_study"),
                "date_range": edu.get("date_range"),
                "start_year": edu.get("start_year"),
                "end_year": edu.get("end_year"),
                "activities": edu.get("activities"),
            })
        return normalized

    def _normalize_company(self, data: dict) -> dict[str, Any]:
        """Normalize company data to consistent format."""
        return {
            "id": data.get("company_id") or data.get("id"),
            "name": data.get("name") or data.get("company"),
            "vanity_name": data.get("vanity_name") or data.get("universal_name"),
            "description": data.get("description") or data.get("company_description"),
            "website": data.get("website") or data.get("company_website"),
            "domain": data.get("company_domain"),
            "industry": data.get("industry") or data.get("company_industry"),
            "company_size": data.get("company_size") or data.get("company_employee_range"),
            "employee_count": data.get("employee_count"),
            "founded_year": data.get("founded_year") or data.get("company_year_founded"),
            "headquarters": {
                "city": data.get("hq_city") or data.get("city"),
                "country": data.get("hq_country") or data.get("country"),
                "region": data.get("hq_region") or data.get("state"),
            },
            "logo_url": data.get("logo_url") or data.get("company_logo_url"),
            "linkedin_url": data.get("linkedin_url") or data.get("company_linkedin_url"),
            "specialties": data.get("specialties", []),
            "company_type": data.get("company_type"),
            "follower_count": data.get("follower_count"),
            "source": "fresh_data_api",
        }

    # =========================================================================
    # Post & Engagement APIs (FUTURE IMPLEMENTATION)
    # =========================================================================
    # The Fresh Data API (web-scraping-api2) provides these post/engagement
    # endpoints that can be implemented to replace unreliable linkedin-api tools:
    #
    # AVAILABLE ENDPOINTS (from API research, January 2026):
    # -------------------------------------------------------
    # 1. GET /get-user-posts
    #    - Retrieve a user's activity and posts
    #    - Params: linkedin_url or profile_id
    #    - Returns: List of posts with content, timestamps, engagement counts
    #
    # 2. GET /get-user-comments
    #    - Access comments made by a specific user
    #    - Params: linkedin_url or profile_id
    #    - Returns: List of comments with post context
    #
    # 3. GET /get-user-reactions
    #    - See a user's engagement with content (likes, etc.)
    #    - Params: linkedin_url or profile_id
    #    - Returns: List of posts the user has reacted to
    #
    # 4. GET /get-post-details
    #    - Retrieve complete information about a specific post
    #    - Params: post_url or post_urn
    #    - Returns: Full post content, author, media, engagement metrics
    #
    # 5. GET /get-post-comments
    #    - Get comments on a specific LinkedIn post
    #    - Params: post_url or post_urn, limit
    #    - Returns: List of comments with author info and nested replies
    #
    # 6. GET /get-post-reactions
    #    - View reaction data (likes, celebrates, etc.) for a post
    #    - Params: post_url or post_urn
    #    - Returns: Reaction breakdown by type, list of reactors
    #
    # 7. GET /get-post-reposts
    #    - See who has reshared a particular post
    #    - Params: post_url or post_urn
    #    - Returns: List of users who reshared with their post URLs
    #
    # PRICING (Ultra tier - $200/month):
    # - 100,000 requests/month
    # - 120 requests/minute rate limit
    # - 98% service level claimed
    #
    # API DOCUMENTATION:
    # - https://fdocs.info/api-reference/quickstart
    # - https://rapidapi.com/freshdata-freshdata-default/api/web-scraping-api2
    #
    # IMPLEMENTATION PRIORITY (recommended):
    # 1. get_user_posts - For feed and profile posts retrieval
    # 2. get_post_details - For individual post analysis
    # 3. get_post_comments - For engagement analytics
    # 4. get_post_reactions - For engagement breakdown
    # =========================================================================

    # Placeholder stubs for future implementation:
    #
    # async def get_user_posts(
    #     self,
    #     linkedin_url: str | None = None,
    #     public_id: str | None = None,
    #     limit: int = 10,
    # ) -> list[dict[str, Any]]:
    #     """Get posts from a LinkedIn profile."""
    #     pass
    #
    # async def get_post_details(
    #     self,
    #     post_url: str | None = None,
    #     post_urn: str | None = None,
    # ) -> dict[str, Any] | None:
    #     """Get detailed information about a specific post."""
    #     pass
    #
    # async def get_post_comments(
    #     self,
    #     post_url: str | None = None,
    #     post_urn: str | None = None,
    #     limit: int = 50,
    # ) -> list[dict[str, Any]]:
    #     """Get comments on a specific post."""
    #     pass
    #
    # async def get_post_reactions(
    #     self,
    #     post_url: str | None = None,
    #     post_urn: str | None = None,
    # ) -> dict[str, Any]:
    #     """Get reaction breakdown for a post."""
    #     pass

    # =========================================================================
    # Status Methods
    # =========================================================================

    def get_status(self) -> dict[str, Any]:
        """Get client status information."""
        return {
            "client_type": "fresh_data_api",
            "api_host": self.API_HOST,
            "has_api_key": bool(self._api_key),
            "available_features": [
                "get_profile",
                "search_profiles",
                "get_company",
                "search_companies",
                "get_company_employees",
            ],
            "future_features": [
                # These endpoints are available in the API but not yet implemented
                "get_user_posts",
                "get_user_comments",
                "get_user_reactions",
                "get_post_details",
                "get_post_comments",
                "get_post_reactions",
                "get_post_reposts",
            ],
            "documentation": "https://fdocs.info/api-reference/quickstart",
            "subscription": "https://rapidapi.com/freshdata-freshdata-default/api/web-scraping-api2",
        }
