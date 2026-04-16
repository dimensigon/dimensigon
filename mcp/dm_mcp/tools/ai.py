"""AI-powered MCP tools for natural language automation building.

These tools let external AI agents (Claude Code, custom agents) use
Dimensigon's AI stack:
- orch-library catalog search (TF-IDF over 1,700+ community templates)
- natural language → orchestration-execution intent resolution
- rule-based failure troubleshooting
"""

from __future__ import annotations

import json
import os
import sys

from mcp.types import Tool

from ..client import DimensigonClient


def _ensure_dimensigon_on_path():
    project_root = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    )
    if project_root not in sys.path:
        sys.path.insert(0, project_root)


AI_TOOLS = [
    Tool(
        name="dm_ai_search_templates",
        description=(
            "Search the Dimensigon orch-library (community-curated catalog of "
            "orchestrations and action templates) for entries matching a natural "
            "language query. Uses TF-IDF + fuzzy matching and returns the top-K "
            "ranked entries with name, description, category, and catalog path. "
            "Use dm_ai_fetch_template to get the full JSON for a chosen entry."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language description of what the template should do",
                },
                "entity_type": {
                    "type": "string",
                    "enum": ["orchestration", "action_template"],
                    "description": "Filter by entity type (optional)",
                },
                "action_type": {
                    "type": "string",
                    "enum": ["SHELL", "PYTHON", "ANSIBLE", "REQUEST", "ORCHESTRATION", "NATIVE", "TEST"],
                    "description": "Filter by action type (optional)",
                },
                "difficulty": {
                    "type": "string",
                    "enum": ["beginner", "intermediate", "advanced"],
                    "description": "Filter by difficulty level (optional)",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Max results to return (default 10)",
                    "default": 10,
                },
            },
            "required": ["query"],
        },
    ),
    Tool(
        name="dm_ai_fetch_template",
        description=(
            "Fetch the full JSON of a single template from the orch-library by its "
            "catalog path (as returned in dm_ai_search_templates results). Returns "
            "the complete definition ready to be passed to dm_create_orchestration "
            "or dm_create_action_template."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Catalog path of the template (e.g., 'orchestrations/deploy/nginx.json')",
                },
            },
            "required": ["path"],
        },
    ),
    Tool(
        name="dm_ai_resolve_command",
        description=(
            "Resolve a natural language command into an orchestration-execution plan. "
            "Matches the phrase against existing orchestration names/descriptions, "
            "extracts target servers (by name or granule), and parses parameters "
            "(key=value, 'with X Y', 'using X Y'). Returns {orchestration_id, "
            "orchestration_name, confidence, targets, params, alternatives}. "
            "Pass the result to dm_launch_orchestration."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "user_input": {
                    "type": "string",
                    "description": "Natural language command (e.g., 'deploy nginx on all web servers with version 1.25')",
                },
            },
            "required": ["user_input"],
        },
    ),
    Tool(
        name="dm_ai_troubleshoot",
        description=(
            "Analyze a failed step execution using rule-based pattern matching "
            "against common failure modes (permission denied, command not found, "
            "connection refused, timeouts, disk full, DNS, auth, OOM, etc.). "
            "Returns {root_cause, suggestion, confidence, modified_command}. "
            "Provide the step execution details directly or via execution_id + step_id."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "execution_id": {
                    "type": "string",
                    "description": "UUID of the parent orchestration execution (optional; used to fetch step_data)",
                },
                "step_id": {
                    "type": "string",
                    "description": "UUID of the failed step execution (optional; used with execution_id)",
                },
                "step_data": {
                    "type": "object",
                    "description": (
                        "Direct step data if not fetching via IDs. Keys: command, "
                        "stdout, stderr, rc, server_name, step_name, orchestration_name."
                    ),
                },
            },
            "required": [],
        },
    ),
]


async def handle_ai_tool(name: str, arguments: dict, client: DimensigonClient) -> str:
    if name == "dm_ai_search_templates":
        return _search_templates(arguments)
    if name == "dm_ai_fetch_template":
        return _fetch_template(arguments)
    if name == "dm_ai_resolve_command":
        return await _resolve_command(arguments, client)
    if name == "dm_ai_troubleshoot":
        return await _troubleshoot(arguments, client)
    return f"Unknown AI tool: {name}"


def _search_templates(arguments: dict) -> str:
    _ensure_dimensigon_on_path()
    from dimensigon.ai.template_suggest import suggest

    filters = {}
    for k in ("entity_type", "action_type", "difficulty"):
        if arguments.get(k):
            filters[k] = arguments[k]

    result = suggest(
        query=arguments["query"],
        top_k=arguments.get("top_k", 10),
        **filters,
    )
    return json.dumps(result, indent=2, default=str)


def _fetch_template(arguments: dict) -> str:
    _ensure_dimensigon_on_path()
    from dimensigon.ai.template_suggest import fetch_template

    data = fetch_template(arguments["path"])
    if data is None:
        return json.dumps({"error": f"Template not found or inaccessible: {arguments['path']}"})
    return json.dumps(data, indent=2, default=str)


async def _resolve_command(arguments: dict, client: DimensigonClient) -> str:
    _ensure_dimensigon_on_path()
    from dimensigon.ai.nl_runner import resolve_intent

    orchestrations = await client.list_orchestrations()
    servers = await client.list_servers()

    orchestrations = [
        {
            "id": o.get("id"),
            "name": o.get("name"),
            "description": o.get("description") or "",
        }
        for o in (orchestrations or [])
        if o.get("id") and o.get("name")
    ]
    servers = [
        {
            "id": s.get("id"),
            "name": s.get("name"),
            "granules": s.get("granules") or [],
        }
        for s in (servers or [])
        if s.get("id") and s.get("name")
    ]

    result = resolve_intent(arguments["user_input"], orchestrations, servers)
    return json.dumps(result, indent=2, default=str)


async def _troubleshoot(arguments: dict, client: DimensigonClient) -> str:
    _ensure_dimensigon_on_path()
    from dimensigon.ai.troubleshoot import analyze_failure

    step_data = arguments.get("step_data")
    if not step_data:
        execution_id = arguments.get("execution_id")
        step_id = arguments.get("step_id")
        if not execution_id or not step_id:
            return json.dumps(
                {"error": "Provide either step_data or both execution_id and step_id"}
            )
        try:
            execution = await client.get_execution(execution_id)
        except Exception as e:
            return json.dumps({"error": f"Failed to fetch execution {execution_id}: {e}"})

        step_exec = None
        for s in execution.get("steps", []) or []:
            if s.get("id") == step_id or s.get("step_id") == step_id:
                step_exec = s
                break
        if step_exec is None:
            return json.dumps({"error": f"Step {step_id} not found in execution {execution_id}"})

        step_data = {
            "command": step_exec.get("command") or step_exec.get("stdout_command") or "",
            "stdout": step_exec.get("stdout") or "",
            "stderr": step_exec.get("stderr") or "",
            "rc": step_exec.get("rc"),
            "server_name": step_exec.get("server_name") or step_exec.get("server") or "",
            "step_name": step_exec.get("step_name") or step_exec.get("name") or "",
            "orchestration_name": execution.get("orchestration_name") or "",
        }

    result = analyze_failure(step_data)
    return json.dumps(result, indent=2, default=str)
