"""
LinkedIn MCP Authentication CLI.

Provides commands for:
- OAuth authentication (official API)
- Cookie extraction (unofficial API)
- Status checking
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

from linkedin_mcp.config.settings import get_settings
from linkedin_mcp.core.logging import configure_logging, get_logger
from linkedin_mcp.services.linkedin.official_client import LinkedInOfficialClient
from linkedin_mcp.services.storage.token_storage import (
    CookieData,
    TokenData,
    delete_official_token,
    delete_unofficial_cookies,
    get_official_token,
    get_unofficial_cookies,
    store_official_token,
    store_unofficial_cookies,
)

logger = get_logger(__name__)


def cmd_status(args: argparse.Namespace) -> int:
    """Check authentication status for both APIs."""
    print("\n=== LinkedIn MCP Authentication Status ===\n")

    # Check Official OAuth
    print("📱 Official API (OAuth 2.0):")
    official_token = get_official_token()
    if official_token:
        if official_token.is_expired:
            print("   ❌ Token EXPIRED")
            print("      Run: linkedin-mcp-auth oauth")
        elif official_token.expires_soon:
            print(f"   ⚠️  Token expires in {official_token.days_until_expiry} days")
            print("      Consider re-authenticating soon")
        else:
            print(f"   ✅ Authenticated ({official_token.days_until_expiry} days remaining)")
        print(f"      Scopes: {', '.join(official_token.scopes)}")
    else:
        print("   ❌ Not authenticated")
        print("      Run: linkedin-mcp-auth oauth")

    print()

    # Check Unofficial Cookies
    print("🍪 Unofficial API (Cookies):")
    cookies = get_unofficial_cookies()
    if cookies:
        if cookies.is_stale:
            print(f"   ⚠️  Cookies may be stale ({cookies.hours_since_extraction}h old)")
            print("      Run: linkedin-mcp-auth extract-cookies")
        else:
            print(f"   ✅ Cookies loaded ({cookies.hours_since_extraction}h old)")
        if cookies.browser:
            print(f"      Source: {cookies.browser}")
    else:
        print("   ❌ No cookies stored")
        print("      Run: linkedin-mcp-auth extract-cookies")

    print()
    return 0


def cmd_oauth(args: argparse.Namespace) -> int:
    """Start OAuth authentication flow."""
    settings = get_settings()

    print("\n=== LinkedIn OAuth Authentication ===\n")

    # Check for client credentials
    if not settings.linkedin.client_id or not settings.linkedin.client_secret:
        print("❌ LinkedIn OAuth credentials not configured.")
        print()
        print("Please set the following environment variables:")
        print("   LINKEDIN_CLIENT_ID=your_client_id")
        print("   LINKEDIN_CLIENT_SECRET=your_client_secret")
        print()
        print("Get these from: https://www.linkedin.com/developers/apps")
        return 1

    # Check if already authenticated (and not forcing)
    if not args.force:
        existing_token = get_official_token()
        if existing_token and not existing_token.is_expired:
            print(f"✅ Already authenticated ({existing_token.days_until_expiry} days remaining)")
            print()
            print("Use --force to re-authenticate anyway.")
            return 0

    print("Starting OAuth flow...")
    print("A browser window will open for you to log in to LinkedIn.")
    print()

    # OAuth scopes for LinkedIn API
    # Community Management API enabled January 2026
    # Note: w_member_social includes posts, comments, and reactions per LinkedIn docs
    scopes = [
        # Core OIDC scopes (required)
        "openid",
        "profile",
        "email",
        # Share on LinkedIn - posts, comments, and reactions
        "w_member_social",
    ]

    # Initialize client
    client = LinkedInOfficialClient(
        client_id=settings.linkedin.client_id.get_secret_value()
        if settings.linkedin.client_id
        else "",
        client_secret=settings.linkedin.client_secret.get_secret_value()
        if settings.linkedin.client_secret
        else "",
        redirect_uri=settings.linkedin.redirect_uri,
        scopes=scopes,
    )

    # Start authentication
    if client.authenticate_interactive(timeout=args.timeout):
        # Store token
        token_data = TokenData(
            access_token=client._access_token,
            expires_at=datetime.fromtimestamp(client._token_expires_at),
            scopes=client.scopes,
        )
        store_official_token(token_data)

        print()
        print("✅ Authentication successful!")
        print(f"   Token valid for {token_data.days_until_expiry} days")
        print("   Token stored securely in system keychain")

        # Test the token
        user_info = client.get_user_info()
        if user_info:
            print()
            print(f"   Logged in as: {user_info.get('name', 'Unknown')}")
            print(f"   Email: {user_info.get('email', 'Unknown')}")

        return 0
    else:
        print()
        print("❌ Authentication failed or timed out.")
        print("   Please try again.")
        return 1


def cmd_extract_cookies(args: argparse.Namespace) -> int:
    """Extract cookies from browser."""
    print("\n=== LinkedIn Cookie Extraction ===\n")

    browser = args.browser.lower()

    try:
        import browser_cookie3

        print(f"Extracting cookies from {browser.title()}...")

        # Get cookies based on browser
        if browser == "firefox":
            cookiejar = browser_cookie3.firefox(domain_name=".linkedin.com")
        elif browser == "chrome":
            cookiejar = browser_cookie3.chrome(domain_name=".linkedin.com")
        elif browser == "edge":
            cookiejar = browser_cookie3.edge(domain_name=".linkedin.com")
        elif browser == "opera":
            cookiejar = browser_cookie3.opera(domain_name=".linkedin.com")
        elif browser == "brave":
            cookiejar = browser_cookie3.brave(domain_name=".linkedin.com")
        else:
            print(f"❌ Unsupported browser: {browser}")
            print("   Supported: firefox, chrome, edge, opera, brave")
            return 1

        # Find the li_at cookie
        li_at = None
        jsessionid = None

        for cookie in cookiejar:
            if cookie.name == "li_at":
                li_at = cookie.value
            elif cookie.name == "JSESSIONID":
                jsessionid = cookie.value

        if not li_at:
            print("❌ Could not find li_at cookie.")
            print()
            print("Make sure you are logged into LinkedIn in your browser:")
            print(f"   1. Open {browser.title()}")
            print("   2. Go to https://www.linkedin.com")
            print("   3. Log in if not already logged in")
            print("   4. Run this command again")
            return 1

        # Store cookies
        cookie_data = CookieData(
            li_at=li_at,
            jsessionid=jsessionid,
            browser=browser,
        )
        store_unofficial_cookies(cookie_data)

        print()
        print("✅ Cookies extracted successfully!")
        print(f"   Browser: {browser.title()}")
        print("   Cookies stored securely in system keychain")
        print()
        print("Note: These cookies typically last 24-48 hours.")
        print("      Run this command again if you experience auth errors.")

        return 0

    except Exception as e:
        print(f"❌ Error extracting cookies: {e}")
        print()
        print("Common issues:")
        print("   - Browser is running (try closing it)")
        print("   - Profile path changed")
        print("   - Permission issues")
        return 1


def cmd_logout(args: argparse.Namespace) -> int:
    """Clear stored credentials."""
    print("\n=== LinkedIn MCP Logout ===\n")

    if args.all or args.oauth:
        if delete_official_token():
            print("✅ Deleted official OAuth token")
        else:
            print("⚠️  No official token to delete")

    if args.all or args.cookies:
        if delete_unofficial_cookies():
            print("✅ Deleted unofficial cookies")
        else:
            print("⚠️  No cookies to delete")

    print()
    return 0


def main() -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="linkedin-mcp-auth",
        description="LinkedIn MCP Authentication CLI",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Status command
    status_parser = subparsers.add_parser("status", help="Check authentication status")
    status_parser.set_defaults(func=cmd_status)

    # OAuth command
    oauth_parser = subparsers.add_parser("oauth", help="Authenticate via OAuth")
    oauth_parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Force re-authentication even if already authenticated",
    )
    oauth_parser.add_argument(
        "--timeout",
        "-t",
        type=int,
        default=120,
        help="Timeout in seconds for authentication (default: 120)",
    )
    oauth_parser.set_defaults(func=cmd_oauth)

    # Extract cookies command
    extract_parser = subparsers.add_parser(
        "extract-cookies",
        help="Extract cookies from browser",
    )
    extract_parser.add_argument(
        "--browser",
        "-b",
        default="firefox",
        choices=["firefox", "chrome", "edge", "opera", "brave"],
        help="Browser to extract cookies from (default: firefox)",
    )
    extract_parser.set_defaults(func=cmd_extract_cookies)

    # Logout command
    logout_parser = subparsers.add_parser("logout", help="Clear stored credentials")
    logout_parser.add_argument(
        "--all",
        "-a",
        action="store_true",
        help="Clear all credentials",
    )
    logout_parser.add_argument(
        "--oauth",
        action="store_true",
        help="Clear only OAuth token",
    )
    logout_parser.add_argument(
        "--cookies",
        action="store_true",
        help="Clear only cookies",
    )
    logout_parser.set_defaults(func=cmd_logout)

    # Parse arguments
    args = parser.parse_args()

    # Default to status if no command
    if not args.command:
        args = parser.parse_args(["status"])

    # Configure logging
    settings = get_settings()
    configure_logging(settings.logging)

    # Run command
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\nCancelled.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
