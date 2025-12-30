"""
LinkedIn Intelligence MCP Server.

Main FastMCP server definition with all tools, resources, and prompts.
"""

from fastmcp import FastMCP

# Create FastMCP server instance with defaults
# Actual settings applied during lifespan
mcp = FastMCP(
    name="LinkedIn Intelligence MCP",
    instructions="AI-powered LinkedIn analytics, content creation, and engagement automation.",
    version="0.1.0",
)


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
        logger.info("Fetching authenticated user profile")
        profile = ctx.linkedin_client.get_user_profile()
        return {"success": True, "profile": profile}
    except Exception as e:
        logger.error("Failed to fetch profile", error=str(e))
        return {"error": str(e)}


@mcp.tool()
async def get_profile(profile_id: str) -> dict:
    """
    Get a LinkedIn profile by public ID or URN.

    Args:
        profile_id: LinkedIn public ID (e.g., "johndoe") or URN

    Returns profile data including experience, education, and skills.
    """
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger

    logger = get_logger(__name__)
    ctx = get_context()

    if not ctx.linkedin_client:
        return {"error": "LinkedIn client not initialized"}

    try:
        logger.info("Fetching profile", profile_id=profile_id)
        profile = ctx.linkedin_client.get_profile(profile_id)
        return {"success": True, "profile": profile}
    except Exception as e:
        logger.error("Failed to fetch profile", error=str(e), profile_id=profile_id)
        return {"error": str(e)}


# =============================================================================
# Feed & Posts Tools
# =============================================================================


@mcp.tool()
async def get_feed(limit: int = 10) -> dict:
    """
    Get the authenticated user's LinkedIn feed.

    Args:
        limit: Maximum number of feed items to return (default: 10)

    Returns recent feed posts with engagement data.
    """
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger

    logger = get_logger(__name__)
    ctx = get_context()

    if not ctx.linkedin_client:
        return {"error": "LinkedIn client not initialized"}

    try:
        logger.info("Fetching feed", limit=limit)
        feed = ctx.linkedin_client.get_feed_posts(limit=limit)
        return {"success": True, "posts": feed, "count": len(feed)}
    except Exception as e:
        logger.error("Failed to fetch feed", error=str(e))
        return {"error": str(e)}


@mcp.tool()
async def get_profile_posts(profile_id: str, limit: int = 10) -> dict:
    """
    Get posts from a specific LinkedIn profile.

    Args:
        profile_id: LinkedIn public ID or URN
        limit: Maximum number of posts to return (default: 10)

    Returns posts with engagement metrics (likes, comments, shares).
    """
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger

    logger = get_logger(__name__)
    ctx = get_context()

    if not ctx.linkedin_client:
        return {"error": "LinkedIn client not initialized"}

    try:
        logger.info("Fetching profile posts", profile_id=profile_id, limit=limit)
        posts = ctx.linkedin_client.get_profile_posts(profile_id, post_count=limit)
        return {"success": True, "posts": posts, "count": len(posts)}
    except Exception as e:
        logger.error("Failed to fetch posts", error=str(e), profile_id=profile_id)
        return {"error": str(e)}


@mcp.tool()
async def create_post(
    text: str,
    visibility: str = "PUBLIC",
) -> dict:
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

    try:
        logger.info("Creating post", visibility=visibility, length=len(text))
        result = ctx.linkedin_client.post(text)
        return {"success": True, "post": result}
    except Exception as e:
        logger.error("Failed to create post", error=str(e))
        return {"error": str(e)}


# =============================================================================
# Engagement Tools
# =============================================================================


@mcp.tool()
async def get_post_reactions(post_urn: str) -> dict:
    """
    Get reactions/likes on a specific post.

    Args:
        post_urn: LinkedIn post URN

    Returns list of users who reacted and reaction types.
    """
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger

    logger = get_logger(__name__)
    ctx = get_context()

    if not ctx.linkedin_client:
        return {"error": "LinkedIn client not initialized"}

    try:
        logger.info("Fetching post reactions", post_urn=post_urn)
        reactions = ctx.linkedin_client.get_post_reactions(post_urn)
        return {"success": True, "reactions": reactions}
    except Exception as e:
        logger.error("Failed to fetch reactions", error=str(e), post_urn=post_urn)
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
        logger.info("Liking post", post_urn=post_urn)
        ctx.linkedin_client.react_to_post(post_urn, "LIKE")
        return {"success": True, "message": "Post liked successfully"}
    except Exception as e:
        logger.error("Failed to like post", error=str(e), post_urn=post_urn)
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

    try:
        logger.info("Commenting on post", post_urn=post_urn)
        result = ctx.linkedin_client.comment_on_post(post_urn, text)
        return {"success": True, "comment": result}
    except Exception as e:
        logger.error("Failed to comment", error=str(e), post_urn=post_urn)
        return {"error": str(e)}


# =============================================================================
# Messaging Tools
# =============================================================================


@mcp.tool()
async def get_conversations(limit: int = 20) -> dict:
    """
    Get LinkedIn messaging conversations.

    Args:
        limit: Maximum number of conversations to return

    Returns list of conversations with latest messages.
    """
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger

    logger = get_logger(__name__)
    ctx = get_context()

    if not ctx.linkedin_client:
        return {"error": "LinkedIn client not initialized"}

    try:
        logger.info("Fetching conversations", limit=limit)
        conversations = ctx.linkedin_client.get_conversations()
        return {"success": True, "conversations": conversations[:limit]}
    except Exception as e:
        logger.error("Failed to fetch conversations", error=str(e))
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

    try:
        logger.info("Sending message", recipient=profile_id)
        result = ctx.linkedin_client.send_message(text, recipients=[profile_id])
        return {"success": True, "message": result}
    except Exception as e:
        logger.error("Failed to send message", error=str(e), recipient=profile_id)
        return {"error": str(e)}


# =============================================================================
# Search Tools
# =============================================================================


@mcp.tool()
async def search_people(
    keywords: str,
    limit: int = 10,
    connection_of: str | None = None,
    current_company: str | None = None,
) -> dict:
    """
    Search for people on LinkedIn.

    Args:
        keywords: Search keywords
        limit: Maximum results to return
        connection_of: Filter by connection of this profile ID
        current_company: Filter by current company

    Returns list of matching profiles.
    """
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger

    logger = get_logger(__name__)
    ctx = get_context()

    if not ctx.linkedin_client:
        return {"error": "LinkedIn client not initialized"}

    try:
        logger.info("Searching people", keywords=keywords, limit=limit)
        results = ctx.linkedin_client.search_people(
            keywords=keywords,
            limit=limit,
            connection_of=connection_of,
            current_company=[current_company] if current_company else None,
        )
        return {"success": True, "results": results, "count": len(results)}
    except Exception as e:
        logger.error("Failed to search", error=str(e))
        return {"error": str(e)}


@mcp.tool()
async def get_connections(limit: int = 50) -> dict:
    """
    Get the authenticated user's LinkedIn connections.

    Args:
        limit: Maximum connections to return

    Returns list of connection profiles.
    """
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger

    logger = get_logger(__name__)
    ctx = get_context()

    if not ctx.linkedin_client:
        return {"error": "LinkedIn client not initialized"}

    try:
        logger.info("Fetching connections", limit=limit)
        connections = ctx.linkedin_client.get_profile_connections(limit=limit)
        return {"success": True, "connections": connections, "count": len(connections)}
    except Exception as e:
        logger.error("Failed to fetch connections", error=str(e))
        return {"error": str(e)}


# =============================================================================
# Analytics Tools (Future Implementation)
# =============================================================================


@mcp.tool()
async def get_post_analytics(post_urn: str) -> dict:
    """
    Get analytics for a specific post.

    Args:
        post_urn: LinkedIn post URN

    Returns engagement metrics including views, reactions, comments, and shares.
    Note: Some metrics require Partner API access.
    """
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger

    logger = get_logger(__name__)
    ctx = get_context()

    if not ctx.linkedin_client:
        return {"error": "LinkedIn client not initialized"}

    try:
        logger.info("Fetching post analytics", post_urn=post_urn)

        # Get reactions count
        reactions = ctx.linkedin_client.get_post_reactions(post_urn)

        # Get comments count
        comments = ctx.linkedin_client.get_post_comments(post_urn)

        return {
            "success": True,
            "analytics": {
                "post_urn": post_urn,
                "reactions_count": len(reactions) if reactions else 0,
                "comments_count": len(comments) if comments else 0,
                "note": "View count requires Partner API access",
            },
        }
    except Exception as e:
        logger.error("Failed to fetch analytics", error=str(e), post_urn=post_urn)
        return {"error": str(e)}


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
        }
        return json.dumps(info, indent=2)
    except Exception as e:
        logger.error("Failed to get server info", error=str(e))
        return json.dumps({"error": str(e)})


# =============================================================================
# Prompts
# =============================================================================


@mcp.prompt()
def analyze_engagement(profile_id: str) -> str:
    """
    Generate a prompt to analyze engagement patterns for a profile.
    """
    return f"""Analyze the LinkedIn engagement patterns for profile: {profile_id}

Please use the following tools in sequence:
1. get_profile({profile_id}) - Get profile information
2. get_profile_posts({profile_id}, limit=20) - Get recent posts

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
