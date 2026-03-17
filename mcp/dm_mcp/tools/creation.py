from __future__ import annotations

import json

from mcp.types import Tool

from ..client import DimensigonClient

CREATION_TOOLS = [
    Tool(
        name="dm_create_action_template",
        description=(
            "Create a reusable action template. Types: SHELL (bash commands), "
            "PYTHON (python code), REQUEST (HTTP calls), ORCHESTRATION (sub-orchestration)."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Template name (max 40 chars)",
                    "maxLength": 40,
                },
                "action_type": {
                    "type": "string",
                    "description": "Type of action",
                    "enum": ["SHELL", "PYTHON", "REQUEST", "ORCHESTRATION", "ANSIBLE"],
                },
                "code": {"type": "string", "description": "Code/command to execute"},
                "description": {"type": "string", "description": "Human-readable description"},
                "expected_rc": {"type": "integer", "description": "Expected return code (e.g. 0)"},
                "expected_stdout": {"type": "string", "description": "Expected stdout pattern"},
                "expected_stderr": {"type": "string", "description": "Expected stderr pattern"},
                "schema": {
                    "type": "object",
                    "description": (
                        "Input/output schema: "
                        '{input: {var: {type, description}}, required: [...], output: [...]}'
                    ),
                },
                "pre_process": {"type": "string", "description": "Python code to run before execution"},
                "post_process": {"type": "string", "description": "Python code to run after execution"},
                "system_kwargs": {"type": "object", "description": "System kwargs (e.g. timeout)"},
            },
            "required": ["name", "action_type", "code"],
        },
    ),
    Tool(
        name="dm_create_orchestration",
        description=(
            "Create a complete orchestration with steps and dependencies in one call. "
            "Each step needs a unique string 'id' (for referencing in parent_step_ids), "
            "'undo' (false=forward, true=rollback), and either 'action_template_id' "
            "or 'action_type'+'code'. Dependencies form a DAG via parent_step_ids."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Orchestration name"},
                "description": {"type": "string", "description": "What this orchestration does"},
                "stop_on_error": {
                    "type": "boolean",
                    "description": "Stop on step error",
                    "default": True,
                },
                "undo_on_error": {
                    "type": "boolean",
                    "description": "Run undo steps on error",
                    "default": True,
                },
                "stop_undo_on_error": {
                    "type": "boolean",
                    "description": "Stop undo chain on error",
                    "default": True,
                },
                "steps": {
                    "type": "array",
                    "description": "List of steps forming the orchestration",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {
                                "type": "string",
                                "description": "Unique local reference ID for this step",
                            },
                            "undo": {
                                "type": "boolean",
                                "description": "false=do step, true=undo step",
                            },
                            "name": {"type": "string", "description": "Step name (max 40 chars)"},
                            "description": {"type": "string"},
                            "action_template_id": {
                                "type": "string",
                                "description": "UUID of existing action template",
                            },
                            "action_type": {
                                "type": "string",
                                "description": "Inline type: SHELL, PYTHON, REQUEST, ORCHESTRATION",
                                "enum": ["SHELL", "PYTHON", "REQUEST", "ORCHESTRATION"],
                            },
                            "code": {"type": "string", "description": "Inline code"},
                            "target": {
                                "type": ["string", "array"],
                                "description": "Target server granule(s) or 'all'",
                            },
                            "parent_step_ids": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "IDs of steps that must complete before this one",
                            },
                            "schema": {"type": "object"},
                            "expected_rc": {"type": "integer"},
                            "stop_on_error": {"type": "boolean"},
                            "pre_process": {"type": "string"},
                            "post_process": {"type": "string"},
                        },
                        "required": ["id", "undo"],
                    },
                },
            },
            "required": ["name", "steps"],
        },
    ),
    Tool(
        name="dm_add_step",
        description="Add step(s) to an existing orchestration.",
        inputSchema={
            "type": "object",
            "properties": {
                "orchestration_id": {
                    "type": "string",
                    "description": "UUID of the orchestration",
                },
                "steps": {
                    "type": "array",
                    "description": "Steps to add",
                    "items": {
                        "type": "object",
                        "properties": {
                            "undo": {"type": "boolean"},
                            "name": {"type": "string"},
                            "action_template_id": {"type": "string"},
                            "action_type": {
                                "type": "string",
                                "enum": ["SHELL", "PYTHON", "REQUEST", "ORCHESTRATION"],
                            },
                            "code": {"type": "string"},
                            "target": {"type": ["string", "array"]},
                            "parent_step_ids": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "schema": {"type": "object"},
                            "expected_rc": {"type": "integer"},
                            "stop_on_error": {"type": "boolean"},
                            "pre_process": {"type": "string"},
                            "post_process": {"type": "string"},
                        },
                        "required": ["undo"],
                    },
                },
            },
            "required": ["orchestration_id", "steps"],
        },
    ),
]


async def handle_creation_tool(name: str, arguments: dict, client: DimensigonClient) -> str:
    if name == "dm_create_action_template":
        data = {k: v for k, v in arguments.items() if v is not None}
        # version is auto-set to 1 for new templates
        data.setdefault("version", 1)
        result = await client.create_action_template(data)
        return f"Action template created successfully.\n{json.dumps(result, indent=2)}"

    if name == "dm_create_orchestration":
        data = {
            "name": arguments["name"],
            "steps": arguments["steps"],
        }
        for key in ("description", "stop_on_error", "undo_on_error", "stop_undo_on_error"):
            if key in arguments:
                data[key] = arguments[key]
        result = await client.create_orchestration_full(data)
        oid = result.get("id", "?")
        ver = result.get("version", "?")
        step_ids = result.get("step_ids", [])
        lines = [
            f"Orchestration created successfully.",
            f"  ID: {oid}",
            f"  Version: {ver}",
            f"  Steps created: {len(step_ids)}",
        ]
        for i, sid in enumerate(step_ids):
            rid = arguments["steps"][i]["id"] if i < len(arguments["steps"]) else "?"
            lines.append(f"    {rid} → {sid}")
        return "\n".join(lines)

    if name == "dm_add_step":
        orch_id = arguments["orchestration_id"]
        steps = arguments["steps"]
        for s in steps:
            s["orchestration_id"] = orch_id
        result = await client.create_steps(steps if len(steps) > 1 else steps[0])
        return f"Step(s) added successfully.\n{json.dumps(result, indent=2)}"

    return f"Unknown creation tool: {name}"
