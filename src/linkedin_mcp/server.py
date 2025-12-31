"""
LinkedIn Intelligence MCP Server.

Main FastMCP server definition with all tools, resources, and prompts.
"""

from fastmcp import FastMCP

# Create FastMCP server instance with defaults
mcp = FastMCP(
    name="LinkedIn Intelligence MCP",
    instructions="AI-powered LinkedIn analytics, content creation, and engagement automation.",
    version="0.1.0",
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

        return {
            "success": True,
            "context": {
                "is_initialized": ctx.is_initialized,
                "has_linkedin_client": ctx.has_linkedin_client,
                "has_database": ctx.has_database,
                "has_scheduler": ctx.has_scheduler,
                "has_browser": ctx.has_browser,
                "linkedin_client_type": type(ctx.linkedin_client).__name__ if ctx.linkedin_client else None,
            },
            "settings": {
                "api_enabled": settings.linkedin.api_enabled,
                "email": settings.linkedin.email,
                "password_set": settings.linkedin.password is not None,
                "session_cookie_path": str(settings.session_cookie_path),
                "session_cookie_path_absolute": str(settings.session_cookie_path.absolute()),
            },
            "cookie_file": {
                "exists": cookie_exists,
                "keys": cookie_content,
            },
            "environment": {
                "LINKEDIN_API_ENABLED": os.environ.get("LINKEDIN_API_ENABLED"),
                "LINKEDIN_EMAIL": os.environ.get("LINKEDIN_EMAIL"),
                "LINKEDIN_PASSWORD": "***" if os.environ.get("LINKEDIN_PASSWORD") else None,
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

    Returns comprehensive profile data including:
    - Basic info (name, headline, location)
    - Experience and education
    - Skills and endorsements
    - Contact information
    """
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger

    logger = get_logger(__name__)
    ctx = get_context()

    if not ctx.linkedin_client:
        return {"error": "LinkedIn client not initialized"}

    try:
        profile = await ctx.linkedin_client.get_own_profile()
        return {"success": True, "profile": profile}
    except Exception as e:
        logger.error("Failed to fetch profile", error=str(e))
        return {"error": str(e)}


@mcp.tool()
async def get_profile(profile_id: str, use_cache: bool = True) -> dict:
    """
    Get a LinkedIn profile by public ID or URN.

    Args:
        profile_id: LinkedIn public ID (e.g., "johndoe") or URN
        use_cache: Whether to use cached data if available (default: True)

    Returns profile data including experience, education, and skills.
    """
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger
    from linkedin_mcp.services.cache import CacheService, get_cache

    logger = get_logger(__name__)
    ctx = get_context()
    cache = get_cache()

    if not ctx.linkedin_client:
        return {"error": "LinkedIn client not initialized"}

    cache_key = cache.make_key("profile", profile_id)

    try:
        if use_cache:
            cached_data = await cache.get(cache_key)
            if cached_data:
                return {"success": True, "profile": cached_data, "cached": True}

        profile = await ctx.linkedin_client.get_profile(profile_id)
        await cache.set(cache_key, profile, CacheService.TTL_PROFILE)
        return {"success": True, "profile": profile, "cached": False}
    except Exception as e:
        logger.error("Failed to fetch profile", error=str(e), profile_id=profile_id)
        return {"error": str(e)}


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

    if not ctx.linkedin_client:
        return {"error": "LinkedIn client not initialized"}

    limit = min(limit, 50)  # Cap at 50
    cache_key = cache.make_key("posts", profile_id, str(limit))

    try:
        if use_cache:
            cached_data = await cache.get(cache_key)
            if cached_data:
                return {"success": True, "posts": cached_data, "count": len(cached_data), "cached": True}

        posts = await ctx.linkedin_client.get_profile_posts(profile_id, limit=limit)
        await cache.set(cache_key, posts, CacheService.TTL_POSTS)
        return {"success": True, "posts": posts, "count": len(posts), "cached": False}
    except Exception as e:
        logger.error("Failed to fetch posts", error=str(e), profile_id=profile_id)
        return {"error": str(e)}


@mcp.tool()
async def create_post(text: str, visibility: str = "PUBLIC") -> dict:
    """
    Create a new LinkedIn post.

    Args:
        text: Post content (max 3000 characters)
        visibility: Post visibility - PUBLIC, CONNECTIONS, or LOGGED_IN

    Returns the created post details.
    """
    from linkedin_mcp.config.constants import MAX_POST_LENGTH
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger

    logger = get_logger(__name__)
    ctx = get_context()

    if not ctx.linkedin_client:
        return {"error": "LinkedIn client not initialized"}

    if len(text) > MAX_POST_LENGTH:
        return {"error": f"Post exceeds maximum length of {MAX_POST_LENGTH} characters"}

    if visibility not in ("PUBLIC", "CONNECTIONS", "LOGGED_IN"):
        return {"error": "Invalid visibility. Must be PUBLIC, CONNECTIONS, or LOGGED_IN"}

    try:
        result = await ctx.linkedin_client.create_post(text, visibility=visibility)
        return {"success": True, "post": result}
    except Exception as e:
        logger.error("Failed to create post", error=str(e))
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

    if not ctx.linkedin_client:
        return {"error": "LinkedIn client not initialized"}

    try:
        reactions = await ctx.linkedin_client.get_post_reactions(post_urn)
        return {"success": True, "reactions": reactions, "count": len(reactions)}
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

    if not ctx.linkedin_client:
        return {"error": "LinkedIn client not initialized"}

    try:
        comments = await ctx.linkedin_client.get_post_comments(post_urn, limit=limit)
        return {"success": True, "comments": comments, "count": len(comments)}
    except Exception as e:
        logger.error("Failed to fetch comments", error=str(e), post_urn=post_urn)
        return {"error": str(e)}


@mcp.tool()
async def like_post(post_urn: str) -> dict:
    """
    Like a LinkedIn post.

    Args:
        post_urn: LinkedIn post URN to like

    Returns success status.
    """
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger

    logger = get_logger(__name__)
    ctx = get_context()

    if not ctx.linkedin_client:
        return {"error": "LinkedIn client not initialized"}

    try:
        await ctx.linkedin_client.react_to_post(post_urn, "LIKE")
        return {"success": True, "message": "Post liked successfully"}
    except Exception as e:
        logger.error("Failed to like post", error=str(e), post_urn=post_urn)
        return {"error": str(e)}


@mcp.tool()
async def react_to_post(post_urn: str, reaction: str = "LIKE") -> dict:
    """
    React to a LinkedIn post with a specific reaction type.

    Args:
        post_urn: LinkedIn post URN
        reaction: Reaction type - LIKE, CELEBRATE, SUPPORT, LOVE, INSIGHTFUL, FUNNY

    Returns success status.
    """
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger

    logger = get_logger(__name__)
    ctx = get_context()

    if not ctx.linkedin_client:
        return {"error": "LinkedIn client not initialized"}

    valid_reactions = ("LIKE", "CELEBRATE", "SUPPORT", "LOVE", "INSIGHTFUL", "FUNNY")
    if reaction.upper() not in valid_reactions:
        return {"error": f"Invalid reaction. Must be one of: {', '.join(valid_reactions)}"}

    try:
        await ctx.linkedin_client.react_to_post(post_urn, reaction.upper())
        return {"success": True, "message": f"Reacted with {reaction}"}
    except Exception as e:
        logger.error("Failed to react to post", error=str(e), post_urn=post_urn)
        return {"error": str(e)}


@mcp.tool()
async def comment_on_post(post_urn: str, text: str) -> dict:
    """
    Add a comment to a LinkedIn post.

    Args:
        post_urn: LinkedIn post URN
        text: Comment text

    Returns the created comment details.
    """
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger

    logger = get_logger(__name__)
    ctx = get_context()

    if not ctx.linkedin_client:
        return {"error": "LinkedIn client not initialized"}

    if not text.strip():
        return {"error": "Comment text cannot be empty"}

    try:
        result = await ctx.linkedin_client.comment_on_post(post_urn, text)
        return {"success": True, "comment": result}
    except Exception as e:
        logger.error("Failed to comment", error=str(e), post_urn=post_urn)
        return {"error": str(e)}


@mcp.tool()
async def reply_to_comment(comment_urn: str, text: str) -> dict:
    """
    Reply to a comment on a LinkedIn post.

    Args:
        comment_urn: LinkedIn comment URN
        text: Reply text

    Returns the created reply details.
    """
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger

    logger = get_logger(__name__)
    ctx = get_context()

    if not ctx.linkedin_client:
        return {"error": "LinkedIn client not initialized"}

    if not text.strip():
        return {"error": "Reply text cannot be empty"}

    try:
        result = await ctx.linkedin_client.reply_to_comment(comment_urn, text)
        return {"success": True, "reply": result}
    except Exception as e:
        logger.error("Failed to reply to comment", error=str(e), comment_urn=comment_urn)
        return {"error": str(e)}


@mcp.tool()
async def unreact_to_post(post_urn: str) -> dict:
    """
    Remove reaction from a LinkedIn post.

    Args:
        post_urn: LinkedIn post URN

    Returns success status.
    """
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger

    logger = get_logger(__name__)
    ctx = get_context()

    if not ctx.linkedin_client:
        return {"error": "LinkedIn client not initialized"}

    try:
        await ctx.linkedin_client.unreact_to_post(post_urn)
        return {"success": True, "message": "Reaction removed"}
    except Exception as e:
        logger.error("Failed to remove reaction", error=str(e), post_urn=post_urn)
        return {"error": str(e)}


# =============================================================================
# Connection Management Tools
# =============================================================================


@mcp.tool()
async def send_connection_request(profile_id: str, message: str | None = None) -> dict:
    """
    Send a connection request to a LinkedIn user.

    Args:
        profile_id: LinkedIn public ID
        message: Optional personalized message (max 300 characters)

    Returns success status.
    """
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger

    logger = get_logger(__name__)
    ctx = get_context()

    if not ctx.linkedin_client:
        return {"error": "LinkedIn client not initialized"}

    # Validate message length
    if message and len(message) > 300:
        return {"error": "Connection message cannot exceed 300 characters"}

    try:
        result = await ctx.linkedin_client.send_connection_request(profile_id, message=message)
        return {"success": True, "result": result, "profile_id": profile_id}
    except Exception as e:
        logger.error("Failed to send connection request", error=str(e), profile_id=profile_id)
        return {"error": str(e)}


@mcp.tool()
async def remove_connection(profile_id: str) -> dict:
    """
    Remove a LinkedIn connection.

    Args:
        profile_id: LinkedIn public ID of the connection to remove

    Returns success status.
    """
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger

    logger = get_logger(__name__)
    ctx = get_context()

    if not ctx.linkedin_client:
        return {"error": "LinkedIn client not initialized"}

    try:
        result = await ctx.linkedin_client.remove_connection(profile_id)
        return {"success": True, "result": result, "profile_id": profile_id}
    except Exception as e:
        logger.error("Failed to remove connection", error=str(e), profile_id=profile_id)
        return {"error": str(e)}


@mcp.tool()
async def get_pending_invitations(sent: bool = False) -> dict:
    """
    Get pending connection invitations.

    Args:
        sent: If True, get invitations you sent; otherwise get received invitations

    Returns list of pending invitations.
    """
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger

    logger = get_logger(__name__)
    ctx = get_context()

    if not ctx.linkedin_client:
        return {"error": "LinkedIn client not initialized"}

    try:
        invitations = await ctx.linkedin_client.get_pending_invitations(sent=sent)
        return {
            "success": True,
            "invitations": invitations,
            "count": len(invitations),
            "type": "sent" if sent else "received",
        }
    except Exception as e:
        logger.error("Failed to fetch invitations", error=str(e))
        return {"error": str(e)}


@mcp.tool()
async def accept_invitation(invitation_id: str, shared_secret: str) -> dict:
    """
    Accept a connection invitation.

    Args:
        invitation_id: Invitation ID from get_pending_invitations
        shared_secret: Shared secret from the invitation

    Returns success status.
    """
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger

    logger = get_logger(__name__)
    ctx = get_context()

    if not ctx.linkedin_client:
        return {"error": "LinkedIn client not initialized"}

    try:
        result = await ctx.linkedin_client.accept_invitation(invitation_id, shared_secret)
        return {"success": True, "result": result}
    except Exception as e:
        logger.error("Failed to accept invitation", error=str(e), invitation_id=invitation_id)
        return {"error": str(e)}


@mcp.tool()
async def reject_invitation(invitation_id: str, shared_secret: str) -> dict:
    """
    Reject/ignore a connection invitation.

    Args:
        invitation_id: Invitation ID from get_pending_invitations
        shared_secret: Shared secret from the invitation

    Returns success status.
    """
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger

    logger = get_logger(__name__)
    ctx = get_context()

    if not ctx.linkedin_client:
        return {"error": "LinkedIn client not initialized"}

    try:
        result = await ctx.linkedin_client.reject_invitation(invitation_id, shared_secret)
        return {"success": True, "result": result}
    except Exception as e:
        logger.error("Failed to reject invitation", error=str(e), invitation_id=invitation_id)
        return {"error": str(e)}


@mcp.tool()
async def send_bulk_messages(profile_ids: str, text: str) -> dict:
    """
    Send a message to multiple LinkedIn connections.

    Args:
        profile_ids: Comma-separated list of profile public IDs (max 25)
        text: Message content

    Returns success/failure status for each recipient.
    """
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger

    logger = get_logger(__name__)
    ctx = get_context()

    if not ctx.linkedin_client:
        return {"error": "LinkedIn client not initialized"}

    if not text.strip():
        return {"error": "Message text cannot be empty"}

    # Parse and validate IDs
    ids = [p.strip() for p in profile_ids.split(",") if p.strip()]
    if not ids:
        return {"error": "No profile IDs provided"}

    if len(ids) > 25:
        return {"error": "Maximum 25 recipients per bulk message"}

    results = []
    errors = []

    for profile_id in ids:
        try:
            await ctx.linkedin_client.send_message([profile_id], text)
            results.append({"profile_id": profile_id, "success": True})
        except Exception as e:
            logger.warning("Failed to send message", profile_id=profile_id, error=str(e))
            errors.append({"profile_id": profile_id, "error": str(e)})

    return {
        "success": len(errors) == 0,
        "sent": results,
        "failed": errors,
        "total_sent": len(results),
        "total_failed": len(errors),
    }


# =============================================================================
# Messaging Tools
# =============================================================================


@mcp.tool()
async def get_conversations(limit: int = 20) -> dict:
    """
    Get LinkedIn messaging conversations.

    Args:
        limit: Maximum number of conversations to return (default: 20)

    Returns list of conversations with latest messages.
    """
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger

    logger = get_logger(__name__)
    ctx = get_context()

    if not ctx.linkedin_client:
        return {"error": "LinkedIn client not initialized"}

    try:
        conversations = await ctx.linkedin_client.get_conversations()
        return {"success": True, "conversations": conversations[:limit], "count": min(len(conversations), limit)}
    except Exception as e:
        logger.error("Failed to fetch conversations", error=str(e))
        return {"error": str(e)}


@mcp.tool()
async def get_conversation(conversation_id: str) -> dict:
    """
    Get a specific messaging conversation.

    Args:
        conversation_id: LinkedIn conversation ID

    Returns conversation with full message history.
    """
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger

    logger = get_logger(__name__)
    ctx = get_context()

    if not ctx.linkedin_client:
        return {"error": "LinkedIn client not initialized"}

    try:
        conversation = await ctx.linkedin_client.get_conversation(conversation_id)
        return {"success": True, "conversation": conversation}
    except Exception as e:
        logger.error("Failed to fetch conversation", error=str(e), conversation_id=conversation_id)
        return {"error": str(e)}


@mcp.tool()
async def send_message(profile_id: str, text: str) -> dict:
    """
    Send a LinkedIn message to a connection.

    Args:
        profile_id: Recipient's LinkedIn public ID
        text: Message content

    Returns success status and message details.
    """
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger

    logger = get_logger(__name__)
    ctx = get_context()

    if not ctx.linkedin_client:
        return {"error": "LinkedIn client not initialized"}

    if not text.strip():
        return {"error": "Message text cannot be empty"}

    try:
        result = await ctx.linkedin_client.send_message([profile_id], text)
        return {"success": True, "message": result}
    except Exception as e:
        logger.error("Failed to send message", error=str(e), recipient=profile_id)
        return {"error": str(e)}


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
    """
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger

    logger = get_logger(__name__)
    ctx = get_context()

    if not ctx.linkedin_client:
        return {"error": "LinkedIn client not initialized"}

    limit = min(limit, 50)  # Cap at 50

    try:
        results = await ctx.linkedin_client.search_people(
            keywords=keywords,
            limit=limit,
            keyword_title=keyword_title,
            keyword_company=keyword_company,
        )
        return {"success": True, "results": results, "count": len(results)}
    except Exception as e:
        logger.error("Failed to search", error=str(e))
        return {"error": str(e)}


@mcp.tool()
async def search_companies(keywords: str, limit: int = 10) -> dict:
    """
    Search for companies on LinkedIn.

    Args:
        keywords: Search keywords
        limit: Maximum results to return (default: 10, max: 50)

    Returns list of matching companies.
    """
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger

    logger = get_logger(__name__)
    ctx = get_context()

    if not ctx.linkedin_client:
        return {"error": "LinkedIn client not initialized"}

    limit = min(limit, 50)  # Cap at 50

    try:
        results = await ctx.linkedin_client.search_companies(keywords=keywords, limit=limit)
        return {"success": True, "results": results, "count": len(results)}
    except Exception as e:
        logger.error("Failed to search companies", error=str(e))
        return {"error": str(e)}


@mcp.tool()
async def get_connections(limit: int = 50) -> dict:
    """
    Get the authenticated user's LinkedIn connections.

    Args:
        limit: Maximum connections to return (default: 50, max: 500)

    Returns list of connection profiles.
    """
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger

    logger = get_logger(__name__)
    ctx = get_context()

    if not ctx.linkedin_client:
        return {"error": "LinkedIn client not initialized"}

    limit = min(limit, 500)  # Cap at 500

    try:
        connections = await ctx.linkedin_client.get_profile_connections(limit=limit)
        return {"success": True, "connections": connections, "count": len(connections)}
    except Exception as e:
        logger.error("Failed to fetch connections", error=str(e))
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

    if not ctx.linkedin_client:
        return {"error": "LinkedIn client not initialized"}

    try:
        # Fetch engagement data
        reactions = await ctx.linkedin_client.get_post_reactions(post_urn)
        comments = await ctx.linkedin_client.get_post_comments(post_urn)

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

    if not ctx.linkedin_client:
        return {"error": "LinkedIn client not initialized"}

    post_limit = min(post_limit, 50)

    try:
        posts = await ctx.linkedin_client.get_profile_posts(profile_id, limit=post_limit)

        if not posts:
            return {"success": True, "message": "No posts found for analysis"}

        analysis = analyzer.analyze_posts_performance(posts)

        return {
            "success": True,
            "profile_id": profile_id,
            "analysis": analysis,
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

    if not ctx.linkedin_client:
        return {"error": "LinkedIn client not initialized"}

    post_limit = min(post_limit, 50)

    try:
        posts = await ctx.linkedin_client.get_profile_posts(profile_id, limit=post_limit)

        if not posts:
            return {"success": True, "message": "No posts found for analysis"}

        analysis = analyzer.analyze_posting_patterns(posts)

        return {
            "success": True,
            "profile_id": profile_id,
            "posting_analysis": analysis,
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

    if not ctx.linkedin_client:
        return {"error": "LinkedIn client not initialized"}

    try:
        comments = await ctx.linkedin_client.get_post_comments(post_urn)

        if not comments:
            return {"success": True, "message": "No comments to analyze"}

        analysis = analyzer.analyze_commenters(comments)

        return {
            "success": True,
            "post_urn": post_urn,
            "audience_analysis": analysis,
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

    if not ctx.linkedin_client:
        return {"error": "LinkedIn client not initialized"}

    post_limit = min(post_limit, 50)

    try:
        posts = await ctx.linkedin_client.get_profile_posts(profile_id, limit=post_limit)

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

    if not ctx.linkedin_client:
        return {"error": "LinkedIn client not initialized"}

    post_limit = min(post_limit, 50)

    try:
        # Fetch data
        profile = await ctx.linkedin_client.get_profile(profile_id)
        posts = await ctx.linkedin_client.get_profile_posts(profile_id, limit=post_limit)

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
        }
    except Exception as e:
        logger.error("Failed to generate report", error=str(e), profile_id=profile_id)
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
