"""
Server lifespan management for LinkedIn MCP Server.

Handles initialization and cleanup of all services including:
- LinkedIn API client
- Database connections
- Scheduler
- Browser automation
"""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any

from linkedin_mcp.config.settings import Settings, get_settings
from linkedin_mcp.core.context import AppContext, clear_context, set_context
from linkedin_mcp.core.exceptions import LinkedInAuthError
from linkedin_mcp.core.logging import configure_logging, get_logger

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from fastmcp import FastMCP
    from playwright.async_api import Browser, BrowserContext
    from sqlalchemy.ext.asyncio import AsyncEngine

logger = get_logger(__name__)


async def init_official_client(settings: Settings) -> Any:
    """
    Initialize the LinkedIn Official API client using OAuth 2.0.

    This client provides reliable access to basic profile data via LinkedIn's
    official API using proper OAuth authentication.

    Supports two token sources (in priority order):
    1. System keychain (secure, recommended) - via linkedin-mcp-auth CLI
    2. Legacy JSON file fallback - for backward compatibility

    Args:
        settings: Application settings

    Returns:
        Initialized LinkedInOfficialClient, or None if not configured
    """
    import time

    from linkedin_mcp.services.linkedin.official_client import LinkedInOfficialClient
    from linkedin_mcp.services.storage.token_storage import get_official_token

    # Priority 1: Check system keychain for token
    token_data = get_official_token()

    if token_data:
        if token_data.is_expired:
            logger.warning(
                "Official LinkedIn API token expired",
                expired_at=token_data.expires_at.isoformat(),
            )
            logger.info("Run: linkedin-mcp-auth oauth --force")
            return None

        if token_data.expires_soon:
            logger.warning(
                "Official LinkedIn API token expires soon",
                days_remaining=token_data.days_until_expiry,
            )
            logger.info("Consider re-authenticating: linkedin-mcp-auth oauth --force")

        try:
            # Create client with token from keychain
            client = LinkedInOfficialClient(
                client_id=settings.linkedin.client_id.get_secret_value()
                if settings.linkedin.client_id else "",
                client_secret=settings.linkedin.client_secret.get_secret_value()
                if settings.linkedin.client_secret else "",
            )

            # Set the token directly from keychain
            client._access_token = token_data.access_token
            client._token_expires_at = token_data.expires_at.timestamp()

            logger.info(
                "Official LinkedIn API client initialized from keychain",
                days_remaining=token_data.days_until_expiry,
                scopes=token_data.scopes,
            )
            return client

        except Exception as e:
            logger.warning(
                "Failed to initialize Official LinkedIn API client from keychain",
                error=str(e),
            )
            # Fall through to legacy file check

    # Priority 2: Legacy JSON file fallback
    token_path = settings.session_cookie_path.parent / "oauth_token.json"

    if not token_path.exists():
        logger.info(
            "Official LinkedIn API disabled - no token found",
            keychain_checked=True,
            legacy_path=str(token_path),
        )
        logger.info("Run: linkedin-mcp-auth oauth")
        return None

    try:
        # Legacy: load from JSON file
        client = LinkedInOfficialClient(
            client_id=settings.linkedin.client_id.get_secret_value()
            if settings.linkedin.client_id else "",
            client_secret=settings.linkedin.client_secret.get_secret_value()
            if settings.linkedin.client_secret else "",
            token_path=token_path,
        )

        if client.is_authenticated:
            logger.info(
                "Official LinkedIn API client initialized from legacy file",
                token_valid_for=f"{client._token_expires_at - time.time():.0f}s"
                if client._token_expires_at else "unknown",
            )
            logger.info(
                "Consider migrating to keychain: linkedin-mcp-auth oauth --force"
            )
            return client
        else:
            logger.warning("Official LinkedIn API token expired or invalid")
            logger.info("Run: linkedin-mcp-auth oauth --force")
            return None

    except Exception as e:
        logger.warning(
            "Failed to initialize Official LinkedIn API client",
            error=str(e),
        )
        return None


async def init_linkedin_client(settings: Settings) -> Any:
    """
    Initialize the LinkedIn API client (unofficial/Voyager API).

    Supports multiple authentication methods (in priority order):
    1. Cookies from system keychain (via linkedin-mcp-auth extract-cookies)
    2. Username/password from environment (legacy, may cause issues)

    Args:
        settings: Application settings

    Returns:
        Initialized LinkedInClient wrapper, or None if disabled
    """
    import os

    from linkedin_mcp.services.storage.token_storage import get_unofficial_cookies

    # Debug: Log environment variables
    logger.info(
        "LinkedIn unofficial client init - checking config",
        api_enabled=settings.linkedin.api_enabled,
        email=settings.linkedin.email,
        password_set=settings.linkedin.password is not None,
        cookie_path=str(settings.session_cookie_path),
    )

    # Check if linkedin-api is enabled
    if not settings.linkedin.api_enabled:
        logger.info(
            "LinkedIn unofficial API disabled",
            reason="LINKEDIN_API_ENABLED=false or not set",
        )
        return None

    from linkedin_mcp.services.linkedin import LinkedInClient

    # Priority 1: Try keychain cookies (safer, no password needed)
    cookies = get_unofficial_cookies()

    if cookies:
        if cookies.is_stale:
            logger.warning(
                "LinkedIn cookies may be stale",
                hours_old=cookies.hours_since_extraction,
            )
            logger.info("Consider refreshing: linkedin-mcp-auth extract-cookies")

        try:
            logger.info(
                "Initializing LinkedIn client from keychain cookies",
                browser=cookies.browser,
                hours_old=cookies.hours_since_extraction,
            )

            # Create client with cookies (no password needed)
            client = LinkedInClient(
                cookies={
                    "li_at": cookies.li_at,
                    "JSESSIONID": cookies.jsessionid or "",
                },
                rate_limit=settings.rate_limit.requests_per_minute * 60,
            )

            await client.initialize()
            logger.info("LinkedIn unofficial client initialized from keychain cookies")
            return client

        except Exception as e:
            logger.warning(
                "Failed to initialize LinkedIn client from keychain cookies",
                error=str(e),
            )
            logger.info("Run: linkedin-mcp-auth extract-cookies")
            # Fall through to legacy method

    # Priority 2: Legacy username/password method (may cause session issues)
    if not settings.linkedin.email or not settings.linkedin.password:
        logger.info(
            "LinkedIn unofficial API disabled - no credentials",
            reason="No keychain cookies and no LINKEDIN_EMAIL/PASSWORD set",
        )
        logger.info("Run: linkedin-mcp-auth extract-cookies")
        return None

    logger.warning(
        "Using username/password auth (may cause session issues)",
        recommendation="Use: linkedin-mcp-auth extract-cookies instead",
    )

    try:
        logger.info(
            "Initializing LinkedIn client with credentials",
            email=settings.linkedin.email,
            cookie_path=str(settings.session_cookie_path),
        )

        client = LinkedInClient(
            email=settings.linkedin.email,
            password=settings.linkedin.password.get_secret_value(),
            cookie_path=settings.session_cookie_path,
            rate_limit=settings.rate_limit.requests_per_minute * 60,
        )

        logger.info("LinkedInClient created, calling initialize()")
        await client.initialize()

        logger.info("LinkedIn unofficial client initialized (legacy method)")
        return client

    except Exception as e:
        import traceback
        logger.error(
            "Failed to initialize LinkedIn client",
            error=str(e),
            error_type=type(e).__name__,
            traceback=traceback.format_exc(),
        )
        raise LinkedInAuthError(
            "Failed to authenticate with LinkedIn",
            cause=e,
        ) from e




async def init_marketing_client(settings: Settings, official_client: Any) -> Any:
    """
    Initialize the LinkedIn Marketing API client for Community Management.

    Requires:
    1. Valid OAuth token from official_client
    2. Community Management API product enabled in Developer Portal

    Args:
        settings: Application settings
        official_client: LinkedIn Official API client with valid OAuth token

    Returns:
        Initialized LinkedInMarketingClient, or None if not available
    """
    if not official_client:
        logger.info(
            "Marketing API disabled - requires OAuth authentication",
            recommendation="Run: linkedin-mcp-auth oauth",
        )
        return None

    if not official_client.is_authenticated:
        logger.info("Marketing API disabled - OAuth token expired or invalid")
        return None

    try:
        from linkedin_mcp.services.linkedin.marketing_client import LinkedInMarketingClient

        # Get access token from official client
        access_token = official_client._access_token

        if not access_token:
            logger.warning("Marketing API disabled - no access token available")
            return None

        client = LinkedInMarketingClient(
            access_token=access_token,
        )

        logger.info(
            "Marketing API client initialized",
            features=["organization_lookup", "follower_counts"],
        )
        return client

    except Exception as e:
        logger.warning(
            "Failed to initialize Marketing API client",
            error=str(e),
        )
        return None


async def init_fresh_data_client(settings: Settings) -> Any:
    """
    Initialize the Fresh LinkedIn Data API client (RapidAPI).

    Requires:
    - THIRDPARTY_RAPIDAPI_KEY environment variable

    Args:
        settings: Application settings

    Returns:
        Initialized FreshLinkedInDataClient, or None if not configured
    """
    if not settings.third_party.rapidapi_key:
        logger.info(
            "Fresh Data API disabled - no API key configured",
            recommendation="Set THIRDPARTY_RAPIDAPI_KEY in .env",
        )
        return None

    try:
        from linkedin_mcp.services.linkedin.fresh_data_client import FreshLinkedInDataClient

        client = FreshLinkedInDataClient(
            rapidapi_key=settings.third_party.rapidapi_key.get_secret_value(),
            timeout=settings.third_party.rapidapi_timeout,
        )

        logger.info(
            "Fresh Data API client initialized",
            features=["profile_search", "company_search", "employee_search"],
        )
        return client

    except Exception as e:
        logger.warning(
            "Failed to initialize Fresh Data API client",
            error=str(e),
        )
        return None


async def init_database(settings: Settings) -> "AsyncEngine | None":
    """
    Initialize the database engine.

    Args:
        settings: Application settings

    Returns:
        SQLAlchemy async engine
    """
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    try:
        logger.info("Initializing database", url=settings.database.url.split("///")[0])

        # Ensure data directory exists for SQLite
        if "sqlite" in settings.database.url:
            db_path = settings.database.url.split("///")[-1]
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        engine = create_async_engine(
            settings.database.url,
            echo=settings.database.echo,
        )

        # Test connection
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))

        logger.info("Database initialized successfully")
        return engine

    except Exception as e:
        logger.error("Failed to initialize database", error=str(e))
        return None


async def init_scheduler(settings: Settings) -> "AsyncIOScheduler | None":
    """
    Initialize the APScheduler.

    Args:
        settings: Application settings

    Returns:
        Configured scheduler instance
    """
    if not settings.scheduler.enabled:
        logger.info("Scheduler disabled by configuration")
        return None

    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler

        logger.info("Initializing scheduler")

        scheduler = AsyncIOScheduler(
            timezone=settings.scheduler.timezone,
            job_defaults={
                "coalesce": settings.scheduler.coalesce,
                "max_instances": settings.scheduler.max_instances,
                "misfire_grace_time": settings.scheduler.misfire_grace_time,
            },
        )

        logger.info("Scheduler initialized successfully")
        return scheduler

    except Exception as e:
        logger.error("Failed to initialize scheduler", error=str(e))
        return None


async def init_browser(settings: Settings) -> tuple["Browser | None", "BrowserContext | None"]:
    """
    Initialize Playwright browser for automation fallback.

    Args:
        settings: Application settings

    Returns:
        Tuple of (Browser, BrowserContext) or (None, None)
    """
    if not settings.features.browser_fallback:
        logger.info("Browser fallback disabled by configuration")
        return None, None

    try:
        from playwright.async_api import async_playwright

        logger.info("Initializing browser automation")

        # Ensure user data directory exists
        settings.browser.user_data_dir.mkdir(parents=True, exist_ok=True)

        playwright = await async_playwright().start()

        browser = await playwright.chromium.launch(
            headless=settings.browser.headless,
            slow_mo=settings.browser.slowmo,
        )

        context = await browser.new_context(
            viewport={
                "width": settings.browser.viewport_width,
                "height": settings.browser.viewport_height,
            },
            storage_state=str(settings.browser.user_data_dir / "state.json")
            if (settings.browser.user_data_dir / "state.json").exists()
            else None,
        )

        logger.info("Browser automation initialized successfully")
        return browser, context

    except Exception as e:
        logger.error("Failed to initialize browser", error=str(e))
        return None, None


async def init_data_provider(
    settings: Settings,
    primary_client: Any | None = None,
    marketing_client: Any | None = None,
    fresh_data_client: Any | None = None,
) -> Any:
    """
    Initialize the LinkedIn data provider with automatic fallback.

    The data provider orchestrates between multiple data sources:
    1. Primary: tomquirk/linkedin-api (fastest, most features)
    2. Marketing API: LinkedIn Official Community Management API (organizations)
    3. Fresh Data API: RapidAPI Fresh LinkedIn Profile Data (search)
    4. Enhanced: HTTP client with curl_cffi (anti-detection)
    5. Headless: Browser scraper (most reliable, slowest)

    Args:
        settings: Application settings
        primary_client: Optional pre-initialized linkedin-api client
        marketing_client: Optional Marketing API client (Community Management)
        fresh_data_client: Optional Fresh LinkedIn Data API client (RapidAPI)

    Returns:
        Initialized LinkedInDataProvider, or None if no data sources available
    """
    from linkedin_mcp.services.storage.token_storage import get_unofficial_cookies

    # Get cookies for fallback clients
    cookies = get_unofficial_cookies()

    # Allow initialization if any data source is available
    if not cookies and not primary_client and not marketing_client and not fresh_data_client:
        logger.info(
            "Data provider disabled - no data sources available",
            recommendation="Run: linkedin-mcp-auth oauth (for Marketing API) or set THIRDPARTY_RAPIDAPI_KEY",
        )
        return None

    try:
        from linkedin_mcp.services.linkedin.data_provider import LinkedInDataProvider

        # Prepare cookies dict for fallback clients
        cookie_dict = {}
        if cookies:
            cookie_dict["li_at"] = cookies.li_at
            if cookies.jsessionid:
                cookie_dict["JSESSIONID"] = cookies.jsessionid

        # Get the underlying linkedin-api client if available
        underlying_client = None
        if primary_client and hasattr(primary_client, "_client"):
            underlying_client = primary_client._client

        # Create data provider with full fallback chain
        provider = LinkedInDataProvider(
            primary_client=underlying_client,
            marketing_client=marketing_client,
            fresh_data_client=fresh_data_client,
            cookies=cookie_dict,
            enable_enhanced=settings.features.browser_fallback,
            enable_headless=settings.features.browser_fallback,
        )

        await provider.initialize()

        logger.info(
            "Data provider initialized with fallback chain",
            primary=underlying_client is not None,
            marketing=marketing_client is not None,
            fresh_data=fresh_data_client is not None,
            cookies_available=bool(cookie_dict),
            enhanced_enabled=settings.features.browser_fallback,
            headless_enabled=settings.features.browser_fallback,
        )

        return provider

    except Exception as e:
        logger.warning(
            "Failed to initialize data provider",
            error=str(e),
        )
        return None


async def shutdown_services(ctx: AppContext) -> None:
    """
    Gracefully shutdown all services.

    Args:
        ctx: Application context with services to shutdown
    """
    logger.info("Shutting down services")
    ctx.mark_shutting_down()

    # Stop scheduler
    if ctx.scheduler and ctx.scheduler.running:
        logger.debug("Stopping scheduler")
        ctx.scheduler.shutdown(wait=False)

    # Close browser
    if ctx.browser_context:
        logger.debug("Saving browser state")
        try:
            state_path = ctx.settings.browser.user_data_dir / "state.json"
            await ctx.browser_context.storage_state(path=str(state_path))
            await ctx.browser_context.close()
        except Exception as e:
            logger.warning("Error saving browser state", error=str(e))

    if ctx.browser:
        logger.debug("Closing browser")
        try:
            await ctx.browser.close()
        except Exception as e:
            logger.warning("Error closing browser", error=str(e))

    # Close database
    if ctx.db_engine:
        logger.debug("Closing database connections")
        try:
            await ctx.db_engine.dispose()
        except Exception as e:
            logger.warning("Error closing database", error=str(e))

    # Close LinkedIn client
    if ctx.linkedin_client:
        logger.debug("Closing LinkedIn client")
        try:
            await ctx.linkedin_client.close()
        except Exception as e:
            logger.warning("Error closing LinkedIn client", error=str(e))

    # Close Marketing API client
    if ctx.marketing_client:
        logger.debug("Closing Marketing API client")
        try:
            await ctx.marketing_client.close()
        except Exception as e:
            logger.warning("Error closing Marketing API client", error=str(e))

    # Close Fresh Data API client
    if ctx.fresh_data_client:
        logger.debug("Closing Fresh Data API client")
        try:
            await ctx.fresh_data_client.close()
        except Exception as e:
            logger.warning("Error closing Fresh Data API client", error=str(e))

    # Close data provider (includes enhanced client and headless scraper)
    if ctx.data_provider:
        logger.debug("Closing data provider")
        try:
            await ctx.data_provider.close()
        except Exception as e:
            logger.warning("Error closing data provider", error=str(e))

    logger.info("All services shut down")


@asynccontextmanager
async def lifespan(server: "FastMCP") -> AsyncGenerator[AppContext, None]:
    """
    Server lifespan context manager.

    Initializes all services on startup and cleans up on shutdown.

    Yields:
        AppContext: Initialized application context
    """
    # Load settings
    settings = get_settings()

    # Configure logging first
    configure_logging(settings.logging)

    logger.info(
        "Starting LinkedIn MCP Server",
        version=settings.server.version,
        transport=settings.server.transport,
    )

    # Initialize context
    ctx = AppContext(settings=settings)

    try:
        # Initialize services concurrently where possible
        # Note: Marketing client depends on official client, so initialized separately
        official_task = asyncio.create_task(init_official_client(settings))
        linkedin_task = asyncio.create_task(init_linkedin_client(settings))
        fresh_data_task = asyncio.create_task(init_fresh_data_client(settings))
        db_task = asyncio.create_task(init_database(settings))
        scheduler_task = asyncio.create_task(init_scheduler(settings))
        browser_task = asyncio.create_task(init_browser(settings))

        # Wait for all initializations
        results = await asyncio.gather(
            official_task,
            linkedin_task,
            fresh_data_task,
            db_task,
            scheduler_task,
            browser_task,
            return_exceptions=True,
        )

        # Process results
        (
            official_result,
            linkedin_result,
            fresh_data_result,
            db_result,
            scheduler_result,
            browser_result,
        ) = results

        # Handle Official LinkedIn client (preferred for basic profile)
        if isinstance(official_result, Exception):
            logger.warning(
                "Official LinkedIn API initialization failed",
                error=str(official_result),
            )
        else:
            ctx.official_client = official_result

        # Handle LinkedIn client (optional - server can run without auth for testing)
        if isinstance(linkedin_result, Exception):
            logger.warning(
                "LinkedIn authentication failed - some tools will be unavailable",
                error=str(linkedin_result),
            )
        else:
            ctx.linkedin_client = linkedin_result

        # Handle Fresh Data API client (RapidAPI)
        fresh_data_client = None
        if isinstance(fresh_data_result, Exception):
            logger.warning(
                "Fresh Data API initialization failed",
                error=str(fresh_data_result),
            )
        else:
            fresh_data_client = fresh_data_result
            ctx.fresh_data_client = fresh_data_result

        # Handle database (optional but recommended)
        if isinstance(db_result, Exception):
            logger.warning("Database initialization failed", error=str(db_result))
        else:
            ctx.db_engine = db_result

        # Handle scheduler (optional)
        if isinstance(scheduler_result, Exception):
            logger.warning("Scheduler initialization failed", error=str(scheduler_result))
        else:
            ctx.scheduler = scheduler_result

        # Handle browser (optional)
        if isinstance(browser_result, Exception):
            logger.warning("Browser initialization failed", error=str(browser_result))
        elif browser_result != (None, None):
            ctx.browser, ctx.browser_context = browser_result

            # Initialize BrowserAutomation wrapper for profile scraping
            from linkedin_mcp.services.browser import BrowserAutomation, set_browser_automation
            automation = BrowserAutomation(
                browser=ctx.browser,
                context=ctx.browser_context,
            )
            await automation.initialize()
            set_browser_automation(automation)
            logger.info("Browser automation initialized for profile scraping")

        # Initialize Marketing API client (depends on official client for OAuth token)
        marketing_client = None
        if ctx.official_client:
            try:
                marketing_client = await init_marketing_client(settings, ctx.official_client)
                ctx.marketing_client = marketing_client
            except Exception as e:
                logger.warning("Marketing API initialization failed", error=str(e))

        # Initialize data provider with fallback chain (after all clients are ready)
        # This provides automatic fallback: primary → marketing → fresh_data → enhanced → headless
        try:
            data_provider_result = await init_data_provider(
                settings=settings,
                primary_client=ctx.linkedin_client,
                marketing_client=marketing_client,
                fresh_data_client=fresh_data_client,
            )
            ctx.data_provider = data_provider_result
        except Exception as e:
            logger.warning("Data provider initialization failed", error=str(e))

        # Start scheduler if available
        if ctx.scheduler:
            ctx.scheduler.start()

        # Mark as initialized
        ctx.mark_initialized()
        set_context(ctx)

        logger.info(
            "Server initialized successfully",
            official_api=ctx.has_official_client,
            marketing_api=ctx.has_marketing_client,
            fresh_data_api=ctx.has_fresh_data_client,
            unofficial_api=ctx.has_linkedin_client,
            data_provider=ctx.has_data_provider,
            database=ctx.has_database,
            scheduler=ctx.has_scheduler,
            browser=ctx.has_browser,
        )

        yield ctx

    except Exception as e:
        logger.error("Failed to initialize server", error=str(e))
        raise

    finally:
        # Cleanup on shutdown
        await shutdown_services(ctx)
        clear_context()
        logger.info("LinkedIn MCP Server stopped")
