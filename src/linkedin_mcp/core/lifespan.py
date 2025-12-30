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
    from linkedin_api import Linkedin
    from playwright.async_api import Browser, BrowserContext
    from sqlalchemy.ext.asyncio import AsyncEngine

logger = get_logger(__name__)


async def init_linkedin_client(settings: Settings) -> "Linkedin | None":
    """
    Initialize the LinkedIn API client.

    Args:
        settings: Application settings

    Returns:
        Initialized LinkedIn client or None if authentication fails
    """
    try:
        logger.info("Initializing LinkedIn client")

        # Check for existing session cookies
        cookie_path = settings.session_cookie_path
        cookies = None

        if cookie_path.exists():
            import json
            try:
                with cookie_path.open() as f:
                    cookies = json.load(f)
                logger.info("Loaded existing session cookies")
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Failed to load cookies, will authenticate fresh", error=str(e))

        # Initialize client (runs in thread pool since it's sync)
        def create_client() -> Any:
            from linkedin_api import Linkedin as LinkedinClient
            return LinkedinClient(
                settings.linkedin.email,
                settings.linkedin.password.get_secret_value(),
                cookies=cookies,
                refresh_cookies=True,
            )

        client = await asyncio.get_event_loop().run_in_executor(
            None, create_client
        )

        # Save cookies for future sessions
        await save_session_cookies(client, cookie_path)

        logger.info("LinkedIn client initialized successfully")
        return client

    except Exception as e:
        logger.error("Failed to initialize LinkedIn client", error=str(e))
        raise LinkedInAuthError(
            "Failed to authenticate with LinkedIn",
            cause=e,
        ) from e


async def save_session_cookies(client: "Linkedin", cookie_path: Path) -> None:
    """Save session cookies for persistence."""
    import json

    try:
        cookie_path.parent.mkdir(parents=True, exist_ok=True)

        # Extract cookies from client session
        if hasattr(client, "client") and hasattr(client.client, "cookies"):
            cookies = dict(client.client.cookies)
            with cookie_path.open("w") as f:
                json.dump(cookies, f)
            logger.debug("Session cookies saved")
    except Exception as e:
        logger.warning("Failed to save session cookies", error=str(e))


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

    # Save LinkedIn session
    if ctx.linkedin_client:
        logger.debug("Saving LinkedIn session")
        await save_session_cookies(
            ctx.linkedin_client,
            ctx.settings.session_cookie_path,
        )

    logger.info("All services shut down")


@asynccontextmanager
async def lifespan() -> AsyncGenerator[AppContext, None]:
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
        linkedin_task = asyncio.create_task(init_linkedin_client(settings))
        db_task = asyncio.create_task(init_database(settings))
        scheduler_task = asyncio.create_task(init_scheduler(settings))
        browser_task = asyncio.create_task(init_browser(settings))

        # Wait for all initializations
        results = await asyncio.gather(
            linkedin_task,
            db_task,
            scheduler_task,
            browser_task,
            return_exceptions=True,
        )

        # Process results
        linkedin_result, db_result, scheduler_result, browser_result = results

        # Handle LinkedIn client (required)
        if isinstance(linkedin_result, Exception):
            raise linkedin_result
        ctx.linkedin_client = linkedin_result

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

        # Start scheduler if available
        if ctx.scheduler:
            ctx.scheduler.start()

        # Mark as initialized
        ctx.mark_initialized()
        set_context(ctx)

        logger.info(
            "Server initialized successfully",
            linkedin=ctx.has_linkedin_client,
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
