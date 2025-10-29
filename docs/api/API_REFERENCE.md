# Dimensigon 2.0 API Reference

**Version:** 2.0
**Base URL:** `http://<server>:<port>`
**Default Port:** 5000
**Authentication:** JWT Bearer Token

---

## Table of Contents

1. [Authentication](#authentication)
2. [API v2.0 - New Endpoints](#api-v20---new-endpoints)
   - [Data Dictionary API](#data-dictionary-api)
   - [Executions Viewer API](#executions-viewer-api)
3. [API v1.0 - Legacy Endpoints](#api-v10---legacy-endpoints)
4. [Request/Response Formats](#requestresponse-formats)
5. [Error Handling](#error-handling)
6. [Rate Limiting](#rate-limiting)
7. [Pagination](#pagination)

---

## Authentication

### Overview

Dimensigon uses JWT (JSON Web Tokens) for authentication. All API endpoints (except `/login` and `/refresh`) require a valid JWT token in the Authorization header.

### Obtain Access Token

**POST** `/login`

Authenticate with username and password to obtain access and refresh tokens.

#### Request

```bash
curl -X POST http://localhost:5000/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "your_password"
  }'
```

#### Request Body Schema

```json
{
  "username": "string (required)",
  "password": "string (required)"
}
```

#### Response (200 OK)

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

#### Error Response (401 Unauthorized)

```json
{
  "error": "Bad username or password"
}
```

### Refresh Access Token

**POST** `/refresh`

Obtain a new access token using a refresh token.

#### Request

```bash
curl -X POST http://localhost:5000/refresh \
  -H "Authorization: Bearer <refresh_token>"
```

#### Response (200 OK)

```json
{
  "username": "admin",
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

### Using JWT Tokens

Include the access token in the Authorization header for all authenticated requests:

```bash
curl -X GET http://localhost:5000/api/v2/executions \
  -H "Authorization: Bearer <access_token>"
```

---

## API v2.0 - New Endpoints

The new v2.0 API provides enhanced functionality for data introspection and execution monitoring.

### Data Dictionary API

Base path: `/api/v2/data-dictionary`

The Data Dictionary API provides introspection and documentation for Dimensigon data models, including orchestrations, actions, and their schemas.

#### List All Entities

**GET** `/api/v2/data-dictionary/entities`

Retrieve a list of all available entities in the data dictionary.

##### Request

```bash
curl -X GET http://localhost:5000/api/v2/data-dictionary/entities \
  -H "Authorization: Bearer <token>"
```

##### Response (200 OK)

```json
{
  "entities": [
    {
      "key": "orchestration",
      "name": "Orchestration",
      "table": "D_orchestration",
      "description": "Orchestration workflow definitions",
      "count": 42
    },
    {
      "key": "action_template",
      "name": "ActionTemplate",
      "table": "D_action_template",
      "description": "Action template definitions",
      "count": 128
    },
    {
      "key": "step",
      "name": "Step",
      "table": "D_step",
      "description": "Orchestration step definitions",
      "count": 315
    },
    {
      "key": "orch_execution",
      "name": "OrchExecution",
      "table": "L_orch_execution",
      "description": "Orchestration execution records",
      "count": 1024
    },
    {
      "key": "step_execution",
      "name": "StepExecution",
      "table": "L_step_execution",
      "description": "Step execution records",
      "count": 5120
    },
    {
      "key": "server",
      "name": "Server",
      "table": "D_server",
      "description": "Server/node definitions",
      "count": 12
    },
    {
      "key": "user",
      "name": "User",
      "table": "D_user",
      "description": "User accounts",
      "count": 8
    },
    {
      "key": "gate",
      "name": "Gate",
      "table": "D_gate",
      "description": "Network gateway definitions",
      "count": 24
    },
    {
      "key": "route",
      "name": "Route",
      "table": "D_route",
      "description": "Network routing definitions",
      "count": 36
    },
    {
      "key": "file",
      "name": "File",
      "table": "D_file",
      "description": "File distribution definitions",
      "count": 58
    }
  ],
  "total": 10
}
```

##### Response Fields

- `entities`: Array of entity definitions
  - `key`: Internal entity key (used in API paths)
  - `name`: Entity class name
  - `table`: Database table name
  - `description`: Entity description
  - `count`: Number of records in the database
- `total`: Total number of entity types

#### Get Entity Schema

**GET** `/api/v2/data-dictionary/entities/<entity_key>`

Retrieve detailed schema information for a specific entity.

##### Request

```bash
curl -X GET http://localhost:5000/api/v2/data-dictionary/entities/orchestration \
  -H "Authorization: Bearer <token>"
```

##### Response (200 OK)

```json
{
  "entity": "orchestration",
  "schema": {
    "table_name": "D_orchestration",
    "description": "Orchestration workflow definitions with step dependencies",
    "columns": [
      {
        "name": "id",
        "type": "UUID()",
        "nullable": false,
        "primary_key": true,
        "unique": false,
        "default": null,
        "foreign_keys": []
      },
      {
        "name": "name",
        "type": "VARCHAR(80)",
        "nullable": false,
        "primary_key": false,
        "unique": false,
        "default": null,
        "foreign_keys": []
      },
      {
        "name": "version",
        "type": "INTEGER",
        "nullable": false,
        "primary_key": false,
        "unique": false,
        "default": null,
        "foreign_keys": []
      },
      {
        "name": "description",
        "type": "TEXT",
        "nullable": true,
        "primary_key": false,
        "unique": false,
        "default": null,
        "foreign_keys": []
      },
      {
        "name": "stop_on_error",
        "type": "BOOLEAN",
        "nullable": true,
        "primary_key": false,
        "unique": false,
        "default": null,
        "foreign_keys": []
      },
      {
        "name": "stop_undo_on_error",
        "type": "BOOLEAN",
        "nullable": true,
        "primary_key": false,
        "unique": false,
        "default": null,
        "foreign_keys": []
      },
      {
        "name": "undo_on_error",
        "type": "BOOLEAN",
        "nullable": true,
        "primary_key": false,
        "unique": false,
        "default": null,
        "foreign_keys": []
      },
      {
        "name": "created_at",
        "type": "DATETIME",
        "nullable": true,
        "primary_key": false,
        "unique": false,
        "default": null,
        "foreign_keys": []
      },
      {
        "name": "last_modified_at",
        "type": "DATETIME",
        "nullable": true,
        "primary_key": false,
        "unique": false,
        "default": null,
        "foreign_keys": []
      }
    ],
    "relationships": [
      {
        "name": "steps",
        "target": "Step",
        "uselist": true,
        "back_populates": "orchestration",
        "cascade": "all, delete-orphan"
      }
    ],
    "constraints": [
      "UNIQUE(name, version)"
    ],
    "methods": [
      {
        "name": "set_dependencies",
        "signature": "(dependencies: Union[Dict, Iterable])",
        "doc": "Set step dependencies for orchestration workflow"
      },
      {
        "name": "to_json",
        "signature": "(add_target: bool, add_params: bool, add_steps: bool)",
        "doc": "Convert orchestration to JSON representation"
      }
    ]
  }
}
```

#### List Orchestrations

**GET** `/api/v2/data-dictionary/orchestrations`

List all orchestrations with pagination and search.

##### Query Parameters

- `page` (integer): Page number (default: 1)
- `per_page` (integer): Items per page (default: 50, max: 200)
- `search` (string): Search in name or description

##### Request

```bash
curl -X GET "http://localhost:5000/api/v2/data-dictionary/orchestrations?page=1&per_page=20&search=deploy" \
  -H "Authorization: Bearer <token>"
```

##### Response (200 OK)

```json
{
  "orchestrations": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "Deploy Application",
      "version": 3,
      "description": "Deploy application to production servers",
      "step_count": 8,
      "has_schema": true
    },
    {
      "id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
      "name": "Deploy Database",
      "version": 2,
      "description": "Deploy database schema updates",
      "step_count": 5,
      "has_schema": true
    }
  ],
  "total": 42,
  "pages": 3,
  "page": 1,
  "per_page": 20
}
```

##### Response Fields

- `orchestrations`: Array of orchestration summaries
  - `id`: Orchestration UUID
  - `name`: Orchestration name
  - `version`: Version number
  - `description`: Orchestration description
  - `step_count`: Number of steps in the orchestration
  - `has_schema`: Whether orchestration has JSON schema defined
- `total`: Total number of orchestrations matching filters
- `pages`: Total number of pages
- `page`: Current page number
- `per_page`: Items per page

#### Get Orchestration Details

**GET** `/api/v2/data-dictionary/orchestrations/<orchestration_id>`

Retrieve detailed schema for a specific orchestration including all steps.

##### Request

```bash
curl -X GET http://localhost:5000/api/v2/data-dictionary/orchestrations/550e8400-e29b-41d4-a716-446655440000 \
  -H "Authorization: Bearer <token>"
```

##### Response (200 OK)

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Deploy Application",
  "version": 3,
  "description": "Deploy application to production servers",
  "schema": {
    "type": "object",
    "properties": {
      "app_name": {
        "type": "string",
        "description": "Application name to deploy"
      },
      "environment": {
        "type": "string",
        "enum": ["dev", "staging", "production"],
        "description": "Target environment"
      },
      "version": {
        "type": "string",
        "description": "Application version to deploy"
      }
    },
    "required": ["app_name", "environment", "version"]
  },
  "dependencies": {
    "step1": ["step2", "step3"],
    "step2": ["step4"],
    "step3": ["step4"]
  },
  "root_steps": [
    "7c9e6679-7425-40de-944b-e07fc1f90ae7"
  ],
  "steps": [
    {
      "id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
      "name": "Validate Input",
      "action_type": "SHELL",
      "description": "Validate deployment parameters",
      "schema": {
        "type": "object",
        "properties": {
          "app_name": {"type": "string"}
        }
      },
      "target": "all",
      "undo": false,
      "parents": [],
      "children": [
        "8d0e7690-8536-51ef-b058-f18ed2g01bf8"
      ],
      "action_template": {
        "id": "9e1f8701-9647-62fg-c169-g29fe3h12cg9",
        "name": "Validate Parameters",
        "version": 1,
        "schema": {
          "type": "object",
          "properties": {
            "params": {
              "type": "object"
            }
          }
        },
        "system_kwargs": ["server", "executor"]
      }
    },
    {
      "id": "8d0e7690-8536-51ef-b058-f18ed2g01bf8",
      "name": "Stop Application",
      "action_type": "SHELL",
      "description": "Stop running application",
      "schema": null,
      "target": "production_servers",
      "undo": true,
      "parents": [
        "7c9e6679-7425-40de-944b-e07fc1f90ae7"
      ],
      "children": [],
      "action_template": {
        "id": "af2g9812-a758-73gh-d27a-h3afg4i23dha",
        "name": "Stop Service",
        "version": 2,
        "schema": {
          "type": "object",
          "properties": {
            "service_name": {"type": "string"}
          }
        },
        "system_kwargs": ["server"]
      }
    }
  ]
}
```

##### Response Fields

- `id`: Orchestration UUID
- `name`: Orchestration name
- `version`: Version number
- `description`: Orchestration description
- `schema`: JSON Schema for orchestration parameters
- `dependencies`: Step dependency graph (parent -> children mapping)
- `root_steps`: Array of root step IDs (steps with no parents)
- `steps`: Array of step definitions
  - `id`: Step UUID
  - `name`: Step name
  - `action_type`: Action type (SHELL, PYTHON, etc.)
  - `description`: Step description
  - `schema`: JSON Schema for step parameters
  - `target`: Target servers/granules for execution
  - `undo`: Whether step has undo capability
  - `parents`: Array of parent step IDs
  - `children`: Array of child step IDs
  - `action_template`: Associated action template details

##### Error Response (404 Not Found)

```json
{
  "error": "Orchestration not found"
}
```

#### List Action Templates

**GET** `/api/v2/data-dictionary/action-templates`

List all action templates with pagination and filtering.

##### Query Parameters

- `page` (integer): Page number (default: 1)
- `per_page` (integer): Items per page (default: 50, max: 200)
- `search` (string): Search in name or description
- `action_type` (string): Filter by action type (SHELL, PYTHON, etc.)

##### Request

```bash
curl -X GET "http://localhost:5000/api/v2/data-dictionary/action-templates?page=1&per_page=20&action_type=SHELL" \
  -H "Authorization: Bearer <token>"
```

##### Response (200 OK)

```json
{
  "action_templates": [
    {
      "id": "9e1f8701-9647-62fg-c169-g29fe3h12cg9",
      "name": "Execute Shell Command",
      "version": 2,
      "action_type": "SHELL",
      "description": "Execute arbitrary shell command",
      "has_schema": true
    },
    {
      "id": "bf2h9823-b869-84hi-e38b-i4bgh5j34eib",
      "name": "Copy File",
      "version": 1,
      "action_type": "SHELL",
      "description": "Copy file to remote servers",
      "has_schema": true
    }
  ],
  "total": 128,
  "pages": 7,
  "page": 1,
  "per_page": 20
}
```

#### Get Action Template Details

**GET** `/api/v2/data-dictionary/action-templates/<action_id>`

Retrieve detailed schema for a specific action template.

##### Request

```bash
curl -X GET http://localhost:5000/api/v2/data-dictionary/action-templates/9e1f8701-9647-62fg-c169-g29fe3h12cg9 \
  -H "Authorization: Bearer <token>"
```

##### Response (200 OK)

```json
{
  "id": "9e1f8701-9647-62fg-c169-g29fe3h12cg9",
  "name": "Execute Shell Command",
  "version": 2,
  "action_type": "SHELL",
  "description": "Execute arbitrary shell command on target servers",
  "schema": {
    "type": "object",
    "properties": {
      "command": {
        "type": "string",
        "description": "Shell command to execute"
      },
      "timeout": {
        "type": "integer",
        "description": "Command timeout in seconds",
        "default": 300
      },
      "working_dir": {
        "type": "string",
        "description": "Working directory for command execution"
      }
    },
    "required": ["command"]
  },
  "system_kwargs": ["server", "executor", "timestamp"],
  "input_parameters": {
    "command": {
      "type": "string",
      "description": "Shell command to execute"
    },
    "timeout": {
      "type": "integer",
      "description": "Command timeout in seconds",
      "default": 300
    },
    "working_dir": {
      "type": "string",
      "description": "Working directory for command execution"
    }
  },
  "required_parameters": ["command"],
  "output_parameters": {},
  "examples": []
}
```

##### Response Fields

- `id`: Action template UUID
- `name`: Action template name
- `version`: Version number
- `action_type`: Type of action (SHELL, PYTHON, HTTP, etc.)
- `description`: Action description
- `schema`: Complete JSON Schema for action parameters
- `system_kwargs`: System-provided parameters (injected automatically)
- `input_parameters`: Input parameter definitions
- `required_parameters`: List of required parameter names
- `output_parameters`: Output parameter definitions
- `examples`: Example usage scenarios

#### Search Data Dictionary

**GET** `/api/v2/data-dictionary/search`

Search across orchestrations, action templates, and steps.

##### Query Parameters

- `q` (string, required): Search query
- `limit` (integer): Maximum results per category (default: 20, max: 100)

##### Request

```bash
curl -X GET "http://localhost:5000/api/v2/data-dictionary/search?q=deploy&limit=10" \
  -H "Authorization: Bearer <token>"
```

##### Response (200 OK)

```json
{
  "orchestrations": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "Deploy Application",
      "version": 3,
      "description": "Deploy application to production servers",
      "type": "orchestration"
    },
    {
      "id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
      "name": "Deploy Database",
      "version": 2,
      "description": "Deploy database schema updates",
      "type": "orchestration"
    }
  ],
  "action_templates": [
    {
      "id": "9e1f8701-9647-62fg-c169-g29fe3h12cg9",
      "name": "Deploy Docker Container",
      "version": 1,
      "action_type": "SHELL",
      "description": "Deploy Docker container to server",
      "type": "action_template"
    }
  ],
  "steps": [],
  "total": 3
}
```

##### Response Fields

- `orchestrations`: Array of matching orchestrations
- `action_templates`: Array of matching action templates
- `steps`: Array of matching steps
- `total`: Total number of results across all categories

##### Error Response (400 Bad Request)

```json
{
  "error": "Search query required"
}
```

---

### Executions Viewer API

Base path: `/api/v2/executions`

The Executions Viewer API provides real-time execution monitoring with filtering, pagination, and detailed views.

#### List Executions

**GET** `/api/v2/executions/`

List orchestration executions with filtering and pagination.

##### Query Parameters

- `page` (integer): Page number (default: 1)
- `per_page` (integer): Items per page (default: 50, max: 200)
- `status` (string): Filter by status (`running`, `success`, `failed`)
- `orchestration_id` (UUID): Filter by orchestration ID
- `server_id` (UUID): Filter by server ID
- `start_date` (ISO datetime): Filter executions after this date
- `end_date` (ISO datetime): Filter executions before this date
- `search` (string): Search in orchestration name or message

##### Request

```bash
curl -X GET "http://localhost:5000/api/v2/executions/?page=1&per_page=50&status=success" \
  -H "Authorization: Bearer <token>"
```

##### Response (200 OK)

```json
{
  "executions": [
    {
      "id": "a1b2c3d4-e5f6-4a5b-8c7d-9e0f1a2b3c4d",
      "orchestration": {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "name": "Deploy Application",
        "version": 3
      },
      "start_time": "2025-10-29T10:15:30.000000",
      "end_time": "2025-10-29T10:18:45.000000",
      "duration": 195.0,
      "status": "success",
      "success": true,
      "undo_success": null,
      "message": "Deployment completed successfully",
      "executor": "admin",
      "server": {
        "id": "b2c3d4e5-f6a7-5b6c-9d8e-0f1a2b3c4d5e",
        "name": "prod-server-01"
      },
      "params": {
        "app_name": "myapp",
        "environment": "production",
        "version": "1.2.3"
      },
      "step_count": 8
    },
    {
      "id": "b2c3d4e5-f6a7-5b6c-9d8e-0f1a2b3c4d5e",
      "orchestration": {
        "id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
        "name": "Deploy Database",
        "version": 2
      },
      "start_time": "2025-10-29T09:30:00.000000",
      "end_time": "2025-10-29T09:35:15.000000",
      "duration": 315.0,
      "status": "success",
      "success": true,
      "undo_success": null,
      "message": "Database deployment completed",
      "executor": "admin",
      "server": {
        "id": "c3d4e5f6-a7b8-6c7d-ae9f-1a2b3c4d5e6f",
        "name": "db-server-01"
      },
      "params": {
        "schema_version": "2.5.0"
      },
      "step_count": 5
    }
  ],
  "total": 1024,
  "pages": 21,
  "page": 1,
  "per_page": 50
}
```

##### Response Fields

- `executions`: Array of execution summaries
  - `id`: Execution UUID
  - `orchestration`: Orchestration details
    - `id`: Orchestration UUID
    - `name`: Orchestration name
    - `version`: Orchestration version
  - `start_time`: Execution start time (ISO format)
  - `end_time`: Execution end time (ISO format, null if running)
  - `duration`: Execution duration in seconds (null if running)
  - `status`: Execution status (`running`, `success`, `failed`)
  - `success`: Boolean success flag
  - `undo_success`: Boolean undo success flag (if undo was performed)
  - `message`: Execution message or error details
  - `executor`: Username of the user who triggered execution
  - `server`: Server details where execution occurred
    - `id`: Server UUID
    - `name`: Server name
  - `params`: Execution parameters (JSON object)
  - `step_count`: Number of steps in the execution
- `total`: Total number of executions matching filters
- `pages`: Total number of pages
- `page`: Current page number
- `per_page`: Items per page

#### Get Execution Details

**GET** `/api/v2/executions/<execution_id>`

Retrieve detailed information about a specific execution including all step executions.

##### Request

```bash
curl -X GET http://localhost:5000/api/v2/executions/a1b2c3d4-e5f6-4a5b-8c7d-9e0f1a2b3c4d \
  -H "Authorization: Bearer <token>"
```

##### Response (200 OK)

```json
{
  "id": "a1b2c3d4-e5f6-4a5b-8c7d-9e0f1a2b3c4d",
  "orchestration": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "Deploy Application",
    "version": 3
  },
  "start_time": "2025-10-29T10:15:30.000000",
  "end_time": "2025-10-29T10:18:45.000000",
  "duration": 195.0,
  "status": "success",
  "success": true,
  "undo_success": null,
  "message": "Deployment completed successfully",
  "executor": "admin",
  "server": {
    "id": "b2c3d4e5-f6a7-5b6c-9d8e-0f1a2b3c4d5e",
    "name": "prod-server-01"
  },
  "params": {
    "app_name": "myapp",
    "environment": "production",
    "version": "1.2.3"
  },
  "step_count": 8,
  "step_executions": [
    {
      "id": "c3d4e5f6-a7b8-6c7d-ae9f-1a2b3c4d5e6f",
      "step": {
        "id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
        "name": "Validate Input",
        "action_type": "SHELL"
      },
      "server": {
        "id": "b2c3d4e5-f6a7-5b6c-9d8e-0f1a2b3c4d5e",
        "name": "prod-server-01"
      },
      "start_time": "2025-10-29T10:15:31.000000",
      "end_time": "2025-10-29T10:15:33.000000",
      "duration": 2.0,
      "status": "success",
      "success": true,
      "rc": 0,
      "stdout": "Validation successful",
      "stderr": "",
      "params": {
        "app_name": "myapp"
      },
      "timings": {
        "pre_process": 0.1,
        "execution": 1.8,
        "post_process": 0.1
      }
    },
    {
      "id": "d4e5f6a7-b8c9-7d8e-bf0a-2b3c4d5e6f7a",
      "step": {
        "id": "8d0e7690-8536-51ef-b058-f18ed2g01bf8",
        "name": "Stop Application",
        "action_type": "SHELL"
      },
      "server": {
        "id": "b2c3d4e5-f6a7-5b6c-9d8e-0f1a2b3c4d5e",
        "name": "prod-server-01"
      },
      "start_time": "2025-10-29T10:15:34.000000",
      "end_time": "2025-10-29T10:15:38.000000",
      "duration": 4.0,
      "status": "success",
      "success": true,
      "rc": 0,
      "stdout": "Application stopped",
      "stderr": "",
      "params": {
        "service_name": "myapp"
      },
      "timings": {
        "pre_process": 0.2,
        "execution": 3.5,
        "post_process": 0.3
      }
    }
  ]
}
```

##### Response Fields

Same as list executions, plus:
- `step_executions`: Array of step execution details (see Step Execution format below)

##### Error Response (404 Not Found)

```json
{
  "error": "Execution not found"
}
```

#### Get Execution Steps

**GET** `/api/v2/executions/<execution_id>/steps`

Get all step executions for a specific orchestration execution.

##### Request

```bash
curl -X GET http://localhost:5000/api/v2/executions/a1b2c3d4-e5f6-4a5b-8c7d-9e0f1a2b3c4d/steps \
  -H "Authorization: Bearer <token>"
```

##### Response (200 OK)

```json
{
  "execution_id": "a1b2c3d4-e5f6-4a5b-8c7d-9e0f1a2b3c4d",
  "steps": [
    {
      "id": "c3d4e5f6-a7b8-6c7d-ae9f-1a2b3c4d5e6f",
      "step": {
        "id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
        "name": "Validate Input",
        "action_type": "SHELL"
      },
      "server": {
        "id": "b2c3d4e5-f6a7-5b6c-9d8e-0f1a2b3c4d5e",
        "name": "prod-server-01"
      },
      "start_time": "2025-10-29T10:15:31.000000",
      "end_time": "2025-10-29T10:15:33.000000",
      "duration": 2.0,
      "status": "success",
      "success": true,
      "rc": 0,
      "stdout": "Validation successful",
      "stderr": "",
      "params": {
        "app_name": "myapp"
      },
      "timings": {
        "pre_process": 0.1,
        "execution": 1.8,
        "post_process": 0.1
      }
    }
  ],
  "total": 8
}
```

#### Get Execution Statistics

**GET** `/api/v2/executions/stats`

Get execution statistics and metrics for a time period.

##### Query Parameters

- `hours` (integer): Time range in hours (default: 24, max: 720)

##### Request

```bash
curl -X GET "http://localhost:5000/api/v2/executions/stats?hours=48" \
  -H "Authorization: Bearer <token>"
```

##### Response (200 OK)

```json
{
  "time_range": "Last 48 hours",
  "total_executions": 387,
  "running": 3,
  "successful": 352,
  "failed": 32,
  "success_rate": 91.67,
  "top_orchestrations": [
    {
      "name": "Deploy Application",
      "version": 3,
      "count": 124
    },
    {
      "name": "Database Backup",
      "version": 1,
      "count": 89
    },
    {
      "name": "Health Check",
      "version": 2,
      "count": 76
    }
  ],
  "recent_failures": [
    {
      "id": "e5f6a7b8-c9d0-8e9f-c1a2-3b4c5d6e7f8a",
      "orchestration": "Deploy Application",
      "start_time": "2025-10-29T14:30:00.000000",
      "message": "Connection timeout to target server"
    },
    {
      "id": "f6a7b8c9-d0e1-9f0a-d2b3-4c5d6e7f8a9b",
      "orchestration": "Database Backup",
      "start_time": "2025-10-29T12:15:00.000000",
      "message": "Insufficient disk space"
    }
  ]
}
```

##### Response Fields

- `time_range`: Human-readable time range description
- `total_executions`: Total number of executions in the time range
- `running`: Number of currently running executions
- `successful`: Number of successful executions
- `failed`: Number of failed executions
- `success_rate`: Success rate percentage
- `top_orchestrations`: Most frequently executed orchestrations
  - `name`: Orchestration name
  - `version`: Orchestration version
  - `count`: Number of executions
- `recent_failures`: Recent failed executions
  - `id`: Execution UUID
  - `orchestration`: Orchestration name
  - `start_time`: Execution start time
  - `message`: Failure message

#### Get Running Executions

**GET** `/api/v2/executions/running`

Get all currently running executions.

##### Request

```bash
curl -X GET http://localhost:5000/api/v2/executions/running \
  -H "Authorization: Bearer <token>"
```

##### Response (200 OK)

```json
{
  "executions": [
    {
      "id": "g7h8i9j0-k1l2-a0b1-e3f4-5c6d7e8f9a0b",
      "orchestration": {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "name": "Deploy Application",
        "version": 3
      },
      "start_time": "2025-10-29T15:45:00.000000",
      "end_time": null,
      "duration": null,
      "status": "running",
      "success": null,
      "undo_success": null,
      "message": null,
      "executor": "admin",
      "server": {
        "id": "b2c3d4e5-f6a7-5b6c-9d8e-0f1a2b3c4d5e",
        "name": "prod-server-01"
      },
      "params": {
        "app_name": "myapp",
        "environment": "production",
        "version": "1.2.4"
      },
      "step_count": 8
    }
  ],
  "total": 3
}
```

#### Get Recent Executions

**GET** `/api/v2/executions/recent`

Get most recent executions (completed or running).

##### Query Parameters

- `limit` (integer): Number of executions to return (default: 20, max: 100)

##### Request

```bash
curl -X GET "http://localhost:5000/api/v2/executions/recent?limit=10" \
  -H "Authorization: Bearer <token>"
```

##### Response (200 OK)

```json
{
  "executions": [
    {
      "id": "a1b2c3d4-e5f6-4a5b-8c7d-9e0f1a2b3c4d",
      "orchestration": {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "name": "Deploy Application",
        "version": 3
      },
      "start_time": "2025-10-29T15:30:00.000000",
      "end_time": "2025-10-29T15:33:15.000000",
      "duration": 195.0,
      "status": "success",
      "success": true,
      "undo_success": null,
      "message": "Deployment completed successfully",
      "executor": "admin",
      "server": {
        "id": "b2c3d4e5-f6a7-5b6c-9d8e-0f1a2b3c4d5e",
        "name": "prod-server-01"
      },
      "params": {
        "app_name": "myapp",
        "environment": "production",
        "version": "1.2.3"
      },
      "step_count": 8
    }
  ],
  "total": 10
}
```

#### Get Step Execution Details

**GET** `/api/v2/executions/step-executions/<step_execution_id>`

Get detailed information about a specific step execution.

##### Request

```bash
curl -X GET http://localhost:5000/api/v2/executions/step-executions/c3d4e5f6-a7b8-6c7d-ae9f-1a2b3c4d5e6f \
  -H "Authorization: Bearer <token>"
```

##### Response (200 OK)

```json
{
  "id": "c3d4e5f6-a7b8-6c7d-ae9f-1a2b3c4d5e6f",
  "step": {
    "id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
    "name": "Validate Input",
    "action_type": "SHELL"
  },
  "server": {
    "id": "b2c3d4e5-f6a7-5b6c-9d8e-0f1a2b3c4d5e",
    "name": "prod-server-01"
  },
  "start_time": "2025-10-29T10:15:31.000000",
  "end_time": "2025-10-29T10:15:33.000000",
  "duration": 2.0,
  "status": "success",
  "success": true,
  "rc": 0,
  "stdout": "Validation successful\nAll parameters are valid\nReady to proceed",
  "stderr": "",
  "params": {
    "app_name": "myapp",
    "environment": "production"
  },
  "timings": {
    "pre_process": 0.1,
    "execution": 1.8,
    "post_process": 0.1
  },
  "orchestration_execution": {
    "id": "a1b2c3d4-e5f6-4a5b-8c7d-9e0f1a2b3c4d",
    "orchestration": {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "Deploy Application"
    }
  }
}
```

##### Response Fields

- `id`: Step execution UUID
- `step`: Step details
  - `id`: Step definition UUID
  - `name`: Step name
  - `action_type`: Action type
- `server`: Server where step executed
  - `id`: Server UUID
  - `name`: Server name
- `start_time`: Step start time (ISO format)
- `end_time`: Step end time (ISO format, null if running)
- `duration`: Step duration in seconds (null if running)
- `status`: Step status (`running`, `success`, `failed`)
- `success`: Boolean success flag
- `rc`: Return code (integer, for shell/script actions)
- `stdout`: Standard output from step execution
- `stderr`: Standard error from step execution
- `params`: Step execution parameters
- `timings`: Execution phase timings
  - `pre_process`: Pre-processing time in seconds
  - `execution`: Actual execution time in seconds
  - `post_process`: Post-processing time in seconds
- `orchestration_execution`: Parent orchestration execution details

##### Error Response (404 Not Found)

```json
{
  "error": "Step execution not found"
}
```

---

## API v1.0 - Legacy Endpoints

Base path: `/api/v1.0`

The v1.0 API provides the original RESTful interface for managing all Dimensigon resources. All v1.0 endpoints require JWT authentication.

### Common Query Parameters (All List Endpoints)

- `limit` (integer): Maximum number of results
- `offset` (integer): Number of results to skip
- `order_by` (string): Field to order by
- `filter` (JSON): Filter conditions
- `human` (boolean): Return human-readable format
- `split_lines` (boolean): Split stdout/stderr into arrays

### Orchestrations

#### List Orchestrations

**GET** `/api/v1.0/orchestrations`

##### Query Parameters

- `target` (boolean): Include target information
- `vars` (boolean): Include variable definitions
- `steps` (boolean): Include step definitions
- `action` (boolean): Include action template details
- `schema` (boolean): Include JSON schema

##### Request

```bash
curl -X GET "http://localhost:5000/api/v1.0/orchestrations?steps=true&action=true" \
  -H "Authorization: Bearer <token>"
```

##### Response (200 OK)

```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "Deploy Application",
    "version": 3,
    "description": "Deploy application to production servers",
    "stop_on_error": true,
    "stop_undo_on_error": true,
    "undo_on_error": true,
    "created_at": "2025-01-15T10:00:00.000000",
    "last_modified_at": "2025-10-20T15:30:00.000000",
    "steps": [
      {
        "id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
        "orchestration_id": "550e8400-e29b-41d4-a716-446655440000",
        "action_template_id": "9e1f8701-9647-62fg-c169-g29fe3h12cg9",
        "undo": false,
        "target": "all"
      }
    ]
  }
]
```

#### Get Orchestration

**GET** `/api/v1.0/orchestrations/<orchestration_id>`

##### Request

```bash
curl -X GET http://localhost:5000/api/v1.0/orchestrations/550e8400-e29b-41d4-a716-446655440000 \
  -H "Authorization: Bearer <token>"
```

##### Response (200 OK)

Returns single orchestration object (same format as list item).

#### Create Orchestration

**POST** `/api/v1.0/orchestrations`

##### Request Body

```json
{
  "name": "New Orchestration",
  "version": 1,
  "description": "Description of the orchestration",
  "stop_on_error": true,
  "stop_undo_on_error": true,
  "undo_on_error": true,
  "steps": [
    {
      "id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
      "action_template_id": "9e1f8701-9647-62fg-c169-g29fe3h12cg9",
      "undo": false,
      "target": "production_servers"
    }
  ]
}
```

##### Request

```bash
curl -X POST http://localhost:5000/api/v1.0/orchestrations \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d @orchestration.json
```

##### Response (201 Created)

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "version": 1
}
```

#### Update Orchestration

**PATCH** `/api/v1.0/orchestrations/<orchestration_id>`

##### Request Body

```json
{
  "description": "Updated description",
  "stop_on_error": false
}
```

##### Request

```bash
curl -X PATCH http://localhost:5000/api/v1.0/orchestrations/550e8400-e29b-41d4-a716-446655440000 \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"description": "Updated description"}'
```

##### Response (204 No Content)

### Action Templates

#### List Action Templates

**GET** `/api/v1.0/action_templates`

##### Request

```bash
curl -X GET http://localhost:5000/api/v1.0/action_templates \
  -H "Authorization: Bearer <token>"
```

##### Response (200 OK)

```json
[
  {
    "id": "9e1f8701-9647-62fg-c169-g29fe3h12cg9",
    "name": "Execute Shell Command",
    "version": 2,
    "action_type": "SHELL",
    "description": "Execute arbitrary shell command",
    "code": "#!/bin/bash\n{{command}}",
    "expected_stdout": null,
    "expected_stderr": null,
    "expected_rc": 0,
    "pre_process": null,
    "post_process": null,
    "schema": {
      "type": "object",
      "properties": {
        "command": {"type": "string"}
      }
    },
    "system_kwargs": ["server", "executor"],
    "last_modified_at": "2025-10-15T12:00:00.000000"
  }
]
```

#### Get Action Template

**GET** `/api/v1.0/action_templates/<action_template_id>`

#### Create Action Template

**POST** `/api/v1.0/action_templates`

##### Request Body

```json
{
  "name": "New Action",
  "version": 1,
  "action_type": "SHELL",
  "description": "Action description",
  "code": "#!/bin/bash\necho 'Hello World'",
  "expected_rc": 0,
  "schema": {
    "type": "object",
    "properties": {}
  }
}
```

#### Update Action Template

**PATCH** `/api/v1.0/action_templates/<action_template_id>`

### Executions

#### List Orchestration Executions

**GET** `/api/v1.0/orchestration_executions`

##### Query Parameters

- `human` (boolean): Human-readable format
- `steps` (boolean): Include step executions

##### Request

```bash
curl -X GET "http://localhost:5000/api/v1.0/orchestration_executions?human=true&steps=true" \
  -H "Authorization: Bearer <token>"
```

##### Response (200 OK)

```json
[
  {
    "id": "a1b2c3d4-e5f6-4a5b-8c7d-9e0f1a2b3c4d",
    "orchestration_id": "550e8400-e29b-41d4-a716-446655440000",
    "start_time": "2025-10-29T10:15:30.000000",
    "end_time": "2025-10-29T10:18:45.000000",
    "target": ["production_servers"],
    "params": {
      "app_name": "myapp",
      "environment": "production"
    },
    "executor_id": "d5e6f7a8-b9c0-7d8e-9f0a-1b2c3d4e5f6a",
    "server_id": "b2c3d4e5-f6a7-5b6c-9d8e-0f1a2b3c4d5e",
    "success": true,
    "undo_success": null,
    "message": "Deployment completed successfully"
  }
]
```

#### Get Orchestration Execution

**GET** `/api/v1.0/orchestration_executions/<execution_id>`

#### Get Orchestration Executions by Orchestration

**GET** `/api/v1.0/orchestrations/<orchestration_id>/executions`

##### Request

```bash
curl -X GET http://localhost:5000/api/v1.0/orchestrations/550e8400-e29b-41d4-a716-446655440000/executions \
  -H "Authorization: Bearer <token>"
```

#### Get Step Executions by Orchestration Execution

**GET** `/api/v1.0/orchestration_executions/<execution_id>/step_executions`

##### Request

```bash
curl -X GET http://localhost:5000/api/v1.0/orchestration_executions/a1b2c3d4-e5f6-4a5b-8c7d-9e0f1a2b3c4d/step_executions \
  -H "Authorization: Bearer <token>"
```

#### List Step Executions

**GET** `/api/v1.0/step_executions`

##### Request

```bash
curl -X GET http://localhost:5000/api/v1.0/step_executions \
  -H "Authorization: Bearer <token>"
```

#### Get Step Execution

**GET** `/api/v1.0/step_executions/<execution_id>`

### Steps

#### List Steps

**GET** `/api/v1.0/steps`

##### Request

```bash
curl -X GET http://localhost:5000/api/v1.0/steps \
  -H "Authorization: Bearer <token>"
```

##### Response (200 OK)

```json
[
  {
    "id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
    "orchestration_id": "550e8400-e29b-41d4-a716-446655440000",
    "action_template_id": "9e1f8701-9647-62fg-c169-g29fe3h12cg9",
    "undo": false,
    "target": "all",
    "created_on": "2025-01-15T10:00:00.000000"
  }
]
```

#### Get Step

**GET** `/api/v1.0/steps/<step_id>`

#### Create Step

**POST** `/api/v1.0/steps`

#### Update Step

**PATCH** `/api/v1.0/steps/<step_id>`

#### Delete Step

**DELETE** `/api/v1.0/steps/<step_id>`

#### Get Step Parent Relationships

**GET** `/api/v1.0/steps/<step_id>/relationship/parents`

#### Get Step Child Relationships

**GET** `/api/v1.0/steps/<step_id>/relationship/children`

### Servers

#### List Servers

**GET** `/api/v1.0/servers`

##### Request

```bash
curl -X GET http://localhost:5000/api/v1.0/servers \
  -H "Authorization: Bearer <token>"
```

##### Response (200 OK)

```json
[
  {
    "id": "b2c3d4e5-f6a7-5b6c-9d8e-0f1a2b3c4d5e",
    "name": "prod-server-01",
    "granules": ["production", "web"],
    "me": false,
    "created_on": "2025-01-10T08:00:00.000000",
    "last_modified_at": "2025-10-15T12:00:00.000000",
    "gates": [
      {
        "id": "c3d4e5f6-a7b8-6c7d-ae9f-1a2b3c4d5e6f",
        "dns": "prod-server-01.example.com",
        "port": 5000
      }
    ]
  }
]
```

#### Get Server

**GET** `/api/v1.0/servers/<server_id>`

#### Create Server

**POST** `/api/v1.0/servers`

##### Request Body

```json
{
  "name": "new-server",
  "granules": ["production"],
  "gates": [
    {
      "dns": "new-server.example.com",
      "port": 5000
    }
  ]
}
```

#### Update Server

**PATCH** `/api/v1.0/servers/<server_id>`

#### Delete Server

**DELETE** `/api/v1.0/servers/<server_id>`

### Users

#### List Users

**GET** `/api/v1.0/users`

##### Request

```bash
curl -X GET http://localhost:5000/api/v1.0/users \
  -H "Authorization: Bearer <token>"
```

##### Response (200 OK)

```json
[
  {
    "id": "d5e6f7a8-b9c0-7d8e-9f0a-1b2c3d4e5f6a",
    "name": "admin",
    "email": "admin@example.com",
    "created_at": "2025-01-01T00:00:00.000000",
    "active": true,
    "groups": "admins,operators",
    "last_modified_at": "2025-10-15T12:00:00.000000"
  }
]
```

#### Get User

**GET** `/api/v1.0/users/<user_id>`

#### Create User

**POST** `/api/v1.0/users`

##### Request Body

```json
{
  "name": "newuser",
  "email": "newuser@example.com",
  "password": "securepassword",
  "active": true,
  "groups": ["operators"]
}
```

#### Update User

**PATCH** `/api/v1.0/users/<user_id>`

#### Delete User

**DELETE** `/api/v1.0/users/<user_id>`

### Vault

The Vault provides secure storage for configuration and secrets.

#### List Vault Entries

**GET** `/api/v1.0/vault`

##### Request

```bash
curl -X GET http://localhost:5000/api/v1.0/vault \
  -H "Authorization: Bearer <token>"
```

#### Get Vault Entry

**GET** `/api/v1.0/vault/<scope>/<name>`

**GET** `/api/v1.0/vault/<name>`

##### Request

```bash
curl -X GET http://localhost:5000/api/v1.0/vault/global/api_key \
  -H "Authorization: Bearer <token>"
```

##### Response (200 OK)

```json
{
  "scope": "global",
  "name": "api_key",
  "value": "encrypted_value_here",
  "last_modified_at": "2025-10-15T12:00:00.000000"
}
```

#### Create/Update Vault Entry

**POST** `/api/v1.0/vault`

##### Request Body

```json
{
  "scope": "global",
  "name": "api_key",
  "value": "my_secret_value"
}
```

#### Delete Vault Entry

**DELETE** `/api/v1.0/vault/<scope>/<name>`

### Software

#### List Software

**GET** `/api/v1.0/software`

#### Get Software

**GET** `/api/v1.0/software/<software_id>`

#### Create Software

**POST** `/api/v1.0/software`

#### Update Software

**PATCH** `/api/v1.0/software/<software_id>`

#### Delete Software

**DELETE** `/api/v1.0/software/<software_id>`

#### Get Software Servers

**GET** `/api/v1.0/software/<software_id>/servers`

### Files

#### List Files

**GET** `/api/v1.0/file`

#### Get File

**GET** `/api/v1.0/file/<file_id>`

#### Create File

**POST** `/api/v1.0/file`

#### Update File

**PATCH** `/api/v1.0/file/<file_id>`

#### Delete File

**DELETE** `/api/v1.0/file/<file_id>`

#### Get File Destinations

**GET** `/api/v1.0/file/<file_id>/destinations`

### Logs

#### List Logs

**GET** `/api/v1.0/log`

#### Get Log

**GET** `/api/v1.0/log/<log_id>`

### Transfers

#### List Transfers

**GET** `/api/v1.0/transfers`

#### Get Transfer

**GET** `/api/v1.0/transfers/<transfer_id>`

### Granules

#### List Granules

**GET** `/api/v1.0/granules`

Returns a list of all unique granule values across all servers.

##### Request

```bash
curl -X GET http://localhost:5000/api/v1.0/granules \
  -H "Authorization: Bearer <token>"
```

##### Response (200 OK)

```json
{
  "granules": ["production", "staging", "development", "web", "database", "cache"]
}
```

---

## Request/Response Formats

### Content Type

All API requests and responses use JSON format:

```
Content-Type: application/json
```

### Date/Time Format

All timestamps use ISO 8601 format with microseconds:

```
2025-10-29T10:15:30.000000
```

Alternative datetime format used in some v1.0 endpoints:

```
2025-10-29 10:15:30
```

### UUID Format

All entity IDs use UUID format:

```
550e8400-e29b-41d4-a716-446655440000
```

### JSON Schema

Many entities support JSON Schema for validation:

```json
{
  "type": "object",
  "properties": {
    "parameter_name": {
      "type": "string",
      "description": "Parameter description",
      "default": "default_value"
    }
  },
  "required": ["parameter_name"]
}
```

---

## Error Handling

### Error Response Format

All error responses follow this format:

```json
{
  "error": {
    "type": "ErrorClassName",
    "message": "Human-readable error message",
    "path": ["schema", "path", "to", "error"],
    "additional_field": "additional_value"
  }
}
```

### HTTP Status Codes

- `200 OK`: Successful GET request
- `201 Created`: Successful POST request creating a resource
- `204 No Content`: Successful PUT/PATCH/DELETE request
- `400 Bad Request`: Invalid request (validation error, missing required fields)
- `401 Unauthorized`: Missing or invalid authentication token
- `403 Forbidden`: Authenticated but not authorized for this resource
- `404 Not Found`: Resource not found
- `409 Conflict`: Resource conflict (e.g., duplicate unique field)
- `422 Unprocessable Entity`: Valid JSON but semantic errors
- `500 Internal Server Error`: Server error

### Common Error Types

#### Validation Error (400)

```json
{
  "error": {
    "type": "ValidationError",
    "message": "'command' is a required property",
    "path": ["properties"],
    "schema": {
      "type": "object",
      "required": ["command"]
    }
  }
}
```

#### Authentication Error (401)

```json
{
  "error": "Bad username or password"
}
```

#### Not Found Error (404)

```json
{
  "error": "Orchestration not found"
}
```

#### Resource Not Found (404)

```json
{
  "error": {
    "type": "NoResultFound",
    "message": "No row was found for one()"
  }
}
```

#### Invalid Date Format Error (400)

```json
{
  "error": {
    "type": "InvalidDateFormat",
    "message": "Date '2025-13-45' does not match format '%Y-%m-%d %H:%M:%S'"
  }
}
```

### Debug Mode

When the application is running in debug mode, error responses include stack traces:

```json
{
  "error": {
    "type": "ValueError",
    "message": "Invalid parameter",
    "traceback": [
      "Traceback (most recent call last):",
      "  File \"/app/dimensigon/web/routes.py\", line 45, in endpoint",
      "    process_request()",
      "ValueError: Invalid parameter"
    ]
  }
}
```

---

## Rate Limiting

**Note:** Rate limiting is not currently enforced in Dimensigon 2.0, but may be added in future versions.

Best practices:
- Limit parallel requests to reasonable numbers (e.g., max 10 concurrent)
- Use pagination for large result sets
- Cache responses when appropriate
- Use WebSocket connections for real-time monitoring instead of polling

---

## Pagination

### v2.0 API Pagination

v2.0 endpoints use page-based pagination:

#### Query Parameters

- `page` (integer): Page number (1-indexed, default: 1)
- `per_page` (integer): Items per page (default: 50, max varies by endpoint)

#### Response Format

```json
{
  "items": [...],
  "total": 1024,
  "pages": 21,
  "page": 1,
  "per_page": 50
}
```

#### Example

```bash
# Get page 2 with 20 items per page
curl -X GET "http://localhost:5000/api/v2/executions/?page=2&per_page=20" \
  -H "Authorization: Bearer <token>"
```

### v1.0 API Pagination

v1.0 endpoints use offset-based pagination:

#### Query Parameters

- `limit` (integer): Maximum number of results to return
- `offset` (integer): Number of results to skip

#### Example

```bash
# Get 20 results starting from result 40
curl -X GET "http://localhost:5000/api/v1.0/orchestrations?limit=20&offset=40" \
  -H "Authorization: Bearer <token>"
```

### Sorting

Many endpoints support sorting via query parameters:

```bash
# Sort by start_time descending (v2.0 - built-in)
curl -X GET "http://localhost:5000/api/v2/executions/" \
  -H "Authorization: Bearer <token>"

# Sort by name ascending (v1.0)
curl -X GET "http://localhost:5000/api/v1.0/orchestrations?order_by=name" \
  -H "Authorization: Bearer <token>"
```

---

## Additional Resources

### Health Check

**GET** `/healthcheck`

Check the health status of the Dimensigon instance.

#### Request

```bash
curl -X GET http://localhost:5000/healthcheck
```

#### Response (200 OK)

```json
{
  "version": "2.0.0",
  "catalog_version": "2025-10-29 15:30:45",
  "services": [],
  "server": {
    "id": "b2c3d4e5-f6a7-5b6c-9d8e-0f1a2b3c4d5e",
    "name": "prod-server-01"
  },
  "neighbours": [
    {
      "id": "c3d4e5f6-a7b8-6c7d-ae9f-1a2b3c4d5e6f",
      "name": "prod-server-02"
    }
  ],
  "cluster": {
    "alive": [
      "b2c3d4e5-f6a7-5b6c-9d8e-0f1a2b3c4d5e",
      "c3d4e5f6-a7b8-6c7d-ae9f-1a2b3c4d5e6f"
    ],
    "in_coma": []
  },
  "now": "2025-10-29T15:45:00.000000"
}
```

### Ping

**POST** `/ping`

Simple ping endpoint for network connectivity testing.

#### Request

```bash
curl -X POST http://localhost:5000/ping \
  -H "Content-Type: application/json" \
  -d '{"timestamp": "2025-10-29T15:45:00.000000"}'
```

#### Response (200 OK)

```json
{
  "timestamp": "2025-10-29T15:45:00.000000",
  "dest_time": "2025-10-29T15:45:00.123456",
  "servers": {}
}
```

---

## GUI Routes (DM-WebManager)

Base path: `/dm-webmanager`

The DM-WebManager provides a web-based GUI for managing Dimensigon.

### Dashboard

**GET** `/dm-webmanager/`

**GET** `/dm-webmanager/dashboard`

Main dashboard view showing system overview.

### Orchestrations Management

**GET** `/dm-webmanager/orchestrations`

View and manage orchestrations through the GUI.

### Executions Monitoring

**GET** `/dm-webmanager/executions`

Monitor orchestration executions in real-time.

### Data Dictionary Browser

**GET** `/dm-webmanager/data-dictionary`

Browse data models and schemas through the GUI.

### Admin Panel

**GET** `/admin`

Flask-Admin interface with the following sections:

#### Workflow Category
- **Orchestrations**: Manage orchestration definitions
- **Action Templates**: Manage action templates
- **Steps**: Manage orchestration steps

#### Monitoring Category
- **Executions**: View orchestration execution history
- **Step Executions**: View detailed step execution logs

#### Infrastructure Category
- **Servers**: Manage server/node definitions

---

## Notes

1. All API v2.0 endpoints require JWT authentication via the `Authorization: Bearer <token>` header
2. All API v1.0 endpoints require JWT authentication via the `Authorization: Bearer <token>` header
3. Some v1.0 endpoints support the `@forward_or_dispatch()` decorator for cluster-wide operations
4. Date/time values are in UTC timezone
5. The API supports distributed operations across the Dimensigon cluster
6. Catalog versioning ensures data consistency across distributed nodes
7. All write operations (POST, PATCH, DELETE) may trigger catalog updates across the cluster
8. The system uses double encryption (SSL + encrypted messaging) for all communications
9. Execution monitoring provides real-time visibility into orchestration runs
10. The Data Dictionary API enables runtime introspection of all data models

---

## Version History

- **v2.0.0** (2025-10): Added Data Dictionary API and Executions Viewer API
- **v1.0.0** (2024): Initial REST API release

---

## Support

For issues, questions, or contributions:
- GitHub: https://github.com/dimensigon/dimensigon
- Documentation: https://dimensigon.com/docs
- Store: https://store.dimensigon.com

---

**Last Updated:** 2025-10-29
