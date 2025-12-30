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
        profile = await ctx.linkedin_client.get_profile(profile_id)
        return {"success": True, "profile": profile}
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


# =============================================================================
# Feed & Posts Tools
# =============================================================================


@mcp.tool()
async def get_feed(limit: int = 10) -> dict:
    """
    Get the authenticated user's LinkedIn feed.

    Args:
        limit: Maximum number of feed items to return (default: 10, max: 50)

    Returns recent feed posts with engagement data.
    """
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger

    logger = get_logger(__name__)
    ctx = get_context()

    if not ctx.linkedin_client:
        return {"error": "LinkedIn client not initialized"}

    limit = min(limit, 50)  # Cap at 50

    try:
        feed = await ctx.linkedin_client.get_feed(limit=limit)
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
        limit: Maximum number of posts to return (default: 10, max: 50)

    Returns posts with engagement metrics (likes, comments, shares).
    """
    from linkedin_mcp.core.context import get_context
    from linkedin_mcp.core.logging import get_logger

    logger = get_logger(__name__)
    ctx = get_context()

    if not ctx.linkedin_client:
        return {"error": "LinkedIn client not initialized"}

    limit = min(limit, 50)  # Cap at 50

    try:
        posts = await ctx.linkedin_client.get_profile_posts(profile_id, limit=limit)
        return {"success": True, "posts": posts, "count": len(posts)}
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
    keywords: str,
    limit: int = 10,
    connection_of: str | None = None,
    current_company: str | None = None,
) -> dict:
    """
    Search for people on LinkedIn.

    Args:
        keywords: Search keywords
        limit: Maximum results to return (default: 10, max: 50)
        connection_of: Filter by connection of this profile ID (optional)
        current_company: Filter by current company (optional)

    Returns list of matching profiles.
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
            connection_of=connection_of,
            current_company=[current_company] if current_company else None,
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
def analyze_engagement(profile_id: str) -> str:
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
