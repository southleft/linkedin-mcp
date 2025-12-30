"""
Pydantic Settings for LinkedIn MCP Server.

Provides type-safe configuration with validation and environment variable loading.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class LinkedInSettings(BaseSettings):
    """LinkedIn API credentials and settings."""

    email: str = Field(..., description="LinkedIn account email")
    password: SecretStr = Field(..., description="LinkedIn account password")

    model_config = SettingsConfigDict(env_prefix="LINKEDIN_")


class DatabaseSettings(BaseSettings):
    """Database configuration."""

    url: str = Field(
        default="sqlite+aiosqlite:///./data/linkedin_mcp.db",
        description="SQLAlchemy async database URL",
    )
    echo: bool = Field(default=False, description="Echo SQL statements")
    pool_size: int = Field(default=5, ge=1, le=20)
    max_overflow: int = Field(default=10, ge=0, le=50)

    model_config = SettingsConfigDict(env_prefix="DATABASE_")

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not v.startswith(("sqlite", "postgresql", "mysql")):
            raise ValueError("Invalid database URL scheme")
        return v


class ServerSettings(BaseSettings):
    """MCP Server configuration."""

    name: str = Field(default="LinkedIn Intelligence MCP")
    version: str = Field(default="0.1.0")
    transport: Literal["stdio", "streamable-http", "sse"] = Field(default="stdio")
    host: str = Field(default="127.0.0.1")
    port: int = Field(default=8000, ge=1024, le=65535)

    model_config = SettingsConfigDict(env_prefix="MCP_")


class SchedulerSettings(BaseSettings):
    """APScheduler configuration."""

    enabled: bool = Field(default=True)
    timezone: str = Field(default="UTC")
    max_instances: int = Field(default=3, ge=1, le=10)
    misfire_grace_time: int = Field(default=60, ge=1)
    coalesce: bool = Field(default=True)

    model_config = SettingsConfigDict(env_prefix="SCHEDULER_")


class BrowserSettings(BaseSettings):
    """Playwright browser automation configuration."""

    headless: bool = Field(default=True)
    timeout: int = Field(default=30000, ge=5000, le=120000)
    user_data_dir: Path = Field(default=Path("./data/browser_data"))
    slowmo: int = Field(default=0, ge=0, le=5000)
    viewport_width: int = Field(default=1280)
    viewport_height: int = Field(default=720)

    model_config = SettingsConfigDict(env_prefix="BROWSER_")


class LoggingSettings(BaseSettings):
    """Logging configuration."""

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(default="INFO")
    format: Literal["json", "console"] = Field(default="json")
    file: Path | None = Field(default=None)

    model_config = SettingsConfigDict(env_prefix="LOG_")


class RateLimitSettings(BaseSettings):
    """Rate limiting configuration."""

    requests_per_minute: int = Field(default=30, ge=1, le=100)
    burst: int = Field(default=10, ge=1, le=50)

    model_config = SettingsConfigDict(env_prefix="RATE_LIMIT_")


class FeatureFlags(BaseSettings):
    """Feature flags for optional functionality."""

    browser_fallback: bool = Field(default=True)
    analytics_tracking: bool = Field(default=True)
    post_scheduling: bool = Field(default=True)

    model_config = SettingsConfigDict(env_prefix="FEATURE_")


class Settings(BaseSettings):
    """Root settings aggregating all configuration sections."""

    linkedin: LinkedInSettings = Field(default_factory=LinkedInSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    server: ServerSettings = Field(default_factory=ServerSettings)
    scheduler: SchedulerSettings = Field(default_factory=SchedulerSettings)
    browser: BrowserSettings = Field(default_factory=BrowserSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    rate_limit: RateLimitSettings = Field(default_factory=RateLimitSettings)
    features: FeatureFlags = Field(default_factory=FeatureFlags)

    # Security
    encryption_key: SecretStr | None = Field(default=None)
    session_cookie_path: Path = Field(default=Path("./data/session_cookies.json"))

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
