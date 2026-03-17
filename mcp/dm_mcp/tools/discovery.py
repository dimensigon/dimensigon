from __future__ import annotations

from mcp.types import Tool

from ..client import DimensigonClient
from ..formatters import (
    format_action_template_detail,
    format_action_template_list,
    format_execution_detail,
    format_execution_list,
    format_orchestration_detail,
    format_orchestration_list,
    format_server_list,
)

DISCOVERY_TOOLS = [
    Tool(
        name="dm_list_servers",
        description="List all servers in the Dimensigon cluster with names, granules, and optionally network gates.",
        inputSchema={
            "type": "object",
            "properties": {
                "include_gates": {
                    "type": "boolean",
                    "description": "Include network gate (IP/port) details",
                    "default": False,
                },
            },
            "required": [],
        },
    ),
    Tool(
        name="dm_list_orchestrations",
        description=(
            "List all orchestrations (multi-step DAG workflows). "
            "Returns name, version, and optionally steps and input/output schema."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "include_steps": {
                    "type": "boolean",
                    "description": "Include step details",
                    "default": False,
                },
                "include_schema": {
                    "type": "boolean",
                    "description": "Include input/output schema",
                    "default": False,
                },
            },
            "required": [],
        },
    ),
    Tool(
        name="dm_get_orchestration",
        description=(
            "Get detailed info about a specific orchestration including steps, "
            "dependencies, targets, and input/output schema."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "orchestration_id": {
                    "type": "string",
                    "description": "UUID of the orchestration",
                },
            },
            "required": ["orchestration_id"],
        },
    ),
    Tool(
        name="dm_list_action_templates",
        description=(
            "List all action templates (reusable automation components). "
            "Types: SHELL, PYTHON, REQUEST, ORCHESTRATION, NATIVE, ANSIBLE."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "action_type": {
                    "type": "string",
                    "description": "Filter by type",
                    "enum": ["SHELL", "PYTHON", "REQUEST", "ORCHESTRATION", "ANSIBLE", "NATIVE", "TEST"],
                },
            },
            "required": [],
        },
    ),
    Tool(
        name="dm_get_action_template",
        description=(
            "Get detailed info about a specific action template including "
            "code, schema, expected output, and pre/post processing."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "action_template_id": {
                    "type": "string",
                    "description": "UUID of the action template",
                },
            },
            "required": ["action_template_id"],
        },
    ),
    Tool(
        name="dm_list_executions",
        description="List orchestration execution history with status, timing, and success/failure.",
        inputSchema={
            "type": "object",
            "properties": {
                "include_steps": {
                    "type": "boolean",
                    "description": "Include step execution details",
                    "default": False,
                },
                "limit": {
                    "type": "integer",
                    "description": "Max recent executions to return",
                    "default": 20,
                },
            },
            "required": [],
        },
    ),
    Tool(
        name="dm_get_execution",
        description=(
            "Get detailed results of a specific execution including all step "
            "results with stdout, stderr, return codes, and timing."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "execution_id": {
                    "type": "string",
                    "description": "UUID of the orchestration execution",
                },
            },
            "required": ["execution_id"],
        },
    ),
]


async def handle_discovery_tool(name: str, arguments: dict, client: DimensigonClient) -> str:
    if name == "dm_list_servers":
        data = await client.list_servers(gates=arguments.get("include_gates", False))
        return format_server_list(data)

    if name == "dm_list_orchestrations":
        data = await client.list_orchestrations(
            steps=arguments.get("include_steps", False),
            schema=arguments.get("include_schema", False),
            target=True,
        )
        return format_orchestration_list(data)

    if name == "dm_get_orchestration":
        data = await client.get_orchestration(arguments["orchestration_id"])
        return format_orchestration_detail(data)

    if name == "dm_list_action_templates":
        data = await client.list_action_templates()
        action_type = arguments.get("action_type")
        if action_type:
            data = [t for t in data if t.get("action_type") == action_type]
        return format_action_template_list(data)

    if name == "dm_get_action_template":
        data = await client.get_action_template(arguments["action_template_id"])
        return format_action_template_detail(data)

    if name == "dm_list_executions":
        data = await client.list_executions(steps=arguments.get("include_steps", False))
        limit = arguments.get("limit", 20)
        if isinstance(data, list) and len(data) > limit:
            data = data[-limit:]
        return format_execution_list(data)

    if name == "dm_get_execution":
        data = await client.get_execution(arguments["execution_id"])
        return format_execution_detail(data)

    return f"Unknown discovery tool: {name}"
