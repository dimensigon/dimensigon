# Dimensigon MCP Server

Model Context Protocol (MCP) server that bridges AI assistants to the Dimensigon REST API, enabling natural language automation discovery, orchestration creation, and execution.

## Overview

The Dimensigon MCP server exposes 15 tools across 4 categories that allow AI assistants (Claude, etc.) to interact with a Dimensigon cluster:

| Category | Tools | Purpose |
|---|---|---|
| **Discovery** | 7 | List/inspect servers, orchestrations, action templates, executions |
| **Creation** | 3 | Create action templates, orchestrations with steps and DAG dependencies |
| **Execution** | 2 | Launch orchestrations on targets, run shell commands |
| **Utility** | 3 | Vault entries, server details, granule listing |

## Requirements

- Python 3.10+
- A running Dimensigon instance with REST API access
- Dependencies: `mcp`, `httpx`, `python-dotenv`

## Installation

```bash
cd mcp/
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Configuration

Set environment variables directly or via a `.env` file in the `mcp/` directory:

| Variable | Default | Description |
|---|---|---|
| `DM_HOST` | `localhost` | Dimensigon server hostname or IP |
| `DM_PORT` | `20194` | Dimensigon server port |
| `DM_SCHEME` | `https` | Protocol (`http` or `https`) |
| `DM_USERNAME` | `root` | Login username |
| `DM_PASSWORD` | *(required)* | Login password |
| `DM_VERIFY_SSL` | `false` | Verify SSL certificates |
| `DM_TOKEN_REFRESH_MARGIN` | `60` | Seconds before token expiry to trigger refresh |

Example `.env` file:

```env
DM_HOST=192.168.1.10
DM_PORT=20194
DM_SCHEME=https
DM_USERNAME=root
DM_PASSWORD=my-secret-password
DM_VERIFY_SSL=false
```

## Running

### Standalone (stdio mode)

```bash
cd mcp/
source .venv/bin/activate
python -m dm_mcp.server
```

### Claude Code Integration

Add to your project's `.mcp.json` or Claude Code settings:

```json
{
  "dimensigon": {
    "command": "python3.11",
    "args": ["-m", "dm_mcp.server"],
    "cwd": "/path/to/dimensigon/mcp",
    "env": {
      "DM_HOST": "your-dm-host",
      "DM_PORT": "20194",
      "DM_USERNAME": "root",
      "DM_PASSWORD": "your-password",
      "DM_SCHEME": "https",
      "DM_VERIFY_SSL": "false"
    }
  }
}
```

## Tools Reference

### Discovery Tools

#### `dm_list_servers`
List all servers in the cluster with names, granules, and optionally network gates.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `include_gates` | boolean | No | Include IP/port gate details |

#### `dm_list_orchestrations`
List all orchestrations with optional step and schema details.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `include_steps` | boolean | No | Include step details |
| `include_schema` | boolean | No | Include input/output schema |

#### `dm_get_orchestration`
Get full details of a specific orchestration including steps, dependencies, and schema.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `orchestration_id` | string | Yes | UUID of the orchestration |

#### `dm_list_action_templates`
List all reusable action templates with optional type filtering.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `action_type` | string | No | Filter: `SHELL`, `PYTHON`, `REQUEST`, `ORCHESTRATION`, `NATIVE`, `ANSIBLE`, `TEST` |

#### `dm_get_action_template`
Get full details of an action template including code, schema, and processing logic.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `action_template_id` | string | Yes | UUID of the action template |

#### `dm_list_executions`
List orchestration execution history.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `include_steps` | boolean | No | Include step execution details |
| `limit` | integer | No | Max results (default: 20) |

#### `dm_get_execution`
Get detailed execution results with per-step stdout, stderr, return codes, and timing.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `execution_id` | string | Yes | UUID of the execution |

### Creation Tools

#### `dm_create_action_template`
Create a reusable action template.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `name` | string | Yes | Template name (max 40 chars) |
| `action_type` | string | Yes | `SHELL`, `PYTHON`, `REQUEST`, `ORCHESTRATION`, `ANSIBLE` |
| `code` | string | Yes | Code/command to execute |
| `description` | string | No | Human-readable description |
| `expected_rc` | integer | No | Expected return code |
| `schema` | object | No | Input/output variable schema |
| `pre_process` | string | No | Python code to run before execution |
| `post_process` | string | No | Python code to run after execution |

#### `dm_create_orchestration`
Create a complete orchestration with steps and DAG dependencies in a single call.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `name` | string | Yes | Orchestration name |
| `description` | string | No | What this orchestration does |
| `stop_on_error` | boolean | No | Stop on step error (default: true) |
| `undo_on_error` | boolean | No | Run undo steps on error (default: true) |
| `steps` | array | Yes | List of step definitions (see below) |

**Step definition:**

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | Yes | Unique local reference ID |
| `undo` | boolean | Yes | `false` = forward step, `true` = rollback step |
| `action_template_id` | string | One of | UUID of existing action template |
| `action_type` + `code` | string | One of | Inline action definition |
| `target` | string/array | No | Target server granule(s) or `"all"` |
| `parent_step_ids` | array | No | IDs of prerequisite steps (forms DAG) |

#### `dm_add_step`
Add steps to an existing orchestration.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `orchestration_id` | string | Yes | UUID of the orchestration |
| `steps` | array | Yes | Steps to add (same schema as above) |

### Execution Tools

#### `dm_launch_orchestration`
Execute an orchestration on target servers.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `orchestration_id` | string | No | UUID (alternative to name) |
| `orchestration_name` | string | No | Name (alternative to UUID) |
| `version` | integer | No | Specific version (latest if omitted) |
| `hosts` | string/array/object | Yes | Target servers or `{granule: [servers]}` |
| `params` | object | No | Input parameters |
| `background` | boolean | No | Run in background (default: true) |
| `timeout` | integer | No | Timeout in seconds |

#### `dm_run_command`
Execute a shell command on target servers.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `command` | string | Yes | Shell command to execute |
| `target` | string/array | No | Target server(s), defaults to current |
| `timeout` | integer | No | Timeout in seconds |

### Utility Tools

#### `dm_list_vault`
List vault entries or scopes.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `scope` | string | No | Filter by scope |
| `list_scopes` | boolean | No | List scopes instead of entries |

#### `dm_get_server_detail`
Get detailed server info including gates and connectivity.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `server_id` | string | Yes | Server UUID or name |

#### `dm_list_granules`
List all server granules (groups/tags).

*No parameters required.*

## Architecture

```
mcp/
  dm_mcp/
    server.py         # MCP entry point (stdio transport)
    client.py         # Async HTTP client → Dimensigon REST API
    auth.py           # JWT authentication (login/refresh/auto-renew)
    config.py         # Environment variable configuration
    exceptions.py     # Error hierarchy
    formatters.py     # API JSON → structured text for LLM
    tools/
      discovery.py    # Read tools (7)
      creation.py     # Write tools (3)
      execution.py    # Execution tools (2)
      utility.py      # Utility tools (3)
```

The server runs as a long-lived stdio process. A singleton `DimensigonClient` manages HTTP connections and JWT token lifecycle. All API responses are formatted into structured text optimized for LLM consumption.

## Usage Examples

Once registered as an MCP server in Claude Code, users can interact naturally:

- *"What servers are in the cluster?"* → calls `dm_list_servers`
- *"Show me all orchestrations"* → calls `dm_list_orchestrations`
- *"Create an orchestration that deploys my app: pull the latest image, stop the old container, start the new one"* → calls `dm_create_orchestration` with 3 SHELL steps in a DAG
- *"Run that orchestration on the web servers"* → calls `dm_launch_orchestration`
- *"What happened in the last execution?"* → calls `dm_list_executions` then `dm_get_execution`

## Dimensigon REST API Endpoints Used

| MCP Tool | HTTP Method | Endpoint |
|---|---|---|
| `dm_list_servers` | GET | `/api/v1.0/servers` |
| `dm_get_server_detail` | GET | `/api/v1.0/servers/<id>` |
| `dm_list_orchestrations` | GET | `/api/v1.0/orchestrations` |
| `dm_get_orchestration` | GET | `/api/v1.0/orchestrations/<id>` |
| `dm_list_action_templates` | GET | `/api/v1.0/action_templates` |
| `dm_get_action_template` | GET | `/api/v1.0/action_templates/<id>` |
| `dm_list_executions` | GET | `/api/v1.0/orchestration_executions` |
| `dm_get_execution` | GET | `/api/v1.0/orchestration_executions/<id>` |
| `dm_create_action_template` | POST | `/api/v1.0/action_templates` |
| `dm_create_orchestration` | POST | `/api/v1.0/orchestrations/full` |
| `dm_add_step` | POST | `/api/v1.0/steps` |
| `dm_launch_orchestration` | POST | `/api/v1.0/launch/orchestration[/<id>]` |
| `dm_run_command` | POST | `/api/v1.0/launch/command` |
| `dm_list_vault` | GET | `/api/v1.0/vault` |
| `dm_list_granules` | GET | `/api/v1.0/granules` |
| *(auth)* | POST | `/login`, `/refresh` |
