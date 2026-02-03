"""
LinkedIn Intelligence MCP Server.

Main FastMCP server definition with all tools, resources, and prompts.
"""

from fastmcp import FastMCP

from linkedin_mcp.core.lifespan import lifespan

# Create FastMCP server instance with lifespan for proper initialization
mcp = FastMCP(
    name="LinkedIn Intelligence MCP",
    instructions="AI-powered LinkedIn analytics, content creation, and engagement automation.",
    version="0.1.0",
    lifespan=lifespan,
)


# =============================================================================
# Diagnostic Tools
# =============================================================================


@mcp.tool()
async def debug_context() -> dict:
    """
    Debug tool to check the internal state of the MCP server.

    Returns information about:
    - Whether LinkedIn client is initialized
    - Settings configuration
    - Cookie file status
    - Initialization errors
    """
    import os
    from pathlib import Path

    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.config.settings import get_settings

    try:
        ctx = get_context()
        settings = get_settings()

        # Check cookie file
        cookie_path = settings.session_cookie_path
        cookie_exists = cookie_path.exists()
        cookie_content = None
        if cookie_exists:
            try:
                import json
                cookie_content = list(json.loads(cookie_path.read_text()).keys())
            except Exception as e:
                cookie_content = f"Error reading: {e}"

        # Get official client status if available
        official_status = None
        if ctx.official_client:
            official_status = ctx.official_client.debug_context()

        return {
            "success": True,
            "context": {
                "is_initialized": ctx.is_initialized,
                "has_official_client": ctx.has_official_client,
                "has_linkedin_client": ctx.has_linkedin_client,
                "has_marketing_client": ctx.has_marketing_client,
                "has_fresh_data_client": ctx.has_fresh_data_client,
                "has_pnd_client": ctx.has_pnd_client,
                "has_data_provider": ctx.has_data_provider,
                "has_database": ctx.has_database,
                "has_scheduler": ctx.has_scheduler,
                "has_browser": ctx.has_browser,
                "linkedin_client_type": type(ctx.linkedin_client).__name__ if ctx.linkedin_client else None,
            },
            "official_api": official_status,
            "data_provider": {
                "initialized": ctx.has_data_provider,
                "pnd_client": ctx.has_pnd_client,
                "marketing_client": ctx.has_marketing_client,
                "fresh_data_client": ctx.has_fresh_data_client,
            },
            "settings": {
                "api_enabled": settings.linkedin.api_enabled,
                "email": settings.linkedin.email,
                "password_set": settings.linkedin.password is not None,
                "session_cookie_path": str(settings.session_cookie_path),
                "session_cookie_path_absolute": str(settings.session_cookie_path.absolute()),
                "rapidapi_key_set": settings.third_party.rapidapi_key is not None,
            },
            "cookie_file": {
                "exists": cookie_exists,
                "keys": cookie_content,
            },
            "environment": {
                "LINKEDIN_API_ENABLED": os.environ.get("LINKEDIN_API_ENABLED"),
                "LINKEDIN_EMAIL": os.environ.get("LINKEDIN_EMAIL"),
                "LINKEDIN_PASSWORD": "***" if os.environ.get("LINKEDIN_PASSWORD") else None,
                "THIRDPARTY_RAPIDAPI_KEY": "***" if os.environ.get("THIRDPARTY_RAPIDAPI_KEY") else None,
                "CWD": os.getcwd(),
            },
        }
    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
        }


# =============================================================================
# Profile Tools
# =============================================================================


@mcp.tool()
async def get_my_profile() -> dict:
    """
    Get the authenticated user's LinkedIn profile.

    Returns profile data including:
    - Basic info (name, email, picture)
    - LinkedIn member ID

    Uses the Official LinkedIn API (OAuth 2.0) when available for reliable results.
    Falls back to unofficial API if official client is not configured.
    """
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger

    logger = get_logger(__name__)
    ctx = get_context()

    result = {
        "success": True,
        "profile": {},
        "source": "official_api",
        "authentication": {
            "method": "OAuth 2.0",
            "scopes": ["openid", "profile", "email", "w_member_social"],
        },
    }

    # Get Official API data first (proves OAuth authentication)
    official_profile = None
    if ctx.has_official_client:
        try:
            official_profile = ctx.official_client.get_my_profile()
            if official_profile:
                result["profile"] = {
                    "id": official_profile.get("id"),
                    "first_name": official_profile.get("first_name"),
                    "last_name": official_profile.get("last_name"),
                    "name": official_profile.get("name"),
                    "email": official_profile.get("email"),
                    "email_verified": official_profile.get("email_verified"),
                    "picture_url": official_profile.get("picture_url"),
                }
        except Exception as e:
            logger.warning("Official API failed", error=str(e))

    # Try to enrich with unofficial API data for more details
    if ctx.linkedin_client:
        try:
            unofficial_profile = await ctx.linkedin_client.get_own_profile()
            if unofficial_profile:
                # Extract public_id from unofficial profile
                public_id = (
                    unofficial_profile.get("public_id")
                    or unofficial_profile.get("publicIdentifier")
                    or unofficial_profile.get("miniProfile", {}).get("publicIdentifier")
                )

                # Add enriched data
                result["profile"]["public_id"] = public_id
                result["profile"]["headline"] = (
                    unofficial_profile.get("headline")
                    or unofficial_profile.get("miniProfile", {}).get("occupation")
                )
                result["profile"]["location"] = unofficial_profile.get("locationName") or unofficial_profile.get("geoLocationName")
                result["profile"]["industry"] = unofficial_profile.get("industryName")
                result["profile"]["connections"] = unofficial_profile.get("connections") or unofficial_profile.get("connectionsCount")
                result["profile"]["profile_url"] = f"https://www.linkedin.com/in/{public_id}" if public_id else None

                # Add experience summary
                experience = unofficial_profile.get("experience", [])
                if experience and len(experience) > 0:
                    current_role = experience[0]
                    result["profile"]["current_position"] = {
                        "title": current_role.get("title"),
                        "company": current_role.get("companyName"),
                        "start_date": current_role.get("timePeriod", {}).get("startDate"),
                    }

                result["enriched_from"] = "unofficial_api"
        except Exception as e:
            logger.debug("Could not enrich profile with unofficial API", error=str(e))

    if not result["profile"]:
        return {"error": "No LinkedIn client available. Configure OAuth token or session cookies."}

    return result


@mcp.tool()
async def get_profile(
    profile_id: str,
    use_cache: bool = True,
    include_activity: bool = True,
    include_network: bool = True,
    include_badges: bool = True,
) -> dict:
    """
    Get comprehensive LinkedIn profile data with multi-source enrichment.

    Uses the Profile Enrichment Engine to aggregate data from multiple endpoints
    in parallel, providing the most complete profile information available.

    Args:
        profile_id: LinkedIn public ID (e.g., "johndoe") or URN
        use_cache: Whether to use cached data if available (default: True)
        include_activity: Include recent activity/posts (default: True)
        include_network: Include network stats like connections/followers (default: True)
        include_badges: Include member badges like Premium status (default: True)

    Returns comprehensive profile data including:
    - Basic info (name, headline, location, photo)
    - Contact information (if available)
    - Skills and endorsements
    - Network information (connections, followers, distance)
    - Member badges (Premium, Creator, etc.)
    - Recent activity summary
    - Enrichment metadata showing data sources used
    """
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger
    from linkedin_mcp.services.browser import get_browser_automation
    from linkedin_mcp.services.cache import CacheService, get_cache
    from linkedin_mcp.services.profile import ProfileEnrichmentEngine

    logger = get_logger(__name__)
    ctx = get_context()
    cache = get_cache()
    browser = get_browser_automation()

    # Check if ANY data source is available
    # Fresh Data API is the most reliable (paid RapidAPI)
    # linkedin_client is secondary (has bot detection issues)
    # browser is tertiary (reliable but slow)
    has_fresh_data = ctx.fresh_data_client is not None
    has_linkedin_client = ctx.linkedin_client is not None
    has_browser = browser and browser.is_available

    if not has_fresh_data and not has_linkedin_client and not has_browser:
        return {
            "error": "No data sources available",
            "reason": "Neither Fresh Data API, LinkedIn session, nor browser automation is configured.",
            "fix_options": [
                "Set THIRDPARTY_RAPIDAPI_KEY for reliable Fresh Data API access (recommended)",
                "Run: linkedin-mcp-auth extract-cookies --browser chrome",
                "Install browser: playwright install chromium",
            ],
            "note": (
                "The Fresh Data API (RapidAPI) is the most reliable source. "
                "Get your API key at: https://rapidapi.com/freshdata-freshdata-default/api/web-scraping-api2"
            ),
        }

    # Create cache key that includes enrichment options
    cache_key = cache.make_key(
        "enriched_profile",
        profile_id,
        f"activity={include_activity}",
        f"network={include_network}",
        f"badges={include_badges}",
    )

    try:
        # Check cache first
        if use_cache:
            cached_data = await cache.get(cache_key)
            if cached_data:
                logger.debug("Returning cached enriched profile", profile_id=profile_id)
                return {"success": True, "profile": cached_data, "cached": True}

        # Use Profile Enrichment Engine for comprehensive data
        # Pass all available sources - engine handles None gracefully
        # Priority: PND API (PRIMARY, 55 endpoints) → Fresh Data (FALLBACK) → Browser → Primary
        engine = ProfileEnrichmentEngine(
            ctx.linkedin_client,  # Can be None - engine handles it
            browser,
            fresh_data_client=ctx.fresh_data_client,  # FALLBACK
            pnd_client=ctx.pnd_client,  # PRIMARY (55 endpoints)
        )
        enriched_profile = await engine.get_enriched_profile(
            public_id=profile_id,
            include_activity=include_activity,
            include_network=include_network,
            include_badges=include_badges,
        )

        # Cache the enriched result
        await cache.set(cache_key, enriched_profile, CacheService.TTL_PROFILE)

        # Check if we got meaningful data
        sources_successful = enriched_profile.get("_enrichment", {}).get("sources_successful", [])
        has_data = (
            enriched_profile.get("firstName")
            or enriched_profile.get("lastName")
            or enriched_profile.get("headline")
            or enriched_profile.get("summary")
            or enriched_profile.get("currentCompany")
            or len(sources_successful) > 1
        )

        if has_data:
            return {
                "success": True,
                "profile": enriched_profile,
                "cached": False,
            }
        else:
            # Provide guidance for limited data scenarios
            suggestions = []
            if not has_fresh_data:
                suggestions.append(
                    "Subscribe to Fresh Data API for reliable profile data: "
                    "https://rapidapi.com/freshdata-freshdata-default/api/web-scraping-api2"
                )
            if not has_linkedin_client:
                suggestions.append(
                    "Re-authenticate: Run 'linkedin-mcp-auth extract-cookies --browser chrome'"
                )
            if not has_browser:
                suggestions.append(
                    "Install Playwright: Run 'playwright install chromium' for browser fallback"
                )

            return {
                "success": True,
                "profile": enriched_profile,
                "cached": False,
                "data_limited": True,
                "reason": (
                    "Profile data is limited. LinkedIn's bot detection may have blocked some sources. "
                    "Fresh Data API (RapidAPI) is the most reliable source for profile data."
                ),
                "what_worked": sources_successful,
                "profile_url": f"https://www.linkedin.com/in/{profile_id}/",
                "suggestions": suggestions,
            }

    except Exception as e:
        logger.error(
            "Profile enrichment failed",
            error=str(e),
            profile_id=profile_id,
        )
        # Check for common error patterns
        error_str = str(e).lower()
        if "redirect" in error_str or "302" in error_str:
            reason = "LinkedIn session expired or was invalidated by LinkedIn's security systems."
            fix = "Run: linkedin-mcp-auth extract-cookies --browser chrome"
        elif "timeout" in error_str:
            reason = "LinkedIn request timed out. Their servers may be slow or blocking requests."
            fix = "Try again in a few minutes, or refresh cookies."
        elif "not subscribed" in error_str or "403" in error_str:
            reason = "Fresh Data API subscription issue."
            fix = "Verify your RapidAPI subscription at: https://rapidapi.com/freshdata-freshdata-default/api/web-scraping-api2"
        else:
            reason = "Unexpected error occurred during profile fetch."
            fix = "Check logs for details and try refreshing cookies."

        return {
            "error": str(e),
            "reason": reason,
            "fix": fix,
            "profile_url": f"https://www.linkedin.com/in/{profile_id}/",
        }


@mcp.tool()
async def get_profile_contact_info(profile_id: str) -> dict:
    """
    Get contact information for a LinkedIn profile.

    Args:
        profile_id: LinkedIn public ID

    Returns contact info including email, phone, websites, and social profiles.
    """
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger

    logger = get_logger(__name__)
    ctx = get_context()

    if not ctx.linkedin_client:
        return {"error": "LinkedIn client not initialized"}

    try:
        contact_info = await ctx.linkedin_client.get_profile_contact_info(profile_id)
        return {"success": True, "contact_info": contact_info}
    except Exception as e:
        logger.error("Failed to fetch contact info", error=str(e), profile_id=profile_id)
        return {"error": str(e)}


@mcp.tool()
async def get_profile_skills(profile_id: str) -> dict:
    """
    Get skills and endorsements for a LinkedIn profile.

    Args:
        profile_id: LinkedIn public ID

    Returns skills categorized by endorsement count with top endorsers.
    """
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger
    from linkedin_mcp.services.cache import CacheService, get_cache

    logger = get_logger(__name__)
    ctx = get_context()
    cache = get_cache()

    if not ctx.linkedin_client:
        return {"error": "LinkedIn client not initialized"}

    cache_key = cache.make_key("skills", profile_id)

    try:
        # Check cache first
        cached_data = await cache.get(cache_key)
        if cached_data:
            return {"success": True, "skills": cached_data, "cached": True}

        profile = await ctx.linkedin_client.get_profile(profile_id)
        skills = profile.get("skills", [])

        # Extract and categorize skills
        skill_data = []
        for skill in skills:
            skill_data.append({
                "name": skill.get("name", ""),
                "endorsement_count": skill.get("endorsementCount", 0),
            })

        # Sort by endorsement count
        skill_data.sort(key=lambda x: x["endorsement_count"], reverse=True)

        await cache.set(cache_key, skill_data, CacheService.TTL_PROFILE)

        return {
            "success": True,
            "skills": skill_data,
            "total_skills": len(skill_data),
            "cached": False,
        }
    except Exception as e:
        logger.error("Failed to fetch skills", error=str(e), profile_id=profile_id)
        return {"error": str(e)}


# =============================================================================
# Professional Network Data API - Unique Features (55 endpoints)
# =============================================================================


@mcp.tool()
async def get_profile_interests(profile_id: str) -> dict:
    """
    Get profile interests including influencers, companies, groups, and topics.

    This data is unique to the Professional Network Data API and provides
    insights into what/who a person follows on LinkedIn.

    Args:
        profile_id: LinkedIn public ID (e.g., "johndoe")

    Returns:
        Profile interests organized by category (influencers, companies, groups, topics)
    """
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger
    from linkedin_mcp.services.cache import CacheService, get_cache

    logger = get_logger(__name__)
    ctx = get_context()
    cache = get_cache()

    if not ctx.pnd_client:
        return {"error": "Professional Network Data API not configured. Set THIRDPARTY_RAPIDAPI_KEY."}

    cache_key = cache.make_key("interests", profile_id)

    try:
        cached_data = await cache.get(cache_key)
        if cached_data:
            return {"success": True, "interests": cached_data, "cached": True}

        interests = await ctx.pnd_client.get_profile_interests(public_id=profile_id)

        if interests.get("error"):
            return {"error": interests.get("error")}

        await cache.set(cache_key, interests, CacheService.TTL_PROFILE)

        return {
            "success": True,
            "profile_id": profile_id,
            "interests": interests,
            "cached": False,
        }
    except Exception as e:
        logger.error("Failed to fetch profile interests", error=str(e), profile_id=profile_id)
        return {"error": str(e)}


@mcp.tool()
async def get_similar_profiles(profile_id: str, limit: int = 10) -> dict:
    """
    Get profiles similar to a given profile.

    Uses the Professional Network Data API to find similar profiles based on
    industry, role, skills, and other factors.

    Args:
        profile_id: LinkedIn public ID (e.g., "johndoe")
        limit: Maximum number of similar profiles to return (default: 10)

    Returns:
        List of similar profiles with relevance scoring
    """
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger
    from linkedin_mcp.services.cache import CacheService, get_cache

    logger = get_logger(__name__)
    ctx = get_context()
    cache = get_cache()

    if not ctx.pnd_client:
        return {"error": "Professional Network Data API not configured. Set THIRDPARTY_RAPIDAPI_KEY."}

    cache_key = cache.make_key("similar", profile_id, str(limit))

    try:
        cached_data = await cache.get(cache_key)
        if cached_data:
            return {"success": True, "similar_profiles": cached_data, "cached": True}

        similar = await ctx.pnd_client.get_similar_profiles(public_id=profile_id, limit=limit)

        # Handle both list and dict responses from client
        if isinstance(similar, list):
            profiles = similar
        elif isinstance(similar, dict):
            if similar.get("error"):
                return {"error": similar.get("error")}
            profiles = similar.get("data", similar.get("profiles", []))
        else:
            profiles = []
        await cache.set(cache_key, profiles, CacheService.TTL_PROFILE)

        return {
            "success": True,
            "profile_id": profile_id,
            "similar_profiles": profiles,
            "count": len(profiles),
            "cached": False,
        }
    except Exception as e:
        logger.error("Failed to fetch similar profiles", error=str(e), profile_id=profile_id)
        return {"error": str(e)}


@mcp.tool()
async def get_profile_articles(profile_id: str, limit: int = 20) -> dict:
    """
    Get articles written by a LinkedIn profile.

    Uses the Professional Network Data API to fetch articles (long-form content)
    published by the specified profile.

    Args:
        profile_id: LinkedIn public ID (e.g., "johndoe")
        limit: Maximum number of articles to return (default: 20)

    Returns:
        List of articles with title, content preview, and engagement metrics
    """
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger
    from linkedin_mcp.services.cache import CacheService, get_cache

    logger = get_logger(__name__)
    ctx = get_context()
    cache = get_cache()

    if not ctx.pnd_client:
        return {"error": "Professional Network Data API not configured. Set THIRDPARTY_RAPIDAPI_KEY."}

    cache_key = cache.make_key("articles", profile_id, str(limit))

    try:
        cached_data = await cache.get(cache_key)
        if cached_data:
            return {"success": True, "articles": cached_data, "cached": True}

        articles = await ctx.pnd_client.get_profile_articles(public_id=profile_id, limit=limit)

        # Handle both list and dict responses from client
        if isinstance(articles, list):
            article_list = articles
        elif isinstance(articles, dict):
            if articles.get("error"):
                return {"error": articles.get("error")}
            article_list = articles.get("data", articles.get("articles", []))
        else:
            article_list = []
        await cache.set(cache_key, article_list, CacheService.TTL_ARTICLES)

        return {
            "success": True,
            "profile_id": profile_id,
            "articles": article_list,
            "count": len(article_list),
            "cached": False,
        }
    except Exception as e:
        logger.error("Failed to fetch profile articles", error=str(e), profile_id=profile_id)
        return {"error": str(e)}


@mcp.tool()
async def get_article(article_url: str) -> dict:
    """
    Get the full content of a LinkedIn article.

    Uses the Professional Network Data API to fetch the complete article
    content, author information, and engagement metrics.

    Args:
        article_url: Full URL of the LinkedIn article

    Returns:
        Article content with title, body, author info, and engagement data
    """
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger
    from linkedin_mcp.services.cache import CacheService, get_cache

    logger = get_logger(__name__)
    ctx = get_context()
    cache = get_cache()

    if not ctx.pnd_client:
        return {"error": "Professional Network Data API not configured. Set THIRDPARTY_RAPIDAPI_KEY."}

    # Create a cache key from the URL
    import hashlib
    url_hash = hashlib.md5(article_url.encode()).hexdigest()[:12]
    cache_key = cache.make_key("article", url_hash)

    try:
        cached_data = await cache.get(cache_key)
        if cached_data:
            return {"success": True, "article": cached_data, "cached": True}

        article = await ctx.pnd_client.get_article(article_url=article_url)

        if article.get("error"):
            return {"error": article.get("error")}

        await cache.set(cache_key, article, CacheService.TTL_PROFILE)

        return {
            "success": True,
            "article": article,
            "cached": False,
        }
    except Exception as e:
        logger.error("Failed to fetch article", error=str(e), article_url=article_url)
        return {"error": str(e)}


@mcp.tool()
async def get_company_by_domain(domain: str) -> dict:
    """
    Get company information by website domain.

    Uses the Professional Network Data API to look up a company by its
    website domain (e.g., "anthropic.com" → Anthropic).

    Args:
        domain: Company website domain (e.g., "anthropic.com")

    Returns:
        Company information including name, industry, size, and LinkedIn URL
    """
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger
    from linkedin_mcp.services.cache import CacheService, get_cache

    logger = get_logger(__name__)
    ctx = get_context()
    cache = get_cache()

    if not ctx.pnd_client:
        return {"error": "Professional Network Data API not configured. Set THIRDPARTY_RAPIDAPI_KEY."}

    cache_key = cache.make_key("company_domain", domain)

    try:
        cached_data = await cache.get(cache_key)
        if cached_data:
            return {"success": True, "company": cached_data, "cached": True}

        company = await ctx.pnd_client.get_company_by_domain(domain=domain)

        # Handle None or dict responses from client
        if company is None:
            return {"error": f"No company found for domain: {domain}"}
        if isinstance(company, dict) and company.get("error"):
            return {"error": company.get("error")}

        await cache.set(cache_key, company, CacheService.TTL_COMPANY)

        return {
            "success": True,
            "domain": domain,
            "company": company,
            "cached": False,
        }
    except Exception as e:
        logger.error("Failed to fetch company by domain", error=str(e), domain=domain)
        return {"error": str(e)}


@mcp.tool()
async def get_network_stats() -> dict:
    """
    Get statistics about the authenticated user's LinkedIn network.

    Returns network size, growth indicators, and connection insights.
    """
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger
    from linkedin_mcp.services.cache import CacheService, get_cache

    logger = get_logger(__name__)
    ctx = get_context()
    cache = get_cache()

    if not ctx.linkedin_client:
        return {"error": "LinkedIn client not initialized"}

    cache_key = "network:stats"

    try:
        cached_data = await cache.get(cache_key)
        if cached_data:
            return {"success": True, "stats": cached_data, "cached": True}

        # Fetch connections
        connections = await ctx.linkedin_client.get_profile_connections(limit=500)

        # Analyze industries
        industries: dict[str, int] = {}
        locations: dict[str, int] = {}
        companies: dict[str, int] = {}

        for conn in connections:
            industry = conn.get("industry", "Unknown")
            industries[industry] = industries.get(industry, 0) + 1

            location = conn.get("locationName", "Unknown")
            locations[location] = locations.get(location, 0) + 1

            company = conn.get("companyName", "Unknown")
            if company != "Unknown":
                companies[company] = companies.get(company, 0) + 1

        # Sort and get top entries
        top_industries = sorted(industries.items(), key=lambda x: x[1], reverse=True)[:10]
        top_locations = sorted(locations.items(), key=lambda x: x[1], reverse=True)[:10]
        top_companies = sorted(companies.items(), key=lambda x: x[1], reverse=True)[:10]

        stats = {
            "total_connections": len(connections),
            "top_industries": dict(top_industries),
            "top_locations": dict(top_locations),
            "top_companies": dict(top_companies),
        }

        await cache.set(cache_key, stats, CacheService.TTL_CONNECTIONS)

        return {"success": True, "stats": stats, "cached": False}
    except Exception as e:
        logger.error("Failed to fetch network stats", error=str(e))
        return {"error": str(e)}


@mcp.tool()
async def batch_get_profiles(profile_ids: str) -> dict:
    """
    Get multiple LinkedIn profiles efficiently.

    Args:
        profile_ids: Comma-separated list of profile public IDs (max 10)

    Returns profiles with basic info and success/failure status for each.
    """
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger
    from linkedin_mcp.services.cache import CacheService, get_cache

    logger = get_logger(__name__)
    ctx = get_context()
    cache = get_cache()

    if not ctx.linkedin_client:
        return {"error": "LinkedIn client not initialized"}

    # Parse and validate IDs
    ids = [p.strip() for p in profile_ids.split(",") if p.strip()]
    if not ids:
        return {"error": "No profile IDs provided"}

    if len(ids) > 10:
        return {"error": "Maximum 10 profiles per batch request"}

    results = []
    errors = []

    for profile_id in ids:
        cache_key = cache.make_key("profile", profile_id)

        try:
            # Check cache
            cached = await cache.get(cache_key)
            if cached:
                results.append({"profile_id": profile_id, "profile": cached, "cached": True})
                continue

            # Fetch from API
            profile = await ctx.linkedin_client.get_profile(profile_id)
            await cache.set(cache_key, profile, CacheService.TTL_PROFILE)
            results.append({"profile_id": profile_id, "profile": profile, "cached": False})

        except Exception as e:
            logger.warning("Failed to fetch profile in batch", profile_id=profile_id, error=str(e))
            errors.append({"profile_id": profile_id, "error": str(e)})

    return {
        "success": True,
        "profiles": results,
        "errors": errors,
        "total_requested": len(ids),
        "total_fetched": len(results),
        "total_errors": len(errors),
    }


@mcp.tool()
async def get_cache_stats() -> dict:
    """
    Get cache statistics and performance metrics.

    Returns cache size, hit rate, and memory usage.
    """
    from linkedin_mcp.services.cache import get_cache

    cache = get_cache()
    return {"success": True, "cache": cache.stats}


# =============================================================================
# Feed & Posts Tools
# =============================================================================


@mcp.tool()
async def get_feed(limit: int = 10, use_cache: bool = True) -> dict:
    """
    Get the authenticated user's LinkedIn feed.

    Args:
        limit: Maximum number of feed items to return (default: 10, max: 50)
        use_cache: Whether to use cached data if available (default: True)

    Returns recent feed posts with engagement data.
    """
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger
    from linkedin_mcp.services.cache import CacheService, get_cache

    logger = get_logger(__name__)
    ctx = get_context()
    cache = get_cache()

    if not ctx.linkedin_client:
        return {"error": "LinkedIn client not initialized"}

    limit = min(limit, 50)  # Cap at 50
    cache_key = cache.make_key("feed", str(limit))

    try:
        if use_cache:
            cached_data = await cache.get(cache_key)
            if cached_data:
                return {"success": True, "posts": cached_data, "count": len(cached_data), "cached": True}

        feed = await ctx.linkedin_client.get_feed(limit=limit)
        await cache.set(cache_key, feed, CacheService.TTL_FEED)
        return {"success": True, "posts": feed, "count": len(feed), "cached": False}
    except Exception as e:
        logger.error("Failed to fetch feed", error=str(e))
        return {"error": str(e)}


@mcp.tool()
async def get_profile_posts(profile_id: str, limit: int = 10, use_cache: bool = True) -> dict:
    """
    Get posts from a specific LinkedIn profile.

    Args:
        profile_id: LinkedIn public ID or URN
        limit: Maximum number of posts to return (default: 10, max: 50)
        use_cache: Whether to use cached data if available (default: True)

    Returns posts with engagement metrics (likes, comments, shares).
    """
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger
    from linkedin_mcp.services.cache import CacheService, get_cache

    logger = get_logger(__name__)
    ctx = get_context()
    cache = get_cache()

    limit = min(limit, 50)  # Cap at 50
    cache_key = cache.make_key("posts", profile_id, str(limit))

    try:
        if use_cache:
            cached_data = await cache.get(cache_key)
            if cached_data:
                return {"success": True, "posts": cached_data, "count": len(cached_data), "cached": True}

        # Use data_provider with full fallback chain (PND → Fresh Data → Enhanced → Headless → Primary)
        if ctx.data_provider:
            result = await ctx.data_provider.get_profile_posts(profile_id, limit=limit)
            posts = result.get("posts", result.get("data", []))
            source = result.get("source", "data_provider")
            if posts:
                await cache.set(cache_key, posts, CacheService.TTL_POSTS)
            return {"success": True, "posts": posts, "count": len(posts), "cached": False, "source": source}

        return {"error": "No LinkedIn data provider available. Configure API credentials."}
    except Exception as e:
        logger.error("Failed to fetch posts", error=str(e), profile_id=profile_id)
        return {"error": str(e)}


@mcp.tool()
async def create_post(text: str, visibility: str = "PUBLIC") -> dict:
    """
    Create a new LinkedIn post using the Official API (recommended) or unofficial API.

    Uses the Official LinkedIn API with w_member_social scope when available.
    This is the TOS-compliant method that requires enabling "Share on LinkedIn" product.

    Args:
        text: Post content (max 3000 characters)
        visibility: Post visibility - PUBLIC or CONNECTIONS

    Returns the created post details including post URN.
    """
    from linkedin_mcp.config.constants import MAX_POST_LENGTH
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger
    from linkedin_mcp.services.linkedin.posts_client import LinkedInPostsClient, PostVisibility

    logger = get_logger(__name__)
    ctx = get_context()

    if len(text) > MAX_POST_LENGTH:
        return {"error": f"Post exceeds maximum length of {MAX_POST_LENGTH} characters"}

    # Map visibility
    visibility_map = {
        "PUBLIC": PostVisibility.PUBLIC,
        "CONNECTIONS": PostVisibility.CONNECTIONS,
        "LOGGED_IN": PostVisibility.CONNECTIONS,  # Map to CONNECTIONS for official API
    }
    if visibility.upper() not in visibility_map:
        return {"error": "Invalid visibility. Must be PUBLIC or CONNECTIONS"}

    # Prefer Official API - TOS compliant and reliable
    if ctx.has_official_client:
        try:
            posts_client = LinkedInPostsClient(
                access_token=ctx.official_client._access_token,
                member_urn=None,  # Will be fetched automatically
            )
            result = posts_client.create_text_post(
                text=text,
                visibility=visibility_map[visibility.upper()],
            )
            if result and result.get("success"):
                logger.info("Created post via Official API", post_urn=result.get("post_urn"))
                return {"success": True, "post": result, "source": "official_api"}
            else:
                logger.warning("Official API post failed, trying unofficial", error=result.get("error"))
        except Exception as e:
            logger.warning("Official API failed, trying unofficial", error=str(e))

    # Fall back to unofficial API
    if ctx.linkedin_client:
        try:
            result = await ctx.linkedin_client.create_post(text, visibility=visibility)
            return {"success": True, "post": result, "source": "unofficial_api"}
        except Exception as e:
            logger.error("Failed to create post via unofficial API", error=str(e))
            return {"error": str(e)}

    return {"error": "No LinkedIn client available. Configure OAuth token or session cookies."}


@mcp.tool()
async def create_image_post(text: str, image_path: str, alt_text: str | None = None, visibility: str = "PUBLIC") -> dict:
    """
    Create a LinkedIn post with an image using the Official API.

    Requires "Share on LinkedIn" product enabled in your LinkedIn Developer app.

    Args:
        text: Post text content (max 3000 characters)
        image_path: Image source - can be:
            - Absolute path to local file (JPG, PNG, GIF)
            - URL to image (http:// or https://)
            - Base64-encoded image (data:image/png;base64,...)
        alt_text: Accessibility text describing the image (recommended)
        visibility: Post visibility - PUBLIC or CONNECTIONS

    Returns the created post details including post URN and image URN.
    """
    import base64
    import tempfile
    from pathlib import Path
    from urllib.parse import urlparse

    import httpx

    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger
    from linkedin_mcp.services.linkedin.posts_client import LinkedInPostsClient, PostVisibility

    logger = get_logger(__name__)
    ctx = get_context()

    valid_extensions = (".jpg", ".jpeg", ".png", ".gif")
    temp_file = None
    image_file = None

    try:
        # Detect input type and resolve to a file path
        if image_path.startswith(("http://", "https://")):
            # URL input - download to temp file
            logger.info("Downloading image from URL", url=image_path[:100])
            try:
                async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                    response = await client.get(image_path)
                    response.raise_for_status()

                    # Determine file extension from content-type or URL
                    content_type = response.headers.get("content-type", "").lower()
                    if "jpeg" in content_type or "jpg" in content_type:
                        ext = ".jpg"
                    elif "png" in content_type:
                        ext = ".png"
                    elif "gif" in content_type:
                        ext = ".gif"
                    else:
                        # Try to get from URL path
                        parsed = urlparse(image_path)
                        path_ext = Path(parsed.path).suffix.lower()
                        ext = path_ext if path_ext in valid_extensions else ".jpg"

                    # Create temp file with proper extension
                    temp_file = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
                    temp_file.write(response.content)
                    temp_file.close()
                    image_file = Path(temp_file.name)
                    logger.info("Downloaded image to temp file", path=str(image_file), size=len(response.content))

            except httpx.HTTPStatusError as e:
                return {"error": f"Failed to download image: HTTP {e.response.status_code}"}
            except httpx.RequestError as e:
                return {"error": f"Failed to download image: {str(e)}"}

        elif image_path.startswith("data:image/"):
            # Base64-encoded image
            logger.info("Decoding base64 image")
            try:
                # Parse data URL: data:image/png;base64,<data>
                header, encoded = image_path.split(",", 1)
                # Extract format from header (e.g., "data:image/png;base64")
                mime_part = header.split(";")[0]  # "data:image/png"
                image_format = mime_part.split("/")[1] if "/" in mime_part else "png"

                ext_map = {"jpeg": ".jpg", "jpg": ".jpg", "png": ".png", "gif": ".gif"}
                ext = ext_map.get(image_format.lower(), ".png")

                # Decode and write to temp file
                image_data = base64.b64decode(encoded)
                temp_file = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
                temp_file.write(image_data)
                temp_file.close()
                image_file = Path(temp_file.name)
                logger.info("Decoded base64 image to temp file", path=str(image_file), size=len(image_data))

            except (ValueError, base64.binascii.Error) as e:
                return {"error": f"Invalid base64 image data: {str(e)}"}

        else:
            # Local file path
            image_file = Path(image_path)
            if not image_file.exists():
                return {
                    "error": f"Image file not found: {image_path}",
                    "hint": "You can also provide a URL (http/https) or base64-encoded image (data:image/...)",
                }

        # Validate file extension
        if not image_file.suffix.lower() in valid_extensions:
            return {"error": f"Invalid image format. Supported: {', '.join(valid_extensions)}"}

        # Check official API availability
        if not ctx.has_official_client:
            return {
                "error": "Official API required for image posts. Run 'linkedin-mcp-auth oauth' to authenticate.",
                "hint": "Enable 'Share on LinkedIn' product in your LinkedIn Developer app.",
            }

        visibility_enum = PostVisibility.PUBLIC if visibility.upper() == "PUBLIC" else PostVisibility.CONNECTIONS

        posts_client = LinkedInPostsClient(
            access_token=ctx.official_client._access_token,
        )
        result = posts_client.create_image_post(
            text=text,
            image_path=image_file,
            alt_text=alt_text,
            visibility=visibility_enum,
        )

        if result and result.get("success"):
            logger.info("Created image post", post_urn=result.get("post_urn"))
            return {"success": True, "post": result, "source": "official_api"}
        else:
            return {"success": False, "error": result.get("error", "Unknown error")}

    except Exception as e:
        logger.error("Failed to create image post", error=str(e))
        return {"error": str(e)}

    finally:
        # Clean up temp file if we created one
        if temp_file is not None:
            import os
            try:
                os.unlink(temp_file.name)
                logger.debug("Cleaned up temp image file", path=temp_file.name)
            except OSError:
                pass  # Ignore cleanup errors


@mcp.tool()
async def create_video_post(text: str, video_path: str, title: str | None = None, visibility: str = "PUBLIC") -> dict:
    """
    Create a LinkedIn post with a video using the Official API.

    Requires "Share on LinkedIn" product enabled in your LinkedIn Developer app.

    LinkedIn supports video uploads up to 10 minutes for most users.
    Supported formats: MP4 (recommended), MOV
    Maximum file size: 200MB
    Recommended specs: 1080p, H.264 codec, AAC audio, 30fps

    Args:
        text: Post text content (max 3000 characters)
        video_path: Video source - can be:
            - Absolute path to local file (MP4, MOV)
            - URL to video (http:// or https://)
        title: Optional title for the video
        visibility: Post visibility - PUBLIC or CONNECTIONS

    Returns the created post details including post URN and video URN.
    Note: Video may take a few minutes to process before appearing in the feed.
    """
    import tempfile
    from pathlib import Path

    import httpx

    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger
    from linkedin_mcp.services.linkedin.posts_client import LinkedInPostsClient, PostVisibility

    logger = get_logger(__name__)
    ctx = get_context()

    valid_extensions = (".mp4", ".mov")
    temp_file = None
    video_file = None

    try:
        # Detect input type and resolve to a file path
        if video_path.startswith(("http://", "https://")):
            # URL input - download to temp file
            logger.info("Downloading video from URL", url=video_path[:100])
            try:
                async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
                    response = await client.get(video_path)
                    response.raise_for_status()

                    # Determine file extension from content-type or URL
                    content_type = response.headers.get("content-type", "").lower()
                    if "quicktime" in content_type or "mov" in content_type:
                        ext = ".mov"
                    else:
                        ext = ".mp4"

                    # Save to temp file
                    temp_file = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
                    temp_file.write(response.content)
                    temp_file.close()
                    video_file = Path(temp_file.name)
                    logger.info("Downloaded video to temp file", path=str(video_file), size_mb=len(response.content) / 1024 / 1024)

            except httpx.HTTPError as e:
                return {"error": f"Failed to download video from URL: {str(e)}"}

        else:
            # Local file path
            video_file = Path(video_path)
            if not video_file.exists():
                return {
                    "error": f"Video file not found: {video_path}",
                    "hint": "You can also provide a URL (http/https) to download the video.",
                }

        # Validate file extension
        if video_file.suffix.lower() not in valid_extensions:
            return {"error": f"Invalid video format. Supported: {', '.join(valid_extensions)}"}

        # Check official API availability
        if not ctx.has_official_client:
            return {
                "error": "Official API required for video posts. Run 'linkedin-mcp-auth oauth' to authenticate.",
                "hint": "Enable 'Share on LinkedIn' product in your LinkedIn Developer app.",
            }

        visibility_enum = PostVisibility.PUBLIC if visibility.upper() == "PUBLIC" else PostVisibility.CONNECTIONS

        posts_client = LinkedInPostsClient(
            access_token=ctx.official_client._access_token,
        )
        result = posts_client.create_video_post(
            text=text,
            video_path=video_file,
            title=title,
            visibility=visibility_enum,
        )

        if result and result.get("success"):
            logger.info("Created video post", post_urn=result.get("post_urn"))
            return {"success": True, "post": result, "source": "official_api"}
        else:
            return {"success": False, "error": result.get("error", "Unknown error")}

    except Exception as e:
        logger.error("Failed to create video post", error=str(e))
        return {"error": str(e)}

    finally:
        # Clean up temp file if we created one
        if temp_file is not None:
            import os
            try:
                os.unlink(temp_file.name)
                logger.debug("Cleaned up temp video file", path=temp_file.name)
            except OSError:
                pass  # Ignore cleanup errors


@mcp.tool()
async def create_document_post(text: str, document_path: str, title: str | None = None, visibility: str = "PUBLIC") -> dict:
    """
    Create a LinkedIn post with a document (PDF, PPTX, DOCX) using the Official API.

    Documents appear as carousel-style slideshows in the LinkedIn feed.
    Great for sharing presentations, guides, reports, etc.

    Requires "Share on LinkedIn" product enabled in your LinkedIn Developer app.

    Supported formats: PDF (recommended), PPTX, DOCX
    Maximum file size: 100MB

    Args:
        text: Post text content (max 3000 characters)
        document_path: Document source - can be:
            - Absolute path to local file (PDF, PPTX, DOCX)
            - URL to document (http:// or https://)
        title: Optional title for the document (defaults to filename)
        visibility: Post visibility - PUBLIC or CONNECTIONS

    Returns the created post details including post URN and document URN.
    """
    import tempfile
    from pathlib import Path

    import httpx

    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger
    from linkedin_mcp.services.linkedin.posts_client import LinkedInPostsClient, PostVisibility

    logger = get_logger(__name__)
    ctx = get_context()

    valid_extensions = (".pdf", ".pptx", ".docx")
    temp_file = None
    document_file = None

    try:
        # Detect input type and resolve to a file path
        if document_path.startswith(("http://", "https://")):
            # URL input - download to temp file
            logger.info("Downloading document from URL", url=document_path[:100])
            try:
                async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
                    response = await client.get(document_path)
                    response.raise_for_status()

                    # Determine file extension from content-type or URL
                    content_type = response.headers.get("content-type", "").lower()
                    if "pdf" in content_type:
                        ext = ".pdf"
                    elif "presentation" in content_type or "pptx" in content_type:
                        ext = ".pptx"
                    elif "wordprocessing" in content_type or "docx" in content_type:
                        ext = ".docx"
                    else:
                        # Try to infer from URL
                        from urllib.parse import urlparse
                        parsed = urlparse(document_path)
                        path_ext = Path(parsed.path).suffix.lower()
                        ext = path_ext if path_ext in valid_extensions else ".pdf"

                    # Save to temp file
                    temp_file = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
                    temp_file.write(response.content)
                    temp_file.close()
                    document_file = Path(temp_file.name)
                    logger.info("Downloaded document to temp file", path=str(document_file), size_mb=len(response.content) / 1024 / 1024)

            except httpx.HTTPError as e:
                return {"error": f"Failed to download document from URL: {str(e)}"}

        else:
            # Local file path
            document_file = Path(document_path)
            if not document_file.exists():
                return {
                    "error": f"Document file not found: {document_path}",
                    "hint": "You can also provide a URL (http/https) to download the document.",
                }

        # Validate file extension
        if document_file.suffix.lower() not in valid_extensions:
            return {"error": f"Invalid document format. Supported: {', '.join(valid_extensions)}"}

        # Check official API availability
        if not ctx.has_official_client:
            return {
                "error": "Official API required for document posts. Run 'linkedin-mcp-auth oauth' to authenticate.",
                "hint": "Enable 'Share on LinkedIn' product in your LinkedIn Developer app.",
            }

        visibility_enum = PostVisibility.PUBLIC if visibility.upper() == "PUBLIC" else PostVisibility.CONNECTIONS

        posts_client = LinkedInPostsClient(
            access_token=ctx.official_client._access_token,
        )
        result = posts_client.create_document_post(
            text=text,
            document_path=document_file,
            title=title,
            visibility=visibility_enum,
        )

        if result and result.get("success"):
            logger.info("Created document post", post_urn=result.get("post_urn"))
            return {"success": True, "post": result, "source": "official_api"}
        else:
            return {"success": False, "error": result.get("error", "Unknown error")}

    except Exception as e:
        logger.error("Failed to create document post", error=str(e))
        return {"error": str(e)}

    finally:
        # Clean up temp file if we created one
        if temp_file is not None:
            import os
            try:
                os.unlink(temp_file.name)
                logger.debug("Cleaned up temp document file", path=temp_file.name)
            except OSError:
                pass  # Ignore cleanup errors


@mcp.tool()
async def create_poll(
    question: str,
    options: str,
    duration_days: int = 7,
    visibility: str = "PUBLIC",
) -> dict:
    """
    Create a LinkedIn poll using the Official API.

    Requires "Share on LinkedIn" product enabled in your LinkedIn Developer app.

    Args:
        question: Poll question (also displayed as post text, max 140 characters)
        options: Comma-separated poll options (2-4 options, each max 140 characters)
        duration_days: Poll duration - 1, 3, 7, or 14 days (default: 7)
        visibility: Post visibility - PUBLIC or CONNECTIONS

    Returns the created poll post details.
    """
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger
    from linkedin_mcp.services.linkedin.posts_client import LinkedInPostsClient, PostVisibility

    logger = get_logger(__name__)
    ctx = get_context()

    # Parse options
    option_list = [opt.strip() for opt in options.split(",") if opt.strip()]
    if len(option_list) < 2 or len(option_list) > 4:
        return {"error": "Poll must have 2-4 options (comma-separated)"}

    # Validate duration
    if duration_days not in (1, 3, 7, 14):
        return {"error": "Poll duration must be 1, 3, 7, or 14 days"}

    # Check official API availability
    if not ctx.has_official_client:
        return {
            "error": "Official API required for polls. Run 'linkedin-mcp-auth oauth' to authenticate.",
            "hint": "Enable 'Share on LinkedIn' product in your LinkedIn Developer app.",
        }

    visibility_enum = PostVisibility.PUBLIC if visibility.upper() == "PUBLIC" else PostVisibility.CONNECTIONS

    try:
        posts_client = LinkedInPostsClient(
            access_token=ctx.official_client._access_token,
        )
        result = posts_client.create_poll(
            question=question,
            options=option_list,
            duration_days=duration_days,
            visibility=visibility_enum,
        )

        if result and result.get("success"):
            logger.info("Created poll", post_urn=result.get("post_urn"))
            return {"success": True, "poll": result, "source": "official_api"}
        else:
            return {"success": False, "error": result.get("error", "Unknown error")}

    except Exception as e:
        logger.error("Failed to create poll", error=str(e))
        return {"error": str(e)}


@mcp.tool()
async def delete_post(post_urn: str) -> dict:
    """
    Delete a LinkedIn post using the Official API.

    Requires "Share on LinkedIn" product enabled in your LinkedIn Developer app.

    Args:
        post_urn: The URN of the post to delete (e.g., "urn:li:share:123456")

    Returns success status.
    """
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger
    from linkedin_mcp.services.linkedin.posts_client import LinkedInPostsClient

    logger = get_logger(__name__)
    ctx = get_context()

    if not ctx.has_official_client:
        return {
            "error": "Official API required to delete posts. Run 'linkedin-mcp-auth oauth' to authenticate.",
        }

    try:
        posts_client = LinkedInPostsClient(
            access_token=ctx.official_client._access_token,
        )
        result = posts_client.delete_post(post_urn)

        if result and result.get("success"):
            logger.info("Deleted post", post_urn=post_urn)
            return {"success": True, "message": f"Post {post_urn} deleted", "source": "official_api"}
        else:
            return {"success": False, "error": result.get("error", "Unknown error")}

    except Exception as e:
        logger.error("Failed to delete post", error=str(e), post_urn=post_urn)
        return {"error": str(e)}


@mcp.tool()
async def edit_post(
    post_urn: str,
    text: str | None = None,
    image_path: str | None = None,
    alt_text: str | None = None,
) -> dict:
    """
    Edit/update an existing LinkedIn post using the Official API.

    Requires "Share on LinkedIn" product enabled in your LinkedIn Developer app.

    Args:
        post_urn: The URN of the post to edit (e.g., "urn:li:share:123456")
        text: New text content for the post (optional, max 3000 characters)
        image_path: Path to new image file to replace existing media (optional)
        alt_text: Alt text for the new image (optional)

    Returns:
        Success status with updated fields information.

    Note:
        At least one of 'text' or 'image_path' must be provided.
        This uses LinkedIn's PARTIAL_UPDATE method to update only specified fields.
    """
    from pathlib import Path

    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger
    from linkedin_mcp.services.linkedin.posts_client import LinkedInPostsClient

    logger = get_logger(__name__)
    ctx = get_context()

    if not ctx.has_official_client:
        return {
            "error": "Official API required to edit posts. Run 'linkedin-mcp-auth oauth' to authenticate.",
        }

    try:
        posts_client = LinkedInPostsClient(
            access_token=ctx.official_client._access_token,
        )

        # Convert string path to Path object if provided
        image = Path(image_path) if image_path else None

        result = posts_client.update_post(
            post_urn=post_urn,
            text=text,
            image_path=image,
            alt_text=alt_text,
        )

        if result and result.get("success"):
            logger.info(
                "Edited post",
                post_urn=post_urn,
                updated_fields=result.get("updated_fields"),
            )
            return {
                "success": True,
                "message": f"Post {post_urn} updated successfully",
                "updated_fields": result.get("updated_fields"),
                "new_image_urn": result.get("new_image_urn"),
                "source": "official_api",
            }
        else:
            return {"success": False, "error": result.get("error", "Unknown error")}

    except Exception as e:
        logger.error("Failed to edit post", error=str(e), post_urn=post_urn)
        return {"error": str(e)}


@mcp.tool()
async def create_comment(
    post_urn: str,
    text: str,
    parent_comment_urn: str | None = None,
    image_path: str | None = None,
) -> dict:
    """
    Create a comment on a LinkedIn post using the Official API.

    Requires "Share on LinkedIn" product enabled in your LinkedIn Developer app.

    Args:
        post_urn: The URN of the post to comment on (e.g., "urn:li:share:123456" or "urn:li:activity:123456")
        text: The comment text content (max 1250 characters)
        parent_comment_urn: Optional URN of parent comment for nested replies
        image_path: Optional image source (only for nested replies) - can be:
            - Absolute path to local file (JPG, PNG, GIF)
            - URL to image (http:// or https://)
            - Base64-encoded image (data:image/png;base64,...)

    Returns the created comment details including comment ID.

    Note: LinkedIn only allows images in nested comments (replies to other comments),
    not in top-level comments directly on posts.

    Note: Commenting requires the "Community Management API" product from LinkedIn,
    which has a separate approval process. The "Share on LinkedIn" product only
    allows creating posts, not comments. If you receive a permission error,
    you'll need to apply for Community Management API access in your Developer Portal.
    """
    import base64
    import tempfile
    from pathlib import Path
    from urllib.parse import urlparse

    import httpx

    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger
    from linkedin_mcp.services.linkedin.posts_client import LinkedInPostsClient

    logger = get_logger(__name__)
    ctx = get_context()

    if not ctx.has_official_client:
        return {
            "error": "Official API required to create comments. Run 'linkedin-mcp-auth oauth' to authenticate.",
            "hint": "Enable 'Share on LinkedIn' product in your LinkedIn Developer app.",
        }

    if not text or not text.strip():
        return {"error": "Comment text cannot be empty"}

    if len(text) > 1250:
        return {"error": f"Comment text too long ({len(text)} chars). Maximum is 1250 characters."}

    # Check image constraint early
    if image_path and not parent_comment_urn:
        return {
            "error": "LinkedIn only allows images in nested comments (replies to other comments). "
            "To add an image, you must provide parent_comment_urn to reply to an existing comment.",
            "hint": "First create a text comment, then use the returned comment_id as parent_comment_urn for an image reply.",
        }

    valid_extensions = (".jpg", ".jpeg", ".png", ".gif")
    temp_file = None
    image_file = None

    try:
        # Handle image if provided
        if image_path:
            if image_path.startswith(("http://", "https://")):
                # URL input - download to temp file
                logger.info("Downloading comment image from URL", url=image_path[:100])
                try:
                    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                        response = await client.get(image_path)
                        response.raise_for_status()

                        content_type = response.headers.get("content-type", "").lower()
                        if "jpeg" in content_type or "jpg" in content_type:
                            ext = ".jpg"
                        elif "png" in content_type:
                            ext = ".png"
                        elif "gif" in content_type:
                            ext = ".gif"
                        else:
                            parsed = urlparse(image_path)
                            path_ext = Path(parsed.path).suffix.lower()
                            ext = path_ext if path_ext in valid_extensions else ".jpg"

                        temp_file = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
                        temp_file.write(response.content)
                        temp_file.close()
                        image_file = Path(temp_file.name)

                except httpx.HTTPStatusError as e:
                    return {"error": f"Failed to download image: HTTP {e.response.status_code}"}
                except httpx.RequestError as e:
                    return {"error": f"Failed to download image: {str(e)}"}

            elif image_path.startswith("data:image/"):
                # Base64-encoded image
                logger.info("Decoding base64 comment image")
                try:
                    header, encoded = image_path.split(",", 1)
                    mime_part = header.split(";")[0]
                    image_format = mime_part.split("/")[1] if "/" in mime_part else "png"

                    ext_map = {"jpeg": ".jpg", "jpg": ".jpg", "png": ".png", "gif": ".gif"}
                    ext = ext_map.get(image_format.lower(), ".png")

                    image_data = base64.b64decode(encoded)
                    temp_file = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
                    temp_file.write(image_data)
                    temp_file.close()
                    image_file = Path(temp_file.name)

                except (ValueError, base64.binascii.Error) as e:
                    return {"error": f"Invalid base64 image data: {str(e)}"}

            else:
                # Local file path
                image_file = Path(image_path)
                if not image_file.exists():
                    return {
                        "error": f"Image file not found: {image_path}",
                        "hint": "You can also provide a URL (http/https) or base64-encoded image (data:image/...)",
                    }

            # Validate extension
            if not image_file.suffix.lower() in valid_extensions:
                return {"error": f"Invalid image format. Supported: {', '.join(valid_extensions)}"}

        posts_client = LinkedInPostsClient(
            access_token=ctx.official_client._access_token,
        )
        result = posts_client.create_comment(
            post_urn=post_urn,
            text=text,
            parent_comment_urn=parent_comment_urn,
            image_path=image_file,
        )

        if result and result.get("success"):
            logger.info("Created comment", comment_id=result.get("comment_id"), post_urn=post_urn)
            return {"success": True, "comment": result, "source": "official_api"}
        else:
            return {"success": False, "error": result.get("error", "Unknown error")}

    except Exception as e:
        logger.error("Failed to create comment", error=str(e), post_urn=post_urn)
        return {"error": str(e)}

    finally:
        # Clean up temp file if we created one
        if temp_file is not None:
            import os
            try:
                os.unlink(temp_file.name)
            except OSError:
                pass


@mcp.tool()
async def delete_comment(
    post_urn: str,
    comment_id: str,
) -> dict:
    """
    Delete a comment from a LinkedIn post using the Official API.

    Requires "Community Management API" product enabled in your LinkedIn Developer app.

    Args:
        post_urn: The URN of the post containing the comment (e.g., "urn:li:share:123456" or "urn:li:activity:123456")
        comment_id: The ID or URN of the comment to delete

    Returns success status.

    Note: You can only delete comments that you have authored.
    """
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger
    from linkedin_mcp.services.linkedin.posts_client import LinkedInPostsClient

    logger = get_logger(__name__)
    ctx = get_context()

    if not ctx.has_official_client:
        return {
            "error": "Official API required to delete comments. Run 'linkedin-mcp-auth oauth' to authenticate.",
            "hint": "Enable 'Community Management API' product in your LinkedIn Developer app.",
        }

    try:
        posts_client = LinkedInPostsClient(
            access_token=ctx.official_client._access_token,
        )
        result = posts_client.delete_comment(
            post_urn=post_urn,
            comment_id=comment_id,
        )

        if result and result.get("success"):
            logger.info("Deleted comment", comment_id=comment_id, post_urn=post_urn)
            return {"success": True, "result": result, "source": "official_api"}
        else:
            return {"success": False, "error": result.get("error", "Unknown error")}

    except Exception as e:
        logger.error("Failed to delete comment", error=str(e), post_urn=post_urn)
        return {"error": str(e)}


@mcp.tool()
async def get_comments_official(
    post_urn: str,
    start: int = 0,
    count: int = 50,
) -> dict:
    """
    Get comments on a LinkedIn post using the Official API.

    Requires "Community Management API" product enabled in your LinkedIn Developer app.

    Args:
        post_urn: The URN of the post (e.g., "urn:li:share:123456" or "urn:li:ugcPost:123456")
        start: Pagination start index (default: 0)
        count: Number of comments to return (default: 50, max: 100)

    Returns list of comments with:
        - id: Comment ID
        - urn: Full comment URN (use this as parent_comment_urn to reply)
        - actor_urn: URN of the comment author
        - actor_name: Name of the comment author (if available)
        - text: Comment text content
        - parent_comment: URN of parent comment if this is a reply
        - created_at: Timestamp when comment was created

    Use the returned comment URN as parent_comment_urn in create_comment to reply to a comment.
    """
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger
    from linkedin_mcp.services.linkedin.posts_client import LinkedInPostsClient

    logger = get_logger(__name__)
    ctx = get_context()

    if not ctx.has_official_client:
        return {
            "error": "Official API required to fetch comments. Run 'linkedin-mcp-auth oauth' to authenticate.",
            "hint": "Enable 'Community Management API' product in your LinkedIn Developer app.",
        }

    try:
        posts_client = LinkedInPostsClient(
            access_token=ctx.official_client._access_token,
        )
        result = posts_client.get_post_comments(
            post_urn=post_urn,
            start=start,
            count=count,
        )

        if result and result.get("success"):
            comments = result.get("comments", [])
            logger.info(
                "Retrieved comments via official API",
                post_urn=post_urn,
                comment_count=len(comments),
            )
            return {
                "success": True,
                "comments": comments,
                "total": result.get("total", len(comments)),
                "paging": result.get("paging", {}),
                "source": "official_api",
            }
        else:
            return {"success": False, "error": result.get("error", "Unknown error"), "comments": []}

    except Exception as e:
        logger.error("Failed to fetch comments", error=str(e), post_urn=post_urn)
        return {"error": str(e), "comments": []}


@mcp.tool()
async def create_reaction(
    target_urn: str,
    reaction_type: str = "LIKE",
) -> dict:
    """
    Add a reaction to a LinkedIn post or comment using the Official API.

    Requires "Community Management API" product enabled in your LinkedIn Developer app.

    Args:
        target_urn: The URN of the post or comment to react to
                   (e.g., "urn:li:share:123456", "urn:li:activity:123456",
                    "urn:li:comment:(urn:li:activity:123,456)")
        reaction_type: Type of reaction to add. Options:
            - LIKE (👍 Like) - default
            - PRAISE or CELEBRATE (👏 Celebrate)
            - EMPATHY or LOVE (❤️ Love)
            - INTEREST or INSIGHTFUL (💡 Insightful)
            - APPRECIATION or SUPPORT (🙏 Support)
            - ENTERTAINMENT or FUNNY (😄 Funny)

    Returns the created reaction details.

    Note: The MAYBE reaction type is deprecated and no longer supported.
    """
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger
    from linkedin_mcp.services.linkedin.posts_client import LinkedInPostsClient

    logger = get_logger(__name__)
    ctx = get_context()

    if not ctx.has_official_client:
        return {
            "error": "Official API required to create reactions. Run 'linkedin-mcp-auth oauth' to authenticate.",
            "hint": "Enable 'Community Management API' product in your LinkedIn Developer app.",
        }

    try:
        posts_client = LinkedInPostsClient(
            access_token=ctx.official_client._access_token,
        )
        result = posts_client.create_reaction(
            target_urn=target_urn,
            reaction_type=reaction_type,
        )

        if result and result.get("success"):
            logger.info(
                "Created reaction",
                reaction_type=result.get("reaction_type"),
                target_urn=target_urn,
            )
            return {"success": True, "reaction": result, "source": "official_api"}
        else:
            return {"success": False, "error": result.get("error", "Unknown error")}

    except Exception as e:
        logger.error("Failed to create reaction", error=str(e), target_urn=target_urn)
        return {"error": str(e)}


@mcp.tool()
async def delete_reaction(
    target_urn: str,
) -> dict:
    """
    Remove a reaction from a LinkedIn post or comment using the Official API.

    Requires "Community Management API" product enabled in your LinkedIn Developer app.

    Args:
        target_urn: The URN of the post or comment to remove reaction from
                   (e.g., "urn:li:share:123456", "urn:li:activity:123456")

    Returns success status.

    Note: This removes your reaction from the specified content.
    """
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger
    from linkedin_mcp.services.linkedin.posts_client import LinkedInPostsClient

    logger = get_logger(__name__)
    ctx = get_context()

    if not ctx.has_official_client:
        return {
            "error": "Official API required to delete reactions. Run 'linkedin-mcp-auth oauth' to authenticate.",
            "hint": "Enable 'Community Management API' product in your LinkedIn Developer app.",
        }

    try:
        posts_client = LinkedInPostsClient(
            access_token=ctx.official_client._access_token,
        )
        result = posts_client.delete_reaction(target_urn=target_urn)

        if result and result.get("success"):
            logger.info("Deleted reaction", target_urn=target_urn)
            return {"success": True, "result": result, "source": "official_api"}
        else:
            return {"success": False, "error": result.get("error", "Unknown error")}

    except Exception as e:
        logger.error("Failed to delete reaction", error=str(e), target_urn=target_urn)
        return {"error": str(e)}


@mcp.tool()
async def get_auth_status() -> dict:
    """
    Get LinkedIn authentication status for both official and unofficial APIs.

    Returns detailed status including:
    - Official API status (OAuth token expiry, available features)
    - Unofficial API status (cookie freshness, available features)
    - Recommended actions if not authenticated
    """
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.services.storage.token_storage import get_official_token, get_unofficial_cookies

    ctx = get_context()

    result = {
        "success": True,
        "official_api": {
            "authenticated": ctx.has_official_client,
            "features": [],
            "status": "not_configured",
        },
        "ad_library_api": {
            "available": ctx.has_ad_library_client,
            "features": [],
            "status": "not_configured",
        },
        "unofficial_api": {
            "authenticated": ctx.has_linkedin_client,
            "features": [],
            "status": "not_configured",
        },
        "recommendations": [],
    }

    # Check official API
    official_token = get_official_token()
    if official_token:
        if official_token.is_expired:
            result["official_api"]["status"] = "expired"
            result["recommendations"].append("Run 'linkedin-mcp-auth oauth' to re-authenticate")
        elif official_token.expires_soon:
            result["official_api"]["status"] = "expiring_soon"
            result["official_api"]["days_remaining"] = official_token.days_until_expiry
            result["recommendations"].append(f"Token expires in {official_token.days_until_expiry} days - consider re-authenticating")
        else:
            result["official_api"]["status"] = "active"
            result["official_api"]["days_remaining"] = official_token.days_until_expiry
            result["official_api"]["scopes"] = official_token.scopes

        # List available features based on scopes
        if "w_member_social" in official_token.scopes:
            result["official_api"]["features"].extend(["create_post", "create_image_post", "create_video_post", "create_document_post", "create_poll", "delete_post"])
        if "profile" in official_token.scopes or "openid" in official_token.scopes:
            result["official_api"]["features"].append("get_my_profile")
    else:
        result["recommendations"].append("Run 'linkedin-mcp-auth oauth' to enable official API features")

    # Check Ad Library API
    if ctx.has_ad_library_client:
        result["ad_library_api"]["status"] = "active"
        result["ad_library_api"]["features"] = [
            "search_ads", "search_ads_by_advertiser", "search_ads_by_keyword"
        ]
    elif ctx.has_official_client:
        # OAuth token exists but Ad Library not available - might need product enabled
        result["ad_library_api"]["status"] = "product_not_enabled"
        result["recommendations"].append("Enable 'LinkedIn Ad Library' product in your Developer app for ad transparency features")
    else:
        result["ad_library_api"]["status"] = "requires_oauth"

    # Check unofficial API
    cookies = get_unofficial_cookies()
    if cookies:
        if cookies.is_stale:
            result["unofficial_api"]["status"] = "stale"
            result["unofficial_api"]["hours_old"] = cookies.hours_since_extraction
            result["recommendations"].append("Run 'linkedin-mcp-auth extract-cookies' to refresh cookies")
        else:
            result["unofficial_api"]["status"] = "active"
            result["unofficial_api"]["hours_old"] = cookies.hours_since_extraction
            result["unofficial_api"]["features"] = [
                "get_profile", "get_company", "get_conversations", "send_message",
                "search_people", "search_companies", "get_connections"
            ]
    elif ctx.has_linkedin_client:
        result["unofficial_api"]["status"] = "active_legacy"
        result["unofficial_api"]["features"] = ["get_profile", "get_company", "messaging", "search"]
    else:
        result["recommendations"].append("Run 'linkedin-mcp-auth extract-cookies' for unofficial API features")

    return result


# =============================================================================
# Ad Library Tools (Ad Transparency & Research)
# =============================================================================


@mcp.tool()
async def search_ads(
    keyword: str | None = None,
    advertiser: str | None = None,
    country: str | None = None,
    count: int = 25,
) -> dict:
    """
    Search for ads in the LinkedIn Ad Library.

    The Ad Library provides transparency into ads running on LinkedIn.
    At least one of keyword or advertiser must be provided.

    Requires "LinkedIn Ad Library" product enabled in your LinkedIn Developer app.

    Args:
        keyword: Search term to find in ad content
        advertiser: Company/advertiser name to search for
        country: ISO 3166-1 alpha-2 country code (e.g., "US", "GB", "DE")
        count: Number of results to return (default 25, max 100)

    Returns:
        List of ads matching the search criteria with details including:
        - Advertiser and payer information
        - Ad content (text, images, videos)
        - Impression data and targeting parameters
    """
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger

    logger = get_logger(__name__)
    ctx = get_context()

    if not keyword and not advertiser:
        return {"error": "At least one of 'keyword' or 'advertiser' must be provided"}

    if not ctx.has_ad_library_client:
        return {
            "error": "Ad Library API not available. Requires OAuth authentication and Ad Library product enabled.",
            "hint": "Run 'linkedin-mcp-auth oauth' and enable 'LinkedIn Ad Library' in your Developer app.",
        }

    try:
        result = await ctx.ad_library_client.search_ads(
            keyword=keyword,
            advertiser=advertiser,
            country=country,
            count=count,
        )

        if result.get("success"):
            logger.info(
                "Ad Library search successful",
                keyword=keyword,
                advertiser=advertiser,
                result_count=len(result.get("elements", [])),
            )
            return result
        else:
            return {"error": result.get("error", "Unknown error")}

    except Exception as e:
        logger.error("Ad Library search failed", error=str(e))
        return {"error": str(e)}


@mcp.tool()
async def search_ads_by_advertiser(
    advertiser_name: str,
    country: str | None = None,
    count: int = 25,
) -> dict:
    """
    Search for all ads by a specific advertiser/company.

    Requires "LinkedIn Ad Library" product enabled in your LinkedIn Developer app.

    Args:
        advertiser_name: Name of the advertiser/company to search for
        country: Optional country filter (ISO 3166-1 alpha-2 code)
        count: Number of results to return (default 25, max 100)

    Returns:
        List of ads from the specified advertiser with full details.
    """
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger

    logger = get_logger(__name__)
    ctx = get_context()

    if not ctx.has_ad_library_client:
        return {
            "error": "Ad Library API not available. Requires OAuth authentication and Ad Library product enabled.",
            "hint": "Run 'linkedin-mcp-auth oauth' and enable 'LinkedIn Ad Library' in your Developer app.",
        }

    try:
        result = await ctx.ad_library_client.search_ads_by_advertiser(
            advertiser_name=advertiser_name,
            country=country,
            count=count,
        )

        if result.get("success"):
            logger.info(
                "Advertiser ad search successful",
                advertiser=advertiser_name,
                result_count=len(result.get("elements", [])),
            )
            return result
        else:
            return {"error": result.get("error", "Unknown error")}

    except Exception as e:
        logger.error("Advertiser ad search failed", error=str(e))
        return {"error": str(e)}


@mcp.tool()
async def search_ads_by_keyword(
    keyword: str,
    country: str | None = None,
    count: int = 25,
) -> dict:
    """
    Search for ads containing a specific keyword.

    Requires "LinkedIn Ad Library" product enabled in your LinkedIn Developer app.

    Args:
        keyword: Search term to find in ad content
        country: Optional country filter (ISO 3166-1 alpha-2 code)
        count: Number of results to return (default 25, max 100)

    Returns:
        List of ads matching the keyword with full details.
    """
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger

    logger = get_logger(__name__)
    ctx = get_context()

    if not ctx.has_ad_library_client:
        return {
            "error": "Ad Library API not available. Requires OAuth authentication and Ad Library product enabled.",
            "hint": "Run 'linkedin-mcp-auth oauth' and enable 'LinkedIn Ad Library' in your Developer app.",
        }

    try:
        result = await ctx.ad_library_client.search_ads_by_keyword(
            keyword=keyword,
            country=country,
            count=count,
        )

        if result.get("success"):
            logger.info(
                "Keyword ad search successful",
                keyword=keyword,
                result_count=len(result.get("elements", [])),
            )
            return result
        else:
            return {"error": result.get("error", "Unknown error")}

    except Exception as e:
        logger.error("Keyword ad search failed", error=str(e))
        return {"error": str(e)}


# =============================================================================
# Content Creation & Scheduling Tools
# =============================================================================


@mcp.tool()
async def analyze_draft_content(content: str, industry: str | None = None) -> dict:
    """
    Analyze draft content and get suggestions for improvement.

    Args:
        content: Draft post content to analyze
        industry: Optional industry for targeted hashtag suggestions

    Returns content analysis with score, suggestions, and recommended hashtags.
    """
    from linkedin_mcp.services.scheduler import get_suggestion_engine

    engine = get_suggestion_engine()

    analysis = engine.analyze_content(content)
    suggested_hashtags = engine.suggest_hashtags(content, industry)

    analysis["suggested_hashtags"] = suggested_hashtags

    return {"success": True, "analysis": analysis}


@mcp.tool()
async def create_draft(
    content: str,
    title: str | None = None,
    tags: str | None = None,
) -> dict:
    """
    Create a content draft for later publishing.

    Args:
        content: Draft content
        title: Optional title for organization
        tags: Comma-separated tags for categorization

    Returns the created draft details.
    """
    from linkedin_mcp.services.scheduler import get_draft_manager

    manager = get_draft_manager()

    tag_list = [t.strip() for t in tags.split(",")] if tags else None

    draft = manager.create_draft(content=content, title=title, tags=tag_list)

    return {"success": True, "draft": draft}


@mcp.tool()
async def list_drafts(tag: str | None = None) -> dict:
    """
    List all content drafts.

    Args:
        tag: Optional tag to filter by

    Returns list of drafts sorted by last update.
    """
    from linkedin_mcp.services.scheduler import get_draft_manager

    manager = get_draft_manager()

    drafts = manager.list_drafts(tag=tag)

    return {"success": True, "drafts": drafts, "count": len(drafts)}


@mcp.tool()
async def get_draft(draft_id: str) -> dict:
    """
    Get a specific draft by ID.

    Args:
        draft_id: ID of the draft

    Returns the draft details.
    """
    from linkedin_mcp.services.scheduler import get_draft_manager

    manager = get_draft_manager()

    draft = manager.get_draft(draft_id)

    if not draft:
        return {"error": f"Draft not found: {draft_id}"}

    return {"success": True, "draft": draft}


@mcp.tool()
async def update_draft(
    draft_id: str,
    content: str | None = None,
    title: str | None = None,
    tags: str | None = None,
) -> dict:
    """
    Update a content draft.

    Args:
        draft_id: ID of the draft to update
        content: New content (optional)
        title: New title (optional)
        tags: New comma-separated tags (optional)

    Returns the updated draft.
    """
    from linkedin_mcp.services.scheduler import get_draft_manager

    manager = get_draft_manager()

    tag_list = [t.strip() for t in tags.split(",")] if tags else None

    draft = manager.update_draft(
        draft_id=draft_id,
        content=content,
        title=title,
        tags=tag_list,
    )

    if not draft:
        return {"error": f"Draft not found: {draft_id}"}

    return {"success": True, "draft": draft}


@mcp.tool()
async def delete_draft(draft_id: str) -> dict:
    """
    Delete a content draft.

    Args:
        draft_id: ID of the draft to delete

    Returns success status.
    """
    from linkedin_mcp.services.scheduler import get_draft_manager

    manager = get_draft_manager()

    if manager.delete_draft(draft_id):
        return {"success": True, "message": f"Draft {draft_id} deleted"}

    return {"error": f"Draft not found: {draft_id}"}


@mcp.tool()
async def publish_draft(draft_id: str, visibility: str = "PUBLIC") -> dict:
    """
    Publish a draft as a LinkedIn post.

    Args:
        draft_id: ID of the draft to publish
        visibility: Post visibility - PUBLIC, CONNECTIONS, or LOGGED_IN

    Returns the published post details.
    """
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger
    from linkedin_mcp.services.scheduler import get_draft_manager

    logger = get_logger(__name__)
    ctx = get_context()
    manager = get_draft_manager()

    if not ctx.linkedin_client:
        return {"error": "LinkedIn client not initialized"}

    draft = manager.get_draft(draft_id)
    if not draft:
        return {"error": f"Draft not found: {draft_id}"}

    try:
        result = await ctx.linkedin_client.create_post(
            draft["content"],
            visibility=visibility,
        )

        # Mark draft as published
        draft["status"] = "published"
        draft["published_at"] = result.get("created", "")

        return {
            "success": True,
            "draft_id": draft_id,
            "post": result,
        }
    except Exception as e:
        logger.error("Failed to publish draft", error=str(e), draft_id=draft_id)
        return {"error": str(e)}


@mcp.tool()
async def schedule_post(
    content: str,
    scheduled_time: str,
    visibility: str = "PUBLIC",
    timezone: str = "UTC",
) -> dict:
    """
    Schedule a post for future publishing.

    Args:
        content: Post content
        scheduled_time: ISO format datetime (e.g., "2024-12-25T10:00:00")
        visibility: Post visibility - PUBLIC, CONNECTIONS, or LOGGED_IN
        timezone: Timezone for the scheduled time (default: UTC)

    Returns the scheduled post details with job_id.
    """
    from datetime import datetime

    from linkedin_mcp.config.constants import MAX_POST_LENGTH
    from linkedin_mcp.core.logging import get_logger
    from linkedin_mcp.services.scheduler import get_post_manager

    logger = get_logger(__name__)
    manager = get_post_manager()

    # Validate content length
    if len(content) > MAX_POST_LENGTH:
        return {"error": f"Post exceeds maximum length of {MAX_POST_LENGTH} characters"}

    # Validate visibility
    if visibility not in ("PUBLIC", "CONNECTIONS", "LOGGED_IN"):
        return {"error": "Invalid visibility. Must be PUBLIC, CONNECTIONS, or LOGGED_IN"}

    # Parse scheduled time
    try:
        scheduled_dt = datetime.fromisoformat(scheduled_time.replace("Z", "+00:00"))
    except ValueError as e:
        return {"error": f"Invalid datetime format: {e}"}

    # Check if time is in the future
    if scheduled_dt <= datetime.now():
        return {"error": "Scheduled time must be in the future"}

    post = manager.schedule_post(
        content=content,
        scheduled_time=scheduled_dt,
        visibility=visibility,
        timezone=timezone,
    )

    logger.info("Post scheduled", job_id=post["job_id"])

    return {"success": True, "scheduled_post": post}


@mcp.tool()
async def list_scheduled_posts(status: str | None = None) -> dict:
    """
    List all scheduled posts.

    Args:
        status: Filter by status (pending, published, failed, cancelled)

    Returns list of scheduled posts.
    """
    from linkedin_mcp.services.scheduler import get_post_manager

    manager = get_post_manager()

    posts = manager.list_scheduled_posts(status=status)

    return {"success": True, "scheduled_posts": posts, "count": len(posts)}


@mcp.tool()
async def get_scheduled_post(job_id: str) -> dict:
    """
    Get a specific scheduled post.

    Args:
        job_id: ID of the scheduled post

    Returns the scheduled post details.
    """
    from linkedin_mcp.services.scheduler import get_post_manager

    manager = get_post_manager()

    post = manager.get_scheduled_post(job_id)

    if not post:
        return {"error": f"Scheduled post not found: {job_id}"}

    return {"success": True, "scheduled_post": post}


@mcp.tool()
async def cancel_scheduled_post(job_id: str) -> dict:
    """
    Cancel a scheduled post.

    Args:
        job_id: ID of the scheduled post to cancel

    Returns success status.
    """
    from linkedin_mcp.services.scheduler import get_post_manager

    manager = get_post_manager()

    if manager.cancel_scheduled_post(job_id):
        return {"success": True, "message": f"Scheduled post {job_id} cancelled"}

    return {"error": f"Cannot cancel post: {job_id}. Post may not exist or is not pending."}


@mcp.tool()
async def update_scheduled_post(
    job_id: str,
    content: str | None = None,
    scheduled_time: str | None = None,
    visibility: str | None = None,
) -> dict:
    """
    Update a scheduled post.

    Args:
        job_id: ID of the scheduled post
        content: New content (optional)
        scheduled_time: New ISO format datetime (optional)
        visibility: New visibility (optional)

    Returns the updated scheduled post.
    """
    from datetime import datetime

    from linkedin_mcp.services.scheduler import get_post_manager

    manager = get_post_manager()

    # Parse scheduled time if provided
    scheduled_dt = None
    if scheduled_time:
        try:
            scheduled_dt = datetime.fromisoformat(scheduled_time.replace("Z", "+00:00"))
        except ValueError as e:
            return {"error": f"Invalid datetime format: {e}"}

    post = manager.update_scheduled_post(
        job_id=job_id,
        content=content,
        scheduled_time=scheduled_dt,
        visibility=visibility,
    )

    if not post:
        return {"error": f"Cannot update post: {job_id}. Post may not exist or is not pending."}

    return {"success": True, "scheduled_post": post}


# =============================================================================
# Engagement Tools
# =============================================================================


@mcp.tool()
async def get_post_reactions(post_urn: str) -> dict:
    """
    Get reactions/likes on a specific post.

    Args:
        post_urn: LinkedIn post URN (e.g., "urn:li:activity:123456789")

    Returns list of users who reacted and reaction types.
    """
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger

    logger = get_logger(__name__)
    ctx = get_context()

    try:
        # Use data_provider with full fallback chain (PND → Fresh Data → Enhanced → Headless → Primary)
        if ctx.data_provider:
            result = await ctx.data_provider.get_post_reactions(post_urn)
            reactions = result.get("reactions", result.get("data", []))
            source = result.get("source", "data_provider")
            return {
                "success": True,
                "reactions": reactions,
                "count": len(reactions),
                "summary": result.get("summary", {}),
                "source": source,
            }

        return {"error": "No LinkedIn data provider available. Configure API credentials."}
    except Exception as e:
        logger.error("Failed to fetch reactions", error=str(e), post_urn=post_urn)
        return {"error": str(e)}


@mcp.tool()
async def get_post_comments(post_urn: str, limit: int = 50) -> dict:
    """
    Get comments on a specific post.

    Args:
        post_urn: LinkedIn post URN
        limit: Maximum comments to return (default: 50)

    Returns list of comments with author info.
    """
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger

    logger = get_logger(__name__)
    ctx = get_context()

    try:
        # Use data_provider with full fallback chain (PND → Fresh Data → Enhanced → Headless → Primary)
        if ctx.data_provider:
            result = await ctx.data_provider.get_post_comments(post_urn, limit=limit)
            comments = result.get("comments", result.get("data", []))
            source = result.get("source", "data_provider")
            return {
                "success": True,
                "comments": comments,
                "count": len(comments),
                "source": source,
            }

        return {"error": "No LinkedIn data provider available. Configure API credentials."}
    except Exception as e:
        logger.error("Failed to fetch comments", error=str(e), post_urn=post_urn)
        return {"error": str(e)}


# =============================================================================
# Connection Management Tools (REMOVED - linkedin-api unreliable)
# =============================================================================
# The following tools have been removed due to LinkedIn's aggressive bot detection:
# - like_post, react_to_post, comment_on_post, reply_to_comment, unreact_to_post
# - send_connection_request, remove_connection, get_pending_invitations
# - accept_invitation, reject_invitation, send_bulk_messages
# - get_conversations, get_conversation, send_message
# These tools relied on cookie-based authentication which is frequently blocked.
# =============================================================================


# =============================================================================
# Search Tools
# =============================================================================


@mcp.tool()
async def search_people(
    keywords: str | None = None,
    limit: int = 10,
    keyword_title: str | None = None,
    keyword_company: str | None = None,
) -> dict:
    """
    Search for people on LinkedIn.

    Args:
        keywords: General search keywords
        limit: Maximum results to return (default: 10, max: 50)
        keyword_title: Filter by job title (e.g., 'VP Engineering', 'Product Manager')
        keyword_company: Filter by company name

    Note: Location/region filters are not supported by the underlying API.

    Returns list of matching profiles with name, title, location, and profile URL.

    Search priority:
    1. Fresh Data API (requires Pro plan $45/mo for search-leads endpoint)
    2. linkedin-api (cookie-based, may be blocked by LinkedIn bot detection)
    """
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger

    logger = get_logger(__name__)
    ctx = get_context()

    limit = min(limit, 50)  # Cap at 50
    sources_tried = []
    errors_encountered = []

    logger.info(
        "Starting people search",
        keywords=keywords,
        keyword_title=keyword_title,
        keyword_company=keyword_company,
        limit=limit,
    )

    # Try data provider first (has comprehensive fallback chain including Fresh Data API)
    if ctx.data_provider:
        try:
            logger.debug("Trying data_provider.search_profiles (Fresh Data API → linkedin-api fallback)")
            title_keywords = [keyword_title] if keyword_title else None
            company_names = [keyword_company] if keyword_company else None

            result = await ctx.data_provider.search_profiles(
                query=keywords,
                title_keywords=title_keywords,
                company_names=company_names,
                limit=limit,
            )
            source = result.get("source", "unknown")
            data = result.get("data", [])
            logger.info("Search completed via data_provider", source=source, count=len(data))
            return {
                "success": True,
                "results": data,
                "count": len(data),
                "source": source,
            }
        except PermissionError as e:
            # Fresh Data API subscription limitation (Basic plan doesn't have search)
            sources_tried.append("fresh_data_api")
            errors_encountered.append(f"Fresh Data API: {str(e)}")
            logger.info("Fresh Data API search not available on current plan, trying linkedin_client")
        except Exception as e:
            sources_tried.append("data_provider")
            errors_encountered.append(f"Data provider: {str(e)}")
            logger.warning("Data provider search failed, trying linkedin_client", error=str(e))
    else:
        logger.debug("data_provider not available")

    # Fall back to linkedin_client if data provider fails
    if not ctx.linkedin_client:
        logger.warning(
            "No search sources available",
            sources_tried=sources_tried,
            errors=errors_encountered,
        )
        return {
            "error": "LinkedIn search not available. Fresh Data API search requires Pro plan ($45/mo), and linkedin-api is not configured.",
            "sources_tried": sources_tried,
            "suggestion": "Configure linkedin-api with session cookies, or upgrade Fresh Data API to Pro plan for search capabilities.",
        }

    try:
        logger.debug("Trying linkedin_client.search_people (cookie-based)")
        results = await ctx.linkedin_client.search_people(
            keywords=keywords,
            limit=limit,
            keyword_title=keyword_title,
            keyword_company=keyword_company,
        )
        logger.info("Search completed via linkedin_client", count=len(results))
        return {
            "success": True,
            "results": results,
            "count": len(results),
            "source": "linkedin_api",
            "note": "Using cookie-based linkedin-api. Results may be limited if LinkedIn detects bot activity.",
        }
    except Exception as e:
        from linkedin_mcp.core.exceptions import format_error_response
        sources_tried.append("linkedin_api")
        errors_encountered.append(f"linkedin-api: {str(e)}")
        logger.error(
            "All search sources failed",
            error=str(e),
            sources_tried=sources_tried,
        )
        error_response = format_error_response(e)
        error_response["sources_tried"] = sources_tried
        error_response["diagnostic_info"] = {
            "fresh_data_api": "Requires Pro plan ($45/mo) for Search Lead/Company",
            "linkedin_api": "Cookie-based, subject to LinkedIn bot detection",
            "errors": errors_encountered,
        }
        return error_response


@mcp.tool()
async def search_companies(keywords: str, limit: int = 10) -> dict:
    """
    Search for companies on LinkedIn.

    Args:
        keywords: Search keywords
        limit: Maximum results to return (default: 10, max: 50)

    Returns list of matching companies.

    Search priority:
    1. Fresh Data API (requires Pro plan $45/mo for search-companies endpoint)
    2. linkedin-api (cookie-based, may be blocked by LinkedIn bot detection)
    """
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger

    logger = get_logger(__name__)
    ctx = get_context()

    limit = min(limit, 50)  # Cap at 50
    sources_tried = []
    errors_encountered = []

    logger.info("Starting company search", keywords=keywords, limit=limit)

    # Try data provider first (has comprehensive fallback chain)
    if ctx.data_provider:
        try:
            logger.debug("Trying data_provider.search_companies (Fresh Data API → linkedin-api fallback)")
            result = await ctx.data_provider.search_companies(query=keywords, limit=limit)
            source = result.get("source", "unknown")
            data = result.get("data", [])
            logger.info("Company search completed via data_provider", source=source, count=len(data))
            return {
                "success": True,
                "results": data,
                "count": len(data),
                "source": source,
            }
        except PermissionError as e:
            sources_tried.append("fresh_data_api")
            errors_encountered.append(f"Fresh Data API: {str(e)}")
            logger.info("Fresh Data API company search not available on current plan, trying linkedin_client")
        except Exception as e:
            sources_tried.append("data_provider")
            errors_encountered.append(f"Data provider: {str(e)}")
            logger.warning("Data provider company search failed, trying linkedin_client", error=str(e))
    else:
        logger.debug("data_provider not available")

    # Fall back to linkedin_client if data provider fails
    if not ctx.linkedin_client:
        logger.warning(
            "No company search sources available",
            sources_tried=sources_tried,
            errors=errors_encountered,
        )
        return {
            "error": "LinkedIn company search not available. Fresh Data API search requires Pro plan ($45/mo), and linkedin-api is not configured.",
            "sources_tried": sources_tried,
            "suggestion": "Configure linkedin-api with session cookies, or upgrade Fresh Data API to Pro plan for search capabilities.",
        }

    try:
        logger.debug("Trying linkedin_client.search_companies (cookie-based)")
        results = await ctx.linkedin_client.search_companies(keywords=keywords, limit=limit)
        logger.info("Company search completed via linkedin_client", count=len(results))
        return {
            "success": True,
            "results": results,
            "count": len(results),
            "source": "linkedin_api",
            "note": "Using cookie-based linkedin-api. Results may be limited if LinkedIn detects bot activity.",
        }
    except Exception as e:
        from linkedin_mcp.core.exceptions import format_error_response
        sources_tried.append("linkedin_api")
        errors_encountered.append(f"linkedin-api: {str(e)}")
        logger.error(
            "All company search sources failed",
            error=str(e),
            sources_tried=sources_tried,
        )
        error_response = format_error_response(e)
        error_response["sources_tried"] = sources_tried
        error_response["diagnostic_info"] = {
            "fresh_data_api": "Requires Pro plan ($45/mo) for Search Lead/Company",
            "linkedin_api": "Cookie-based, subject to LinkedIn bot detection",
            "errors": errors_encountered,
        }
        return error_response


# =============================================================================
# Job Search Tools
# =============================================================================


@mcp.tool()
async def search_jobs(
    keywords: str | None = None,
    location_name: str | None = None,
    job_type: str | None = None,
    experience: str | None = None,
    remote: str | None = None,
    distance: int | None = None,
    listed_at: int = 86400,
    limit: int = 10,
) -> dict:
    """
    Search for job postings on LinkedIn.

    Args:
        keywords: Search keywords (e.g., 'Python Developer', 'Product Manager')
        location_name: Location (e.g., 'San Francisco Bay Area', 'New York')
        job_type: Job type filter - F=Full-time, P=Part-time, C=Contract, T=Temporary, I=Internship
        experience: Experience level - 1=Internship, 2=Entry, 3=Associate, 4=Mid-Senior, 5=Director, 6=Executive
        remote: Remote options - 1=On-site, 2=Remote, 3=Hybrid
        distance: Distance from location in miles
        listed_at: Max seconds since job was posted (default: 86400 = 24 hours)
        limit: Maximum results to return (default: 10, max: 50)

    Returns list of matching job postings.

    WARNING: Uses unofficial API. May trigger LinkedIn bot detection with heavy use.
    """
    from linkedin_mcp.config.settings import get_settings
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger

    logger = get_logger(__name__)
    ctx = get_context()
    settings = get_settings()

    if not settings.features.jobs_enabled:
        return {
            "error": "Job search feature is disabled",
            "suggestion": "Set FEATURE_JOBS_ENABLED=true to enable job search tools",
        }

    if not ctx.linkedin_client:
        return {
            "error": "LinkedIn client not available. Job search requires cookie-based authentication.",
            "suggestion": "Configure linkedin-api with session cookies using: linkedin-mcp-auth extract-cookies",
        }

    limit = min(limit, 50)

    # Parse filter values into lists as expected by the API
    job_type_list = [job_type] if job_type else None
    experience_list = [experience] if experience else None
    remote_list = [remote] if remote else None

    try:
        results = await ctx.linkedin_client.search_jobs(
            keywords=keywords,
            location_name=location_name,
            job_type=job_type_list,
            experience=experience_list,
            remote=remote_list,
            distance=distance,
            listed_at=listed_at,
            limit=limit,
        )

        return {
            "success": True,
            "jobs": results,
            "count": len(results) if results else 0,
            "source": "linkedin_api",
            "note": "Uses unofficial API. Results may be limited by LinkedIn bot detection.",
        }
    except Exception as e:
        from linkedin_mcp.core.exceptions import format_error_response

        logger.error("Job search failed", error=str(e), keywords=keywords)
        return format_error_response(e)


@mcp.tool()
async def get_job(job_id: str) -> dict:
    """
    Get detailed information about a specific job posting.

    Args:
        job_id: LinkedIn job ID (from search results or job URL)

    Returns job details including description, requirements, company info, etc.

    WARNING: Uses unofficial API.
    """
    from linkedin_mcp.config.settings import get_settings
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger

    logger = get_logger(__name__)
    ctx = get_context()
    settings = get_settings()

    if not settings.features.jobs_enabled:
        return {"error": "Job search feature is disabled"}

    if not ctx.linkedin_client:
        return {"error": "LinkedIn client not available"}

    try:
        job = await ctx.linkedin_client.get_job(job_id)
        return {"success": True, "job": job, "source": "linkedin_api"}
    except Exception as e:
        from linkedin_mcp.core.exceptions import format_error_response

        logger.error("Failed to fetch job", error=str(e), job_id=job_id)
        return format_error_response(e)


@mcp.tool()
async def get_job_skills(job_id: str) -> dict:
    """
    Get skills required for a job posting.

    Args:
        job_id: LinkedIn job ID

    Returns list of required and preferred skills for the job.

    WARNING: Uses unofficial API.
    """
    from linkedin_mcp.config.settings import get_settings
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger

    logger = get_logger(__name__)
    ctx = get_context()
    settings = get_settings()

    if not settings.features.jobs_enabled:
        return {"error": "Job search feature is disabled"}

    if not ctx.linkedin_client:
        return {"error": "LinkedIn client not available"}

    try:
        skills = await ctx.linkedin_client.get_job_skills(job_id)
        return {"success": True, "skills": skills, "source": "linkedin_api"}
    except Exception as e:
        from linkedin_mcp.core.exceptions import format_error_response

        logger.error("Failed to fetch job skills", error=str(e), job_id=job_id)
        return format_error_response(e)


@mcp.tool()
async def get_profile_views() -> dict:
    """
    Get profile view statistics for the authenticated user.

    Returns profile view data including view count and viewer information
    (if available based on your LinkedIn subscription).

    WARNING: Uses unofficial API.
    """
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger

    logger = get_logger(__name__)
    ctx = get_context()

    if not ctx.linkedin_client:
        return {"error": "LinkedIn client not available"}

    try:
        views = await ctx.linkedin_client.get_current_profile_views()
        return {"success": True, "profile_views": views, "source": "linkedin_api"}
    except Exception as e:
        from linkedin_mcp.core.exceptions import format_error_response

        logger.error("Failed to fetch profile views", error=str(e))
        return format_error_response(e)


# =============================================================================
# Messaging Tools
# =============================================================================


@mcp.tool()
async def get_conversations(limit: int = 20) -> dict:
    """
    Get your LinkedIn messaging conversations.

    Args:
        limit: Maximum conversations to return (default: 20)

    Returns list of conversations with participants and last message preview.

    WARNING: Uses unofficial API. May trigger LinkedIn bot detection.
    """
    from linkedin_mcp.config.settings import get_settings
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger

    logger = get_logger(__name__)
    ctx = get_context()
    settings = get_settings()

    if not settings.features.messaging_enabled:
        return {
            "error": "Messaging feature is disabled",
            "suggestion": "Set FEATURE_MESSAGING_ENABLED=true to enable messaging tools",
        }

    if not ctx.linkedin_client:
        return {
            "error": "LinkedIn client not available. Messaging requires cookie-based authentication.",
            "suggestion": "Configure linkedin-api with session cookies using: linkedin-mcp-auth extract-cookies",
        }

    try:
        conversations = await ctx.linkedin_client.get_conversations()
        # Limit results
        limited = conversations[:limit] if conversations else []
        return {
            "success": True,
            "conversations": limited,
            "count": len(limited),
            "total_available": len(conversations) if conversations else 0,
            "source": "linkedin_api",
            "note": "Uses unofficial API. May trigger bot detection with frequent access.",
        }
    except Exception as e:
        from linkedin_mcp.core.exceptions import format_error_response

        logger.error("Failed to fetch conversations", error=str(e))
        return format_error_response(e)


@mcp.tool()
async def get_conversation(conversation_id: str) -> dict:
    """
    Get full message history for a specific conversation.

    Args:
        conversation_id: Conversation ID (from get_conversations results)

    Returns conversation details with full message history.

    WARNING: Uses unofficial API.
    """
    from linkedin_mcp.config.settings import get_settings
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger

    logger = get_logger(__name__)
    ctx = get_context()
    settings = get_settings()

    if not settings.features.messaging_enabled:
        return {"error": "Messaging feature is disabled"}

    if not ctx.linkedin_client:
        return {"error": "LinkedIn client not available"}

    try:
        conversation = await ctx.linkedin_client.get_conversation(conversation_id)
        return {
            "success": True,
            "conversation": conversation,
            "source": "linkedin_api",
        }
    except Exception as e:
        from linkedin_mcp.core.exceptions import format_error_response

        logger.error("Failed to fetch conversation", error=str(e), conversation_id=conversation_id)
        return format_error_response(e)


@mcp.tool()
async def get_conversation_details(profile_id: str) -> dict:
    """
    Get conversation ID and details for a specific profile.

    Useful for finding the conversation ID to send a message to someone.

    Args:
        profile_id: LinkedIn profile ID or URN

    Returns conversation details including conversation ID.

    WARNING: Uses unofficial API.
    """
    from linkedin_mcp.config.settings import get_settings
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger

    logger = get_logger(__name__)
    ctx = get_context()
    settings = get_settings()

    if not settings.features.messaging_enabled:
        return {"error": "Messaging feature is disabled"}

    if not ctx.linkedin_client:
        return {"error": "LinkedIn client not available"}

    try:
        details = await ctx.linkedin_client.get_conversation_details(profile_id)
        return {
            "success": True,
            "conversation_details": details,
            "source": "linkedin_api",
        }
    except Exception as e:
        from linkedin_mcp.core.exceptions import format_error_response

        logger.error("Failed to fetch conversation details", error=str(e), profile_id=profile_id)
        return format_error_response(e)


@mcp.tool()
async def send_message(recipients: list[str], text: str) -> dict:
    """
    Send a LinkedIn message to one or more recipients.

    Args:
        recipients: List of LinkedIn profile public IDs (e.g., ['john-doe', 'jane-smith'])
        text: Message content to send

    Returns success status and message details.

    WARNING: Uses unofficial API. May trigger LinkedIn bot detection.
    Sending too many messages may result in account restrictions.
    Use responsibly and respect LinkedIn's terms of service.
    """
    from linkedin_mcp.config.settings import get_settings
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger

    logger = get_logger(__name__)
    ctx = get_context()
    settings = get_settings()

    if not settings.features.messaging_enabled:
        return {
            "error": "Messaging feature is disabled",
            "suggestion": "Set FEATURE_MESSAGING_ENABLED=true to enable messaging tools",
        }

    if not ctx.linkedin_client:
        return {"error": "LinkedIn client not available"}

    if not recipients:
        return {"error": "At least one recipient is required"}

    if not text or not text.strip():
        return {"error": "Message text cannot be empty"}

    try:
        result = await ctx.linkedin_client.send_message(recipients, text)
        return {
            **result,
            "source": "linkedin_api",
            "warning": "Message sent via unofficial API. Use responsibly to avoid account restrictions.",
        }
    except Exception as e:
        from linkedin_mcp.core.exceptions import format_error_response

        logger.error("Failed to send message", error=str(e), recipient_count=len(recipients))
        return format_error_response(e)


@mcp.tool()
async def mark_conversation_as_seen(conversation_urn: str) -> dict:
    """
    Mark a conversation as read/seen.

    Args:
        conversation_urn: Conversation URN ID

    Returns success status.

    WARNING: Uses unofficial API.
    """
    from linkedin_mcp.config.settings import get_settings
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger

    logger = get_logger(__name__)
    ctx = get_context()
    settings = get_settings()

    if not settings.features.messaging_enabled:
        return {"error": "Messaging feature is disabled"}

    if not ctx.linkedin_client:
        return {"error": "LinkedIn client not available"}

    try:
        result = await ctx.linkedin_client.mark_conversation_as_seen(conversation_urn)
        return {**result, "source": "linkedin_api"}
    except Exception as e:
        from linkedin_mcp.core.exceptions import format_error_response

        logger.error("Failed to mark conversation as seen", error=str(e))
        return format_error_response(e)


# =============================================================================
# Connection Tools
# =============================================================================


@mcp.tool()
async def get_invitations(limit: int = 50) -> dict:
    """
    Get pending connection invitations you've received.

    Args:
        limit: Maximum invitations to return (default: 50)

    Returns list of pending invitations with sender info.

    Note: LinkedIn API only supports fetching received invitations.
    Sent invitations are not available through this endpoint.

    WARNING: Uses unofficial API.
    """
    from linkedin_mcp.config.settings import get_settings
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger

    logger = get_logger(__name__)
    ctx = get_context()
    settings = get_settings()

    if not settings.features.connections_enabled:
        return {
            "error": "Connections feature is disabled",
            "suggestion": "Set FEATURE_CONNECTIONS_ENABLED=true to enable connection tools",
        }

    if not ctx.linkedin_client:
        return {"error": "LinkedIn client not available"}

    try:
        invitations = await ctx.linkedin_client.get_pending_invitations(limit=limit)
        return {
            "success": True,
            "invitations": invitations,
            "count": len(invitations) if invitations else 0,
            "type": "received",
            "source": "linkedin_api",
            "note": "Only received invitations are available. Sent invitations not supported by API.",
        }
    except Exception as e:
        from linkedin_mcp.core.exceptions import format_error_response

        logger.error("Failed to fetch invitations", error=str(e))
        return format_error_response(e)


@mcp.tool()
async def send_connection_request(profile_id: str, message: str | None = None) -> dict:
    """
    Send a connection request to a LinkedIn profile.

    Args:
        profile_id: LinkedIn profile public ID (e.g., 'john-doe')
        message: Optional personalized message (max ~300 characters)

    Returns success status and request details.

    WARNING: Uses unofficial API. May trigger LinkedIn bot detection.
    LinkedIn limits connection requests. Use responsibly.
    """
    from linkedin_mcp.config.settings import get_settings
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger

    logger = get_logger(__name__)
    ctx = get_context()
    settings = get_settings()

    if not settings.features.connections_enabled:
        return {
            "error": "Connections feature is disabled",
            "suggestion": "Set FEATURE_CONNECTIONS_ENABLED=true to enable connection tools",
        }

    if not ctx.linkedin_client:
        return {"error": "LinkedIn client not available"}

    try:
        result = await ctx.linkedin_client.send_connection_request(profile_id, message=message)
        return {
            **result,
            "source": "linkedin_api",
            "warning": "Connection request sent via unofficial API. LinkedIn limits daily connection requests.",
        }
    except Exception as e:
        from linkedin_mcp.core.exceptions import format_error_response

        logger.error("Failed to send connection request", error=str(e), profile_id=profile_id)
        return format_error_response(e)


@mcp.tool()
async def reply_invitation(invitation_id: str, shared_secret: str, action: str = "accept") -> dict:
    """
    Accept or reject a connection invitation.

    Args:
        invitation_id: Invitation ID (from get_invitations results)
        shared_secret: Shared secret (from get_invitations results)
        action: 'accept' or 'reject'

    Returns success status.

    WARNING: Uses unofficial API.
    """
    from linkedin_mcp.config.settings import get_settings
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger

    logger = get_logger(__name__)
    ctx = get_context()
    settings = get_settings()

    if not settings.features.connections_enabled:
        return {"error": "Connections feature is disabled"}

    if not ctx.linkedin_client:
        return {"error": "LinkedIn client not available"}

    if action not in ("accept", "reject"):
        return {"error": "Action must be 'accept' or 'reject'"}

    try:
        if action == "accept":
            result = await ctx.linkedin_client.accept_invitation(invitation_id, shared_secret)
        else:
            result = await ctx.linkedin_client.reject_invitation(invitation_id, shared_secret)

        return {**result, "action": action, "source": "linkedin_api"}
    except Exception as e:
        from linkedin_mcp.core.exceptions import format_error_response

        logger.error("Failed to reply to invitation", error=str(e), action=action)
        return format_error_response(e)


@mcp.tool()
async def remove_connection(profile_id: str) -> dict:
    """
    Remove an existing LinkedIn connection.

    Args:
        profile_id: LinkedIn profile public ID of the connection to remove

    Returns success status.

    WARNING: This action is IRREVERSIBLE. The person will need to re-request
    connection and you'll need to accept. Uses unofficial API.
    """
    from linkedin_mcp.config.settings import get_settings
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger

    logger = get_logger(__name__)
    ctx = get_context()
    settings = get_settings()

    if not settings.features.connections_enabled:
        return {"error": "Connections feature is disabled"}

    if not ctx.linkedin_client:
        return {"error": "LinkedIn client not available"}

    try:
        result = await ctx.linkedin_client.remove_connection(profile_id)
        return {
            **result,
            "source": "linkedin_api",
            "warning": "Connection removed. This action is irreversible.",
        }
    except Exception as e:
        from linkedin_mcp.core.exceptions import format_error_response

        logger.error("Failed to remove connection", error=str(e), profile_id=profile_id)
        return format_error_response(e)


# =============================================================================
# Company Tools
# =============================================================================


@mcp.tool()
async def get_company(public_id: str) -> dict:
    """
    Get detailed company information.

    Args:
        public_id: Company's public identifier (URL slug, e.g., 'microsoft')

    Returns company details including description, industry, employee count, etc.
    """
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger

    logger = get_logger(__name__)
    ctx = get_context()

    # Try data provider first (uses marketing API with fallback chain)
    if ctx.has_data_provider:
        try:
            company = await ctx.data_provider.get_organization(vanity_name=public_id)
            if company:
                return {"success": True, "company": company, "source": "data_provider"}
        except Exception as e:
            logger.debug("Data provider failed for company lookup, trying fallback", error=str(e))

    # Fall back to unofficial client
    if not ctx.linkedin_client:
        return {"error": "No LinkedIn client available for company lookup"}

    try:
        company = await ctx.linkedin_client.get_company(public_id)
        return {"success": True, "company": company, "source": "linkedin_client"}
    except Exception as e:
        from linkedin_mcp.core.exceptions import format_error_response
        logger.error("Failed to fetch company", error=str(e), public_id=public_id)
        return format_error_response(e)


@mcp.tool()
async def get_company_updates(public_id: str, limit: int = 10) -> dict:
    """
    Get recent posts/updates from a company page.

    Args:
        public_id: Company's public identifier (URL slug)
        limit: Maximum updates to return (default: 10, max: 50)

    Returns list of company posts/updates.
    """
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger

    logger = get_logger(__name__)
    ctx = get_context()

    limit = min(limit, 50)

    try:
        # Use data_provider with full fallback chain (PND → Fresh Data → Enhanced → Headless → Primary)
        if ctx.data_provider:
            result = await ctx.data_provider.get_company_posts(public_id, limit=limit)
            updates = result.get("posts", result.get("updates", result.get("data", [])))
            source = result.get("source", "data_provider")
            return {
                "success": True,
                "updates": updates,
                "count": len(updates),
                "source": source,
            }

        return {"error": "No LinkedIn data provider available. Configure API credentials."}
    except Exception as e:
        logger.error("Failed to fetch company updates", error=str(e), public_id=public_id)
        return {"error": str(e)}


@mcp.tool()
async def get_organization_followers(organization_id: str) -> dict:
    """
    Get follower count for an organization using the Community Management API.

    This tool uses the official LinkedIn Community Management API which provides
    accurate follower counts for organizations you have admin access to.

    Args:
        organization_id: LinkedIn organization URN ID (numeric, e.g., '12345678')

    Returns follower count and organization details.

    Note: Requires Community Management API access and admin permissions for the organization.
    """
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger

    logger = get_logger(__name__)
    ctx = get_context()

    # This requires the marketing client (Community Management API)
    if ctx.has_data_provider:
        try:
            result = await ctx.data_provider.get_organization_follower_count(organization_id)
            if result:
                return {
                    "success": True,
                    "organization_id": organization_id,
                    "follower_count": result.get("firstDegreeSize", 0),
                    "raw_data": result,
                    "source": "community_management_api",
                }
        except Exception as e:
            logger.warning(
                "Community Management API failed for follower count",
                error=str(e),
                organization_id=organization_id,
            )

    return {
        "error": "Community Management API not available or organization not accessible",
        "hint": "Ensure you have admin access to this organization and the Marketing API is configured.",
    }


# =============================================================================
# Lead Generation Tools
# =============================================================================

# Note: get_profile_contact_info and get_profile_skills are defined in Profile Tools section


@mcp.tool()
async def get_school(public_id: str) -> dict:
    """
    Get school/university information.

    Args:
        public_id: School's public identifier (URL slug)

    Returns school details including name, description, follower count, etc.
    """
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger

    logger = get_logger(__name__)
    ctx = get_context()

    if not ctx.linkedin_client:
        return {"error": "LinkedIn client not initialized"}

    try:
        school = await ctx.linkedin_client.get_school(public_id)
        return {"success": True, "school": school}
    except Exception as e:
        logger.error("Failed to fetch school", error=str(e), public_id=public_id)
        return {"error": str(e)}


# =============================================================================
# Analytics Tools
# =============================================================================


@mcp.tool()
async def get_post_analytics(post_urn: str) -> dict:
    """
    Get analytics for a specific post.

    Args:
        post_urn: LinkedIn post URN

    Returns engagement metrics including reactions, comments, and shares.
    Note: View count requires Partner API access.
    """
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger

    logger = get_logger(__name__)
    ctx = get_context()

    if not ctx.linkedin_client:
        return {"error": "LinkedIn client not initialized"}

    try:
        # Get reactions
        reactions = await ctx.linkedin_client.get_post_reactions(post_urn)

        # Get comments
        comments = await ctx.linkedin_client.get_post_comments(post_urn)

        # Categorize reactions
        reaction_breakdown = {}
        for reaction in reactions:
            reaction_type = reaction.get("reactionType", "LIKE")
            reaction_breakdown[reaction_type] = reaction_breakdown.get(reaction_type, 0) + 1

        return {
            "success": True,
            "analytics": {
                "post_urn": post_urn,
                "total_reactions": len(reactions),
                "total_comments": len(comments),
                "reaction_breakdown": reaction_breakdown,
                "note": "View count requires Partner API access",
            },
        }
    except Exception as e:
        logger.error("Failed to fetch analytics", error=str(e), post_urn=post_urn)
        return {"error": str(e)}


@mcp.tool()
async def get_rate_limit_status() -> dict:
    """
    Get current rate limit status.

    Returns remaining API calls and rate limit information.
    """
    from linkedin_mcp.core.context import get_context

    ctx = get_context()

    if not ctx.linkedin_client:
        return {"error": "LinkedIn client not initialized"}

    return {
        "success": True,
        "rate_limit": {
            "remaining": ctx.linkedin_client.rate_limit_remaining,
            "max_per_hour": 900,
            "note": "Rate limits are advisory. Excessive requests may trigger LinkedIn restrictions.",
        },
    }


@mcp.tool()
async def analyze_engagement(post_urn: str, follower_count: int | None = None) -> dict:
    """
    Perform deep engagement analysis on a specific post.

    Args:
        post_urn: LinkedIn post URN
        follower_count: Author's follower count for rate calculation (optional)

    Returns comprehensive engagement metrics, reaction distribution, and quality score.
    """
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger
    from linkedin_mcp.services.analytics import get_engagement_analyzer

    logger = get_logger(__name__)
    ctx = get_context()
    analyzer = get_engagement_analyzer()

    try:
        # Use data_provider with full fallback chain (PND → Fresh Data → Enhanced → Headless → Primary)
        if not ctx.data_provider:
            return {"error": "No LinkedIn data provider available. Configure API credentials."}

        # Get reactions via data_provider
        # data_provider returns: {"data": {"reactors": [...], ...}, "source": "..."}
        reactions_result = await ctx.data_provider.get_post_reactions(post_urn)
        data = reactions_result.get("data", {})
        reactions = data.get("reactors", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
        source = reactions_result.get("source", "data_provider")

        # Get comments via data_provider
        # data_provider returns: {"data": {"comments": [...], ...}, "source": "..."}
        comments_result = await ctx.data_provider.get_post_comments(post_urn)
        data = comments_result.get("data", {})
        comments = data.get("comments", data.get("data", [])) if isinstance(data, dict) else (data if isinstance(data, list) else [])

        # Analyze engagement rate
        engagement_metrics = analyzer.calculate_engagement_rate(
            reactions=len(reactions),
            comments=len(comments),
            shares=0,  # Share count not available via unofficial API
            views=None,  # Requires Partner API
            follower_count=follower_count,
        )

        # Analyze reaction distribution
        reaction_analysis = analyzer.analyze_reaction_distribution(reactions)

        return {
            "success": True,
            "post_urn": post_urn,
            "engagement": engagement_metrics,
            "reactions": reaction_analysis,
            "comments_count": len(comments),
            "source": source,
        }
    except Exception as e:
        logger.error("Failed to analyze engagement", error=str(e), post_urn=post_urn)
        return {"error": str(e)}


@mcp.tool()
async def analyze_content_performance(profile_id: str, post_limit: int = 20) -> dict:
    """
    Analyze content performance patterns for a profile.

    Args:
        profile_id: LinkedIn public ID
        post_limit: Number of posts to analyze (default: 20, max: 50)

    Returns content analysis with type distribution, engagement patterns, and recommendations.
    """
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger
    from linkedin_mcp.services.analytics import get_content_analyzer

    logger = get_logger(__name__)
    ctx = get_context()
    analyzer = get_content_analyzer()

    post_limit = min(post_limit, 50)

    try:
        # Use data_provider with full fallback chain (PND → Fresh Data → Enhanced → Headless → Primary)
        if not ctx.data_provider:
            return {"error": "No LinkedIn data provider available. Configure API credentials."}

        result = await ctx.data_provider.get_profile_posts(profile_id, limit=post_limit)
        posts = result.get("posts", result.get("data", []))
        source = result.get("source", "data_provider")

        if not posts:
            return {"success": True, "message": "No posts found for analysis"}

        analysis = analyzer.analyze_posts_performance(posts)

        return {
            "success": True,
            "profile_id": profile_id,
            "analysis": analysis,
            "source": source,
        }
    except Exception as e:
        logger.error("Failed to analyze content", error=str(e), profile_id=profile_id)
        return {"error": str(e)}


@mcp.tool()
async def analyze_optimal_posting_times(profile_id: str, post_limit: int = 30) -> dict:
    """
    Analyze optimal posting times based on engagement patterns.

    Args:
        profile_id: LinkedIn public ID
        post_limit: Number of posts to analyze (default: 30, max: 50)

    Returns optimal posting times by hour and day with engagement averages.
    """
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger
    from linkedin_mcp.services.analytics import get_posting_time_analyzer

    logger = get_logger(__name__)
    ctx = get_context()
    analyzer = get_posting_time_analyzer()

    post_limit = min(post_limit, 50)

    try:
        # Use data_provider with full fallback chain (PND → Fresh Data → Enhanced → Headless → Primary)
        if not ctx.data_provider:
            return {"error": "No LinkedIn data provider available. Configure API credentials."}

        result = await ctx.data_provider.get_profile_posts(profile_id, limit=post_limit)
        posts = result.get("posts", result.get("data", []))
        source = result.get("source", "data_provider")

        if not posts:
            return {"success": True, "message": "No posts found for analysis"}

        analysis = analyzer.analyze_posting_patterns(posts)

        return {
            "success": True,
            "profile_id": profile_id,
            "posting_analysis": analysis,
            "source": source,
        }
    except Exception as e:
        logger.error("Failed to analyze posting times", error=str(e), profile_id=profile_id)
        return {"error": str(e)}


@mcp.tool()
async def analyze_post_audience(post_urn: str) -> dict:
    """
    Analyze the audience engaging with a specific post.

    Args:
        post_urn: LinkedIn post URN

    Returns audience demographics based on commenters' profiles.
    """
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger
    from linkedin_mcp.services.analytics import get_audience_analyzer

    logger = get_logger(__name__)
    ctx = get_context()
    analyzer = get_audience_analyzer()

    try:
        # Use data_provider with full fallback chain (PND → Fresh Data → Enhanced → Headless → Primary)
        if not ctx.data_provider:
            return {"error": "No LinkedIn data provider available. Configure API credentials."}

        result = await ctx.data_provider.get_post_comments(post_urn)
        comments = result.get("comments", result.get("data", []))
        source = result.get("source", "data_provider")

        if not comments:
            return {"success": True, "message": "No comments to analyze"}

        analysis = analyzer.analyze_commenters(comments)

        return {
            "success": True,
            "post_urn": post_urn,
            "audience_analysis": analysis,
            "source": source,
        }
    except Exception as e:
        logger.error("Failed to analyze audience", error=str(e), post_urn=post_urn)
        return {"error": str(e)}


@mcp.tool()
async def analyze_hashtag_performance(profile_id: str, post_limit: int = 30) -> dict:
    """
    Analyze hashtag usage and performance.

    Args:
        profile_id: LinkedIn public ID
        post_limit: Number of posts to analyze (default: 30, max: 50)

    Returns hashtag frequency, engagement correlation, and recommendations.
    """
    from collections import Counter

    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger
    from linkedin_mcp.services.analytics import get_content_analyzer

    logger = get_logger(__name__)
    ctx = get_context()
    analyzer = get_content_analyzer()

    post_limit = min(post_limit, 50)

    try:
        # Use data_provider with full fallback chain (PND → Fresh Data → Enhanced → Headless → Primary)
        if not ctx.data_provider:
            return {"error": "No LinkedIn data provider available. Configure API credentials."}

        result = await ctx.data_provider.get_profile_posts(profile_id, limit=post_limit)
        posts = result.get("posts", result.get("data", []))
        source = result.get("source", "data_provider")

        if not posts:
            return {"success": True, "message": "No posts found for analysis"}

        # Analyze hashtags and their engagement
        hashtag_engagement: dict[str, list[int]] = {}
        posts_with_hashtags = 0
        posts_without_hashtags = 0
        engagement_with_hashtags: list[int] = []
        engagement_without_hashtags: list[int] = []

        for post in posts:
            content = post.get("commentary", post.get("text", ""))
            hashtags = analyzer.extract_hashtags(content)

            reactions = post.get("numLikes", 0) or 0
            comments = post.get("numComments", 0) or 0
            total_engagement = reactions + comments

            if hashtags:
                posts_with_hashtags += 1
                engagement_with_hashtags.append(total_engagement)
                for tag in hashtags:
                    if tag not in hashtag_engagement:
                        hashtag_engagement[tag] = []
                    hashtag_engagement[tag].append(total_engagement)
            else:
                posts_without_hashtags += 1
                engagement_without_hashtags.append(total_engagement)

        # Calculate averages per hashtag
        hashtag_performance = {}
        for tag, engagements in hashtag_engagement.items():
            hashtag_performance[tag] = {
                "uses": len(engagements),
                "avg_engagement": round(sum(engagements) / len(engagements), 1),
            }

        # Sort by average engagement
        top_hashtags = sorted(
            hashtag_performance.items(),
            key=lambda x: x[1]["avg_engagement"],
            reverse=True,
        )[:10]

        # Compare hashtag vs no-hashtag performance
        avg_with = round(sum(engagement_with_hashtags) / len(engagement_with_hashtags), 1) if engagement_with_hashtags else 0
        avg_without = round(sum(engagement_without_hashtags) / len(engagement_without_hashtags), 1) if engagement_without_hashtags else 0

        recommendations = []
        if avg_with > avg_without:
            recommendations.append(f"Posts with hashtags perform {round(avg_with/avg_without if avg_without else 1, 1)}x better")
        if top_hashtags:
            recommendations.append(f"Best performing hashtags: #{top_hashtags[0][0]}")

        return {
            "success": True,
            "profile_id": profile_id,
            "hashtag_analysis": {
                "posts_with_hashtags": posts_with_hashtags,
                "posts_without_hashtags": posts_without_hashtags,
                "avg_engagement_with_hashtags": avg_with,
                "avg_engagement_without_hashtags": avg_without,
                "top_performing_hashtags": dict(top_hashtags),
                "all_hashtags": dict(Counter(
                    tag for post in posts
                    for tag in analyzer.extract_hashtags(post.get("commentary", post.get("text", "")))
                ).most_common(20)),
            },
            "recommendations": recommendations,
            "source": source,
        }
    except Exception as e:
        logger.error("Failed to analyze hashtags", error=str(e), profile_id=profile_id)
        return {"error": str(e)}


@mcp.tool()
async def generate_engagement_report(profile_id: str, post_limit: int = 20) -> dict:
    """
    Generate a comprehensive engagement report for a profile.

    Args:
        profile_id: LinkedIn public ID
        post_limit: Number of posts to analyze (default: 20)

    Returns a full engagement report with content analysis, timing, and recommendations.
    """
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger
    from linkedin_mcp.services.analytics import (
        get_content_analyzer,
        get_engagement_analyzer,
        get_posting_time_analyzer,
    )

    logger = get_logger(__name__)
    ctx = get_context()
    engagement_analyzer = get_engagement_analyzer()
    content_analyzer = get_content_analyzer()
    posting_analyzer = get_posting_time_analyzer()

    post_limit = min(post_limit, 50)

    try:
        # Use data_provider with full fallback chain (PND → Fresh Data → Enhanced → Headless → Primary)
        if not ctx.data_provider:
            return {"error": "No LinkedIn data provider available. Configure API credentials."}

        # Get profile via data_provider
        profile_result = await ctx.data_provider.get_profile(profile_id)
        profile = profile_result.get("profile", profile_result.get("data", profile_result))
        source = profile_result.get("source", "data_provider")

        # Get posts via data_provider
        posts_result = await ctx.data_provider.get_profile_posts(profile_id, limit=post_limit)
        posts = posts_result.get("posts", posts_result.get("data", []))

        if not profile:
            return {"error": "Could not retrieve profile data."}

        if not posts:
            return {"success": True, "message": "No posts found for report"}

        # Aggregate engagement
        total_reactions = 0
        total_comments = 0

        for post in posts:
            total_reactions += post.get("numLikes", 0) or 0
            total_comments += post.get("numComments", 0) or 0

        avg_reactions = round(total_reactions / len(posts), 1)
        avg_comments = round(total_comments / len(posts), 1)

        # Run analyses
        content_analysis = content_analyzer.analyze_posts_performance(posts)
        timing_analysis = posting_analyzer.analyze_posting_patterns(posts)

        # Calculate overall engagement rate
        follower_count = profile.get("followerCount", profile.get("numFollowers"))
        overall_engagement = engagement_analyzer.calculate_engagement_rate(
            reactions=total_reactions,
            comments=total_comments,
            shares=0,
            follower_count=follower_count,
        )

        return {
            "success": True,
            "report": {
                "profile": {
                    "id": profile_id,
                    "name": f"{profile.get('firstName', '')} {profile.get('lastName', '')}".strip(),
                    "headline": profile.get("headline", ""),
                    "followers": follower_count,
                },
                "summary": {
                    "posts_analyzed": len(posts),
                    "total_reactions": total_reactions,
                    "total_comments": total_comments,
                    "avg_reactions_per_post": avg_reactions,
                    "avg_comments_per_post": avg_comments,
                    "overall_engagement": overall_engagement,
                },
                "content_analysis": content_analysis,
                "timing_analysis": timing_analysis,
                "recommendations": content_analysis.get("recommendations", [])
                + timing_analysis.get("recommended_posting_times", []),
            },
            "source": source,
        }
    except Exception as e:
        logger.error("Failed to generate report", error=str(e), profile_id=profile_id)
        return {"error": str(e)}


# =============================================================================
# Content Intelligence Tools (Official API)
# =============================================================================
# These tools use the Official LinkedIn API with r_member_postAnalytics scope
# for accurate analytics on the authenticated user's own content.


@mcp.tool()
async def get_my_posts(count: int = 50) -> dict:
    """
    Get your own LinkedIn posts.

    Uses the data provider to retrieve your authored posts with metadata.
    Returns post URNs that can be used with get_my_post_analytics.

    Args:
        count: Number of posts to retrieve (max 100)

    Returns list of your posts with URNs, content, and timestamps.
    """
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger

    logger = get_logger(__name__)
    ctx = get_context()

    if not ctx.data_provider:
        return {"error": "No LinkedIn data provider available. Configure API credentials."}

    count = min(count, 100)

    try:
        # Get profile ID via official API first (more reliable), fallback to data_provider
        profile_id = None
        if ctx.official_client:
            try:
                official_profile = ctx.official_client.get_my_profile()
                if official_profile:
                    profile_id = official_profile.get("public_id") or official_profile.get("publicIdentifier")
            except Exception:
                pass

        if not profile_id:
            my_profile = await ctx.data_provider.get_own_profile()
            if my_profile:
                profile_id = my_profile.get("public_id") or my_profile.get("publicIdentifier")
        if not profile_id:
            return {"error": "Could not determine your profile ID"}

        # Get posts using the data provider
        result = await ctx.data_provider.get_profile_posts(profile_id, limit=count)
        posts = result.get("posts", result.get("data", []))
        source = result.get("source", "data_provider")

        # Format posts for output
        formatted_posts = []
        for post in posts:
            # Extract URN - may be in different formats
            urn = post.get("urn") or post.get("entityUrn") or post.get("id")

            formatted_posts.append({
                "urn": urn,
                "text": (post.get("commentary", "") or post.get("text", ""))[:500],
                "reactions": post.get("numLikes", 0) or post.get("socialDetail", {}).get("totalSocialActivityCounts", {}).get("numLikes", 0),
                "comments": post.get("numComments", 0) or post.get("socialDetail", {}).get("totalSocialActivityCounts", {}).get("numComments", 0),
                "created_at": post.get("createdAt") or post.get("postedAt"),
                "has_media": bool(post.get("content") or post.get("image") or post.get("video")),
            })

        return {
            "success": True,
            "posts": formatted_posts,
            "count": len(formatted_posts),
            "source": source,
            "note": "Use get_my_post_analytics with the URNs to get official impression data",
        }

    except Exception as e:
        logger.error("Failed to get my posts", error=str(e))
        return {"error": str(e)}


@mcp.tool()
async def get_my_post_analytics(post_urns: list[str] | None = None, limit: int = 10) -> dict:
    """
    Get analytics for your own posts using the Official API.

    Uses the r_member_postAnalytics scope (Community Management API) to get
    accurate impression counts, engagement metrics, and reach data.

    Args:
        post_urns: List of specific post URNs to analyze. If not provided,
                   will fetch your recent posts automatically.
        limit: If no URNs provided, analyze this many recent posts (default: 10)

    Returns analytics including impressions, reactions, comments, shares, and engagement rate.
    """
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger
    from linkedin_mcp.services.linkedin.analytics_client import LinkedInAnalyticsClient
    from linkedin_mcp.services.storage.token_storage import get_official_token

    logger = get_logger(__name__)
    ctx = get_context()

    # Get OAuth token
    token_data = get_official_token()
    if not token_data or token_data.is_expired:
        return {
            "error": "OAuth token not available or expired. Run: linkedin-mcp-auth oauth --force --community-management"
        }

    # Check for analytics scope
    if "r_member_postAnalytics" not in token_data.scopes:
        return {
            "error": "Missing r_member_postAnalytics scope. Re-authenticate with: linkedin-mcp-auth oauth --force --community-management"
        }

    try:
        # If no URNs provided, get recent posts via data provider
        if not post_urns:
            if not ctx.data_provider:
                return {"error": "Provide post_urns or configure data provider to fetch posts automatically"}

            # Get profile ID via official API first, fallback to data_provider
            profile_id = None
            if ctx.official_client:
                try:
                    official_profile = ctx.official_client.get_my_profile()
                    if official_profile:
                        profile_id = official_profile.get("public_id") or official_profile.get("publicIdentifier")
                except Exception:
                    pass

            if not profile_id:
                my_profile = await ctx.data_provider.get_own_profile()
                if my_profile:
                    profile_id = my_profile.get("public_id") or my_profile.get("publicIdentifier")

            if not profile_id:
                return {"error": "Could not retrieve your profile. Please provide post_urns directly."}

            result = await ctx.data_provider.get_profile_posts(profile_id, limit=limit)
            posts = result.get("posts", result.get("data", []))

            # Extract URNs
            post_urns = []
            for post in posts:
                urn = post.get("urn") or post.get("entityUrn") or post.get("id")
                if urn:
                    post_urns.append(urn)

        if not post_urns:
            return {"success": True, "message": "No posts found to analyze"}

        # Get analytics from official API
        client = LinkedInAnalyticsClient(access_token=token_data.access_token)
        analytics = client.get_post_analytics(post_urns)

        return {
            "success": True,
            "analytics": analytics,
            "posts_analyzed": len(analytics),
            "post_urns_checked": post_urns,
        }

    except Exception as e:
        logger.error("Failed to get post analytics", error=str(e))
        return {"error": str(e)}


@mcp.tool()
async def analyze_my_content_performance(post_limit: int = 30) -> dict:
    """
    Analyze your content performance comprehensively.

    Provides detailed analysis of your posting patterns, engagement metrics,
    best performing content types, and optimal posting times.

    Args:
        post_limit: Number of posts to analyze (default: 30, max: 50)

    Returns detailed performance analysis with content breakdown, timing insights, and recommendations.
    """
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger
    from linkedin_mcp.services.analytics import (
        get_content_analyzer,
        get_engagement_analyzer,
        get_posting_time_analyzer,
    )

    logger = get_logger(__name__)
    ctx = get_context()

    if not ctx.data_provider:
        return {"error": "No LinkedIn data provider available. Configure API credentials."}

    post_limit = min(post_limit, 50)

    try:
        # Get profile ID via official API first, fallback to data_provider
        profile_id = None
        if ctx.official_client:
            try:
                official_profile = ctx.official_client.get_my_profile()
                if official_profile:
                    profile_id = official_profile.get("public_id") or official_profile.get("publicIdentifier")
            except Exception:
                pass

        if not profile_id:
            my_profile = await ctx.data_provider.get_own_profile()
            if my_profile:
                profile_id = my_profile.get("public_id") or my_profile.get("publicIdentifier")

        if not profile_id:
            return {"error": "Could not determine your profile ID"}

        # Get your posts
        result = await ctx.data_provider.get_profile_posts(profile_id, limit=post_limit)
        posts = result.get("posts", result.get("data", []))
        source = result.get("source", "data_provider")

        if not posts:
            return {"success": True, "message": "No posts found for analysis"}

        # Run analyses
        content_analyzer = get_content_analyzer()
        posting_analyzer = get_posting_time_analyzer()
        engagement_analyzer = get_engagement_analyzer()

        content_analysis = content_analyzer.analyze_posts_performance(posts)
        timing_analysis = posting_analyzer.analyze_posting_patterns(posts)

        # Aggregate engagement
        total_reactions = sum(p.get("numLikes", 0) or 0 for p in posts)
        total_comments = sum(p.get("numComments", 0) or 0 for p in posts)

        return {
            "success": True,
            "analysis": {
                "posts_analyzed": len(posts),
                "total_reactions": total_reactions,
                "total_comments": total_comments,
                "avg_reactions_per_post": round(total_reactions / len(posts), 1) if posts else 0,
                "avg_comments_per_post": round(total_comments / len(posts), 1) if posts else 0,
                "content_analysis": content_analysis,
                "timing_analysis": timing_analysis,
            },
            "source": source,
        }

    except Exception as e:
        logger.error("Failed to analyze content performance", error=str(e))
        return {"error": str(e)}


@mcp.tool()
async def get_my_posting_recommendations(post_limit: int = 30) -> dict:
    """
    Get personalized posting recommendations based on your content performance.

    Analyzes your posting history to provide data-driven recommendations
    on content types, timing, and engagement strategies.

    Args:
        post_limit: Number of posts to analyze for recommendations (default: 30)

    Returns recommendations prioritized by potential impact.
    """
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger
    from linkedin_mcp.services.analytics import (
        get_content_analyzer,
        get_posting_time_analyzer,
    )

    logger = get_logger(__name__)
    ctx = get_context()

    if not ctx.data_provider:
        return {"error": "No LinkedIn data provider available. Configure API credentials."}

    post_limit = min(post_limit, 50)

    try:
        # Get profile ID via official API first, fallback to data_provider
        profile_id = None
        if ctx.official_client:
            try:
                official_profile = ctx.official_client.get_my_profile()
                if official_profile:
                    profile_id = official_profile.get("public_id") or official_profile.get("publicIdentifier")
            except Exception:
                pass

        if not profile_id:
            my_profile = await ctx.data_provider.get_own_profile()
            if my_profile:
                profile_id = my_profile.get("public_id") or my_profile.get("publicIdentifier")

        if not profile_id:
            return {"error": "Could not determine your profile ID"}

        # Get your posts
        result = await ctx.data_provider.get_profile_posts(profile_id, limit=post_limit)
        posts = result.get("posts", result.get("data", []))

        if not posts or len(posts) < 5:
            return {
                "success": True,
                "message": f"Need at least 5 posts for recommendations. Found {len(posts) if posts else 0}.",
            }

        # Analyze content and timing
        content_analyzer = get_content_analyzer()
        posting_analyzer = get_posting_time_analyzer()

        content_analysis = content_analyzer.analyze_posts_performance(posts)
        timing_analysis = posting_analyzer.analyze_posting_patterns(posts)

        recommendations = []

        # Content type recommendations
        if content_analysis.get("recommendations"):
            recommendations.extend(content_analysis["recommendations"])

        # Timing recommendations
        if timing_analysis.get("recommended_posting_times"):
            for time_rec in timing_analysis["recommended_posting_times"][:3]:
                recommendations.append({
                    "type": "timing",
                    "recommendation": f"Post on {time_rec.get('day', 'weekdays')} around {time_rec.get('hour', 'morning')}",
                    "reason": "Based on your historical engagement patterns",
                })

        # Engagement insights
        total_engagement = sum((p.get("numLikes", 0) or 0) + (p.get("numComments", 0) or 0) for p in posts)
        avg_engagement = total_engagement / len(posts) if posts else 0

        if avg_engagement < 10:
            recommendations.append({
                "type": "engagement",
                "recommendation": "Add more questions or calls-to-action in your posts",
                "reason": f"Your average engagement is {avg_engagement:.1f} - questions typically increase comments",
            })

        return {
            "success": True,
            "recommendations": recommendations,
            "based_on": {
                "posts_analyzed": len(posts),
                "avg_engagement": round(avg_engagement, 1),
            },
        }

    except Exception as e:
        logger.error("Failed to get posting recommendations", error=str(e))
        return {"error": str(e)}


@mcp.tool()
async def generate_my_content_calendar(weeks: int = 4, posts_per_week: int = 3) -> dict:
    """
    Generate a content calendar based on your performance data.

    Creates a data-driven posting schedule that optimizes for your
    best performing days, times, and content types.

    Args:
        weeks: Number of weeks to plan (default: 4, max: 12)
        posts_per_week: Target posts per week (default: 3, max: 7)

    Returns content calendar with suggested dates, times, and content prompts.
    """
    from datetime import datetime, timedelta

    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger
    from linkedin_mcp.services.analytics import (
        get_content_analyzer,
        get_posting_time_analyzer,
    )

    logger = get_logger(__name__)
    ctx = get_context()

    # Validate inputs
    weeks = min(max(weeks, 1), 12)
    posts_per_week = min(max(posts_per_week, 1), 7)

    if not ctx.data_provider:
        return {"error": "No LinkedIn data provider available. Configure API credentials."}

    try:
        # Get profile ID via official API first, fallback to data_provider
        profile_id = None
        if ctx.official_client:
            try:
                official_profile = ctx.official_client.get_my_profile()
                if official_profile:
                    profile_id = official_profile.get("public_id") or official_profile.get("publicIdentifier")
            except Exception:
                pass

        if not profile_id:
            my_profile = await ctx.data_provider.get_own_profile()
            if my_profile:
                profile_id = my_profile.get("public_id") or my_profile.get("publicIdentifier")

        if not profile_id:
            return {"error": "Could not determine your profile ID"}

        result = await ctx.data_provider.get_profile_posts(profile_id, limit=30)
        posts = result.get("posts", result.get("data", []))

        # Analyze content and timing patterns
        content_analyzer = get_content_analyzer()
        posting_analyzer = get_posting_time_analyzer()

        content_analysis = content_analyzer.analyze_posts_performance(posts) if posts else {}
        timing_analysis = posting_analyzer.analyze_posting_patterns(posts) if posts else {}

        # Extract best times from analysis
        best_times = timing_analysis.get("recommended_posting_times", [])
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

        # Default posting days and times if no data
        preferred_days = ["Tuesday", "Wednesday", "Thursday"]
        preferred_hours = ["09:00", "12:00", "17:00"]

        if best_times:
            preferred_days = [t.get("day", "Tuesday") for t in best_times[:posts_per_week]]
            preferred_hours = [f"{t.get('hour', 9):02d}:00" for t in best_times[:3]]

        # Get content type recommendations
        content_types = ["Text post", "Image post", "Document/Carousel"]
        if content_analysis.get("content_type_breakdown"):
            # Sort by engagement
            breakdown = content_analysis["content_type_breakdown"]
            sorted_types = sorted(
                [(k, v) for k, v in breakdown.items() if v.get("count", 0) > 0],
                key=lambda x: x[1].get("avg_engagement", 0),
                reverse=True,
            )
            if sorted_types:
                content_types = [t[0].replace("_", " ").title() for t in sorted_types[:3]]

        # Generate calendar
        calendar = []
        today = datetime.now()
        start_of_week = today - timedelta(days=today.weekday())

        content_prompts = {
            "Text Post": "Share a thought-provoking insight or ask your network a question",
            "Image Post": "Share a visual that tells a story - infographic or behind-the-scenes",
            "Video Post": "Create a short video sharing expertise or industry insights",
            "Document Post": "Share a carousel with valuable takeaways on a topic",
            "Article": "Write a long-form piece on a subject you're expert in",
        }

        for week in range(weeks):
            week_start = start_of_week + timedelta(weeks=week)
            week_posts = []

            for i, day_name in enumerate(preferred_days[:posts_per_week]):
                day_index = day_names.index(day_name) if day_name in day_names else i
                post_date = week_start + timedelta(days=day_index)

                # Skip past dates
                if post_date < today:
                    continue

                content_type = content_types[i % len(content_types)]
                time_slot = preferred_hours[i % len(preferred_hours)]

                week_posts.append({
                    "date": post_date.strftime("%Y-%m-%d"),
                    "day": day_name,
                    "time": time_slot,
                    "suggested_content_type": content_type,
                    "content_prompt": content_prompts.get(content_type, "Share valuable content with your network"),
                })

            if week_posts:
                calendar.append({
                    "week": week + 1,
                    "week_start": week_start.strftime("%Y-%m-%d"),
                    "posts": week_posts,
                })

        return {
            "success": True,
            "calendar": calendar,
            "strategy": {
                "posts_per_week": posts_per_week,
                "preferred_days": preferred_days[:posts_per_week],
                "preferred_times": preferred_hours[:3],
                "recommended_content_types": content_types[:3],
            },
            "based_on": {
                "posts_analyzed": len(posts),
            },
        }

    except Exception as e:
        logger.error("Failed to generate content calendar", error=str(e))
        return {"error": str(e)}


# =============================================================================
# Profile Management Tools
# =============================================================================


@mcp.tool()
async def get_profile_sections() -> dict:
    """
    Get all editable profile sections with current content.

    Returns overview of profile sections including:
    - Basic info (name, headline, location)
    - About/Summary
    - Experience count
    - Education count
    - Skills overview
    """
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.services.profile import ProfileManager

    ctx = get_context()

    if not ctx.linkedin_client:
        return {"error": "LinkedIn client not initialized"}

    manager = ProfileManager(ctx.linkedin_client)
    return await manager.get_profile_sections()


@mcp.tool()
async def get_profile_completeness() -> dict:
    """
    Calculate profile completeness score with improvement suggestions.

    Returns:
    - Completeness score (0-100)
    - Completed vs total sections
    - Specific suggestions for improvement
    """
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.services.profile import ProfileManager

    ctx = get_context()

    if not ctx.linkedin_client:
        return {"error": "LinkedIn client not initialized"}

    manager = ProfileManager(ctx.linkedin_client)
    return await manager.get_profile_completeness()


@mcp.tool()
async def update_profile_headline(headline: str) -> dict:
    """
    Update profile headline.

    Requires Playwright browser automation to be enabled.

    Args:
        headline: New headline text (max 220 characters)

    Returns success status.
    """
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.services.profile import ProfileManager

    ctx = get_context()
    manager = ProfileManager(ctx.linkedin_client)
    return await manager.update_headline(headline)


@mcp.tool()
async def update_profile_summary(summary: str) -> dict:
    """
    Update profile summary/about section.

    Requires Playwright browser automation to be enabled.

    Args:
        summary: New summary text (max 2600 characters)

    Returns success status.
    """
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.services.profile import ProfileManager

    ctx = get_context()
    manager = ProfileManager(ctx.linkedin_client)
    return await manager.update_summary(summary)


@mcp.tool()
async def upload_profile_photo(photo_path: str) -> dict:
    """
    Upload a new profile photo.

    Requires Playwright browser automation to be enabled.

    Args:
        photo_path: Absolute path to the photo file (JPG, PNG)

    Returns success status.
    """
    from pathlib import Path

    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.services.profile import ProfileManager

    # Validate file exists
    if not Path(photo_path).exists():
        return {"error": f"File not found: {photo_path}"}

    # Validate file extension
    valid_extensions = (".jpg", ".jpeg", ".png", ".gif")
    if not photo_path.lower().endswith(valid_extensions):
        return {"error": f"Invalid file type. Supported: {', '.join(valid_extensions)}"}

    ctx = get_context()
    manager = ProfileManager(ctx.linkedin_client)
    return await manager.upload_profile_photo(photo_path)


@mcp.tool()
async def upload_background_photo(photo_path: str) -> dict:
    """
    Upload a new background/banner photo.

    Requires Playwright browser automation to be enabled.

    Args:
        photo_path: Absolute path to the photo file (JPG, PNG)

    Returns success status.
    """
    from pathlib import Path

    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.services.profile import ProfileManager

    # Validate file exists
    if not Path(photo_path).exists():
        return {"error": f"File not found: {photo_path}"}

    # Validate file extension
    valid_extensions = (".jpg", ".jpeg", ".png")
    if not photo_path.lower().endswith(valid_extensions):
        return {"error": f"Invalid file type. Supported: {', '.join(valid_extensions)}"}

    ctx = get_context()
    manager = ProfileManager(ctx.linkedin_client)
    return await manager.upload_background_photo(photo_path)


@mcp.tool()
async def add_profile_skill(skill_name: str) -> dict:
    """
    Add a skill to your profile.

    Requires Playwright browser automation to be enabled.

    Args:
        skill_name: Name of the skill to add

    Returns success status.
    """
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.services.profile import ProfileManager

    ctx = get_context()
    manager = ProfileManager(ctx.linkedin_client)
    return await manager.add_skill(skill_name)


@mcp.tool()
async def check_browser_automation_status() -> dict:
    """
    Check if browser automation is available for profile updates.

    Returns availability status and feature capabilities.
    """
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.services.browser import get_browser_automation

    ctx = get_context()
    automation = get_browser_automation()

    features_requiring_browser = [
        "update_profile_headline",
        "update_profile_summary",
        "upload_profile_photo",
        "upload_background_photo",
        "add_profile_skill",
    ]

    return {
        "success": True,
        "browser_available": ctx.has_browser,
        "automation_ready": automation is not None and automation.is_available,
        "features_requiring_browser": features_requiring_browser,
        "note": "Browser automation is optional but enables profile update features.",
    }


# =============================================================================
# Server Info Resource
# =============================================================================


@mcp.resource("linkedin://server/info")
async def server_info() -> str:
    """
    Get LinkedIn MCP server information and status.
    """
    import json

    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger

    logger = get_logger(__name__)

    try:
        ctx = get_context()
        settings = ctx.settings
        info = {
            "name": settings.server.name,
            "version": settings.server.version,
            "status": {
                "initialized": ctx.is_initialized,
                "linkedin_connected": ctx.has_linkedin_client,
                "database_connected": ctx.has_database,
                "scheduler_running": ctx.has_scheduler,
                "browser_available": ctx.has_browser,
            },
            "features": {
                "browser_fallback": settings.features.browser_fallback,
                "analytics_tracking": settings.features.analytics_tracking,
                "post_scheduling": settings.features.post_scheduling,
                "messaging_enabled": settings.features.messaging_enabled,
                "connections_enabled": settings.features.connections_enabled,
                "jobs_enabled": settings.features.jobs_enabled,
            },
            "rate_limit": {
                "remaining": ctx.linkedin_client.rate_limit_remaining if ctx.linkedin_client else 0,
            },
        }
        return json.dumps(info, indent=2)
    except Exception as e:
        logger.error("Failed to get server info", error=str(e))
        return json.dumps({"error": str(e)})


# =============================================================================
# Prompts
# =============================================================================


@mcp.prompt()
def engagement_analysis_prompt(profile_id: str) -> str:
    """
    Generate a prompt to analyze engagement patterns for a profile.
    """
    return f"""Analyze the LinkedIn engagement patterns for profile: {profile_id}

Please use the following tools in sequence:
1. get_profile("{profile_id}") - Get profile information
2. get_profile_posts("{profile_id}", limit=20) - Get recent posts

Then analyze:
- Posting frequency and timing patterns
- Content themes and topics that perform best
- Engagement rates (likes, comments, shares)
- Hashtag usage and effectiveness
- Best performing post types

Provide actionable recommendations for improving engagement."""


@mcp.prompt()
def content_strategy() -> str:
    """
    Generate a prompt for LinkedIn content strategy development.
    """
    return """Help me develop a LinkedIn content strategy.

Please use these tools to gather data:
1. get_my_profile() - Understand my professional focus
2. get_feed(limit=20) - See what's trending in my network
3. get_connections(limit=50) - Understand my audience

Based on this data, provide:
- Content pillars aligned with my expertise
- Optimal posting schedule
- Content format recommendations
- Engagement strategy with connections
- Hashtag strategy for reach
- Call-to-action suggestions"""


@mcp.prompt()
def competitor_analysis(competitor_ids: str) -> str:
    """
    Generate a prompt to analyze competitor LinkedIn activity.

    Args:
        competitor_ids: Comma-separated list of competitor profile IDs
    """
    profiles = [p.strip() for p in competitor_ids.split(",")]
    profile_list = "\n".join([f"- {p}" for p in profiles])

    return f"""Analyze LinkedIn activity for these competitor profiles:
{profile_list}

For each competitor, use:
1. get_profile("<profile_id>") - Get their profile
2. get_profile_posts("<profile_id>", limit=20) - Get their recent posts

Then analyze and compare:
- Posting frequency and schedule
- Content themes and formats
- Engagement levels (reactions, comments)
- Hashtag strategies
- Audience interaction patterns

Provide a competitive analysis summary with:
- What's working well for competitors
- Gaps and opportunities
- Recommendations for differentiation"""
