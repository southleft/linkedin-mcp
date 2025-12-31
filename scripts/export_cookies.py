#!/usr/bin/env python3
"""
Export LinkedIn cookies from Chrome for linkedin-api authentication.

This script extracts the necessary authentication cookies from Chrome
and saves them in the format expected by the linkedin-api library.

Usage:
    python scripts/export_cookies.py

Note: Close Chrome before running this script.
"""

import json
import os
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

# Chrome cookie paths by OS
CHROME_COOKIE_PATHS = {
    "darwin": Path.home() / "Library/Application Support/Google/Chrome/Default/Cookies",
    "linux": Path.home() / ".config/google-chrome/Default/Cookies",
    "win32": Path.home() / "AppData/Local/Google/Chrome/User Data/Default/Network/Cookies",
}

# LinkedIn cookies we need
LINKEDIN_COOKIES = ["li_at", "JSESSIONID", "liap", "li_rm"]

OUTPUT_PATH = Path("./data/session_cookies.json")


def get_chrome_cookies_path() -> Path:
    """Get Chrome cookies database path for current OS."""
    platform = sys.platform
    if platform not in CHROME_COOKIE_PATHS:
        raise RuntimeError(f"Unsupported platform: {platform}")

    path = CHROME_COOKIE_PATHS[platform]
    if not path.exists():
        raise FileNotFoundError(f"Chrome cookies not found at: {path}")

    return path


def extract_linkedin_cookies() -> dict[str, str]:
    """Extract LinkedIn cookies from Chrome."""
    cookies_path = get_chrome_cookies_path()

    # Copy the cookies database (Chrome locks it)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp:
        tmp_path = tmp.name

    try:
        shutil.copy2(cookies_path, tmp_path)

        conn = sqlite3.connect(tmp_path)
        cursor = conn.cursor()

        # Query for LinkedIn cookies
        placeholders = ",".join(["?"] * len(LINKEDIN_COOKIES))
        cursor.execute(
            f"""
            SELECT name, value, encrypted_value
            FROM cookies
            WHERE host_key LIKE '%linkedin.com'
            AND name IN ({placeholders})
            """,
            LINKEDIN_COOKIES,
        )

        cookies = {}
        for name, value, encrypted_value in cursor.fetchall():
            # On macOS, cookies are encrypted - we get the value if it's not
            if value:
                cookies[name] = value
            elif encrypted_value:
                print(f"Warning: Cookie '{name}' is encrypted. See instructions below.")

        conn.close()
        return cookies

    finally:
        os.unlink(tmp_path)


def main() -> None:
    """Main entry point."""
    print("LinkedIn Cookie Exporter")
    print("=" * 50)
    print()

    # Check if Chrome is running
    print("Note: Please close Chrome before running this script.")
    print()

    try:
        cookies = extract_linkedin_cookies()

        if not cookies:
            print("No LinkedIn cookies found!")
            print()
            print("This usually means one of:")
            print("1. You're not logged into LinkedIn in Chrome")
            print("2. Chrome cookies are encrypted (macOS)")
            print()
            print("ALTERNATIVE METHOD (works on macOS):")
            print("-" * 50)
            print("1. Open Chrome DevTools on linkedin.com (F12)")
            print("2. Go to Application > Cookies > linkedin.com")
            print("3. Find the 'li_at' cookie and copy its value")
            print("4. Create a file at: data/session_cookies.json")
            print("5. With content: {\"li_at\": \"YOUR_COOKIE_VALUE\"}")
            return

        # Check for required cookie
        if "li_at" not in cookies:
            print("Warning: 'li_at' cookie not found - this is required!")

        # Save cookies
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with OUTPUT_PATH.open("w") as f:
            json.dump(cookies, f, indent=2)

        print(f"Exported {len(cookies)} cookies:")
        for name in cookies:
            print(f"  - {name}")
        print()
        print(f"Saved to: {OUTPUT_PATH}")
        print()
        print("Now restart Claude Desktop to use the new session.")

    except FileNotFoundError as e:
        print(f"Error: {e}")
        print()
        print("Make sure Chrome is installed and you've logged into LinkedIn.")
    except Exception as e:
        print(f"Error: {e}")
        print()
        print("Try the manual method described above.")


if __name__ == "__main__":
    main()
