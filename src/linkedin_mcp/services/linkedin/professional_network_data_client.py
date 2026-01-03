"""
Professional Network Data API Client.

Third-party API for comprehensive LinkedIn data access including:
- Profile enrichment and search
- Company/organization data
- Posts, comments, and reactions
- Articles (NEW - not available in previous API)
- Similar profiles and interests (NEW)

API Provider: RapidAPI (professional-network-data by pnd-team)
Documentation: https://rapidapi.com/pnd-team-pnd-team/api/professional-network-data

NOTE: This is the recommended successor to web-scraping-api2 (Fresh Data API)
by the same creator (Stefan Yilmaz). It offers more endpoints (55 vs ~13)
and additional features like article retrieval and profile interests.

Subscribe: https://rapidapi.com/pnd-team-pnd-team/api/professional-network-data
"""

import asyncio
from typing import Any

import httpx
import structlog

logger = structlog.get_logger(__name__)


class ProfessionalNetworkDataClient:
    """
    Professional Network Data API Client via RapidAPI.

    This is the successor to FreshLinkedInDataClient with expanded capabilities:
    - 55 endpoints across 7 categories
    - Article retrieval (NEW)
    - Profile interests (NEW)
    - Similar profiles (NEW)
    - Last active time (NEW)
    - Hiring team data (NEW)

    Pricing tiers:
    - BASIC: Free (limited)
    - PRO: $50/month
    - ULTRA: $175/month
    - MEGA: $500/month

    Documentation: https://rapidapi.com/pnd-team-pnd-team/api/professional-network-data
    """

    # API endpoints - Professional Network Data (pnd-team)
    API_HOST = "professional-network-data.p.rapidapi.com"
    API_BASE = f"https://{API_HOST}"

    def __init__(
        self,
        rapidapi_key: str,
        timeout: float = 30.0,
    ):
        """
        Initialize the Professional Network Data API client.

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

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        params: dict | None = None,
        json_data: dict | None = None,
    ) -> dict[str, Any] | None:
        """
        Make an API request with standard error handling.

        Args:
            method: HTTP method (GET or POST)
            endpoint: API endpoint path
            params: Query parameters
            json_data: JSON body data

        Returns:
            Response data dict or None on error
        """
        client = await self._get_client()
        url = f"{self.API_BASE}{endpoint}"

        try:
            if method.upper() == "GET":
                response = await client.get(url, params=params)
            else:
                response = await client.post(url, json=json_data)

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 403:
                error_msg = response.json().get("message", "Access denied")
                logger.error(
                    "Professional Network Data API subscription required",
                    status=response.status_code,
                    error=error_msg,
                    endpoint=endpoint,
                )
                raise PermissionError(
                    f"Professional Network Data API: {error_msg}. "
                    f"Subscribe at: https://rapidapi.com/pnd-team-pnd-team/api/professional-network-data"
                )
            elif response.status_code == 429:
                error_msg = response.json().get("message", "Rate limited")
                logger.warning(
                    "Professional Network Data API rate limited",
                    error=error_msg,
                    endpoint=endpoint,
                )
                raise RuntimeError(f"Professional Network Data API rate limited: {error_msg}")
            elif response.status_code == 404:
                error_data = response.json() if response.text else {}
                error_msg = error_data.get("message", "Endpoint not found")
                logger.error(
                    "Professional Network Data API endpoint not found",
                    status=response.status_code,
                    error=error_msg,
                    endpoint=endpoint,
                )
                raise RuntimeError(f"Professional Network Data API endpoint not found: {error_msg}")
            else:
                logger.error(
                    "API request failed",
                    endpoint=endpoint,
                    status=response.status_code,
                    error=response.text[:500],
                )
                return None

        except (PermissionError, RuntimeError):
            raise
        except Exception as e:
            logger.error("API request error", endpoint=endpoint, error=str(e))
            raise RuntimeError(f"Professional Network Data API error: {str(e)}")

    # =========================================================================
    # Profile APIs (People Enrichment)
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

        try:
            data = await self._make_request(
                "GET",
                "/person",
                params={"link": linkedin_url},
            )

            if data and data.get("data"):
                logger.info("Profile lookup successful", url=linkedin_url)
                return self._normalize_profile(data["data"])
            else:
                logger.warning("Profile not found", url=linkedin_url)
                return None

        except (PermissionError, RuntimeError):
            raise
        except Exception as e:
            logger.error("Profile lookup error", url=linkedin_url, error=str(e))
            return None

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
        # Build search parameters
        search_params: dict[str, Any] = {}
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
            data = await self._make_request(
                "POST",
                "/search-people",
                json_data=search_params,
            )

            if data:
                results = data.get("data", data.get("leads", []))
                normalized = [self._normalize_profile(p) for p in results[:limit]]
                logger.info("Profile search completed", count=len(normalized))
                return normalized
            return []

        except (PermissionError, RuntimeError):
            raise
        except Exception as e:
            logger.error("Profile search error", error=str(e))
            raise

    async def get_profile_interests(
        self,
        linkedin_url: str | None = None,
        public_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Get interests and topics followed by a profile (NEW CAPABILITY).

        Args:
            linkedin_url: Full LinkedIn profile URL
            public_id: LinkedIn public ID

        Returns:
            Dict with interests, companies followed, schools, etc.
        """
        if not linkedin_url and not public_id:
            return {"error": "Must provide either linkedin_url or public_id"}

        if not linkedin_url and public_id:
            linkedin_url = f"https://www.linkedin.com/in/{public_id}"

        try:
            # Use username from public_id for the interests endpoint
            username = public_id or linkedin_url.split("/in/")[-1].rstrip("/")
            data = await self._make_request(
                "POST",
                "/profiles/interests/groups",
                json_data={"username": username, "page": 1},
            )

            if data and data.get("data"):
                interests_data = data["data"]
                return {
                    "influencers": interests_data.get("influencers", []),
                    "companies": interests_data.get("companies", []),
                    "groups": interests_data.get("groups", []),
                    "schools": interests_data.get("schools", []),
                    "topics": interests_data.get("topics", []),
                    "source": "professional_network_data_api",
                }
            return {"error": "No interests data found"}

        except (PermissionError, RuntimeError):
            raise
        except Exception as e:
            logger.error("Profile interests error", error=str(e))
            return {"error": str(e)}

    async def get_similar_profiles(
        self,
        linkedin_url: str | None = None,
        public_id: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Get similar profiles to a given profile (NEW CAPABILITY).

        Args:
            linkedin_url: Full LinkedIn profile URL
            public_id: LinkedIn public ID
            limit: Maximum similar profiles to return

        Returns:
            List of similar profile dicts
        """
        if not linkedin_url and not public_id:
            return []

        if not linkedin_url and public_id:
            linkedin_url = f"https://www.linkedin.com/in/{public_id}"

        try:
            data = await self._make_request(
                "GET",
                "/similar-profiles",
                params={"url": linkedin_url},
            )

            if data:
                # Handle both list response and dict with "data" key
                if isinstance(data, list):
                    profiles = data
                elif isinstance(data, dict):
                    profiles = data.get("data", data.get("profiles", []))
                else:
                    profiles = []

                if profiles:
                    normalized = [self._normalize_profile(p) for p in profiles[:limit]]
                    logger.info("Similar profiles retrieved", count=len(normalized))
                    return normalized
            return []

        except (PermissionError, RuntimeError):
            raise
        except Exception as e:
            logger.error("Similar profiles error", error=str(e))
            return []

    async def get_profile_network(
        self,
        linkedin_url: str | None = None,
        public_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Get network statistics for a profile.

        Args:
            linkedin_url: Full LinkedIn profile URL
            public_id: LinkedIn public ID

        Returns:
            Dict with connections count, followers, etc.
        """
        if not linkedin_url and not public_id:
            return {"error": "Must provide either linkedin_url or public_id"}

        if not linkedin_url and public_id:
            linkedin_url = f"https://www.linkedin.com/in/{public_id}"

        try:
            data = await self._make_request(
                "GET",
                "/person-network",
                params={"link": linkedin_url},
            )

            if data and data.get("data"):
                network_data = data["data"]
                return {
                    "connections": network_data.get("connections"),
                    "followers": network_data.get("followers"),
                    "following": network_data.get("following"),
                    "source": "professional_network_data_api",
                }
            return {}

        except (PermissionError, RuntimeError):
            raise
        except Exception as e:
            logger.error("Profile network error", error=str(e))
            return {"error": str(e)}

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

        try:
            data = await self._make_request(
                "GET",
                "/company",
                params={"link": linkedin_url},
            )

            if data and data.get("data"):
                logger.info("Company lookup successful", url=linkedin_url)
                return self._normalize_company(data["data"])
            else:
                logger.warning("Company not found", url=linkedin_url)
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
        search_params: dict[str, Any] = {"query": query}
        if industries:
            search_params["industry_codes"] = industries
        if company_sizes:
            search_params["company_headcounts"] = company_sizes
        if locations:
            search_params["geo_codes"] = locations

        try:
            data = await self._make_request(
                "POST",
                "/search-companies",
                json_data=search_params,
            )

            if data:
                companies = data.get("data", data.get("companies", []))
                results = [self._normalize_company(c) for c in companies[:limit]]
                logger.info("Company search completed", count=len(results))
                return results
            return []

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
        search_params: dict[str, Any] = {}
        if company_id:
            search_params["current_company_ids"] = [int(company_id)]
        if company_name:
            search_params["current_company_names"] = [company_name]
        if title_keywords:
            search_params["title_keywords"] = title_keywords

        return await self.search_profiles(**search_params, limit=limit)

    async def get_company_by_domain(
        self,
        domain: str,
    ) -> dict[str, Any] | None:
        """
        Get company by domain name (NEW CAPABILITY).

        Args:
            domain: Company website domain (e.g., "anthropic.com")

        Returns:
            Company data dict or None
        """
        try:
            data = await self._make_request(
                "GET",
                "/get-company-by-domain",
                params={"domain": domain},
            )

            if data:
                # Handle both direct dict response and nested "data" key
                if isinstance(data, dict):
                    company_data = data.get("data", data) if "data" in data else data
                    # Skip if it's just an error response
                    if company_data and not company_data.get("error"):
                        logger.info("Company lookup by domain successful", domain=domain)
                        return self._normalize_company(company_data)
            return None

        except (PermissionError, RuntimeError):
            raise
        except Exception as e:
            logger.error("Company domain lookup error", domain=domain, error=str(e))
            return None

    # =========================================================================
    # Article APIs (NEW - Not available in Fresh Data API)
    # =========================================================================

    async def get_article(
        self,
        article_url: str,
    ) -> dict[str, Any] | None:
        """
        Get a LinkedIn article by URL (NEW CAPABILITY).

        This is not available in the Fresh Data API.

        Args:
            article_url: Full LinkedIn article URL

        Returns:
            Article data dict or None
        """
        try:
            data = await self._make_request(
                "GET",
                "/get-article",
                params={"url": article_url},
            )

            if data:
                # Handle both direct dict response and nested "data" key
                if isinstance(data, dict):
                    article_data = data.get("data", data) if "data" in data else data
                    if article_data and not article_data.get("error"):
                        logger.info("Article lookup successful", url=article_url)
                        return self._normalize_article(article_data)
            return None

        except (PermissionError, RuntimeError):
            raise
        except Exception as e:
            logger.error("Article lookup error", url=article_url, error=str(e))
            return None

    async def get_profile_articles(
        self,
        linkedin_url: str | None = None,
        public_id: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """
        Get articles written by a profile (NEW CAPABILITY).

        Args:
            linkedin_url: Full LinkedIn profile URL
            public_id: LinkedIn public ID
            limit: Maximum articles to return

        Returns:
            List of article dicts
        """
        if not linkedin_url and not public_id:
            return []

        if not linkedin_url and public_id:
            linkedin_url = f"https://www.linkedin.com/in/{public_id}"

        try:
            # Use username from public_id for the articles endpoint
            username = public_id or linkedin_url.split("/in/")[-1].rstrip("/")
            data = await self._make_request(
                "GET",
                "/get-user-articles",
                params={"username": username},
            )

            if data:
                # Handle both list response and dict with "data" key
                if isinstance(data, list):
                    articles = data
                elif isinstance(data, dict):
                    articles = data.get("data", data.get("articles", []))
                else:
                    articles = []

                if articles:
                    normalized = [self._normalize_article(a) for a in articles[:limit]]
                    logger.info("Profile articles retrieved", count=len(normalized))
                    return normalized
            return []

        except (PermissionError, RuntimeError):
            raise
        except Exception as e:
            logger.error("Profile articles error", error=str(e))
            return []

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
            limit: Maximum posts to return

        Returns:
            List of post dicts with content, engagement counts, media
        """
        if not linkedin_url and not public_id:
            logger.error("Must provide either linkedin_url or public_id")
            return []

        if not linkedin_url and public_id:
            linkedin_url = f"https://www.linkedin.com/in/{public_id}"

        try:
            data = await self._make_request(
                "GET",
                "/person-posts",
                params={"link": linkedin_url, "type": post_type},
            )

            if data and data.get("data"):
                posts = data["data"]
                normalized = [self._normalize_post(p) for p in posts[:limit]]
                logger.info("Profile posts retrieved", count=len(normalized))
                return normalized
            return []

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

        try:
            data = await self._make_request(
                "GET",
                "/company-posts",
                params={"link": linkedin_url, "sort_by": sort_by},
            )

            if data and data.get("data"):
                posts = data["data"]
                normalized = [self._normalize_post(p) for p in posts[:limit]]
                logger.info("Company posts retrieved", count=len(normalized))
                return normalized
            return []

        except PermissionError:
            raise
        except Exception as e:
            logger.error("Company posts error", error=str(e))
            return []

    async def get_post(
        self,
        post_url: str | None = None,
        post_urn: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Get a specific post by URL or URN.

        Args:
            post_url: Full LinkedIn post URL
            post_urn: Post URN (e.g., "urn:li:activity:123456789")

        Returns:
            Post data dict or None
        """
        if not post_url and not post_urn:
            return None

        # Convert URN to URL if needed
        if not post_url and post_urn:
            # Extract activity ID from URN
            activity_id = post_urn.split(":")[-1]
            post_url = f"https://www.linkedin.com/feed/update/urn:li:activity:{activity_id}"

        try:
            data = await self._make_request(
                "GET",
                "/post",
                params={"link": post_url},
            )

            if data and data.get("data"):
                return self._normalize_post(data["data"])
            return None

        except (PermissionError, RuntimeError):
            raise
        except Exception as e:
            logger.error("Post lookup error", error=str(e))
            return None

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
        # Convert URN to URL
        activity_id = post_urn.split(":")[-1]
        post_url = f"https://www.linkedin.com/feed/update/urn:li:activity:{activity_id}"

        try:
            data = await self._make_request(
                "GET",
                "/post-comments",
                params={
                    "link": post_url,
                    "sort_by": "Most relevant" if sort_by == "relevance" else "Most recent",
                },
            )

            if data and data.get("data"):
                comments = data["data"]
                normalized = [self._normalize_comment(c) for c in comments[:limit]]
                logger.info("Post comments retrieved", count=len(normalized))
                return normalized
            return []

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
        # Convert URN to URL
        activity_id = post_urn.split(":")[-1]
        post_url = f"https://www.linkedin.com/feed/update/urn:li:activity:{activity_id}"

        try:
            data = await self._make_request(
                "GET",
                "/post-reactions",
                params={"link": post_url, "type": reaction_type},
            )

            if data and data.get("data"):
                reactors = data["data"]
                normalized_reactors = []
                for reactor in reactors[:limit]:
                    normalized_reactors.append({
                        "name": reactor.get("name"),
                        "headline": reactor.get("headline"),
                        "profile_url": reactor.get("linkedin_url"),
                        "profile_image": reactor.get("profile_image_url"),
                        "reaction_type": reactor.get("reaction_type"),
                    })

                logger.info("Post reactions retrieved", count=len(normalized_reactors))
                return {
                    "total_count": len(normalized_reactors),
                    "reactors": normalized_reactors,
                    "source": "professional_network_data_api",
                }
            return {"total_count": 0, "reactors": [], "source": "professional_network_data_api"}

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
        search_params: dict[str, Any] = {}
        if keywords:
            search_params["keywords"] = keywords
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

        try:
            data = await self._make_request(
                "POST",
                "/search-posts",
                json_data=search_params,
            )

            if data and data.get("data"):
                posts = data["data"]
                normalized = [self._normalize_post(p) for p in posts[:limit]]
                logger.info("Post search completed", count=len(normalized))
                return normalized
            return []

        except PermissionError:
            raise
        except Exception as e:
            logger.error("Post search error", error=str(e))
            return []

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
            # NEW fields available in PND API
            "last_active": data.get("last_active"),
            "premium": data.get("premium"),
            "open_to_work": data.get("open_to_work"),
            "hiring": data.get("hiring"),
            "source": "professional_network_data_api",
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
            "source": "professional_network_data_api",
        }

    def _normalize_post(self, data: dict) -> dict[str, Any]:
        """Normalize post data to consistent format."""
        return {
            "urn": data.get("urn") or data.get("post_urn"),
            "text": data.get("text") or data.get("commentary"),
            "post_url": data.get("post_url") or data.get("url"),
            "author": {
                "name": data.get("poster_name") or data.get("author_name"),
                "headline": data.get("poster_headline") or data.get("author_headline"),
                "profile_url": data.get("poster_linkedin_url") or data.get("author_url"),
                "profile_image": data.get("poster_image_url") or data.get("author_image"),
            },
            "engagement": {
                "likes": data.get("num_likes", 0),
                "comments": data.get("num_comments", 0),
                "reposts": data.get("num_reposts", 0),
            },
            "media": {
                "images": data.get("images", []),
                "video": data.get("video"),
                "document": data.get("document"),
            },
            "posted_at": data.get("time") or data.get("posted_at"),
            "source": "professional_network_data_api",
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
            "source": "professional_network_data_api",
        }

    def _normalize_article(self, data: dict) -> dict[str, Any]:
        """Normalize article data to consistent format (NEW)."""
        return {
            "id": data.get("article_id") or data.get("id"),
            "title": data.get("title"),
            "subtitle": data.get("subtitle"),
            "content": data.get("content") or data.get("body"),
            "url": data.get("url") or data.get("article_url"),
            "cover_image": data.get("cover_image") or data.get("image_url"),
            "author": {
                "name": data.get("author_name"),
                "headline": data.get("author_headline"),
                "profile_url": data.get("author_linkedin_url"),
                "profile_image": data.get("author_image_url"),
            },
            "engagement": {
                "likes": data.get("num_likes", 0),
                "comments": data.get("num_comments", 0),
            },
            "published_at": data.get("published_at") or data.get("time"),
            "source": "professional_network_data_api",
        }

    # =========================================================================
    # Status Methods
    # =========================================================================

    def get_status(self) -> dict[str, Any]:
        """Get client status information."""
        return {
            "client_type": "professional_network_data_api",
            "api_host": self.API_HOST,
            "has_api_key": bool(self._api_key),
            "features": {
                "people_enrichment": [
                    "get_profile",
                    "search_profiles",
                    "get_profile_posts",
                    "get_profile_interests (NEW)",
                    "get_similar_profiles (NEW)",
                    "get_profile_network",
                    "get_profile_articles (NEW)",
                ],
                "company": [
                    "get_company",
                    "search_companies",
                    "get_company_employees",
                    "get_company_posts",
                    "get_company_by_domain (NEW)",
                ],
                "posts": [
                    "get_post",
                    "search_posts",
                    "get_post_comments",
                    "get_post_reactions",
                ],
                "articles": [
                    "get_article (NEW)",
                    "get_profile_articles (NEW)",
                ],
            },
            "pricing": {
                "BASIC": "Free (limited)",
                "PRO": "$50/month",
                "ULTRA": "$175/month",
                "MEGA": "$500/month",
            },
            "note": "This is the successor to Fresh Data API with 55 endpoints (vs ~13). New features: articles, interests, similar profiles.",
            "documentation": "https://rapidapi.com/pnd-team-pnd-team/api/professional-network-data",
        }
