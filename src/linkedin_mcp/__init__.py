"""
LinkedIn Intelligence MCP Server.

AI-powered LinkedIn analytics, content creation, and engagement automation
through the Model Context Protocol.
"""

__version__ = "0.1.0"
__author__ = "TJ Pitre"


def get_mcp():
    """Get the MCP server instance (lazy import to avoid settings validation at import time)."""
    from linkedin_mcp.server import mcp
    return mcp


__all__ = ["get_mcp", "__version__"]
