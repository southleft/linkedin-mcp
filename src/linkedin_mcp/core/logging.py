"""
Structured logging configuration for LinkedIn MCP Server.

Uses structlog for structured, context-aware logging with JSON and console output.
"""

import logging
import sys
from pathlib import Path
from typing import Any

import structlog
from structlog.types import Processor

from linkedin_mcp.config.settings import LoggingSettings


def add_app_context(
    _logger: logging.Logger,
    _method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Add application context to log entries."""
    event_dict["app"] = "linkedin-mcp"
    return event_dict


def configure_logging(settings: LoggingSettings) -> None:
    """
    Configure structured logging based on settings.

    Args:
        settings: LoggingSettings instance with log configuration
    """
    # Determine log level
    log_level = getattr(logging, settings.level.upper(), logging.INFO)

    # Shared processors for all outputs
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="iso"),
        add_app_context,
    ]

    # Configure based on output format
    if settings.format == "json":
        # JSON format for production/machine parsing
        processors: list[Processor] = [
            *shared_processors,
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Console format for development
        processors = [
            *shared_processors,
            structlog.dev.ConsoleRenderer(
                colors=True,
                exception_formatter=structlog.dev.plain_traceback,
            ),
        ]

    # Configure structlog - MUST use stderr for MCP stdio transport
    # stdout is reserved for JSON-RPC protocol messages only
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )

    # Configure standard library logging - MUST use stderr for MCP
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stderr,
        level=log_level,
    )

    # Configure file logging if specified
    if settings.file:
        configure_file_logging(settings.file, log_level)

    # Suppress noisy third-party loggers
    suppress_noisy_loggers()


def configure_file_logging(log_file: Path, level: int) -> None:
    """
    Configure file-based logging.

    Args:
        log_file: Path to log file
        level: Logging level
    """
    # Ensure directory exists
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # Create file handler
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(level)

    # JSON formatter for file output
    file_handler.setFormatter(
        logging.Formatter("%(message)s")
    )

    # Add to root logger
    logging.getLogger().addHandler(file_handler)


def suppress_noisy_loggers() -> None:
    """Suppress overly verbose third-party loggers."""
    noisy_loggers = [
        "httpx",
        "httpcore",
        "urllib3",
        "asyncio",
        "playwright",
        "aiosqlite",
        "sqlalchemy.engine",
        "apscheduler",  # Suppress scheduler startup messages
        "apscheduler.scheduler",
        "apscheduler.executors.default",
    ]

    for logger_name in noisy_loggers:
        logging.getLogger(logger_name).setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> structlog.BoundLogger:
    """
    Get a structured logger instance.

    Args:
        name: Optional logger name (module name recommended)

    Returns:
        BoundLogger: Configured structlog logger
    """
    logger = structlog.get_logger(name)
    return logger


class LogContext:
    """
    Context manager for adding temporary logging context.

    Usage:
        with LogContext(user_id="123", action="post"):
            logger.info("Processing request")
    """

    def __init__(self, **context: Any) -> None:
        self.context = context
        self.token: Any = None

    def __enter__(self) -> "LogContext":
        self.token = structlog.contextvars.bind_contextvars(**self.context)
        return self

    def __exit__(self, *args: Any) -> None:
        structlog.contextvars.unbind_contextvars(*self.context.keys())


def log_operation(
    operation: str,
    **context: Any,
) -> LogContext:
    """
    Create a logging context for an operation.

    Args:
        operation: Name of the operation being performed
        **context: Additional context to include in logs

    Returns:
        LogContext: Context manager for the operation

    Usage:
        with log_operation("fetch_profile", profile_id="123"):
            # All logs within this block include operation context
            logger.info("Starting fetch")
    """
    return LogContext(operation=operation, **context)


# Convenience functions for common log patterns
def log_api_call(
    logger: structlog.BoundLogger,
    method: str,
    endpoint: str,
    **kwargs: Any,
) -> None:
    """Log an API call with standard context."""
    logger.info(
        "api_call",
        method=method,
        endpoint=endpoint,
        **kwargs,
    )


def log_api_response(
    logger: structlog.BoundLogger,
    method: str,
    endpoint: str,
    status_code: int,
    duration_ms: float,
    **kwargs: Any,
) -> None:
    """Log an API response with standard context."""
    log_method = logger.info if status_code < 400 else logger.error
    log_method(
        "api_response",
        method=method,
        endpoint=endpoint,
        status_code=status_code,
        duration_ms=round(duration_ms, 2),
        **kwargs,
    )


def log_error(
    logger: structlog.BoundLogger,
    error: Exception,
    **kwargs: Any,
) -> None:
    """Log an error with full context."""
    logger.error(
        "error",
        error_type=type(error).__name__,
        error_message=str(error),
        **kwargs,
    )
