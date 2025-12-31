#!/usr/bin/env python3
"""
Diagnostic script to trace LinkedIn client initialization.
This mimics exactly what happens during MCP server startup.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Set environment variables to match Claude Desktop config
os.environ["LINKEDIN_API_ENABLED"] = "true"
os.environ["LINKEDIN_EMAIL"] = "tpitre@southleft.com"
os.environ["LINKEDIN_PASSWORD"] = "placeholder"


def diagnose():
    """Run diagnostic checks."""
    print("=" * 60)
    print("LinkedIn MCP Server - Initialization Diagnostic")
    print("=" * 60)

    # Step 1: Check settings loading
    print("\n[Step 1] Loading settings...")
    try:
        from linkedin_mcp.config.settings import Settings, get_settings

        # Clear cache to force reload
        get_settings.cache_clear()
        settings = get_settings()

        print(f"  ✓ Settings loaded successfully")
        print(f"  - api_enabled: {settings.linkedin.api_enabled} (type: {type(settings.linkedin.api_enabled).__name__})")
        print(f"  - email: {settings.linkedin.email}")
        print(f"  - password: {'<set>' if settings.linkedin.password else '<not set>'}")
        print(f"  - session_cookie_path: {settings.session_cookie_path}")
        print(f"  - session_cookie_path.absolute(): {settings.session_cookie_path.absolute()}")
        print(f"  - session_cookie_path.exists(): {settings.session_cookie_path.exists()}")
    except Exception as e:
        print(f"  ✗ Failed to load settings: {e}")
        import traceback
        traceback.print_exc()
        return

    # Step 2: Check if API is enabled
    print("\n[Step 2] Checking API enabled status...")
    if not settings.linkedin.api_enabled:
        print(f"  ✗ API is disabled (api_enabled={settings.linkedin.api_enabled})")
        print("  → This is why 'LinkedIn client not initialized' error occurs!")
        return
    print(f"  ✓ API is enabled")

    # Step 3: Check credentials
    print("\n[Step 3] Checking credentials...")
    if not settings.linkedin.email:
        print(f"  ✗ Email not set")
        return
    if not settings.linkedin.password:
        print(f"  ✗ Password not set")
        return
    print(f"  ✓ Credentials present")

    # Step 4: Check cookie file
    print("\n[Step 4] Checking cookie file...")
    cookie_path = settings.session_cookie_path

    # Try both relative and absolute paths
    paths_to_try = [
        cookie_path,
        cookie_path.absolute(),
        Path("/Users/tjpitre/Sites/linkedin-mcp") / cookie_path,
        Path("/Users/tjpitre/Sites/linkedin-mcp/data/session_cookies.json"),
    ]

    found_path = None
    for p in paths_to_try:
        print(f"  - Trying: {p}")
        if p.exists():
            print(f"    ✓ EXISTS")
            found_path = p
            break
        else:
            print(f"    ✗ not found")

    if not found_path:
        print(f"  ✗ Cookie file not found at any location!")
        return

    # Step 5: Read and parse cookies
    print(f"\n[Step 5] Reading cookies from {found_path}...")
    try:
        content = found_path.read_text()
        cookie_dict = json.loads(content)
        print(f"  ✓ Loaded {len(cookie_dict)} cookies")
        print(f"  - Keys: {list(cookie_dict.keys())}")

        # Check required cookies
        required = ["li_at", "JSESSIONID"]
        for req in required:
            if req in cookie_dict:
                value = cookie_dict[req]
                print(f"  - {req}: {value[:30]}... ({len(value)} chars)")
            else:
                print(f"  ✗ Missing required cookie: {req}")
                return
    except Exception as e:
        print(f"  ✗ Failed to read cookies: {e}")
        return

    # Step 6: Create RequestsCookieJar
    print("\n[Step 6] Creating RequestsCookieJar...")
    try:
        from requests.cookies import RequestsCookieJar

        cookie_jar = RequestsCookieJar()
        for name, value in cookie_dict.items():
            cookie_jar.set(name, value, domain=".linkedin.com", path="/")

        print(f"  ✓ Created RequestsCookieJar with {len(cookie_jar)} cookies")
        for cookie in cookie_jar:
            print(f"    - {cookie.name}: {cookie.value[:30]}... (domain={cookie.domain})")
    except Exception as e:
        print(f"  ✗ Failed to create cookie jar: {e}")
        import traceback
        traceback.print_exc()
        return

    # Step 7: Test linkedin-api initialization
    print("\n[Step 7] Testing linkedin-api initialization...")
    print("  ⚠️  This will attempt to create a Linkedin client")
    print("  ⚠️  If cookies are valid, it should NOT make any HTTP requests")

    try:
        from linkedin_api import Linkedin

        print("  - Importing Linkedin class...")
        print(f"  - Creating client with cookies={len(cookie_jar)} items")
        print(f"  - email={settings.linkedin.email}")
        print(f"  - password=<placeholder>")
        print(f"  - refresh_cookies=True")

        # This is the actual test
        client = Linkedin(
            settings.linkedin.email,
            settings.linkedin.password.get_secret_value(),
            cookies=cookie_jar,
            refresh_cookies=True,
        )

        print(f"  ✓ Linkedin client created successfully!")
        print(f"  - Client type: {type(client)}")
        print(f"  - Has client.client: {hasattr(client, 'client')}")

        if hasattr(client, 'client'):
            inner_client = client.client
            print(f"  - Inner client type: {type(inner_client)}")
            if hasattr(inner_client, 'cookies'):
                print(f"  - Inner client cookies: {len(inner_client.cookies)} cookies")

    except Exception as e:
        print(f"  ✗ Failed to create Linkedin client: {e}")
        import traceback
        traceback.print_exc()

        error_str = str(e).lower()
        if "challenge" in error_str:
            print("\n  → CHALLENGE error indicates cookies were NOT used!")
            print("  → linkedin-api fell back to username/password auth")
            print("  → This means the cookies parameter was None or empty")
        return

    print("\n" + "=" * 60)
    print("DIAGNOSIS COMPLETE - All checks passed!")
    print("=" * 60)
    print("\nIf you're still seeing 'LinkedIn client not initialized',")
    print("the issue may be in how the MCP server runs vs this script.")


if __name__ == "__main__":
    diagnose()
