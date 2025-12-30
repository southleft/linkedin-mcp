"""
LinkedIn MCP Server entry point.

Starts the MCP server with the configured transport.
"""

import asyncio
import sys

from linkedin_mcp.config.settings import get_settings
from linkedin_mcp.core.lifespan import lifespan
from linkedin_mcp.core.logging import configure_logging, get_logger
from linkedin_mcp.server import mcp


async def run_server() -> None:
    """Run the MCP server with lifespan management."""
    settings = get_settings()
    configure_logging(settings.logging)
    logger = get_logger(__name__)

    logger.info(
        "Starting LinkedIn MCP Server",
        name=settings.server.name,
        version=settings.server.version,
        transport=settings.server.transport,
    )

    async with lifespan() as ctx:
        logger.info(
            "Server ready",
            linkedin=ctx.has_linkedin_client,
            database=ctx.has_database,
            scheduler=ctx.has_scheduler,
        )

        # Run the MCP server based on transport
        if settings.server.transport == "stdio":
            await mcp.run_stdio_async()
        elif settings.server.transport == "streamable-http":
            await mcp.run_uvicorn_async(
                host=settings.server.host,
                port=settings.server.port,
            )
        elif settings.server.transport == "sse":
            await mcp.run_sse_async(
                host=settings.server.host,
                port=settings.server.port,
            )
        else:
            logger.error("Unknown transport", transport=settings.server.transport)
            sys.exit(1)


def main() -> None:
    """Main entry point for the LinkedIn MCP Server."""
    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        print("\nServer stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"Server error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
