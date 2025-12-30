"""
Custom exceptions for LinkedIn MCP Server.

Provides a hierarchy of exceptions for proper error handling and reporting.
"""

from typing import Any


class LinkedInMCPError(Exception):
    """Base exception for all LinkedIn MCP errors."""

    def __init__(
        self,
        message: str,
        *,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}
        self.cause = cause

    def __str__(self) -> str:
        base = self.message
        if self.details:
            base += f" | Details: {self.details}"
        if self.cause:
            base += f" | Caused by: {self.cause}"
        return base


class LinkedInAuthError(LinkedInMCPError):
    """Authentication-related errors."""

    def __init__(
        self,
        message: str = "LinkedIn authentication failed",
        *,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, details=details, cause=cause)


class LinkedInRateLimitError(LinkedInMCPError):
    """Rate limiting errors from LinkedIn API."""

    def __init__(
        self,
        message: str = "LinkedIn rate limit exceeded",
        *,
        retry_after: int | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        details = details or {}
        if retry_after:
            details["retry_after_seconds"] = retry_after
        super().__init__(message, details=details, cause=cause)
        self.retry_after = retry_after


class LinkedInAPIError(LinkedInMCPError):
    """General API errors from LinkedIn."""

    def __init__(
        self,
        message: str = "LinkedIn API error",
        *,
        status_code: int | None = None,
        endpoint: str | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        details = details or {}
        if status_code:
            details["status_code"] = status_code
        if endpoint:
            details["endpoint"] = endpoint
        super().__init__(message, details=details, cause=cause)
        self.status_code = status_code
        self.endpoint = endpoint


class LinkedInSessionError(LinkedInMCPError):
    """Session management errors."""

    def __init__(
        self,
        message: str = "LinkedIn session error",
        *,
        session_expired: bool = False,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        details = details or {}
        details["session_expired"] = session_expired
        super().__init__(message, details=details, cause=cause)
        self.session_expired = session_expired


class LinkedInProfileError(LinkedInMCPError):
    """Profile-related errors."""

    def __init__(
        self,
        message: str = "LinkedIn profile error",
        *,
        profile_id: str | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        details = details or {}
        if profile_id:
            details["profile_id"] = profile_id
        super().__init__(message, details=details, cause=cause)
        self.profile_id = profile_id


class LinkedInPostError(LinkedInMCPError):
    """Post creation/management errors."""

    def __init__(
        self,
        message: str = "LinkedIn post error",
        *,
        post_id: str | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        details = details or {}
        if post_id:
            details["post_id"] = post_id
        super().__init__(message, details=details, cause=cause)
        self.post_id = post_id


class LinkedInMessageError(LinkedInMCPError):
    """Messaging-related errors."""

    def __init__(
        self,
        message: str = "LinkedIn messaging error",
        *,
        conversation_id: str | None = None,
        recipient_id: str | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        details = details or {}
        if conversation_id:
            details["conversation_id"] = conversation_id
        if recipient_id:
            details["recipient_id"] = recipient_id
        super().__init__(message, details=details, cause=cause)
        self.conversation_id = conversation_id
        self.recipient_id = recipient_id


class FeatureDisabledError(LinkedInMCPError):
    """Feature flag disabled error."""

    def __init__(
        self,
        feature_name: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        message = f"Feature '{feature_name}' is disabled"
        details = details or {}
        details["feature_name"] = feature_name
        super().__init__(message, details=details)
        self.feature_name = feature_name


class BrowserAutomationError(LinkedInMCPError):
    """Browser automation (Playwright) errors."""

    def __init__(
        self,
        message: str = "Browser automation error",
        *,
        selector: str | None = None,
        url: str | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        details = details or {}
        if selector:
            details["selector"] = selector
        if url:
            details["url"] = url
        super().__init__(message, details=details, cause=cause)
        self.selector = selector
        self.url = url


class SchedulerError(LinkedInMCPError):
    """Scheduler-related errors."""

    def __init__(
        self,
        message: str = "Scheduler error",
        *,
        job_id: str | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        details = details or {}
        if job_id:
            details["job_id"] = job_id
        super().__init__(message, details=details, cause=cause)
        self.job_id = job_id


class DatabaseError(LinkedInMCPError):
    """Database-related errors."""

    def __init__(
        self,
        message: str = "Database error",
        *,
        operation: str | None = None,
        table: str | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        details = details or {}
        if operation:
            details["operation"] = operation
        if table:
            details["table"] = table
        super().__init__(message, details=details, cause=cause)
        self.operation = operation
        self.table = table


class ValidationError(LinkedInMCPError):
    """Input validation errors."""

    def __init__(
        self,
        message: str = "Validation error",
        *,
        field: str | None = None,
        value: Any = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        details = details or {}
        if field:
            details["field"] = field
        if value is not None:
            details["value"] = str(value)[:100]  # Truncate for safety
        super().__init__(message, details=details)
        self.field = field
        self.value = value
