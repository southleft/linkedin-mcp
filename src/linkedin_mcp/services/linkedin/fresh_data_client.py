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
                logger.warning(
                    "Fresh Data API search requires Pro plan or higher",
                    status=response.status_code,
                    error=error_msg,
                    endpoint="/search-leads",
                    suggestion="Basic plan ($10/mo) doesn't include Search Lead/Company. Upgrade to Pro ($45/mo) for search capabilities.",
                )
                raise PermissionError(
                    f"Fresh Data API search requires Pro plan or higher. "
                    f"Basic plan doesn't include Search Lead/Company. "
                    f"Will fall back to linkedin-api if available. Error: {error_msg}"
                )
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
                logger.warning(
                    "Fresh Data API search endpoint not available",
                    status=response.status_code,
                    error=error_msg,
                    endpoint="/search-leads",
                    suggestion="This endpoint may require a higher subscription tier or may have been deprecated.",
                )
                raise RuntimeError(f"Fresh Data API search endpoint not available: {error_msg}")
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
    # Post & Engagement APIs
    # =========================================================================

    async def get_profile_posts(
        self,
        linkedin_url: str | None = None,
        public_id: str | None = None,
        post_type: str = "posts",
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """
        Get posts from a LinkedIn profile.

        Args:
            linkedin_url: Full LinkedIn profile URL
            public_id: LinkedIn public ID (e.g., "williamhgates")
            post_type: Type of content - "posts", "comments", or "reactions"
            limit: Maximum posts to return (API returns ~50 per page)

        Returns:
            List of post dicts with content, engagement counts, media
        """
        if not linkedin_url and not public_id:
            logger.error("Must provide either linkedin_url or public_id")
            return []

        if not linkedin_url and public_id:
            linkedin_url = f"https://www.linkedin.com/in/{public_id}"

        client = await self._get_client()
        all_posts: list[dict[str, Any]] = []
        start = 0

        try:
            while len(all_posts) < limit:
                params = {
                    "linkedin_url": linkedin_url,
                    "type": post_type,
                    "start": start,
                }

                response = await client.get(
                    f"{self.API_BASE}/get-profile-posts",
                    params=params,
                )

                if response.status_code == 200:
                    data = response.json()
                    posts = data.get("data", [])
                    if not posts:
                        break

                    for post in posts:
                        all_posts.append(self._normalize_post(post))
                        if len(all_posts) >= limit:
                            break

                    start += 50  # Pagination increment
                elif response.status_code == 403:
                    error_msg = response.json().get("message", "Access denied")
                    logger.error("Fresh Data API subscription required", error=error_msg)
                    raise PermissionError(f"Fresh Data API: {error_msg}")
                else:
                    logger.error("Failed to get posts", status=response.status_code)
                    break

            logger.info("Profile posts retrieved", count=len(all_posts))
            return all_posts[:limit]

        except PermissionError:
            raise
        except Exception as e:
            logger.error("Profile posts error", error=str(e))
            return []

    async def get_company_posts(
        self,
        linkedin_url: str | None = None,
        company_id: str | None = None,
        sort_by: str = "recent",
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """
        Get posts from a company page.

        Args:
            linkedin_url: Full LinkedIn company URL
            company_id: LinkedIn company ID
            sort_by: "recent" or "top"
            limit: Maximum posts to return

        Returns:
            List of post dicts
        """
        if not linkedin_url and not company_id:
            logger.error("Must provide either linkedin_url or company_id")
            return []

        if not linkedin_url and company_id:
            linkedin_url = f"https://www.linkedin.com/company/{company_id}"

        client = await self._get_client()
        all_posts: list[dict[str, Any]] = []
        start = 0

        try:
            while len(all_posts) < limit:
                params = {
                    "linkedin_url": linkedin_url,
                    "sort_by": sort_by,
                    "start": start,
                }

                response = await client.get(
                    f"{self.API_BASE}/get-company-posts",
                    params=params,
                )

                if response.status_code == 200:
                    data = response.json()
                    posts = data.get("data", [])
                    if not posts:
                        break

                    for post in posts:
                        all_posts.append(self._normalize_post(post))
                        if len(all_posts) >= limit:
                            break

                    start += 50
                elif response.status_code == 403:
                    error_msg = response.json().get("message", "Access denied")
                    raise PermissionError(f"Fresh Data API: {error_msg}")
                else:
                    logger.error("Failed to get company posts", status=response.status_code)
                    break

            logger.info("Company posts retrieved", count=len(all_posts))
            return all_posts[:limit]

        except PermissionError:
            raise
        except Exception as e:
            logger.error("Company posts error", error=str(e))
            return []

    async def get_post_comments(
        self,
        post_urn: str,
        sort_by: str = "relevance",
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """
        Get comments on a specific post.

        Args:
            post_urn: Post URN (e.g., "urn:li:activity:123456789")
            sort_by: "relevance" or "recent"
            limit: Maximum comments to return

        Returns:
            List of comment dicts with author info
        """
        client = await self._get_client()
        all_comments: list[dict[str, Any]] = []
        page = 0

        try:
            while len(all_comments) < limit:
                params = {
                    "urn": post_urn,
                    "sort_by": "Most relevant" if sort_by == "relevance" else "Most recent",
                    "page": page,
                }

                response = await client.get(
                    f"{self.API_BASE}/get-post-comments",
                    params=params,
                )

                if response.status_code == 200:
                    data = response.json()
                    comments = data.get("data", [])
                    if not comments:
                        break

                    for comment in comments:
                        all_comments.append(self._normalize_comment(comment))
                        if len(all_comments) >= limit:
                            break

                    page += 1
                elif response.status_code == 403:
                    error_msg = response.json().get("message", "Access denied")
                    raise PermissionError(f"Fresh Data API: {error_msg}")
                else:
                    logger.error("Failed to get comments", status=response.status_code)
                    break

            logger.info("Post comments retrieved", count=len(all_comments))
            return all_comments[:limit]

        except PermissionError:
            raise
        except Exception as e:
            logger.error("Post comments error", error=str(e))
            return []

    async def get_post_reactions(
        self,
        post_urn: str,
        reaction_type: str = "ALL",
        limit: int = 100,
    ) -> dict[str, Any]:
        """
        Get reactions on a specific post.

        Args:
            post_urn: Post URN (e.g., "urn:li:activity:123456789")
            reaction_type: "ALL", "LIKE", "EMPATHY", "APPRECIATION", "INTEREST", "PRAISE"
            limit: Maximum reactors to return

        Returns:
            Dict with reaction breakdown and list of reactors
        """
        client = await self._get_client()
        all_reactors: list[dict[str, Any]] = []
        page = 0

        try:
            while len(all_reactors) < limit:
                params = {
                    "urn": post_urn,
                    "type": reaction_type,
                    "page": page,
                }

                response = await client.get(
                    f"{self.API_BASE}/get-post-reactions",
                    params=params,
                )

                if response.status_code == 200:
                    data = response.json()
                    reactors = data.get("data", [])
                    total_count = data.get("total_count", 0)

                    if not reactors:
                        break

                    for reactor in reactors:
                        all_reactors.append({
                            "name": reactor.get("name"),
                            "headline": reactor.get("headline"),
                            "profile_url": reactor.get("linkedin_url"),
                            "profile_image": reactor.get("profile_image_url"),
                            "reaction_type": reactor.get("reaction_type"),
                        })
                        if len(all_reactors) >= limit:
                            break

                    page += 1
                elif response.status_code == 403:
                    error_msg = response.json().get("message", "Access denied")
                    raise PermissionError(f"Fresh Data API: {error_msg}")
                else:
                    logger.error("Failed to get reactions", status=response.status_code)
                    break

            logger.info("Post reactions retrieved", count=len(all_reactors))
            return {
                "total_count": len(all_reactors),
                "reactors": all_reactors[:limit],
                "source": "fresh_data_api",
            }

        except PermissionError:
            raise
        except Exception as e:
            logger.error("Post reactions error", error=str(e))
            return {"total_count": 0, "reactors": [], "error": str(e)}

    async def search_posts(
        self,
        keywords: str | None = None,
        sort_by: str = "recent",
        date_posted: str | None = None,
        content_type: str | None = None,
        from_member_urns: list[str] | None = None,
        from_company_ids: list[str] | None = None,
        limit: int = 25,
    ) -> list[dict[str, Any]]:
        """
        Search LinkedIn posts.

        Args:
            keywords: Search keywords
            sort_by: "recent" (Latest) or "top" (Top match)
            date_posted: "Past 24 hours", "Past week", "Past month", etc.
            content_type: "Videos", "Images", "Documents", etc.
            from_member_urns: Filter to specific member URNs
            from_company_ids: Filter to specific company IDs
            limit: Maximum posts to return

        Returns:
            List of matching posts
        """
        client = await self._get_client()

        try:
            search_params: dict[str, Any] = {}
            if keywords:
                search_params["search_keywords"] = keywords
            if sort_by:
                search_params["sort_by"] = "Latest" if sort_by == "recent" else "Top match"
            if date_posted:
                search_params["date_posted"] = date_posted
            if content_type:
                search_params["content_type"] = content_type
            if from_member_urns:
                search_params["from_member"] = from_member_urns
            if from_company_ids:
                search_params["from_company"] = from_company_ids

            all_posts: list[dict[str, Any]] = []
            page = 0

            while len(all_posts) < limit:
                search_params["page"] = page

                response = await client.post(
                    f"{self.API_BASE}/search-posts",
                    json=search_params,
                )

                if response.status_code == 200:
                    data = response.json()
                    posts = data.get("data", [])
                    if not posts:
                        break

                    for post in posts:
                        all_posts.append(self._normalize_post(post))
                        if len(all_posts) >= limit:
                            break

                    page += 1
                elif response.status_code == 403:
                    error_msg = response.json().get("message", "Access denied")
                    raise PermissionError(f"Fresh Data API: {error_msg}")
                else:
                    logger.error("Post search failed", status=response.status_code)
                    break

            logger.info("Post search completed", count=len(all_posts))
            return all_posts[:limit]

        except PermissionError:
            raise
        except Exception as e:
            logger.error("Post search error", error=str(e))
            return []

    def _normalize_post(self, data: dict) -> dict[str, Any]:
        """Normalize post data to consistent format.

        Includes both nested and flat field names for compatibility with
        analytics functions that expect numLikes/numComments.
        """
        num_likes = data.get("num_likes", 0) or 0
        num_comments = data.get("num_comments", 0) or 0
        num_reposts = data.get("num_reposts", 0) or 0
        text_content = data.get("text") or data.get("commentary") or ""

        return {
            "urn": data.get("urn") or data.get("post_urn"),
            "text": text_content,
            "commentary": text_content,  # Alias for analytics compatibility
            "post_url": data.get("post_url") or data.get("url"),
            "author": {
                "name": data.get("poster_name") or data.get("author_name"),
                "headline": data.get("poster_headline") or data.get("author_headline"),
                "profile_url": data.get("poster_linkedin_url") or data.get("author_url"),
                "profile_image": data.get("poster_image_url") or data.get("author_image"),
            },
            # Nested format (new style)
            "engagement": {
                "likes": num_likes,
                "comments": num_comments,
                "reposts": num_reposts,
            },
            # Flat format (for analytics compatibility)
            "numLikes": num_likes,
            "numComments": num_comments,
            "numReposts": num_reposts,
            "media": {
                "images": data.get("images", []),
                "video": data.get("video"),
                "document": data.get("document"),
            },
            "posted_at": data.get("time") or data.get("posted_at"),
            "source": "fresh_data_api",
        }

    def _normalize_comment(self, data: dict) -> dict[str, Any]:
        """Normalize comment data to consistent format."""
        return {
            "id": data.get("comment_id") or data.get("id"),
            "text": data.get("text") or data.get("comment"),
            "author": {
                "name": data.get("commenter_name") or data.get("author_name"),
                "headline": data.get("commenter_headline") or data.get("author_headline"),
                "profile_url": data.get("commenter_linkedin_url") or data.get("author_url"),
                "profile_image": data.get("commenter_image_url") or data.get("author_image"),
            },
            "engagement": {
                "likes": data.get("num_likes", 0),
                "replies": data.get("num_replies", 0),
            },
            "posted_at": data.get("time") or data.get("posted_at"),
            "source": "fresh_data_api",
        }

    # =========================================================================
    # Status Methods
    # =========================================================================

    def get_status(self) -> dict[str, Any]:
        """Get client status information."""
        return {
            "client_type": "fresh_data_api",
            "api_host": self.API_HOST,
            "has_api_key": bool(self._api_key),
            "features_by_plan": {
                "basic": [
                    "get_profile",
                    "get_company",
                    "get_profile_posts",
                    "get_company_posts",
                    "get_post_comments",
                    "get_post_reactions",
                    "job_search",
                ],
                "pro_and_above": [
                    "search_profiles (search-leads)",
                    "search_companies",
                    "get_company_employees",
                    "search_posts",
                ],
            },
            "note": "Search Lead/Company requires Pro plan ($45/mo) or higher. Basic plan supports profile/company lookup and posts.",
            "documentation": "https://fdocs.info/api-reference/quickstart",
            "subscription": "https://rapidapi.com/freshdata-freshdata-default/api/web-scraping-api2",
        }
