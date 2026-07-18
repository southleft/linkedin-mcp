"""
LinkedIn MCP Server entry point.

Starts the MCP server with the configured transport.
FastMCP handles lifespan management automatically via the lifespan parameter in server.py.
"""

import sys

from linkedin_mcp.config.settings import get_settings
from linkedin_mcp.server import mcp


def main() -> None:
    """Main entry point for the LinkedIn MCP Server.

    FastMCP handles all lifecycle management including:
    - Lifespan context (initialization/shutdown)
    - Signal handling

    Transport is selected from settings (MCP_TRANSPORT / MCP_HOST / MCP_PORT):
    - "stdio" (default): local child-process transport (Claude Code, Claude Desktop)
    - "streamable-http" / "sse": network transport for remote MCP clients
    """
    settings = get_settings()
    transport = settings.server.transport

    try:
        if transport == "stdio":
            # Local child-process transport — no host/port.
            mcp.run()
        else:
            # Network transport. FastMCP 2.x uses "http" for streamable HTTP.
            fastmcp_transport = "http" if transport == "streamable-http" else transport
            mcp.run(
                transport=fastmcp_transport,
                host=settings.server.host,
                port=settings.server.port,
            )
    except KeyboardInterrupt:
        print("\nServer stopped by user", file=sys.stderr)
        sys.exit(0)
    except Exception as e:
        print(f"Server error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
