#!/usr/bin/env python3
"""
Test script to verify which LinkedIn MCP tools actually work.
Run this to document accurate capabilities.
"""
import asyncio
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from linkedin_mcp.services.linkedin.client import LinkedInClient


async def test_tool(name: str, func, *args, **kwargs):
    """Test a tool and report result."""
    print(f"\n{'='*60}")
    print(f"Testing: {name}")
    print(f"{'='*60}")
    try:
        result = await func(*args, **kwargs)
        if result:
            print(f"✅ SUCCESS - Returned {type(result).__name__}")
            if isinstance(result, dict):
                print(f"   Keys: {list(result.keys())[:5]}")
            elif isinstance(result, list):
                print(f"   Count: {len(result)}")
                if result and isinstance(result[0], dict):
                    print(f"   Sample keys: {list(result[0].keys())[:5]}")
            return True
        else:
            print(f"⚠️  EMPTY - Returned empty/None")
            return False
    except Exception as e:
        print(f"❌ FAILED - {type(e).__name__}: {e}")
        return False


async def main():
    # Cookie path
    cookie_path = Path(__file__).parent.parent / "data" / "session_cookies.json"

    print("Initializing LinkedIn client...")
    # Email/password can be placeholders when using cookie auth
    client = LinkedInClient(
        email="test@example.com",
        password="placeholder",
        cookie_path=cookie_path,
    )
    await client.initialize()

    results = {}

    # Test 1: Get my profile
    results["get_own_profile"] = await test_tool(
        "get_own_profile()",
        client.get_own_profile
    )

    # Test 2: Get specific profile
    results["get_profile"] = await test_tool(
        "get_profile('williamhgates')",
        client.get_profile,
        "williamhgates"
    )

    # Test 3: Get feed
    results["get_feed"] = await test_tool(
        "get_feed(limit=3)",
        client.get_feed,
        limit=3
    )

    # Test 4: Get profile posts (the problematic one)
    my_profile = await client.get_own_profile()
    my_id = my_profile.get("public_id", "me") if my_profile else "me"
    results["get_profile_posts_own"] = await test_tool(
        f"get_profile_posts('{my_id}')",
        client.get_profile_posts,
        my_id,
        limit=5
    )

    # Test 4b: Get other's profile posts
    results["get_profile_posts_other"] = await test_tool(
        "get_profile_posts('williamhgates')",
        client.get_profile_posts,
        "williamhgates",
        limit=5
    )

    # Test 5: Search people - basic
    results["search_people_basic"] = await test_tool(
        "search_people(keywords='software engineer')",
        client.search_people,
        keywords="software engineer",
        limit=5
    )

    # Test 6: Search people - with title filter
    results["search_people_title"] = await test_tool(
        "search_people(keyword_title='VP Engineering')",
        client.search_people,
        keyword_title="VP Engineering",
        limit=5
    )

    # Test 7: Search people - with region
    results["search_people_region"] = await test_tool(
        "search_people(keywords='engineer', regions=['us:0'])",
        client.search_people,
        keywords="engineer",
        regions=["us:0"],
        limit=5
    )

    # Test 8: Search companies
    results["search_companies"] = await test_tool(
        "search_companies('fintech')",
        client.search_companies,
        keywords="fintech",
        limit=5
    )

    # Test 9: Get connections
    results["get_profile_connections"] = await test_tool(
        "get_profile_connections(limit=5)",
        client.get_profile_connections,
        limit=5
    )

    # Test 10: Get conversations
    results["get_conversations"] = await test_tool(
        "get_conversations()",
        client.get_conversations
    )

    # Test 11: Get pending invitations
    results["get_pending_invitations"] = await test_tool(
        "get_pending_invitations()",
        client.get_pending_invitations
    )

    # Test 12: Get profile contact info
    results["get_profile_contact_info"] = await test_tool(
        "get_profile_contact_info('williamhgates')",
        client.get_profile_contact_info,
        "williamhgates"
    )

    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    working = [k for k, v in results.items() if v]
    broken = [k for k, v in results.items() if not v]

    print(f"\n✅ WORKING ({len(working)}):")
    for t in working:
        print(f"   - {t}")

    print(f"\n❌ BROKEN/EMPTY ({len(broken)}):")
    for t in broken:
        print(f"   - {t}")

    await client.close()


if __name__ == "__main__":
    asyncio.run(main())
