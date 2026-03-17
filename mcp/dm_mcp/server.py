"""Dimensigon MCP Server - Bridge between MCP protocol and Dimensigon REST API."""

import asyncio
import logging
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from .client import DimensigonClient
from .exceptions import (
    AuthenticationError,
    DimensigonAPIError,
    DimensigonConnectionError,
)
from .tools import ALL_TOOLS, TOOL_HANDLERS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

server = Server("dimensigon")
_client: DimensigonClient | None = None


def get_client() -> DimensigonClient:
    global _client
    if _client is None:
        _client = DimensigonClient()
    return _client


@server.list_tools()
async def list_tools() -> list[Tool]:
    return ALL_TOOLS


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    handler = TOOL_HANDLERS.get(name)
    if not handler:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]

    client = get_client()
    try:
        result = await handler(name, arguments, client)
        return [TextContent(type="text", text=result)]
    except AuthenticationError as e:
        return [TextContent(type="text", text=f"Authentication error: {e}")]
    except DimensigonConnectionError as e:
        return [TextContent(type="text", text=f"Connection error: {e}")]
    except DimensigonAPIError as e:
        return [TextContent(type="text", text=f"API error ({e.status_code}): {e.message}")]
    except Exception as e:
        logger.exception(f"Unexpected error in tool {name}")
        return [TextContent(type="text", text=f"Error: {type(e).__name__}: {e}")]


async def main():
    logger.info("Starting Dimensigon MCP Server...")
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
