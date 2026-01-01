"""
Enhanced LinkedIn HTTP client with anti-detection measures.

Uses curl_cffi for TLS fingerprint spoofing and modern browser headers
to avoid LinkedIn's bot detection systems.
"""

import asyncio
import json
import random
import time
from typing import Any
from urllib.parse import urljoin

from linkedin_mcp.core.exceptions import (
    LinkedInAPIError,
    LinkedInAuthError,
    LinkedInRateLimitError,
)
from linkedin_mcp.core.logging import get_logger

logger = get_logger(__name__)

# Try to import curl_cffi for TLS fingerprint spoofing
try:
    from curl_cffi import requests as cffi_requests
    CURL_CFFI_AVAILABLE = True
    logger.info("curl_cffi available for TLS fingerprint spoofing")
except ImportError:
    CURL_CFFI_AVAILABLE = False
    logger.warning(
        "curl_cffi not available - TLS fingerprinting may be detected",
        install_cmd="pip install curl_cffi",
    )

# Modern Chrome 131 headers (December 2024)
CHROME_131_HEADERS = {
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "accept": "application/vnd.linkedin.normalized+json+2.1",
    "accept-language": "en-US,en;q=0.9",
    "accept-encoding": "gzip, deflate, br, zstd",
    "x-li-lang": "en_US",
    "x-restli-protocol-version": "2.0.0",
    "x-li-page-instance": "urn:li:page:feed_index_index;",
    "x-li-track": json.dumps({
        "clientVersion": "1.13.22",
        "mpVersion": "v2",
        "osName": "web",
        "timezoneOffset": -5,
        "timezone": "America/New_York",
        "deviceFormFactor": "DESKTOP",
        "mpName": "voyager-web",
        "displayDensity": 2,
        "displayWidth": 2560,
        "displayHeight": 1440,
    }),
    "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "cache-control": "no-cache",
    "pragma": "no-cache",
}

# LinkedIn API base URL
LINKEDIN_API_BASE = "https://www.linkedin.com/voyager/api/"


class EnhancedLinkedInSession:
    """
    Enhanced HTTP session for LinkedIn with anti-detection measures.

    Features:
    - TLS fingerprint spoofing via curl_cffi
    - Modern Chrome 131+ headers
    - Human-like request timing with jitter
    - Automatic cookie management
    - Response validation with helpful error messages
    """

    def __init__(
        self,
        cookies: dict[str, str] | None = None,
        use_curl_cffi: bool = True,
    ):
        """
        Initialize enhanced session.

        Args:
            cookies: LinkedIn session cookies (li_at, JSESSIONID, etc.)
            use_curl_cffi: Whether to use curl_cffi for TLS spoofing
        """
        self._cookies = cookies or {}
        self._use_curl_cffi = use_curl_cffi and CURL_CFFI_AVAILABLE
        self._session = None
        self._last_request_time = 0.0
        self._min_request_interval = 1.0  # Minimum seconds between requests

    async def initialize(self) -> None:
        """Initialize the HTTP session with appropriate configuration."""
        if self._use_curl_cffi:
            # Use curl_cffi with Chrome 131 impersonation
            self._session = cffi_requests.Session(
                impersonate="chrome131",
                timeout=30,
            )
            self._session.headers.update(CHROME_131_HEADERS)
            logger.info("Initialized curl_cffi session with Chrome 131 impersonation")
        else:
            # Fallback to standard requests with modern headers
            import requests
            self._session = requests.Session()
            self._session.headers.update(CHROME_131_HEADERS)
            logger.warning("Using standard requests - TLS fingerprint may be detected")

        # Set cookies
        if self._cookies:
            for name, value in self._cookies.items():
                if value:
                    self._session.cookies.set(name, value, domain=".linkedin.com")
            logger.info(
                "Session cookies configured",
                cookie_names=list(self._cookies.keys()),
            )

    async def _add_human_delay(self) -> None:
        """Add human-like delay between requests."""
        elapsed = time.time() - self._last_request_time

        # Base delay to avoid rate limiting
        if elapsed < self._min_request_interval:
            await asyncio.sleep(self._min_request_interval - elapsed)

        # Add random jitter (0.2-1.5 seconds) to appear more human
        jitter = random.uniform(0.2, 1.5)
        await asyncio.sleep(jitter)

        # Occasionally add longer pause (10% chance)
        if random.random() < 0.1:
            extra_pause = random.uniform(1.0, 3.0)
            await asyncio.sleep(extra_pause)
            logger.debug("Added extra human-like pause", seconds=extra_pause)

    def _validate_response(self, response: Any, url: str) -> None:
        """
        Validate response and raise appropriate exceptions.

        Args:
            response: HTTP response object
            url: Request URL for error context

        Raises:
            LinkedInAuthError: For authentication issues
            LinkedInRateLimitError: For rate limiting
            LinkedInAPIError: For other API errors
        """
        status_code = response.status_code

        # Check for common error statuses
        if status_code == 401:
            raise LinkedInAuthError(
                "Authentication expired or invalid",
                details={"url": url, "status": 401},
            )
        elif status_code == 403:
            # Check for CHALLENGE in response
            try:
                text = response.text
                if "CHALLENGE" in text.upper():
                    raise LinkedInAuthError(
                        "LinkedIn security challenge triggered - use browser cookies",
                        details={"url": url, "status": 403, "challenge": True},
                    )
            except Exception:
                pass
            raise LinkedInAPIError(
                "Access forbidden - LinkedIn may be blocking this request",
                details={"url": url, "status": 403},
            )
        elif status_code == 429:
            retry_after = response.headers.get("Retry-After", 60)
            raise LinkedInRateLimitError(
                "Rate limit exceeded",
                retry_after=int(retry_after),
                details={"url": url},
            )
        elif status_code >= 500:
            raise LinkedInAPIError(
                f"LinkedIn server error ({status_code})",
                status_code=status_code,
                details={"url": url},
            )
        elif status_code >= 400:
            raise LinkedInAPIError(
                f"LinkedIn request failed ({status_code})",
                status_code=status_code,
                details={"url": url},
            )

        # Check for empty response (common blocking indicator)
        try:
            content = response.text.strip()
            if not content:
                raise LinkedInAPIError(
                    "LinkedIn returned empty response - possible blocking",
                    details={"url": url, "suggestion": "Try refreshing cookies"},
                )
        except Exception:
            pass

    async def get(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Make GET request to LinkedIn API.

        Args:
            endpoint: API endpoint (relative to voyager/api/)
            params: Query parameters

        Returns:
            JSON response data
        """
        if not self._session:
            raise LinkedInAPIError("Session not initialized")

        url = urljoin(LINKEDIN_API_BASE, endpoint)

        await self._add_human_delay()

        def make_request():
            return self._session.get(url, params=params)

        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None, make_request
            )
            self._last_request_time = time.time()

            self._validate_response(response, url)

            try:
                return response.json()
            except json.JSONDecodeError as e:
                # Empty or invalid JSON is often a sign of blocking
                raise LinkedInAPIError(
                    "Invalid JSON response from LinkedIn - possible blocking",
                    details={
                        "url": url,
                        "error": str(e),
                        "suggestion": "Try refreshing session cookies",
                    },
                    cause=e,
                )

        except (LinkedInAPIError, LinkedInAuthError, LinkedInRateLimitError):
            raise
        except Exception as e:
            error_str = str(e).lower()

            # Detect redirect loops
            if "redirect" in error_str:
                raise LinkedInAPIError(
                    "LinkedIn redirect loop detected - session may be invalid",
                    details={
                        "url": url,
                        "suggestion": "Re-authenticate: linkedin-mcp-auth extract-cookies",
                    },
                    cause=e,
                )

            raise LinkedInAPIError(
                f"Request failed: {e}",
                details={"url": url},
                cause=e,
            )

    async def post(
        self,
        endpoint: str,
        data: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Make POST request to LinkedIn API.

        Args:
            endpoint: API endpoint
            data: Form data
            json_data: JSON body

        Returns:
            JSON response data
        """
        if not self._session:
            raise LinkedInAPIError("Session not initialized")

        url = urljoin(LINKEDIN_API_BASE, endpoint)

        await self._add_human_delay()

        def make_request():
            if json_data:
                return self._session.post(url, json=json_data)
            return self._session.post(url, data=data)

        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None, make_request
            )
            self._last_request_time = time.time()

            self._validate_response(response, url)

            try:
                return response.json()
            except json.JSONDecodeError:
                # Some POST endpoints return empty success
                if response.status_code in (200, 201, 204):
                    return {"success": True}
                raise

        except (LinkedInAPIError, LinkedInAuthError, LinkedInRateLimitError):
            raise
        except Exception as e:
            raise LinkedInAPIError(
                f"POST request failed: {e}",
                details={"url": url},
                cause=e,
            )

    async def close(self) -> None:
        """Close the session."""
        if self._session:
            try:
                self._session.close()
            except Exception:
                pass
            self._session = None
        logger.info("Enhanced LinkedIn session closed")


class EnhancedLinkedInClient:
    """
    Enhanced LinkedIn API client with anti-detection measures.

    This client can be used as a drop-in enhancement or fallback
    when the standard linkedin-api library gets blocked.

    Features:
    - TLS fingerprint spoofing via curl_cffi
    - Modern Chrome 131+ headers
    - Human-like request patterns
    - Better error messages with actionable suggestions
    """

    def __init__(
        self,
        cookies: dict[str, str] | None = None,
        use_curl_cffi: bool = True,
    ):
        """
        Initialize enhanced client.

        Args:
            cookies: LinkedIn session cookies (li_at required, JSESSIONID optional)
            use_curl_cffi: Whether to use curl_cffi for TLS spoofing
        """
        self._cookies = cookies or {}
        self._session = EnhancedLinkedInSession(
            cookies=cookies,
            use_curl_cffi=use_curl_cffi,
        )
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the client."""
        if self._initialized:
            return

        await self._session.initialize()
        self._initialized = True

        logger.info(
            "Enhanced LinkedIn client initialized",
            curl_cffi=self._session._use_curl_cffi,
            has_cookies=bool(self._cookies),
        )

    async def close(self) -> None:
        """Close the client."""
        await self._session.close()
        self._initialized = False

    # =========================================================================
    # Profile Methods
    # =========================================================================

    async def get_profile(self, public_id: str) -> dict[str, Any]:
        """
        Get a LinkedIn profile by public ID.

        Args:
            public_id: LinkedIn public ID (e.g., "johndoe")

        Returns:
            Profile data
        """
        logger.info("Enhanced client: Fetching profile", public_id=public_id)

        # LinkedIn uses this endpoint for profile data
        endpoint = f"identity/dash/profiles"
        params = {
            "q": "memberIdentity",
            "memberIdentity": public_id,
            "decorationId": "com.linkedin.voyager.dash.deco.identity.profile.WebTopCardCore-16",
        }

        return await self._session.get(endpoint, params=params)

    async def get_own_profile(self) -> dict[str, Any]:
        """Get the authenticated user's profile."""
        logger.info("Enhanced client: Fetching own profile")

        endpoint = "me"
        return await self._session.get(endpoint)

    # =========================================================================
    # Search Methods
    # =========================================================================

    async def search_people(
        self,
        keywords: str | None = None,
        limit: int = 10,
        keyword_title: str | None = None,
        keyword_company: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Search for people on LinkedIn.

        Args:
            keywords: General search keywords
            limit: Maximum results
            keyword_title: Filter by job title
            keyword_company: Filter by company

        Returns:
            List of matching profiles
        """
        logger.info(
            "Enhanced client: Searching people",
            keywords=keywords,
            limit=limit,
        )

        # Build search filters
        filters = []
        if keyword_title:
            filters.append(f"title:{keyword_title}")
        if keyword_company:
            filters.append(f"company:{keyword_company}")

        params = {
            "decorationId": "com.linkedin.voyager.dash.deco.search.SearchClusterCollection-165",
            "count": limit,
            "q": "all",
            "origin": "GLOBAL_SEARCH_HEADER",
            "queryContext": json.dumps({
                "spellCorrectionEnabled": True,
                "relatedSearchesEnabled": True,
            }),
        }

        if keywords:
            params["keywords"] = keywords
        if filters:
            params["filters"] = json.dumps({"resultType": {"values": ["PEOPLE"]}})

        endpoint = "graphql"
        result = await self._session.get(endpoint, params=params)

        # Extract people from search results
        return self._extract_search_results(result)

    def _extract_search_results(self, data: dict) -> list[dict[str, Any]]:
        """Extract people from search response."""
        results = []

        try:
            # Navigate through LinkedIn's nested response structure
            elements = data.get("data", {}).get("searchDashClustersByAll", {}).get("elements", [])

            for cluster in elements:
                items = cluster.get("items", [])
                for item in items:
                    entity = item.get("item", {}).get("entityResult", {})
                    if entity:
                        profile = {
                            "name": entity.get("title", {}).get("text", ""),
                            "headline": entity.get("primarySubtitle", {}).get("text", ""),
                            "location": entity.get("secondarySubtitle", {}).get("text", ""),
                            "profile_url": entity.get("navigationUrl", ""),
                        }
                        # Extract public_id from URL
                        url = profile.get("profile_url", "")
                        if "/in/" in url:
                            parts = url.split("/in/")
                            if len(parts) > 1:
                                profile["public_id"] = parts[1].split("/")[0].split("?")[0]

                        if profile.get("name"):
                            results.append(profile)
        except Exception as e:
            logger.warning("Failed to extract search results", error=str(e))

        return results

    # =========================================================================
    # Feed Methods
    # =========================================================================

    async def get_feed(self, limit: int = 10) -> list[dict[str, Any]]:
        """
        Get the user's LinkedIn feed.

        Args:
            limit: Maximum posts to return

        Returns:
            List of feed posts
        """
        logger.info("Enhanced client: Fetching feed", limit=limit)

        params = {
            "count": limit,
            "q": "feedByUpdateType",
            "updateType": "SHARES_AND_POLLS",
        }

        endpoint = "feed/updates"
        return await self._session.get(endpoint, params=params)

    async def get_profile_posts(
        self,
        public_id: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Get posts from a specific profile."""
        logger.info(
            "Enhanced client: Fetching profile posts",
            public_id=public_id,
            limit=limit,
        )

        params = {
            "count": limit,
            "q": "memberFeed",
            "memberIdentity": public_id,
        }

        endpoint = "feed/updates"
        return await self._session.get(endpoint, params=params)

    # =========================================================================
    # Connection Methods
    # =========================================================================

    async def get_connections(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get user's connections."""
        logger.info("Enhanced client: Fetching connections", limit=limit)

        params = {
            "count": limit,
            "start": 0,
            "sortType": "RECENTLY_ADDED",
        }

        endpoint = "relationships/connections"
        return await self._session.get(endpoint, params=params)


# =============================================================================
# Factory function
# =============================================================================

async def create_enhanced_client(
    li_at: str,
    jsessionid: str | None = None,
    use_curl_cffi: bool = True,
) -> EnhancedLinkedInClient:
    """
    Factory function to create and initialize an enhanced LinkedIn client.

    Args:
        li_at: LinkedIn session cookie (required)
        jsessionid: JSESSIONID cookie (optional but recommended)
        use_curl_cffi: Whether to use curl_cffi for TLS spoofing

    Returns:
        Initialized EnhancedLinkedInClient

    Example:
        client = await create_enhanced_client(
            li_at="AQE...",
            jsessionid="ajax:123...",
        )
        profile = await client.get_profile("williamhgates")
        await client.close()
    """
    cookies = {"li_at": li_at}
    if jsessionid:
        cookies["JSESSIONID"] = jsessionid

    client = EnhancedLinkedInClient(
        cookies=cookies,
        use_curl_cffi=use_curl_cffi,
    )
    await client.initialize()

    return client
