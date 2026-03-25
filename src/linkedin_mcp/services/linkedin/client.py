"""
LinkedIn API client wrapper.

Provides async-compatible wrapper around the tomquirk/linkedin-api library
with session persistence, rate limiting, and retry logic.
"""

import asyncio
import json
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, ParamSpec, TypeVar
from urllib.parse import quote

from requests.cookies import RequestsCookieJar
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from linkedin_mcp.config.constants import MAX_REQUESTS_PER_HOUR
from linkedin_mcp.core.exceptions import (
    LinkedInAPIError,
    LinkedInAuthError,
    LinkedInRateLimitError,
)
from linkedin_mcp.core.logging import get_logger

logger = get_logger(__name__)

P = ParamSpec("P")
R = TypeVar("R")


class RateLimiter:
    """Token bucket rate limiter for LinkedIn API calls."""

    def __init__(self, max_requests: int = MAX_REQUESTS_PER_HOUR, window_seconds: int = 3600):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: list[datetime] = []
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Acquire a rate limit token, waiting if necessary."""
        async with self._lock:
            now = datetime.now()
            cutoff = now - timedelta(seconds=self.window_seconds)

            # Remove expired requests
            self.requests = [r for r in self.requests if r > cutoff]

            if len(self.requests) >= self.max_requests:
                # Calculate wait time
                oldest = min(self.requests)
                wait_time = (oldest + timedelta(seconds=self.window_seconds) - now).total_seconds()

                if wait_time > 0:
                    logger.warning(
                        "Rate limit reached, waiting",
                        wait_seconds=wait_time,
                        request_count=len(self.requests),
                    )
                    raise LinkedInRateLimitError(
                        "Rate limit exceeded",
                        retry_after=int(wait_time),
                    )

            self.requests.append(now)

    @property
    def remaining(self) -> int:
        """Get remaining requests in current window."""
        now = datetime.now()
        cutoff = now - timedelta(seconds=self.window_seconds)
        active = [r for r in self.requests if r > cutoff]
        return max(0, self.max_requests - len(active))


class LinkedInClient:
    """
    Async-compatible LinkedIn API client.

    Wraps the synchronous linkedin-api library with:
    - Async execution via thread pool
    - Session cookie persistence
    - Rate limiting
    - Retry logic with exponential backoff

    Authentication methods (in priority order):
    1. Direct cookies dict (safest, recommended via linkedin-mcp-auth)
    2. Cookie path file (legacy)
    3. Email/password (may cause session issues, not recommended)
    """

    def __init__(
        self,
        email: str | None = None,
        password: str | None = None,
        cookie_path: Path | None = None,
        cookies: dict[str, str] | None = None,
        rate_limit: int = MAX_REQUESTS_PER_HOUR,
        headless_scraper: Any | None = None,
    ):
        """
        Initialize LinkedIn client.

        Args:
            email: LinkedIn email (optional if using cookies)
            password: LinkedIn password (optional if using cookies)
            cookie_path: Path to cookie file (optional)
            cookies: Direct cookies dict with li_at and optionally JSESSIONID
            rate_limit: Max requests per hour
            headless_scraper: Optional HeadlessLinkedInScraper instance for browser-based API calls
        """
        self.email = email
        self.password = password
        self.cookie_path = cookie_path or Path("./data/session_cookies.json")
        self._direct_cookies = cookies  # New: direct cookies from keychain
        self.rate_limiter = RateLimiter(max_requests=rate_limit)
        self._client: Any = None
        self._initialized = False
        self._headless_scraper = headless_scraper
        self._cached_profile_urn: str | None = None

    async def initialize(self) -> None:
        """
        Initialize the LinkedIn client with authentication.

        Authentication priority:
        1. Direct cookies (from keychain, safest)
        2. Cookie file (legacy)
        3. Email/password (may cause session issues)
        """
        if self._initialized:
            logger.info("LinkedIn client already initialized, skipping")
            return

        # Priority 1: Use direct cookies from keychain
        cookies = None
        auth_method = "unknown"

        if self._direct_cookies:
            logger.info(
                "Using direct cookies from keychain",
                has_li_at="li_at" in self._direct_cookies,
                has_jsessionid="JSESSIONID" in self._direct_cookies,
            )
            # Convert dict to RequestsCookieJar
            cookie_jar = RequestsCookieJar()
            for name, value in self._direct_cookies.items():
                if value:  # Only add non-empty cookies
                    cookie_jar.set(name, value, domain=".linkedin.com", path="/")
            cookies = cookie_jar
            auth_method = "keychain_cookies"
        else:
            # Priority 2: Load from cookie file
            logger.info(
                "No direct cookies, checking cookie file",
                cookie_path=str(self.cookie_path),
                cookie_path_exists=self.cookie_path.exists(),
            )
            cookies = await self._load_cookies()
            auth_method = "cookie_file" if cookies else "credentials"

        logger.info(
            "Cookies prepared for initialization",
            has_cookies=cookies is not None,
            cookie_type=type(cookies).__name__ if cookies else None,
            cookie_count=len(cookies) if cookies else 0,
            auth_method=auth_method,
        )

        def create_client() -> Any:
            from linkedin_api import Linkedin

            logger.info(
                "Creating LinkedIn client in executor",
                has_cookies=cookies is not None,
                cookie_count=len(cookies) if cookies else 0,
                auth_method=auth_method,
            )

            # If using cookies only (no password), use empty credentials
            email = self.email or ""
            password = self.password or ""

            # If we have cookies, we might not need credentials
            if cookies and not self.email:
                logger.info(
                    "Using cookie-only authentication (recommended)",
                )

            client = Linkedin(
                email,
                password,
                cookies=cookies,
                refresh_cookies=True,
            )

            logger.info(
                "Linkedin constructor returned",
                client_type=type(client).__name__,
            )

            return client

        try:
            logger.info("Running create_client in executor", auth_method=auth_method)
            self._client = await asyncio.get_event_loop().run_in_executor(
                None, create_client
            )
            self._initialized = True

            logger.info(
                "Client initialized successfully",
                client_type=type(self._client).__name__,
                auth_method=auth_method,
            )

            # Save refreshed cookies (only if using file-based auth)
            if auth_method != "keychain_cookies":
                await self._save_cookies()
                logger.debug("Session cookies saved")

        except Exception as e:
            import traceback
            logger.error(
                "LinkedIn authentication failed",
                error=str(e),
                error_type=type(e).__name__,
                auth_method=auth_method,
                traceback=traceback.format_exc(),
            )
            raise LinkedInAuthError(
                "Failed to authenticate with LinkedIn",
                cause=e,
            ) from e

    async def _load_cookies(self) -> RequestsCookieJar | None:
        """Load session cookies from file and convert to RequestsCookieJar."""
        logger.info("Checking for cookies", path=str(self.cookie_path), exists=self.cookie_path.exists())

        if not self.cookie_path.exists():
            logger.warning("Cookie file not found", path=str(self.cookie_path))
            return None

        try:
            content = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self.cookie_path.read_text()
            )
            cookie_dict = json.loads(content)
            cookie_keys = list(cookie_dict.keys()) if cookie_dict else []
            logger.info("Loaded session cookies", keys=cookie_keys, count=len(cookie_dict))

            # Convert dict to RequestsCookieJar (required by linkedin-api)
            cookie_jar = RequestsCookieJar()
            for name, value in cookie_dict.items():
                cookie_jar.set(name, value, domain=".linkedin.com", path="/")

            logger.info("Converted cookies to RequestsCookieJar")
            return cookie_jar
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load cookies", error=str(e))
            return None

    async def _save_cookies(self) -> None:
        """Save session cookies to file, preserving existing browser cookies.

        This method merges refreshed cookies with existing ones to preserve
        browser-set cookies (bcookie, lidc, bscookie, etc.) that are required
        for full API access.
        """
        if not self._client:
            return

        try:
            self.cookie_path.parent.mkdir(parents=True, exist_ok=True)

            if hasattr(self._client, "client") and hasattr(self._client.client, "cookies"):
                new_cookies = dict(self._client.client.cookies)

                # Load existing cookies to preserve browser-set cookies
                existing_cookies = {}
                if self.cookie_path.exists():
                    try:
                        content = await asyncio.get_event_loop().run_in_executor(
                            None, lambda: self.cookie_path.read_text()
                        )
                        existing_cookies = json.loads(content)
                    except (json.JSONDecodeError, OSError):
                        pass

                # Merge: existing cookies as base, update with new/refreshed cookies
                merged_cookies = {**existing_cookies, **new_cookies}

                # Only save if we have cookies to save
                if merged_cookies:
                    def write_cookies() -> None:
                        with self.cookie_path.open("w") as f:
                            json.dump(merged_cookies, f)

                    await asyncio.get_event_loop().run_in_executor(None, write_cookies)
                    logger.debug(
                        "Session cookies saved",
                        existing_count=len(existing_cookies),
                        new_count=len(new_cookies),
                        merged_count=len(merged_cookies),
                    )

        except Exception as e:
            logger.warning("Failed to save cookies", error=str(e))

    def _ensure_initialized(self) -> None:
        """Ensure client is initialized."""
        if not self._initialized or not self._client:
            raise LinkedInAuthError("LinkedIn client not initialized")

    async def _get_headless_scraper(self) -> Any:
        """Get or create a HeadlessLinkedInScraper for browser-based API calls.

        Uses a persistent browser session stored at ~/.linkedin-mcp/browser-session/.
        On first use, if no saved session exists, a visible browser window opens
        for the user to log in to LinkedIn. After login, the session is saved and
        all subsequent calls use a headless browser automatically.

        Returns:
            Authenticated HeadlessLinkedInScraper instance.

        Raises:
            LinkedInAPIError: If playwright is not installed.
        """
        if self._headless_scraper is not None:
            return self._headless_scraper

        try:
            from linkedin_mcp.services.linkedin.headless_scraper import (
                HeadlessLinkedInScraper,
            )
        except ImportError as e:
            raise LinkedInAPIError(
                "Browser automation required for messaging API but playwright is not installed. "
                "Install with: pip install playwright && playwright install chromium",
                cause=e,
            ) from e

        # Persistent session directory — survives MCP server restarts
        scraper = HeadlessLinkedInScraper()
        # Authentication is handled lazily by ensure_authenticated() on first api_fetch()

        self._headless_scraper = scraper
        return scraper

    async def _execute(self, method: Callable[P, R], *args: P.args, **kwargs: P.kwargs) -> R:
        """Execute a sync API method asynchronously with rate limiting."""
        self._ensure_initialized()
        await self.rate_limiter.acquire()

        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None, lambda: method(*args, **kwargs)
            )
            return result
        except Exception as e:
            error_str = str(e).lower()

            if "rate" in error_str or "limit" in error_str or "429" in error_str:
                raise LinkedInRateLimitError(str(e), cause=e) from e
            elif "auth" in error_str or "login" in error_str or "401" in error_str:
                raise LinkedInAuthError(str(e), cause=e) from e
            else:
                raise LinkedInAPIError(str(e), cause=e) from e

    # ==========================================================================
    # Profile Methods
    # ==========================================================================

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(LinkedInAPIError),
    )
    async def get_profile(self, public_id: str) -> dict[str, Any]:
        """
        Get a LinkedIn profile by public ID.

        Args:
            public_id: LinkedIn public ID (e.g., "johndoe")

        Returns:
            Profile data dictionary
        """
        logger.info("Fetching profile", public_id=public_id)
        return await self._execute(self._client.get_profile, public_id)

    async def get_own_profile(self) -> dict[str, Any]:
        """Get the authenticated user's profile."""
        logger.info("Fetching own profile")
        return await self._execute(self._client.get_user_profile)

    async def get_profile_connections(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get user's connections.

        First fetches the authenticated user's profile to get their URN,
        then retrieves their connections.
        """
        logger.info("Fetching connections", limit=limit)

        # First get the user's own profile to extract their URN
        own_profile = await self._execute(self._client.get_user_profile)

        # Extract URN from profile - it can be in different fields
        urn_id = None
        if own_profile:
            # First check miniProfile (where LinkedIn usually puts the data)
            mini_profile = own_profile.get("miniProfile", {})

            # Try different possible URN locations
            urn_id = (
                own_profile.get("member_urn")
                or own_profile.get("entityUrn")
                or own_profile.get("urn_id")
                or mini_profile.get("entityUrn")
                or mini_profile.get("objectUrn")
            )

            # If URN is in format "urn:li:member:123456" or "urn:li:fs_miniProfile:...", extract just the ID
            if urn_id and ":" in str(urn_id):
                urn_id = str(urn_id).split(":")[-1]

            # Also try public_id if URN not found
            if not urn_id:
                urn_id = (
                    own_profile.get("public_id")
                    or own_profile.get("publicIdentifier")
                    or mini_profile.get("publicIdentifier")
                )

        if not urn_id:
            logger.error("Could not extract URN from own profile", profile_keys=list(own_profile.keys()) if own_profile else [])
            raise LinkedInAPIError("Could not determine user URN for fetching connections")

        logger.info("Got user URN for connections", urn_id=urn_id)
        return await self._execute(self._client.get_profile_connections, urn_id=urn_id)

    async def get_profile_contact_info(self, public_id: str) -> dict[str, Any]:
        """Get profile contact information."""
        logger.info("Fetching contact info", public_id=public_id)
        return await self._execute(self._client.get_profile_contact_info, public_id)

    # ==========================================================================
    # Feed & Posts Methods
    # ==========================================================================

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(LinkedInAPIError),
    )
    async def get_feed(self, limit: int = 10) -> list[dict[str, Any]]:
        """
        Get the user's LinkedIn feed.

        Tries the linkedin-api library first, then falls back to headless browser.

        Args:
            limit: Maximum number of posts to return

        Returns:
            List of feed posts
        """
        logger.info("Fetching feed", limit=limit)
        try:
            return await self._execute(self._client.get_feed_posts, limit=limit)
        except Exception as e:
            logger.warning("linkedin-api get_feed failed, falling back to headless browser", error=str(e))
            return await self.get_feed_posts_headless(limit=limit)

    async def get_profile_posts(
        self,
        public_id: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Get posts from a specific profile."""
        logger.info("Fetching profile posts", public_id=public_id, limit=limit)
        return await self._execute(
            self._client.get_profile_posts,
            public_id,
            post_count=limit,
        )

    async def create_post(
        self,
        text: str,
        visibility: str = "PUBLIC",
    ) -> dict[str, Any]:
        """
        Create a new LinkedIn post.

        Args:
            text: Post content
            visibility: Post visibility (PUBLIC, CONNECTIONS, LOGGED_IN)

        Returns:
            Created post data
        """
        logger.info("Creating post", visibility=visibility, length=len(text))
        return await self._execute(self._client.post, text)

    # ==========================================================================
    # Engagement Methods
    # ==========================================================================

    async def get_post_reactions(self, post_urn: str) -> list[dict[str, Any]]:
        """Get reactions on a post."""
        logger.info("Fetching post reactions", post_urn=post_urn)
        return await self._execute(self._client.get_post_reactions, post_urn)

    async def get_post_comments(
        self,
        post_urn: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get comments on a post."""
        logger.info("Fetching post comments", post_urn=post_urn, limit=limit)
        return await self._execute(self._client.get_post_comments, post_urn, comment_count=limit)

    async def react_to_post(
        self,
        post_urn: str,
        reaction_type: str = "LIKE",
    ) -> None:
        """React to a post."""
        logger.info("Reacting to post", post_urn=post_urn, reaction=reaction_type)
        await self._execute(self._client.react_to_post, post_urn, reaction_type)

    async def comment_on_post(self, post_urn: str, text: str) -> dict[str, Any]:
        """Add a comment to a post."""
        logger.info("Commenting on post", post_urn=post_urn)
        return await self._execute(self._client.comment_on_post, post_urn, text)

    async def reply_to_comment(
        self,
        comment_urn: str,
        text: str,
    ) -> dict[str, Any]:
        """Reply to a comment."""
        logger.info("Replying to comment", comment_urn=comment_urn)
        # LinkedIn API uses post_comment on the comment URN for replies
        return await self._execute(self._client.comment_on_post, comment_urn, text)

    async def unreact_to_post(self, post_urn: str) -> None:
        """Remove reaction from a post."""
        logger.info("Removing reaction from post", post_urn=post_urn)
        await self._execute(self._client.unpost_react, post_urn)

    # ==========================================================================
    # Connection Methods
    # ==========================================================================

    async def send_connection_request(
        self,
        public_id: str,
        message: str | None = None,
    ) -> dict[str, Any]:
        """
        Send a connection request to a profile.

        Args:
            public_id: LinkedIn public ID
            message: Optional personalized message

        Returns:
            dict with success status and details
        """
        logger.info("Sending connection request", public_id=public_id)
        result = await self._execute(
            self._client.add_connection,
            public_id,
            message=message,
        )

        # linkedin-api add_connection returns True on ERROR, False on success
        if result is True:
            return {
                "success": False,
                "error": "LinkedIn API returned an error. Connection request may not have been sent.",
            }

        return {
            "success": True,
            "message": "Connection request sent successfully",
            "profile_id": public_id,
        }

    async def remove_connection(self, public_id: str) -> dict[str, Any]:
        """Remove a connection.

        Returns:
            dict with success status and details
        """
        logger.info("Removing connection", public_id=public_id)
        result = await self._execute(self._client.remove_connection, public_id)

        # linkedin-api remove_connection returns True on ERROR, False on success
        if result is True:
            return {
                "success": False,
                "error": "LinkedIn API returned an error. Connection may not have been removed.",
            }

        return {
            "success": True,
            "message": "Connection removed successfully",
            "profile_id": public_id,
        }

    async def get_pending_invitations(
        self,
        start: int = 0,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """
        Get pending connection invitations (received).

        Note: The LinkedIn API only supports fetching received invitations.
        Sent invitations are not available through this endpoint.

        Args:
            start: Offset for pagination
            limit: Maximum invitations to return

        Returns:
            List of pending invitations
        """
        logger.info("Fetching invitations", start=start, limit=limit)
        return await self._execute(self._client.get_invitations, start=start, limit=limit)

    async def accept_invitation(self, invitation_id: str, shared_secret: str) -> dict[str, Any]:
        """Accept a connection invitation.

        Returns:
            dict with success status and details
        """
        logger.info("Accepting invitation", invitation_id=invitation_id)
        result = await self._execute(
            self._client.reply_invitation,
            invitation_id,
            shared_secret,
            action="accept",
        )

        # linkedin-api reply_invitation returns True on ERROR, False on success
        if result is True:
            return {
                "success": False,
                "error": "LinkedIn API returned an error. Invitation may not have been accepted.",
            }

        return {
            "success": True,
            "message": "Connection invitation accepted successfully",
            "invitation_id": invitation_id,
        }

    async def reject_invitation(self, invitation_id: str, shared_secret: str) -> dict[str, Any]:
        """Reject a connection invitation.

        Returns:
            dict with success status and details
        """
        logger.info("Rejecting invitation", invitation_id=invitation_id)
        result = await self._execute(
            self._client.reply_invitation,
            invitation_id,
            shared_secret,
            action="ignore",
        )

        # linkedin-api reply_invitation returns True on ERROR, False on success
        if result is True:
            return {
                "success": False,
                "error": "LinkedIn API returned an error. Invitation may not have been rejected.",
            }

        return {
            "success": True,
            "message": "Connection invitation rejected successfully",
            "invitation_id": invitation_id,
        }

    # ==========================================================================
    # Messaging Methods (GraphQL-based - LinkedIn migrated from legacy REST)
    # ==========================================================================

    async def _get_profile_urn(self) -> str:
        """Get the authenticated user's profile URN for messaging API calls.

        Tries multiple strategies and caches the result for the session.

        Returns:
            Profile URN string (e.g., 'ACoAAAClzUMBPjPkKDE5pXFQhnfQPlrPXRWq9eU')

        Raises:
            LinkedInAPIError: If profile URN cannot be determined.
        """
        # Return cached value if available
        if self._cached_profile_urn:
            return self._cached_profile_urn

        urn_id = None

        # Strategy 1: Try get_user_profile via linkedin-api
        try:
            own_profile = await self._execute(self._client.get_user_profile)
            if own_profile:
                mini_profile = own_profile.get("miniProfile", {})
                urn_id = (
                    own_profile.get("member_urn")
                    or own_profile.get("entityUrn")
                    or own_profile.get("urn_id")
                    or mini_profile.get("entityUrn")
                    or mini_profile.get("objectUrn")
                )
                if urn_id and ":" in str(urn_id):
                    urn_id = str(urn_id).split(":")[-1]
        except Exception:
            logger.debug("get_user_profile failed, trying direct API call")

        # Strategy 2: /me API call via headless browser (bypasses bot detection)
        if not urn_id:
            try:
                scraper = await self._get_headless_scraper()
                me_data = await scraper.api_fetch(
                    "https://www.linkedin.com/voyager/api/me",
                )
                # Response can have miniProfile at root or under data
                mini = me_data.get("miniProfile", {})
                data_section = me_data.get("data", {})

                urn_id = (
                    mini.get("dashEntityUrn")
                    or mini.get("entityUrn")
                    or me_data.get("entityUrn")
                    or me_data.get("objectUrn")
                    or me_data.get("*miniProfile")
                    or data_section.get("*miniProfile")
                )
                if urn_id and ":" in str(urn_id):
                    urn_id = str(urn_id).split(":")[-1]

                # Also check included entities
                if not urn_id:
                    for item in me_data.get("included", []):
                        entity_urn = item.get("entityUrn", "") or item.get("dashEntityUrn", "")
                        if "fsd_profile" in entity_urn or "fs_miniProfile" in entity_urn:
                            urn_id = entity_urn.split(":")[-1]
                            break
            except Exception:
                logger.debug("Headless /me API call failed")

        # Strategy 3: GraphQL identity endpoint via headless browser
        if not urn_id:
            try:
                scraper = await self._get_headless_scraper()
                data = await scraper.api_fetch(
                    "https://www.linkedin.com/voyager/api/graphql"
                    "?includeWebMetadata=true&variables=()"
                    "&queryId=voyagerIdentityDashProfiles"
                    ".b5c27c04968c409fc0ed3546575b9b7a",
                    headers={"Accept": "application/vnd.linkedin.normalized+json+2.1"},
                )
                for item in data.get("included", []):
                    entity_urn = item.get("entityUrn", "")
                    if "fsd_profile" in entity_urn:
                        urn_id = entity_urn.split(":")[-1]
                        break
            except Exception:
                logger.debug("Headless GraphQL identity endpoint failed")

        if not urn_id:
            raise LinkedInAPIError("Could not extract profile URN for messaging")

        self._cached_profile_urn = urn_id
        return urn_id

    @staticmethod
    def _build_graphql_url(query_id: str, variables: str) -> str:
        """Build a GraphQL URL with LinkedIn's REST-like variable encoding.

        LinkedIn expects: variables=(key:urn%3Ali%3Afsd_profile%3AXXX)
        Top-level commas between key:value pairs stay literal,
        but values are fully percent-encoded.

        Args:
            query_id: The GraphQL query ID.
            variables: Pre-formatted LinkedIn-style variable string.

        Returns:
            Fully constructed URL string.
        """
        def _split_top_level(s: str) -> list[str]:
            """Split on commas not inside parentheses."""
            parts: list[str] = []
            depth = 0
            current: list[str] = []
            for ch in s:
                if ch == "(":
                    depth += 1
                    current.append(ch)
                elif ch == ")":
                    depth -= 1
                    current.append(ch)
                elif ch == "," and depth == 0:
                    parts.append("".join(current))
                    current = []
                else:
                    current.append(ch)
            if current:
                parts.append("".join(current))
            return parts

        encoded_parts = []
        for pair in _split_top_level(variables):
            key, _, value = pair.partition(":")
            if value:
                encoded_parts.append(f"{key.strip()}:{quote(value.strip(), safe='')}")
            else:
                encoded_parts.append(key.strip())
        encoded_vars = ",".join(encoded_parts)
        return (
            f"https://www.linkedin.com/voyager/api/voyagerMessagingGraphQL/graphql"
            f"?queryId={query_id}&variables=({encoded_vars})"
        )

    async def _graphql_fetch_async(self, query_id: str, variables: str) -> dict[str, Any]:
        """Make a GraphQL request to LinkedIn's messaging API via the headless browser.

        Uses the headless browser's fetch() to bypass LinkedIn's bot detection
        that blocks all Python HTTP clients. The browser context provides real
        TLS fingerprints and cookies automatically.

        Args:
            query_id: The GraphQL query ID (e.g., 'messengerConversations.0d5e6781bbee71c3e51c8843c6519f48')
            variables: Pre-formatted LinkedIn-style variable string.

        Returns:
            Parsed JSON response dict.

        Raises:
            LinkedInAPIError: On HTTP errors or invalid responses.
            LinkedInAuthError: On authentication failures.
            LinkedInRateLimitError: On rate limiting.
        """
        self._ensure_initialized()
        await self.rate_limiter.acquire()

        url = self._build_graphql_url(query_id, variables)

        try:
            scraper = await self._get_headless_scraper()
            result = await scraper.api_fetch(
                url,
                headers={"Accept": "application/graphql"},
            )
            return result
        except Exception as e:
            error_str = str(e).lower()
            if "rate" in error_str or "limit" in error_str or "429" in error_str:
                raise LinkedInRateLimitError(str(e), cause=e) from e
            elif "auth" in error_str or "login" in error_str or "401" in error_str or "session expired" in error_str:
                raise LinkedInAuthError(str(e), cause=e) from e
            elif isinstance(e, (LinkedInAPIError, LinkedInAuthError, LinkedInRateLimitError)):
                raise
            else:
                raise LinkedInAPIError(str(e), cause=e) from e

    @staticmethod
    def _normalize_conversation(element: dict[str, Any]) -> dict[str, Any]:
        """Normalize a raw GraphQL conversation element into a clean dict.

        Args:
            element: Raw conversation element from GraphQL response.

        Returns:
            Normalized conversation dict with consistent field names.
        """
        # Extract participants
        participants = []
        for p in element.get("conversationParticipants", []):
            pt = p.get("participantType", {})
            member = pt.get("member", {})
            if member:
                first = member.get("firstName", {}).get("text", "")
                last = member.get("lastName", {}).get("text", "")
                participants.append({
                    "name": f"{first} {last}".strip(),
                    "first_name": first,
                    "last_name": last,
                    "profile_url": member.get("profileUrl", ""),
                })

        # Extract title and description (may be null in some response variants)
        title_obj = element.get("title")
        desc_obj = element.get("descriptionText")

        title = ""
        if isinstance(title_obj, dict):
            title = title_obj.get("text", "")
        elif title_obj:
            title = str(title_obj)
        # Fallback: derive title from non-self participants
        if not title and participants:
            other_participants = [p["name"] for p in participants if p["name"]]
            title = ", ".join(other_participants) if other_participants else ""

        preview = ""
        if isinstance(desc_obj, dict):
            preview = desc_obj.get("text", "")
        elif desc_obj:
            preview = str(desc_obj)

        # Try to get latest message text from embedded messages
        if not preview:
            messages_data = element.get("messages", {})
            if isinstance(messages_data, dict):
                msg_elements = messages_data.get("elements", [])
                if msg_elements:
                    body = msg_elements[0].get("body", {})
                    if isinstance(body, dict):
                        preview = body.get("text", "")

        return {
            "conversation_id": element.get("entityUrn", ""),
            "backend_urn": element.get("backendUrn", ""),
            "title": title,
            "last_message_preview": preview,
            "participants": participants,
            "last_activity_at": element.get("lastActivityAt"),
            "created_at": element.get("createdAt"),
            "unread_count": element.get("unreadCount", 0),
            "is_read": element.get("read", True),
            "is_group_chat": element.get("groupChat", False),
            "state": element.get("state", ""),
            "notification_status": element.get("notificationStatus", ""),
            "categories": element.get("categories", []),
        }

    @staticmethod
    def _normalize_message(element: dict[str, Any]) -> dict[str, Any]:
        """Normalize a raw GraphQL message element into a clean dict.

        Args:
            element: Raw message element from GraphQL response.

        Returns:
            Normalized message dict with consistent field names.
        """
        # Extract sender info
        sender = element.get("sender", {})
        pt = sender.get("participantType", {})
        member = pt.get("member", {})
        first = member.get("firstName", {}).get("text", "") if member else ""
        last = member.get("lastName", {}).get("text", "") if member else ""

        body = element.get("body", {})
        body_text = body.get("text", "") if isinstance(body, dict) else str(body)

        return {
            "message_id": element.get("entityUrn", ""),
            "conversation_urn": element.get("backendConversationUrn", ""),
            "sender_name": f"{first} {last}".strip(),
            "sender_first_name": first,
            "sender_last_name": last,
            "body": body_text,
            "delivered_at": element.get("deliveredAt"),
        }

    async def get_conversations(self, limit: int = 20) -> list[dict[str, Any]]:
        """Get messaging conversations via LinkedIn's GraphQL messaging API.

        Args:
            limit: Maximum number of conversations to return (default: 20).

        Returns:
            List of normalized conversation dicts with participants, previews, and metadata.
        """
        logger.info("Fetching conversations via GraphQL", limit=limit)

        profile_urn = await self._get_profile_urn()
        mailbox_urn = f"urn:li:fsd_profile:{profile_urn}"
        variables = f"mailboxUrn:{mailbox_urn}"

        data = await self._graphql_fetch_async(
            query_id="messengerConversations.0d5e6781bbee71c3e51c8843c6519f48",
            variables=variables,
        )

        # Navigate the response structure
        root = data.get("data", {})
        sync_token_data = root.get("messengerConversationsBySyncToken", {})
        elements = sync_token_data.get("elements", [])

        conversations = [self._normalize_conversation(el) for el in elements]

        # Apply limit
        if limit and len(conversations) > limit:
            conversations = conversations[:limit]

        logger.info("Fetched conversations via GraphQL", count=len(conversations))
        return conversations

    async def get_conversation(
        self,
        conversation_id: str,
        before_timestamp: int | None = None,
        count: int = 20,
    ) -> dict[str, Any]:
        """Get messages for a specific conversation via LinkedIn's GraphQL messaging API.

        Args:
            conversation_id: Conversation URN (e.g., 'urn:li:msg_conversation:(urn:li:fsd_profile:XXX,YYY)')
            before_timestamp: Load messages delivered before this timestamp (for pagination).
            count: Number of messages to fetch (default: 20).

        Returns:
            Dict with conversation_id, messages list, and pagination info.
        """
        logger.info(
            "Fetching conversation messages via GraphQL",
            conversation_id=conversation_id,
            before_timestamp=before_timestamp,
        )

        if before_timestamp is not None:
            # Paginated query with deliveredAt cursor
            variables = (
                f"deliveredAt:{before_timestamp},"
                f"conversationUrn:{conversation_id},"
                f"countBefore:{count},countAfter:0"
            )
            query_id = "messengerMessages.d8ea76885a52fd5dc5c317078ab7c977"
        else:
            # Initial load
            variables = f"conversationUrn:{conversation_id}"
            query_id = "messengerMessages.5846eeb71c981f11e0134cb6626cc314"

        data = await self._graphql_fetch_async(
            query_id=query_id,
            variables=variables,
        )

        # Navigate the response structure
        root = data.get("data", {})
        sync_token_data = root.get("messengerMessagesBySyncToken", {})
        elements = sync_token_data.get("elements", [])

        messages = [self._normalize_message(el) for el in elements]

        # Determine pagination cursor (oldest message timestamp)
        oldest_timestamp = None
        if messages:
            timestamps = [m["delivered_at"] for m in messages if m.get("delivered_at")]
            if timestamps:
                oldest_timestamp = min(timestamps)

        logger.info("Fetched conversation messages via GraphQL", count=len(messages))
        return {
            "conversation_id": conversation_id,
            "messages": messages,
            "message_count": len(messages),
            "oldest_timestamp": oldest_timestamp,
            "has_more": len(elements) >= count,
        }

    async def search_conversations(self, query: str, limit: int = 50) -> list[dict[str, Any]]:
        """Search conversations by participant name or message content.

        Fetches conversations and filters locally by matching the query string
        against participant names and last message previews.

        Args:
            query: Search string to match against participant names or message previews.
            limit: Maximum conversations to fetch before filtering (default: 50).

        Returns:
            List of normalized conversation dicts that match the query.
        """
        logger.info("Searching conversations", query=query, limit=limit)
        query_lower = query.lower()

        all_conversations = await self.get_conversations(limit=limit)

        matches = []
        for conv in all_conversations:
            # Check participant names
            for p in conv.get("participants", []):
                if query_lower in p.get("name", "").lower():
                    matches.append(conv)
                    break
            else:
                # Check title and message preview
                title = conv.get("title", "").lower()
                preview = conv.get("last_message_preview", "").lower()
                if query_lower in title or query_lower in preview:
                    matches.append(conv)

        logger.info("Search conversations matched", query=query, matches=len(matches))
        return matches

    async def send_message(
        self,
        recipients: list[str],
        text: str,
    ) -> dict[str, Any]:
        """
        Send a message to one or more recipients.

        Args:
            recipients: List of profile public IDs (will be converted to URNs)
            text: Message content

        Returns:
            dict with success status and details
        """
        logger.info("Sending message", recipient_count=len(recipients))

        # Convert public IDs to member URNs
        # linkedin-api expects URN IDs like "ACoAACX1hoMBvWqTY21JGe0z91mnmjmLy9Wen4w"
        # not public IDs like "johndoe"
        member_urns = []
        for public_id in recipients:
            try:
                # Get profile to extract the URN
                profile = await self._execute(self._client.get_profile, public_id)
                if not profile:
                    logger.warning("Could not find profile", public_id=public_id)
                    continue

                # Extract member URN from profile
                # profile_urn is like "urn:li:fs_miniProfile:ACoAACX1hoMBvWqTY21JGe0z91mnmjmLy9Wen4w"
                profile_urn = profile.get("profile_urn", "")
                if profile_urn:
                    member_id = profile_urn.split(":")[-1]
                    member_urns.append(member_id)
                    logger.debug("Converted public_id to URN", public_id=public_id, member_id=member_id)
                else:
                    # Try entityUrn as fallback
                    entity_urn = profile.get("entityUrn", "")
                    if entity_urn:
                        member_id = entity_urn.split(":")[-1]
                        member_urns.append(member_id)
                    else:
                        logger.warning("Could not extract URN from profile", public_id=public_id)
            except Exception as e:
                logger.warning("Failed to get profile for messaging", public_id=public_id, error=str(e))
                continue

        if not member_urns:
            return {
                "success": False,
                "error": "Could not resolve any recipient URNs. Ensure recipients are valid LinkedIn public IDs.",
            }

        # Send the message
        # linkedin-api send_message returns True on ERROR, False on success
        result = await self._execute(
            self._client.send_message,
            text,
            recipients=member_urns,
        )

        # Handle boolean return: True = error, False = success
        if result is True:
            return {
                "success": False,
                "error": "LinkedIn API returned an error. Message may not have been sent.",
            }

        return {
            "success": True,
            "message": "Message sent successfully",
            "recipients": recipients,
            "recipient_urns": member_urns,
        }

    async def _send_via_ui(
        self,
        scraper: Any,
        text: str,
        image_path: str | None = None,
    ) -> dict[str, Any]:
        """Send a message using browser UI automation.

        Used when attachments are needed or when API endpoints fail.
        Assumes the browser is already navigated to the correct conversation thread.

        Args:
            scraper: HeadlessLinkedInScraper instance.
            text: Message text (can be empty if only sending an image).
            image_path: Path to image file to attach.

        Returns:
            dict with success status.
        """
        page = scraper._page

        # Attach image if provided
        if image_path:
            import os

            if not os.path.exists(image_path):
                return {"success": False, "error": f"Image file not found: {image_path}"}

            file_input = await page.query_selector(
                'input[accept="image/*"].msg-form__attachment-upload-input'
            )
            if not file_input:
                return {"success": False, "error": "Could not find image upload input in messaging UI"}

            await file_input.set_input_files(image_path)
            logger.info("Image attached", path=image_path)
            await asyncio.sleep(3)  # Wait for upload to complete

        # Type message text if provided
        if text and text.strip():
            msg_input = await page.query_selector(
                '.msg-form__contenteditable, '
                '[contenteditable="true"][role="textbox"]'
            )
            if msg_input:
                await msg_input.click()
                await page.keyboard.type(text, delay=10)
                await asyncio.sleep(0.5)

        # Click send
        send_btn = await page.query_selector('.msg-form__send-button')
        if not send_btn:
            return {"success": False, "error": "Could not find send button"}

        is_disabled = await send_btn.get_attribute("disabled")
        if is_disabled:
            return {"success": False, "error": "Send button is disabled — message or image may not have loaded"}

        await send_btn.click()
        await asyncio.sleep(3)

        return {
            "success": True,
            "message": "Message sent successfully" + (" with image" if image_path else ""),
            "image_attached": bool(image_path),
        }

    async def send_message_headless(
        self,
        text: str,
        conversation_id: str | None = None,
        recipients: list[str] | None = None,
        image_path: str | None = None,
    ) -> dict[str, Any]:
        """Send a message via the headless browser transport.

        Supports both replying to an existing conversation and starting a new one.
        Optionally attach an image file.

        Args:
            text: Message content to send.
            conversation_id: Conversation URN to reply to (from get_conversations results).
            recipients: List of profile public IDs for a new message.
                        Ignored if conversation_id is provided.
            image_path: Absolute path to an image file to attach (png, jpg, gif, etc.).

        Returns:
            dict with success status and details.
        """
        if not text or not text.strip():
            return {"success": False, "error": "Message text cannot be empty"}

        if not conversation_id and not recipients:
            return {"success": False, "error": "Provide either conversation_id or recipients"}

        import uuid as _uuid

        scraper = await self._get_headless_scraper()

        # Get the authenticated user's mailbox URN
        profile_urn = await self._get_profile_urn()
        mailbox_urn = f"urn:li:fsd_profile:{profile_urn}"

        if conversation_id:
            # Reply to existing conversation
            logger.info("Sending reply via headless browser", conversation_id=conversation_id)

            # Navigate to the conversation thread
            import re

            thread_match = re.search(r"(2-[A-Za-z0-9+/=]+)", conversation_id)
            if thread_match:
                thread_id = thread_match.group(1)
                page = scraper._page
                await page.goto(
                    f"https://www.linkedin.com/messaging/thread/{thread_id}/",
                    wait_until="domcontentloaded",
                    timeout=20000,
                )
                await asyncio.sleep(2)

            if image_path:
                # Use UI automation for image attachments
                return await self._send_via_ui(scraper, text, image_path=image_path)

            # Text-only: use the Dash createMessage API endpoint
            result = await scraper.api_fetch(
                "https://www.linkedin.com/voyager/api/"
                "voyagerMessagingDashMessengerMessages?action=createMessage",
                headers={"Content-Type": "application/json"},
                method="POST",
                body={
                    "message": {
                        "body": {
                            "attributes": [],
                            "text": text,
                        },
                        "renderContentUnions": [],
                        "conversationUrn": conversation_id,
                        "originToken": str(_uuid.uuid4()),
                    },
                    "mailboxUrn": mailbox_urn,
                    "trackingId": str(_uuid.uuid4())[:16],
                    "dedupeByClientGeneratedToken": False,
                },
            )
            return {
                "success": True,
                "message": "Reply sent successfully",
                "conversation_id": conversation_id,
            }

        else:
            # Send to recipients by public ID
            logger.info("Sending message via headless browser", recipients=recipients)

            # Strategy 1: Check if an existing conversation exists with any recipient
            # LinkedIn's new messaging system routes all messages through conversations
            # First resolve the public ID to a display name for matching
            recipient_names = {}
            for public_id in recipients:
                try:
                    profile_data = await scraper.api_fetch(
                        "https://www.linkedin.com/voyager/api/identity/dash/profiles"
                        f"?q=memberIdentity&memberIdentity={public_id}"
                        "&decorationId=com.linkedin.voyager.dash.deco.identity.profile"
                        ".FullProfileWithEntities-91",
                    )
                    elements = profile_data.get("elements", [])
                    if elements:
                        el = elements[0]
                        first = el.get("firstName", "")
                        last = el.get("lastName", "")
                        urn = el.get("entityUrn", "")
                        if first or last:
                            recipient_names[public_id] = {
                                "name": f"{first} {last}".strip(),
                                "first": first,
                                "last": last,
                                "urn": urn,
                            }
                except Exception:
                    pass

            try:
                all_convos = await self.get_conversations(limit=50)
                for public_id in recipients:
                    name_info = recipient_names.get(public_id, {})
                    recipient_name = name_info.get("name", "").lower()
                    recipient_urn = name_info.get("urn", "")

                    for conv in all_convos:
                        for p in conv.get("participants", []):
                            p_name = p.get("name", "").lower()
                            p_url = p.get("profile_url", "")

                            # Match by name, public ID in URL, or URN
                            if (
                                (recipient_name and recipient_name == p_name)
                                or public_id.lower() in p_url.lower()
                                or (recipient_urn and recipient_urn.split(":")[-1] in p_url)
                            ):
                                logger.info(
                                    "Found existing conversation for recipient",
                                    public_id=public_id,
                                    matched_name=p_name,
                                    conversation_id=conv["conversation_id"],
                                )
                                return await self.send_message_headless(
                                    text=text,
                                    conversation_id=conv["conversation_id"],
                                )
            except Exception as e:
                logger.debug("Conversation lookup failed", error=str(e))

            # Strategy 2: UI automation for truly new conversations
            logger.info("No existing conversation found, using UI automation", recipients=recipients)

            page = scraper._page
            await page.goto(
                "https://www.linkedin.com/messaging/thread/new/",
                wait_until="domcontentloaded",
                timeout=20000,
            )
            await asyncio.sleep(2)

            # Type the recipient name in the search field
            recipient_input = await page.query_selector(
                'input[name="searchTerm"], '
                'input[placeholder*="Type a name"], '
                'input[role="combobox"]'
            )
            if not recipient_input:
                return {
                    "success": False,
                    "error": "Could not find recipient input field in messaging UI",
                }

            await recipient_input.click()
            await recipient_input.type(recipients[0], delay=50)
            await asyncio.sleep(2)

            # Select the first matching result
            result_option = await page.query_selector(
                '[role="option"], '
                '.msg-connections-typeahead__search-result, '
                'li[class*="typeahead"]'
            )
            if result_option:
                await result_option.click()
                await asyncio.sleep(1)
            else:
                return {
                    "success": False,
                    "error": f"Could not find recipient '{recipients[0]}' in LinkedIn search",
                }

            # Type the message
            msg_input = await page.query_selector(
                '.msg-form__contenteditable, '
                '[contenteditable="true"], '
                '[role="textbox"]'
            )
            if not msg_input:
                return {
                    "success": False,
                    "error": "Could not find message input field",
                }

            await msg_input.click()
            await page.keyboard.type(text, delay=10)
            await asyncio.sleep(1)

            # Click send
            send_btn = await page.query_selector(
                '.msg-form__send-button, '
                'button[type="submit"]'
            )
            if send_btn:
                await send_btn.click()
                await asyncio.sleep(3)
            else:
                return {
                    "success": False,
                    "error": "Could not find send button",
                }

            return {
                "success": True,
                "message": "Message sent successfully",
                "recipients": recipients,
            }

    # ==========================================================================
    # Search Methods
    # ==========================================================================

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(LinkedInAPIError),
    )
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
            keyword_title: Filter by job title keywords
            keyword_company: Filter by company name keywords

        Returns:
            List of matching profiles
        """
        logger.info("Searching people", keywords=keywords, limit=limit)
        return await self._execute(
            self._client.search_people,
            keywords=keywords,
            limit=limit,
            keyword_title=keyword_title,
            keyword_company=keyword_company,
        )

    async def search_companies(
        self,
        keywords: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Search for companies."""
        logger.info("Searching companies", keywords=keywords, limit=limit)
        return await self._execute(
            self._client.search_companies,
            keywords=keywords,
            limit=limit,
        )

    # ==========================================================================
    # Company Methods
    # ==========================================================================

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(LinkedInAPIError),
    )
    async def get_company(self, public_id: str) -> dict[str, Any]:
        """
        Get detailed company information.

        Args:
            public_id: Company's public identifier (from URL slug)

        Returns:
            Company details including description, industry, size, etc.
        """
        logger.info("Fetching company", public_id=public_id)
        return await self._execute(self._client.get_company, public_id)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(LinkedInAPIError),
    )
    async def get_company_updates(
        self,
        public_id: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Get recent posts/updates from a company.

        Args:
            public_id: Company's public identifier
            limit: Maximum number of updates to retrieve

        Returns:
            List of company posts/updates
        """
        logger.info("Fetching company updates", public_id=public_id, limit=limit)
        return await self._execute(
            self._client.get_company_updates,
            public_id,
            max_results=limit,
        )

    # ==========================================================================
    # Lead Generation Methods
    # ==========================================================================

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(LinkedInAPIError),
    )
    async def get_profile_contact_info(self, public_id: str) -> dict[str, Any]:
        """
        Get contact information for a profile.

        Args:
            public_id: Profile's public identifier

        Returns:
            Contact info including email, phone, websites, etc.
        """
        logger.info("Fetching profile contact info", public_id=public_id)
        return await self._execute(self._client.get_profile_contact_info, public_id)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(LinkedInAPIError),
    )
    async def get_profile_skills(self, public_id: str) -> list[dict[str, Any]]:
        """
        Get skills listed on a profile.

        Args:
            public_id: Profile's public identifier

        Returns:
            List of skills with endorsement counts
        """
        logger.info("Fetching profile skills", public_id=public_id)
        return await self._execute(self._client.get_profile_skills, public_id)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(LinkedInAPIError),
    )
    async def get_school(self, public_id: str) -> dict[str, Any]:
        """
        Get school/university information.

        Args:
            public_id: School's public identifier

        Returns:
            School details
        """
        logger.info("Fetching school", public_id=public_id)
        return await self._execute(self._client.get_school, public_id)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(LinkedInAPIError),
    )
    async def get_invitations(
        self,
        limit: int = 20,
        start: int = 0,
    ) -> list[dict[str, Any]]:
        """
        Get pending connection invitations.

        Args:
            limit: Maximum invitations to retrieve
            start: Pagination offset

        Returns:
            List of pending invitations
        """
        logger.info("Fetching invitations", limit=limit, start=start)
        return await self._execute(
            self._client.get_invitations,
            start=start,
            limit=limit,
        )

    async def send_invitation(
        self,
        profile_public_id: str,
        message: str | None = None,
    ) -> dict[str, Any]:
        """
        Send a connection invitation to a profile.

        Args:
            profile_public_id: Target profile's public ID
            message: Optional personalized message (max 300 chars)

        Returns:
            dict with success status and details
        """
        logger.info("Sending invitation", profile_id=profile_public_id)
        result = await self._execute(
            self._client.add_connection,
            profile_public_id,
            message=message,
        )

        # linkedin-api add_connection returns True on ERROR, False on success
        if result is True:
            return {
                "success": False,
                "error": "LinkedIn API returned an error. Connection invitation may not have been sent.",
            }

        return {
            "success": True,
            "message": "Connection invitation sent successfully",
            "profile_id": profile_public_id,
        }

    async def withdraw_invitation(self, invitation_id: str) -> dict[str, Any]:
        """
        Withdraw a pending connection invitation.

        Args:
            invitation_id: ID of the invitation to withdraw

        Returns:
            dict with success status and details
        """
        logger.info("Withdrawing invitation", invitation_id=invitation_id)
        result = await self._execute(
            self._client.remove_connection,
            invitation_id,
        )

        # linkedin-api remove_connection returns True on ERROR, False on success
        if result is True:
            return {
                "success": False,
                "error": "LinkedIn API returned an error. Invitation may not have been withdrawn.",
            }

        return {
            "success": True,
            "message": "Connection invitation withdrawn successfully",
            "invitation_id": invitation_id,
        }

    # ==========================================================================
    # Profile Enrichment Methods (for comprehensive profile data)
    # ==========================================================================

    async def get_profile_network_info(self, public_id: str) -> dict[str, Any]:
        """
        Get network information for a profile.

        Returns connections count, followers count, network distance, and followability.

        Args:
            public_id: Profile's public identifier

        Returns:
            Network info including connections, followers, distance
        """
        logger.info("Fetching profile network info", public_id=public_id)
        return await self._execute(self._client.get_profile_network_info, public_id)

    async def get_profile_member_badges(self, public_id: str) -> dict[str, Any]:
        """
        Get member badges for a profile (Premium, Creator, etc.).

        Args:
            public_id: Profile's public identifier

        Returns:
            Badge information
        """
        logger.info("Fetching profile badges", public_id=public_id)
        return await self._execute(self._client.get_profile_member_badges, public_id)

    async def get_profile_privacy_settings(self, public_id: str) -> dict[str, Any]:
        """
        Get privacy settings for a profile.

        Useful for understanding what data might be restricted.

        Args:
            public_id: Profile's public identifier

        Returns:
            Privacy settings data
        """
        logger.info("Fetching profile privacy settings", public_id=public_id)
        return await self._execute(self._client.get_profile_privacy_settings, public_id)

    async def get_profile_updates(
        self,
        public_id: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Get activity updates for a profile.

        Args:
            public_id: Profile's public identifier
            limit: Maximum updates to retrieve

        Returns:
            List of profile activity updates
        """
        logger.info("Fetching profile updates", public_id=public_id, limit=limit)
        return await self._execute(
            self._client.get_profile_updates,
            public_id=public_id,
            max_results=limit,
        )

    # ==========================================================================
    # Job Search Methods
    # ==========================================================================

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(LinkedInAPIError),
    )
    async def search_jobs(
        self,
        keywords: str | None = None,
        companies: list[str] | None = None,
        experience: list[str] | None = None,
        job_type: list[str] | None = None,
        job_title: list[str] | None = None,
        industries: list[str] | None = None,
        location_name: str | None = None,
        remote: list[str] | None = None,
        listed_at: int = 24 * 60 * 60,
        distance: int | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Search for job postings on LinkedIn.

        Args:
            keywords: Search keywords
            companies: List of company URN IDs to filter by
            experience: Experience levels (1=Internship, 2=Entry, 3=Associate, 4=Mid-Senior, 5=Director, 6=Executive)
            job_type: Job types (F=Full-time, P=Part-time, C=Contract, T=Temporary, V=Volunteer, I=Internship)
            job_title: List of job title URN IDs
            industries: List of industry URN IDs
            location_name: Location name (e.g., "San Francisco Bay Area")
            remote: Remote options (1=On-site, 2=Remote, 3=Hybrid)
            listed_at: Max seconds since job was posted (default 24 hours)
            distance: Distance from location in miles
            limit: Maximum results to return

        Returns:
            List of matching job postings
        """
        logger.info("Searching jobs", keywords=keywords, limit=limit)
        return await self._execute(
            self._client.search_jobs,
            keywords=keywords,
            companies=companies,
            experience=experience,
            job_type=job_type,
            job_title=job_title,
            industries=industries,
            location_name=location_name,
            remote=remote,
            listed_at=listed_at,
            distance=distance,
            limit=limit,
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(LinkedInAPIError),
    )
    async def get_job(self, job_id: str) -> dict[str, Any]:
        """
        Get detailed information about a job posting.

        Args:
            job_id: LinkedIn job ID

        Returns:
            Job posting details including description, requirements, company info
        """
        logger.info("Fetching job details", job_id=job_id)
        return await self._execute(self._client.get_job, job_id)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(LinkedInAPIError),
    )
    async def get_job_skills(self, job_id: str) -> list[dict[str, Any]]:
        """
        Get skills required for a job posting.

        Args:
            job_id: LinkedIn job ID

        Returns:
            List of required and preferred skills for the job
        """
        logger.info("Fetching job skills", job_id=job_id)
        return await self._execute(self._client.get_job_skills, job_id)

    # ==========================================================================
    # Profile Analytics Methods
    # ==========================================================================

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(LinkedInAPIError),
    )
    async def get_current_profile_views(self) -> dict[str, Any]:
        """
        Get profile view statistics for the authenticated user.

        Returns:
            Profile view data including view count and viewer information
        """
        logger.info("Fetching profile views")
        return await self._execute(self._client.get_current_profile_views)

    # ==========================================================================
    # Additional Messaging Methods
    # ==========================================================================

    async def get_conversation_details(self, profile_urn: str) -> dict[str, Any]:
        """
        Get conversation ID and details for a specific profile.

        Uses the conversations list to find a conversation with the given profile URN.
        Falls back to the legacy API if GraphQL search does not find a match.

        Args:
            profile_urn: Profile URN ID (e.g., "ACoAACX1hoMBvWqTY21JGe0z91mnmjmLy9Wen4w")

        Returns:
            Conversation details including conversation ID
        """
        logger.info("Fetching conversation details via GraphQL", profile_urn=profile_urn)

        # Search conversations for one that includes this profile URN in participants
        conversations = await self.get_conversations(limit=50)
        for conv in conversations:
            conv_id = conv.get("conversation_id", "")
            if profile_urn in conv_id:
                return conv
            # Also check participant profile URLs
            for p in conv.get("participants", []):
                if profile_urn in p.get("profile_url", ""):
                    return conv

        # If not found via GraphQL, try legacy method as fallback
        try:
            return await self._execute(self._client.get_conversation_details, profile_urn)
        except Exception:
            return {
                "success": False,
                "error": f"No conversation found for profile URN: {profile_urn}",
            }

    async def get_mailbox_counts(self) -> dict[str, Any]:
        """Get unread message counts for the user's mailbox.

        Returns:
            Dict with mailbox count data from LinkedIn's GraphQL API.
        """
        logger.info("Fetching mailbox counts via GraphQL")
        profile_urn = await self._get_profile_urn()
        mailbox_urn = f"urn:li:fsd_profile:{profile_urn}"
        variables = f"mailboxUrn:{mailbox_urn}"

        data = await self._graphql_fetch_async(
            query_id="messengerMailboxCounts.fc528a5a81a76dff212a4a3d2d48e84b",
            variables=variables,
        )

        return data.get("data", {})

    async def mark_conversation_as_seen(self, conversation_urn: str) -> dict[str, Any]:
        """
        Mark a conversation as seen/read.

        Args:
            conversation_urn: Conversation URN ID

        Returns:
            dict with success status
        """
        logger.info("Marking conversation as seen", conversation_urn=conversation_urn)
        result = await self._execute(self._client.mark_conversation_as_seen, conversation_urn)

        # linkedin-api returns True on ERROR, False on success
        if result is True:
            return {
                "success": False,
                "error": "LinkedIn API returned an error. Conversation may not have been marked as seen.",
            }

        return {
            "success": True,
            "message": "Conversation marked as seen",
            "conversation_urn": conversation_urn,
        }

    # ==========================================================================
    # Headless Browser Search & Feed Methods
    # ==========================================================================

    async def _headless_api_fetch(self, url: str) -> dict[str, Any]:
        """Make a Voyager API call via the headless browser.

        Handles rate limiting, scraper initialization, and error classification.

        Args:
            url: Full URL to fetch via the browser context.

        Returns:
            Parsed JSON response dict.
        """
        await self.rate_limiter.acquire()
        scraper = await self._get_headless_scraper()
        try:
            return await scraper.api_fetch(url)
        except Exception as e:
            error_str = str(e).lower()
            if "rate" in error_str or "limit" in error_str or "429" in error_str:
                raise LinkedInRateLimitError(str(e), cause=e) from e
            elif "auth" in error_str or "login" in error_str or "401" in error_str:
                raise LinkedInAuthError(str(e), cause=e) from e
            elif isinstance(e, (LinkedInAPIError, LinkedInAuthError, LinkedInRateLimitError)):
                raise
            else:
                raise LinkedInAPIError(str(e), cause=e) from e

    @staticmethod
    def _build_search_url(
        keywords: str,
        result_type: str,
        start: int = 0,
        extra_filters: list[tuple[str, str]] | None = None,
    ) -> str:
        """Build a Voyager search GraphQL URL.

        Args:
            keywords: Search query string.
            result_type: Result type filter (CONTENT, PEOPLE, COMPANIES).
            start: Pagination offset.
            extra_filters: Additional (key, value) filter pairs.

        Returns:
            Fully constructed search URL.
        """
        filters = [f"(key:resultType,value:List({result_type}))"]
        if extra_filters:
            for key, value in extra_filters:
                filters.append(f"(key:{key},value:List({value}))")
        filters_str = ",".join(filters)

        encoded_keywords = quote(keywords, safe="")

        variables = (
            f"(start:{start},origin:FACETED_SEARCH,"
            f"query:(keywords:{encoded_keywords},"
            f"flagshipSearchIntent:SEARCH_SRP,"
            f"queryParameters:List({filters_str}),"
            f"includeFiltersInResponse:false))"
        )
        query_id = "voyagerSearchDashClusters.b0928897b71bd00a5a7291755dcd64f0"
        return (
            f"https://www.linkedin.com/voyager/api/graphql"
            f"?variables={variables}&queryId={query_id}"
        )

    @staticmethod
    def _extract_search_results(data: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract entity results from a Voyager search response.

        Args:
            data: Raw JSON response from the search endpoint.

        Returns:
            List of raw entityResult dicts.
        """
        results: list[dict[str, Any]] = []
        root = data.get("data", data)
        clusters = root.get("searchDashClustersByAll", {})
        for cluster in clusters.get("elements", []):
            for item_wrapper in cluster.get("items", []):
                item = item_wrapper.get("item", {})
                entity = item.get("entityResult")
                if entity:
                    results.append(entity)
        return results

    async def search_content(
        self,
        keywords: str,
        date_posted: str = "past-week",
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Search LinkedIn posts/content by keyword via headless browser.

        Args:
            keywords: Search query string.
            date_posted: Time filter - "past-24h", "past-week", "past-month", or "" for any.
            limit: Maximum results to return.

        Returns:
            List of normalized content result dicts.
        """
        logger.info("Searching content via headless browser", keywords=keywords, limit=limit)

        extra_filters: list[tuple[str, str]] = []
        if date_posted:
            extra_filters.append(("datePosted", date_posted))

        all_results: list[dict[str, Any]] = []
        start = 0
        page_size = min(limit, 20)

        while len(all_results) < limit:
            url = self._build_search_url(
                keywords=keywords,
                result_type="CONTENT",
                start=start,
                extra_filters=extra_filters,
            )
            data = await self._headless_api_fetch(url)
            entities = self._extract_search_results(data)

            if not entities:
                break

            for entity in entities:
                if len(all_results) >= limit:
                    break
                all_results.append(self._normalize_content_result(entity))

            start += page_size

        logger.info("Content search completed", count=len(all_results))
        return all_results

    @staticmethod
    def _normalize_content_result(entity: dict[str, Any]) -> dict[str, Any]:
        """Normalize a content search entity into a clean dict.

        Args:
            entity: Raw entityResult from the search response.

        Returns:
            Normalized dict with title, text_preview, author info, and metrics.
        """
        title_obj = entity.get("title", {})
        summary_obj = entity.get("summary", {})
        nav_url = entity.get("navigationUrl", "")

        # Extract insight text (often contains engagement info)
        insights = entity.get("insightsResolutionResults", [])
        reactions_count = 0
        comments_count = 0
        reposts_count = 0

        # Try to extract metrics from insights or socialActivityCounts
        social_counts = entity.get("socialActivityCountsInsight", {})
        if social_counts:
            reactions_count = social_counts.get("numLikes", 0)
            comments_count = social_counts.get("numComments", 0)
            reposts_count = social_counts.get("numShares", 0)

        # Extract author from actorNavigationContext or primarySubtitle
        actor = entity.get("actorNavigationContext", {})
        author_name = actor.get("title", "")
        author_headline = ""
        primary_subtitle = entity.get("primarySubtitle", {})
        if primary_subtitle:
            author_headline = primary_subtitle.get("text", "")

        # If no author from actor, try title for name
        if not author_name:
            secondary = entity.get("secondarySubtitle", {})
            if secondary:
                author_name = secondary.get("text", "")

        return {
            "title": title_obj.get("text", "") if isinstance(title_obj, dict) else str(title_obj),
            "text_preview": summary_obj.get("text", "") if isinstance(summary_obj, dict) else str(summary_obj),
            "author_name": author_name,
            "author_headline": author_headline,
            "url": nav_url,
            "reactions_count": reactions_count,
            "comments_count": comments_count,
            "reposts_count": reposts_count,
            "posted_at": entity.get("actorNavigationContext", {}).get("subtitle", ""),
        }

    async def get_feed_posts_headless(self, limit: int = 20) -> list[dict[str, Any]]:
        """Get the authenticated user's feed via headless browser.

        Falls back to this when the linkedin-api get_feed_posts method fails.

        Args:
            limit: Maximum number of feed posts to return.

        Returns:
            List of raw feed post dicts from the Voyager API.
        """
        logger.info("Fetching feed via headless browser", limit=limit)

        url = (
            "https://www.linkedin.com/voyager/api/graphql"
            "?variables=(count:{count},start:0)"
            "&queryId=voyagerFeedDashTimeline"
            ".d805e081daaa77c0cd24e75e44580fa8"
        ).format(count=limit)

        data = await self._headless_api_fetch(url)

        # Parse feed response
        root = data.get("data", data)
        timeline = root.get("feedDashTimelineByType", root.get("*elements", {}))
        elements = []
        if isinstance(timeline, dict):
            elements = timeline.get("elements", [])
        elif isinstance(timeline, list):
            elements = timeline

        posts: list[dict[str, Any]] = []
        for el in elements:
            if len(posts) >= limit:
                break
            posts.append(el)

        logger.info("Feed fetched via headless browser", count=len(posts))
        return posts

    async def search_people_headless(
        self,
        keywords: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Search for people via headless browser.

        Args:
            keywords: Search query string.
            limit: Maximum results to return.

        Returns:
            List of normalized people search results.
        """
        logger.info("Searching people via headless browser", keywords=keywords, limit=limit)

        all_results: list[dict[str, Any]] = []
        start = 0
        page_size = min(limit, 10)

        while len(all_results) < limit:
            url = self._build_search_url(
                keywords=keywords,
                result_type="PEOPLE",
                start=start,
            )
            data = await self._headless_api_fetch(url)
            entities = self._extract_search_results(data)

            if not entities:
                break

            for entity in entities:
                if len(all_results) >= limit:
                    break
                all_results.append(self._normalize_people_result(entity))

            start += page_size

        logger.info("People search via headless completed", count=len(all_results))
        return all_results

    @staticmethod
    def _normalize_people_result(entity: dict[str, Any]) -> dict[str, Any]:
        """Normalize a people search entity into a clean dict."""
        title_obj = entity.get("title", {})
        name = title_obj.get("text", "") if isinstance(title_obj, dict) else str(title_obj)

        primary_subtitle = entity.get("primarySubtitle", {})
        headline = primary_subtitle.get("text", "") if isinstance(primary_subtitle, dict) else ""

        secondary_subtitle = entity.get("secondarySubtitle", {})
        location = secondary_subtitle.get("text", "") if isinstance(secondary_subtitle, dict) else ""

        nav_url = entity.get("navigationUrl", "")
        entity_urn = entity.get("entityUrn", "")

        return {
            "name": name,
            "headline": headline,
            "location": location,
            "profile_url": nav_url,
            "urn": entity_urn,
        }

    async def search_companies_headless(
        self,
        keywords: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Search for companies via headless browser.

        Args:
            keywords: Search query string.
            limit: Maximum results to return.

        Returns:
            List of normalized company search results.
        """
        logger.info("Searching companies via headless browser", keywords=keywords, limit=limit)

        all_results: list[dict[str, Any]] = []
        start = 0
        page_size = min(limit, 10)

        while len(all_results) < limit:
            url = self._build_search_url(
                keywords=keywords,
                result_type="COMPANIES",
                start=start,
            )
            data = await self._headless_api_fetch(url)
            entities = self._extract_search_results(data)

            if not entities:
                break

            for entity in entities:
                if len(all_results) >= limit:
                    break
                all_results.append(self._normalize_company_result(entity))

            start += page_size

        logger.info("Company search via headless completed", count=len(all_results))
        return all_results

    @staticmethod
    def _normalize_company_result(entity: dict[str, Any]) -> dict[str, Any]:
        """Normalize a company search entity into a clean dict."""
        title_obj = entity.get("title", {})
        name = title_obj.get("text", "") if isinstance(title_obj, dict) else str(title_obj)

        primary_subtitle = entity.get("primarySubtitle", {})
        industry = primary_subtitle.get("text", "") if isinstance(primary_subtitle, dict) else ""

        secondary_subtitle = entity.get("secondarySubtitle", {})
        info = secondary_subtitle.get("text", "") if isinstance(secondary_subtitle, dict) else ""

        summary_obj = entity.get("summary", {})
        description = summary_obj.get("text", "") if isinstance(summary_obj, dict) else ""

        nav_url = entity.get("navigationUrl", "")
        entity_urn = entity.get("entityUrn", "")

        return {
            "name": name,
            "industry": industry,
            "info": info,
            "description": description,
            "company_url": nav_url,
            "urn": entity_urn,
        }

    # ==========================================================================
    # Utility Methods
    # ==========================================================================

    @property
    def rate_limit_remaining(self) -> int:
        """Get remaining API calls in current window."""
        return self.rate_limiter.remaining

    async def close(self) -> None:
        """Close the client, headless scraper, and save session."""
        if self._headless_scraper:
            try:
                await self._headless_scraper.close()
            except Exception as e:
                logger.warning("Failed to close headless scraper", error=str(e))
            self._headless_scraper = None
        await self._save_cookies()
        logger.info("LinkedIn client closed")
