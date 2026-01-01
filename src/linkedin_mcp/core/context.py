"""
Application context for dependency injection.

Provides a centralized container for all services and shared state.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from linkedin_api import Linkedin
    from playwright.async_api import Browser, BrowserContext
    from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

    from linkedin_mcp.config.settings import Settings
    from linkedin_mcp.services.linkedin.data_provider import LinkedInDataProvider
    from linkedin_mcp.services.linkedin.official_client import LinkedInOfficialClient


@dataclass
class AppContext:
    """
    Application context containing all shared services and state.

    This dataclass serves as a dependency injection container,
    providing access to all initialized services throughout the application.

    Attributes:
        settings: Application configuration
        linkedin_client: Unofficial LinkedIn API client
        db_engine: SQLAlchemy async engine
        scheduler: APScheduler instance for scheduled posts
        browser: Playwright browser instance
        browser_context: Playwright browser context with persistent state
        metadata: Additional runtime metadata
    """

    # Configuration
    settings: "Settings"

    # LinkedIn API client (tomquirk/linkedin-api) - Unofficial, less reliable
    linkedin_client: "Linkedin | None" = None

    # LinkedIn Official API client (OAuth 2.0) - Official, reliable for basic profile
    official_client: "LinkedInOfficialClient | None" = None

    # LinkedIn Data Provider with automatic fallback (primary → enhanced → headless)
    data_provider: "LinkedInDataProvider | None" = None

    # Database
    db_engine: "AsyncEngine | None" = None

    # Scheduler
    scheduler: "AsyncIOScheduler | None" = None

    # Browser automation
    browser: "Browser | None" = None
    browser_context: "BrowserContext | None" = None

    # Runtime metadata
    metadata: dict[str, Any] = field(default_factory=dict)

    # State flags
    _initialized: bool = field(default=False, repr=False)
    _shutting_down: bool = field(default=False, repr=False)

    @property
    def is_initialized(self) -> bool:
        """Check if context has been fully initialized."""
        return self._initialized

    @property
    def is_shutting_down(self) -> bool:
        """Check if context is in shutdown state."""
        return self._shutting_down

    @property
    def has_linkedin_client(self) -> bool:
        """Check if LinkedIn client (unofficial) is available."""
        return self.linkedin_client is not None

    @property
    def has_official_client(self) -> bool:
        """Check if LinkedIn Official API client is available."""
        return self.official_client is not None and self.official_client.is_authenticated

    @property
    def has_database(self) -> bool:
        """Check if database is available."""
        return self.db_engine is not None

    @property
    def has_scheduler(self) -> bool:
        """Check if scheduler is available and enabled."""
        return (
            self.scheduler is not None
            and self.settings.scheduler.enabled
        )

    @property
    def has_browser(self) -> bool:
        """Check if browser automation is available."""
        return (
            self.browser is not None
            and self.browser_context is not None
            and self.settings.features.browser_fallback
        )

    @property
    def has_data_provider(self) -> bool:
        """Check if data provider with fallback is available."""
        return self.data_provider is not None

    def get_db_session(self) -> "AsyncSession":
        """
        Create a new database session.

        Returns:
            AsyncSession: A new SQLAlchemy async session

        Raises:
            RuntimeError: If database is not initialized
        """
        if self.db_engine is None:
            raise RuntimeError("Database not initialized")

        from sqlalchemy.ext.asyncio import AsyncSession
        from sqlalchemy.orm import sessionmaker

        async_session = sessionmaker(
            self.db_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        return async_session()

    def mark_initialized(self) -> None:
        """Mark the context as fully initialized."""
        self._initialized = True

    def mark_shutting_down(self) -> None:
        """Mark the context as shutting down."""
        self._shutting_down = True

    def set_metadata(self, key: str, value: Any) -> None:
        """Set a metadata value."""
        self.metadata[key] = value

    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Get a metadata value with optional default."""
        return self.metadata.get(key, default)


# Global context instance (set during lifespan)
_app_context: AppContext | None = None


def get_context() -> AppContext:
    """
    Get the current application context.

    Returns:
        AppContext: The current application context

    Raises:
        RuntimeError: If context has not been initialized
    """
    if _app_context is None:
        raise RuntimeError(
            "Application context not initialized. "
            "Ensure the server lifespan has started."
        )
    return _app_context


def set_context(context: AppContext) -> None:
    """
    Set the global application context.

    Args:
        context: The AppContext instance to set as global
    """
    global _app_context
    _app_context = context


def clear_context() -> None:
    """Clear the global application context."""
    global _app_context
    _app_context = None
