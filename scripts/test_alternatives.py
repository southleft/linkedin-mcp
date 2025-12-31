#!/usr/bin/env python3
"""
Test alternative approaches for broken LinkedIn API endpoints.
Captures actual error messages and tries alternative methods.
"""
import asyncio
import json
import sys
import traceback
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from linkedin_api import Linkedin


def test_with_details(name: str, func, *args, **kwargs):
    """Test a function and capture detailed error info."""
    print(f"\n{'='*60}")
    print(f"Testing: {name}")
    print(f"{'='*60}")
    try:
        result = func(*args, **kwargs)
        if result:
            print(f"✅ SUCCESS - Returned {type(result).__name__}")
            if isinstance(result, dict):
                print(f"   Keys: {list(result.keys())[:10]}")
                if not result:
                    print("   ⚠️  Empty dict returned")
            elif isinstance(result, list):
                print(f"   Count: {len(result)}")
                if result and isinstance(result[0], dict):
                    print(f"   Sample keys: {list(result[0].keys())[:5]}")
            return True, result
        else:
            print(f"⚠️  EMPTY - Returned empty/None")
            return False, None
    except Exception as e:
        print(f"❌ FAILED - {type(e).__name__}: {e}")
        print(f"   Traceback: {traceback.format_exc()[-500:]}")
        return False, str(e)


def main():
    # Load cookies and convert to RequestsCookieJar
    from requests.cookies import RequestsCookieJar

    cookie_path = Path(__file__).parent.parent / "data" / "session_cookies.json"
    with open(cookie_path) as f:
        cookie_dict = json.load(f)

    # Convert dict to RequestsCookieJar (as required by linkedin-api)
    cookie_jar = RequestsCookieJar()
    for name, value in cookie_dict.items():
        cookie_jar.set(name, value, domain=".linkedin.com", path="/")

    print(f"Loaded {len(cookie_dict)} cookies, converted to RequestsCookieJar")
    print("Initializing LinkedIn client with cookies...")
    client = Linkedin("", "", cookies=cookie_jar)

    print("\n" + "="*60)
    print("PHASE 1: Understanding what works")
    print("="*60)

    # Test 1: Get own profile (should work)
    success, me_profile = test_with_details(
        "get_user_profile() - /me endpoint",
        client.get_user_profile
    )

    my_public_id = None
    my_urn_id = None
    if success and me_profile:
        my_public_id = me_profile.get("miniProfile", {}).get("publicIdentifier")
        my_urn_id = me_profile.get("miniProfile", {}).get("entityUrn", "").split(":")[-1]
        print(f"   My public_id: {my_public_id}")
        print(f"   My urn_id: {my_urn_id}")

    print("\n" + "="*60)
    print("PHASE 2: Testing profile fetch methods")
    print("="*60)

    # Test 2a: Get profile with public_id (my own)
    if my_public_id:
        success, _ = test_with_details(
            f"get_profile(public_id='{my_public_id}') - own profile via public_id",
            client.get_profile,
            public_id=my_public_id
        )

    # Test 2b: Get profile with urn_id (my own)
    if my_urn_id:
        success, _ = test_with_details(
            f"get_profile(urn_id='{my_urn_id}') - own profile via urn_id",
            client.get_profile,
            urn_id=my_urn_id
        )

    # Test 2c: Get someone else's profile (Bill Gates as test)
    test_with_details(
        "get_profile(public_id='williamhgates') - other user",
        client.get_profile,
        public_id="williamhgates"
    )

    print("\n" + "="*60)
    print("PHASE 3: Testing posts methods")
    print("="*60)

    # Test 3a: get_profile_posts with own urn_id
    if my_urn_id:
        test_with_details(
            f"get_profile_posts(urn_id='{my_urn_id}') - with urn_id directly",
            client.get_profile_posts,
            urn_id=my_urn_id,
            post_count=3
        )

    # Test 3b: get_profile_updates (alternative method)
    if my_public_id:
        test_with_details(
            f"get_profile_updates(public_id='{my_public_id}')",
            client.get_profile_updates,
            public_id=my_public_id,
            max_results=3
        )

    # Test 3c: get_profile_updates with urn_id
    if my_urn_id:
        test_with_details(
            f"get_profile_updates(urn_id='{my_urn_id}')",
            client.get_profile_updates,
            urn_id=my_urn_id,
            max_results=3
        )

    print("\n" + "="*60)
    print("PHASE 4: Testing feed methods")
    print("="*60)

    # Test 4a: get_feed_posts (already works)
    test_with_details(
        "get_feed_posts(limit=3) - home feed",
        client.get_feed_posts,
        limit=3
    )

    print("\n" + "="*60)
    print("PHASE 5: Testing search with geo filters")
    print("="*60)

    # Test 5a: Search with invalid region format
    test_with_details(
        "search_people(keywords='engineer', regions=['us:0']) - invalid format",
        client.search_people,
        keywords="engineer",
        regions=["us:0"],
        limit=3
    )

    # Test 5b: Search with proper geo URN format (103644278 = United States)
    test_with_details(
        "search_people(regions=['103644278']) - US geo URN",
        client.search_people,
        keywords="engineer",
        regions=["103644278"],
        limit=3
    )

    # Test 5c: Search without region (should work)
    test_with_details(
        "search_people(keywords='engineer') - no region filter",
        client.search_people,
        keywords="engineer",
        limit=3
    )

    print("\n" + "="*60)
    print("PHASE 6: Testing connections")
    print("="*60)

    # Test 6a: get_profile_connections requires urn_id
    if my_urn_id:
        test_with_details(
            f"get_profile_connections(urn_id='{my_urn_id}')",
            client.get_profile_connections,
            urn_id=my_urn_id,
            limit=3
        )

    print("\n" + "="*60)
    print("PHASE 7: Direct API endpoint tests")
    print("="*60)

    # Test direct API calls to understand the error
    if my_public_id:
        print(f"\nTesting direct fetch to /identity/profiles/{my_public_id}/profileView")
        try:
            res = client._fetch(f"/identity/profiles/{my_public_id}/profileView")
            print(f"   Status: {res.status_code}")
            data = res.json()
            if "status" in data:
                print(f"   API Status: {data.get('status')}")
                print(f"   Message: {data.get('message', 'N/A')}")
            else:
                print(f"   Success - keys: {list(data.keys())[:5]}")
        except Exception as e:
            print(f"   Error: {e}")

    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)


if __name__ == "__main__":
    main()
