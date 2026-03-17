from __future__ import annotations

import json

from mcp.types import Tool

from ..client import DimensigonClient
from ..formatters import format_command_result, format_execution_detail

EXECUTION_TOOLS = [
    Tool(
        name="dm_launch_orchestration",
        description=(
            "Execute an orchestration on target servers. Specify by name or ID. "
            "Provide target servers by name, ID, or granule. "
            "Runs in background by default, returning an execution_id for tracking."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "orchestration_id": {
                    "type": "string",
                    "description": "UUID of the orchestration (alternative to orchestration_name)",
                },
                "orchestration_name": {
                    "type": "string",
                    "description": "Name of the orchestration (alternative to orchestration_id)",
                },
                "version": {"type": "integer", "description": "Version (latest if omitted)"},
                "hosts": {
                    "type": ["string", "array", "object"],
                    "description": (
                        "Target servers: a name/ID, list of names/IDs, "
                        "or mapping {granule: [server1, ...]}"
                    ),
                },
                "params": {"type": "object", "description": "Input parameters"},
                "background": {
                    "type": "boolean",
                    "description": "Run in background",
                    "default": True,
                },
                "timeout": {"type": "integer", "description": "Timeout in seconds"},
            },
            "required": ["hosts"],
        },
    ),
    Tool(
        name="dm_run_command",
        description=(
            "Execute a shell command on target servers. "
            "Returns stdout, stderr, and return code per server."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to execute"},
                "target": {
                    "type": ["string", "array"],
                    "description": "Target server(s). Defaults to current server.",
                },
                "timeout": {"type": "integer", "description": "Timeout in seconds"},
            },
            "required": ["command"],
        },
    ),
]


async def handle_execution_tool(name: str, arguments: dict, client: DimensigonClient) -> str:
    if name == "dm_launch_orchestration":
        orch_id = arguments.get("orchestration_id")
        body: dict = {"hosts": arguments["hosts"]}
        if arguments.get("orchestration_name"):
            body["orchestration"] = arguments["orchestration_name"]
        if arguments.get("version"):
            body["version"] = arguments["version"]
        if arguments.get("params"):
            body["params"] = arguments["params"]
        if "background" in arguments:
            body["background"] = arguments["background"]
        if arguments.get("timeout"):
            body["timeout"] = arguments["timeout"]

        result, status_code = await client.launch_orchestration(body, orch_id=orch_id)

        if status_code == 202:
            exec_id = result.get("execution_id", "?")
            return (
                f"Orchestration launched in background.\n"
                f"Execution ID: {exec_id}\n"
                f"Use dm_get_execution to check status."
            )
        return format_execution_detail(result)

    if name == "dm_run_command":
        body: dict = {"command": arguments["command"]}
        if arguments.get("target"):
            body["target"] = arguments["target"]
        if arguments.get("timeout"):
            body["timeout"] = arguments["timeout"]
        result = await client.launch_command(body)
        return format_command_result(result)

    return f"Unknown execution tool: {name}"
