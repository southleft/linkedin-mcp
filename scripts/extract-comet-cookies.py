#!/usr/bin/env python3
"""
One-off cookie extraction for Comet browser — linkedin-mcp's `extract-cookies`
CLI only supports a fixed enum of browsers (chrome, arc, brave, edge, firefox,
opera, opera_gx, vivaldi, chromium, safari, librewolf) and Comet isn't one of
them, nor does the underlying browser_cookie3 library have a Comet class.

Comet IS Chromium-based and uses the identical cookie DB format + AES
encryption scheme as every other Chromium browser — it just has its own
macOS Keychain entry ("Comet Safe Storage", confirmed via `security
dump-keychain`) for the decryption key, which browser_cookie3's generic
`chromium()` helper doesn't know about (it hardcodes "Chromium Safe Storage").

Fix: call browser_cookie3.ChromiumBased directly (the base class every
per-browser wrapper thinly subclasses) with the correct osx_key_service.
This reproduces exactly what cmd_extract_cookies() in
src/linkedin_mcp/cli/auth.py does, substituting the Comet-specific key
service, then stores via the SAME store_unofficial_cookies() function the
real CLI uses — so the result is indistinguishable from a native run.

Run once: /Users/mishaalmurawala/Dev/linkedin-mcp/.venv/bin/python /tmp/extract-comet-linkedin-cookies.py
"""

import sys

sys.path.insert(0, "/Users/mishaalmurawala/Dev/linkedin-mcp/src")

import browser_cookie3

from linkedin_mcp.services.storage.token_storage import CookieData, store_unofficial_cookies

COMET_COOKIE_FILE = "/Users/mishaalmurawala/Library/Application Support/Comet/Default/Cookies"
COMET_KEY_SERVICE = "Comet Safe Storage"
COMET_KEY_USER = "Comet"


def get_comet_cookiejar(domain_name: str = ""):
    return browser_cookie3.ChromiumBased(
        browser="comet",
        cookie_file=COMET_COOKIE_FILE,
        domain_name=domain_name,
        osx_key_service=COMET_KEY_SERVICE,
        osx_key_user=COMET_KEY_USER,
    ).load()


def main() -> int:
    print("\n=== LinkedIn Cookie Extraction (Comet) ===\n")
    print("Extracting cookies from Comet...")

    li_at = None
    jsessionid = None

    for domain in (".linkedin.com", ".www.linkedin.com"):
        try:
            for cookie in get_comet_cookiejar(domain_name=domain):
                if cookie.name == "li_at" and not li_at:
                    li_at = cookie.value
                elif cookie.name == "JSESSIONID" and not jsessionid:
                    jsessionid = cookie.value
        except Exception as e:
            print(f"  (domain {domain} lookup failed: {e})")

    if not li_at or not jsessionid:
        try:
            for cookie in get_comet_cookiejar():
                if "linkedin" in cookie.domain.lower():
                    if cookie.name == "li_at" and not li_at:
                        li_at = cookie.value
                    elif cookie.name == "JSESSIONID" and not jsessionid:
                        jsessionid = cookie.value
        except Exception as e:
            print(f"  (full scan failed: {e})")

    if not li_at:
        print("\n❌ Could not find li_at cookie.")
        print("Make sure you are logged into LinkedIn in Comet:")
        print("   1. Open Comet")
        print("   2. Go to https://www.linkedin.com")
        print("   3. Log in if not already logged in")
        print("   4. Run this script again")
        return 1

    cookie_data = CookieData(
        li_at=li_at,
        jsessionid=jsessionid,
        browser="comet",
    )
    store_unofficial_cookies(cookie_data)

    print("\n✅ Cookies extracted successfully!")
    print("   Browser: Comet")
    print("   Cookies stored securely in system keychain")
    print("\nNote: These cookies typically last 24-48 hours.")
    print("      Re-run this script if you experience auth errors.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
