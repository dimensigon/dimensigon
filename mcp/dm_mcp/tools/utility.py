from __future__ import annotations

from mcp.types import Tool

from ..client import DimensigonClient
from ..formatters import format_granules, format_server_list, format_vault_list

UTILITY_TOOLS = [
    Tool(
        name="dm_list_vault",
        description="List vault entries (secrets/variables) or available scopes.",
        inputSchema={
            "type": "object",
            "properties": {
                "scope": {
                    "type": "string",
                    "description": "Vault scope to filter by (default: global)",
                },
                "list_scopes": {
                    "type": "boolean",
                    "description": "List available scopes instead of entries",
                    "default": False,
                },
            },
            "required": [],
        },
    ),
    Tool(
        name="dm_get_server_detail",
        description="Get detailed info about a server including gates and connectivity.",
        inputSchema={
            "type": "object",
            "properties": {
                "server_id": {
                    "type": "string",
                    "description": "Server UUID or name",
                },
            },
            "required": ["server_id"],
        },
    ),
    Tool(
        name="dm_list_granules",
        description="List all server granules (groups/tags) used to target server groups in orchestrations.",
        inputSchema={
            "type": "object",
            "properties": {},
            "required": [],
        },
    ),
]


async def handle_utility_tool(name: str, arguments: dict, client: DimensigonClient) -> str:
    if name == "dm_list_vault":
        if arguments.get("list_scopes"):
            data = await client.list_vault(scopes=True)
        else:
            data = await client.list_vault(scope=arguments.get("scope"))
        return format_vault_list(data)

    if name == "dm_get_server_detail":
        data = await client.get_server(arguments["server_id"])
        # Wrap single server in list for formatter, then use detail format
        return format_server_list([data] if isinstance(data, dict) else data)

    if name == "dm_list_granules":
        data = await client.list_granules()
        return format_granules(data)

    return f"Unknown utility tool: {name}"
