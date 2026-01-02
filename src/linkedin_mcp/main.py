"""
LinkedIn MCP Server entry point.

Starts the MCP server with the configured transport.
FastMCP handles lifespan management automatically via the lifespan parameter in server.py.
"""

import sys

from linkedin_mcp.server import mcp


def main() -> None:
    """Main entry point for the LinkedIn MCP Server.

    FastMCP handles all lifecycle management including:
    - Lifespan context (initialization/shutdown)
    - Transport selection (stdio by default)
    - Signal handling
    """
    try:
        # mcp.run() handles everything - lifespan is registered in server.py
        mcp.run()
    except KeyboardInterrupt:
        print("\nServer stopped by user", file=sys.stderr)
        sys.exit(0)
    except Exception as e:
        print(f"Server error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
