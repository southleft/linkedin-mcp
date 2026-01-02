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
    ):
        """
        Initialize LinkedIn client.

        Args:
            email: LinkedIn email (optional if using cookies)
            password: LinkedIn password (optional if using cookies)
            cookie_path: Path to cookie file (optional)
            cookies: Direct cookies dict with li_at and optionally JSESSIONID
            rate_limit: Max requests per hour
        """
        self.email = email
        self.password = password
        self.cookie_path = cookie_path or Path("./data/session_cookies.json")
        self._direct_cookies = cookies  # New: direct cookies from keychain
        self.rate_limiter = RateLimiter(max_requests=rate_limit)
        self._client: Any = None
        self._initialized = False

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

        Args:
            limit: Maximum number of posts to return

        Returns:
            List of feed posts
        """
        logger.info("Fetching feed", limit=limit)
        return await self._execute(self._client.get_feed_posts, limit=limit)

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
        sent: bool = False,
    ) -> list[dict[str, Any]]:
        """
        Get pending connection invitations.

        Args:
            sent: If True, get sent invitations; otherwise get received

        Returns:
            List of pending invitations
        """
        logger.info("Fetching invitations", sent=sent)
        if sent:
            return await self._execute(self._client.get_invitations, inviter_id=None)
        return await self._execute(self._client.get_invitations)

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
    # Messaging Methods
    # ==========================================================================

    async def get_conversations(self) -> list[dict[str, Any]]:
        """Get messaging conversations.

        Returns:
            List of conversation dicts extracted from API response.
        """
        logger.info("Fetching conversations")
        result = await self._execute(self._client.get_conversations)
        # The linkedin-api returns raw JSON response with structure:
        # {"elements": [...], "paging": {...}}
        # We need to extract just the elements list
        if isinstance(result, dict):
            return result.get("elements", [])
        return result if isinstance(result, list) else []

    async def get_conversation(self, conversation_id: str) -> dict[str, Any]:
        """Get a specific conversation."""
        logger.info("Fetching conversation", conversation_id=conversation_id)
        return await self._execute(self._client.get_conversation, conversation_id)

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
    # Utility Methods
    # ==========================================================================

    @property
    def rate_limit_remaining(self) -> int:
        """Get remaining API calls in current window."""
        return self.rate_limiter.remaining

    async def close(self) -> None:
        """Close the client and save session."""
        await self._save_cookies()
        logger.info("LinkedIn client closed")
