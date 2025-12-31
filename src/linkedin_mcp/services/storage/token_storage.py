"""
Secure token storage using system keychain.

Uses the `keyring` library to store OAuth tokens and cookies securely in:
- macOS: Keychain
- Windows: Windows Credential Locker
- Linux: Secret Service (GNOME Keyring, KWallet)
"""

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Optional

import keyring
import structlog

logger = structlog.get_logger(__name__)

# Service name for keyring
SERVICE_NAME = "linkedin-mcp"

# Keys for different credential types
OFFICIAL_TOKEN_KEY = "official_oauth_token"
OFFICIAL_METADATA_KEY = "official_oauth_metadata"
UNOFFICIAL_COOKIES_KEY = "unofficial_cookies"
UNOFFICIAL_METADATA_KEY = "unofficial_metadata"


@dataclass
class TokenData:
    """OAuth token data with expiration tracking."""

    access_token: str
    expires_at: datetime
    scopes: list[str]
    token_type: str = "Bearer"
    created_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        if self.created_at is None:
            self.created_at = datetime.now()

    @property
    def is_expired(self) -> bool:
        """Check if token has expired."""
        return datetime.now() >= self.expires_at

    @property
    def expires_soon(self) -> bool:
        """Check if token expires within 7 days."""
        return datetime.now() >= self.expires_at - timedelta(days=7)

    @property
    def days_until_expiry(self) -> int:
        """Get number of days until token expires."""
        delta = self.expires_at - datetime.now()
        return max(0, delta.days)

    @property
    def seconds_until_expiry(self) -> int:
        """Get number of seconds until token expires."""
        delta = self.expires_at - datetime.now()
        return max(0, int(delta.total_seconds()))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "access_token": self.access_token,
            "expires_at": self.expires_at.isoformat(),
            "scopes": self.scopes,
            "token_type": self.token_type,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TokenData":
        """Create from dictionary."""
        return cls(
            access_token=data["access_token"],
            expires_at=datetime.fromisoformat(data["expires_at"]),
            scopes=data["scopes"],
            token_type=data.get("token_type", "Bearer"),
            created_at=datetime.fromisoformat(data["created_at"])
            if data.get("created_at")
            else None,
        )


# ==================== Official OAuth Token Storage ====================


def store_official_token(token_data: TokenData) -> bool:
    """
    Store official OAuth token in system keychain.

    Args:
        token_data: Token data to store

    Returns:
        True if successful, False otherwise
    """
    try:
        # Store token
        keyring.set_password(SERVICE_NAME, OFFICIAL_TOKEN_KEY, token_data.access_token)

        # Store metadata
        metadata = {
            "expires_at": token_data.expires_at.isoformat(),
            "scopes": token_data.scopes,
            "token_type": token_data.token_type,
            "created_at": token_data.created_at.isoformat() if token_data.created_at else None,
        }
        keyring.set_password(SERVICE_NAME, OFFICIAL_METADATA_KEY, json.dumps(metadata))

        logger.info(
            "Stored official OAuth token in keychain",
            expires_in_days=token_data.days_until_expiry,
        )
        return True

    except Exception as e:
        logger.error("Failed to store official token", error=str(e))
        return False


def get_official_token() -> Optional[TokenData]:
    """
    Retrieve official OAuth token from system keychain.

    Returns:
        TokenData if found and valid, None otherwise
    """
    try:
        access_token = keyring.get_password(SERVICE_NAME, OFFICIAL_TOKEN_KEY)
        metadata_str = keyring.get_password(SERVICE_NAME, OFFICIAL_METADATA_KEY)

        if not access_token or not metadata_str:
            logger.debug("No official token found in keychain")
            return None

        metadata = json.loads(metadata_str)

        token_data = TokenData(
            access_token=access_token,
            expires_at=datetime.fromisoformat(metadata["expires_at"]),
            scopes=metadata.get("scopes", []),
            token_type=metadata.get("token_type", "Bearer"),
            created_at=datetime.fromisoformat(metadata["created_at"])
            if metadata.get("created_at")
            else None,
        )

        if token_data.is_expired:
            logger.warning("Official token has expired")
            return None

        if token_data.expires_soon:
            logger.warning(
                "Official token expires soon",
                days_remaining=token_data.days_until_expiry,
            )

        return token_data

    except Exception as e:
        logger.error("Failed to retrieve official token", error=str(e))
        return None


def delete_official_token() -> bool:
    """
    Delete official OAuth token from system keychain.

    Returns:
        True if successful, False otherwise
    """
    try:
        try:
            keyring.delete_password(SERVICE_NAME, OFFICIAL_TOKEN_KEY)
        except keyring.errors.PasswordDeleteError:
            pass

        try:
            keyring.delete_password(SERVICE_NAME, OFFICIAL_METADATA_KEY)
        except keyring.errors.PasswordDeleteError:
            pass

        logger.info("Deleted official OAuth token from keychain")
        return True

    except Exception as e:
        logger.error("Failed to delete official token", error=str(e))
        return False


# ==================== Unofficial Cookie Storage ====================


@dataclass
class CookieData:
    """Cookie data for unofficial API authentication."""

    li_at: str  # Primary authentication cookie
    jsessionid: Optional[str] = None
    extracted_at: Optional[datetime] = None
    browser: Optional[str] = None

    def __post_init__(self) -> None:
        if self.extracted_at is None:
            self.extracted_at = datetime.now()

    @property
    def is_stale(self) -> bool:
        """Check if cookies are older than 24 hours (may need refresh)."""
        if self.extracted_at is None:
            return True
        return datetime.now() >= self.extracted_at + timedelta(hours=24)

    @property
    def hours_since_extraction(self) -> int:
        """Get hours since cookies were extracted."""
        if self.extracted_at is None:
            return 999
        delta = datetime.now() - self.extracted_at
        return int(delta.total_seconds() / 3600)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "li_at": self.li_at,
            "jsessionid": self.jsessionid,
            "extracted_at": self.extracted_at.isoformat() if self.extracted_at else None,
            "browser": self.browser,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CookieData":
        """Create from dictionary."""
        return cls(
            li_at=data["li_at"],
            jsessionid=data.get("jsessionid"),
            extracted_at=datetime.fromisoformat(data["extracted_at"])
            if data.get("extracted_at")
            else None,
            browser=data.get("browser"),
        )


def store_unofficial_cookies(cookie_data: CookieData) -> bool:
    """
    Store unofficial API cookies in system keychain.

    Args:
        cookie_data: Cookie data to store

    Returns:
        True if successful, False otherwise
    """
    try:
        # Store li_at cookie (the main one)
        keyring.set_password(SERVICE_NAME, UNOFFICIAL_COOKIES_KEY, cookie_data.li_at)

        # Store metadata
        metadata = {
            "jsessionid": cookie_data.jsessionid,
            "extracted_at": cookie_data.extracted_at.isoformat()
            if cookie_data.extracted_at
            else None,
            "browser": cookie_data.browser,
        }
        keyring.set_password(SERVICE_NAME, UNOFFICIAL_METADATA_KEY, json.dumps(metadata))

        logger.info(
            "Stored unofficial cookies in keychain",
            browser=cookie_data.browser,
        )
        return True

    except Exception as e:
        logger.error("Failed to store unofficial cookies", error=str(e))
        return False


def get_unofficial_cookies() -> Optional[CookieData]:
    """
    Retrieve unofficial API cookies from system keychain.

    Returns:
        CookieData if found, None otherwise
    """
    try:
        li_at = keyring.get_password(SERVICE_NAME, UNOFFICIAL_COOKIES_KEY)
        metadata_str = keyring.get_password(SERVICE_NAME, UNOFFICIAL_METADATA_KEY)

        if not li_at:
            logger.debug("No unofficial cookies found in keychain")
            return None

        metadata = json.loads(metadata_str) if metadata_str else {}

        cookie_data = CookieData(
            li_at=li_at,
            jsessionid=metadata.get("jsessionid"),
            extracted_at=datetime.fromisoformat(metadata["extracted_at"])
            if metadata.get("extracted_at")
            else None,
            browser=metadata.get("browser"),
        )

        if cookie_data.is_stale:
            logger.warning(
                "Unofficial cookies may be stale",
                hours_old=cookie_data.hours_since_extraction,
            )

        return cookie_data

    except Exception as e:
        logger.error("Failed to retrieve unofficial cookies", error=str(e))
        return None


def delete_unofficial_cookies() -> bool:
    """
    Delete unofficial API cookies from system keychain.

    Returns:
        True if successful, False otherwise
    """
    try:
        try:
            keyring.delete_password(SERVICE_NAME, UNOFFICIAL_COOKIES_KEY)
        except keyring.errors.PasswordDeleteError:
            pass

        try:
            keyring.delete_password(SERVICE_NAME, UNOFFICIAL_METADATA_KEY)
        except keyring.errors.PasswordDeleteError:
            pass

        logger.info("Deleted unofficial cookies from keychain")
        return True

    except Exception as e:
        logger.error("Failed to delete unofficial cookies", error=str(e))
        return False
