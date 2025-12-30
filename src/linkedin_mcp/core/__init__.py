"""Core module for LinkedIn MCP Server."""

from linkedin_mcp.core.context import (
    AppContext,
    clear_context,
    get_context,
    set_context,
)
from linkedin_mcp.core.exceptions import (
    BrowserAutomationError,
    DatabaseError,
    FeatureDisabledError,
    LinkedInAPIError,
    LinkedInAuthError,
    LinkedInMCPError,
    LinkedInMessageError,
    LinkedInPostError,
    LinkedInProfileError,
    LinkedInRateLimitError,
    LinkedInSessionError,
    SchedulerError,
    ValidationError,
)
from linkedin_mcp.core.lifespan import lifespan
from linkedin_mcp.core.logging import (
    LogContext,
    configure_logging,
    get_logger,
    log_api_call,
    log_api_response,
    log_error,
    log_operation,
)

__all__ = [
    # Context
    "AppContext",
    "get_context",
    "set_context",
    "clear_context",
    # Exceptions
    "LinkedInMCPError",
    "LinkedInAuthError",
    "LinkedInRateLimitError",
    "LinkedInAPIError",
    "LinkedInSessionError",
    "LinkedInProfileError",
    "LinkedInPostError",
    "LinkedInMessageError",
    "FeatureDisabledError",
    "BrowserAutomationError",
    "SchedulerError",
    "DatabaseError",
    "ValidationError",
    # Lifespan
    "lifespan",
    # Logging
    "configure_logging",
    "get_logger",
    "LogContext",
    "log_operation",
    "log_api_call",
    "log_api_response",
    "log_error",
]
