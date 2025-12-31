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
    """

    def __init__(
        self,
        email: str,
        password: str,
        cookie_path: Path | None = None,
        rate_limit: int = MAX_REQUESTS_PER_HOUR,
    ):
        self.email = email
        self.password = password
        self.cookie_path = cookie_path or Path("./data/session_cookies.json")
        self.rate_limiter = RateLimiter(max_requests=rate_limit)
        self._client: Any = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the LinkedIn client with authentication."""
        if self._initialized:
            logger.info("LinkedIn client already initialized, skipping")
            return

        logger.info(
            "Starting LinkedIn client initialization",
            cookie_path=str(self.cookie_path),
            cookie_path_exists=self.cookie_path.exists(),
        )

        cookies = await self._load_cookies()

        logger.info(
            "Cookies loaded for initialization",
            has_cookies=cookies is not None,
            cookie_type=type(cookies).__name__ if cookies else None,
            cookie_count=len(cookies) if cookies else 0,
        )

        def create_client() -> Any:
            from linkedin_api import Linkedin

            logger.info(
                "Creating LinkedIn client in executor",
                has_cookies=cookies is not None,
                cookie_count=len(cookies) if cookies else 0,
                cookie_type=type(cookies).__name__ if cookies else None,
            )

            # Log the actual call parameters
            logger.info(
                "Calling Linkedin constructor",
                email=self.email,
                password_length=len(self.password) if self.password else 0,
                cookies_provided=cookies is not None,
                refresh_cookies=True,
            )

            client = Linkedin(
                self.email,
                self.password,
                cookies=cookies,
                refresh_cookies=True,
            )

            logger.info(
                "Linkedin constructor returned",
                client_type=type(client).__name__,
            )

            return client

        try:
            logger.info("Running create_client in executor")
            self._client = await asyncio.get_event_loop().run_in_executor(
                None, create_client
            )
            self._initialized = True

            logger.info(
                "Client initialized, saving cookies",
                client_type=type(self._client).__name__,
            )

            # Save refreshed cookies
            await self._save_cookies()

            logger.info("LinkedIn client initialized successfully")

        except Exception as e:
            import traceback
            logger.error(
                "LinkedIn authentication failed",
                error=str(e),
                error_type=type(e).__name__,
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
        """Save session cookies to file."""
        if not self._client:
            return

        try:
            self.cookie_path.parent.mkdir(parents=True, exist_ok=True)

            if hasattr(self._client, "client") and hasattr(self._client.client, "cookies"):
                cookies = dict(self._client.client.cookies)

                def write_cookies() -> None:
                    with self.cookie_path.open("w") as f:
                        json.dump(cookies, f)

                await asyncio.get_event_loop().run_in_executor(None, write_cookies)
                logger.debug("Session cookies saved")

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
        """Get user's connections."""
        logger.info("Fetching connections", limit=limit)
        return await self._execute(self._client.get_profile_connections, limit=limit)

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
            Request result
        """
        logger.info("Sending connection request", public_id=public_id)
        return await self._execute(
            self._client.add_connection,
            public_id,
            message=message,
        )

    async def remove_connection(self, public_id: str) -> dict[str, Any]:
        """Remove a connection."""
        logger.info("Removing connection", public_id=public_id)
        return await self._execute(self._client.remove_connection, public_id)

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
        """Accept a connection invitation."""
        logger.info("Accepting invitation", invitation_id=invitation_id)
        return await self._execute(
            self._client.reply_invitation,
            invitation_id,
            shared_secret,
            action="accept",
        )

    async def reject_invitation(self, invitation_id: str, shared_secret: str) -> dict[str, Any]:
        """Reject a connection invitation."""
        logger.info("Rejecting invitation", invitation_id=invitation_id)
        return await self._execute(
            self._client.reply_invitation,
            invitation_id,
            shared_secret,
            action="ignore",
        )

    # ==========================================================================
    # Messaging Methods
    # ==========================================================================

    async def get_conversations(self) -> list[dict[str, Any]]:
        """Get messaging conversations."""
        logger.info("Fetching conversations")
        return await self._execute(self._client.get_conversations)

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
            recipients: List of profile public IDs
            text: Message content

        Returns:
            Message data
        """
        logger.info("Sending message", recipient_count=len(recipients))
        return await self._execute(
            self._client.send_message,
            text,
            recipients=recipients,
        )

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
