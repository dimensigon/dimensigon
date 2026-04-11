# Tutorial 19: Natural Language Orchestration Runner

Run orchestrations using plain English instead of memorizing names and parameter syntax.

---

## Overview

The Natural Language (NL) Runner lets you describe what you want to do in everyday language -- "Run health check on all web servers" -- and Dimensigon resolves the intent, identifies the correct orchestration, maps targets, extracts parameters, and presents a confirmation dialog before executing. This removes the barrier of knowing exact orchestration names, target mapping syntax, and parameter formats.

## Prerequisites

- Dimensigon 3.0 installed with WebManager enabled
- Context-Aware AI feature enabled (Feature 17)
- At least one orchestration defined with a descriptive name or description
- Servers/granules registered in your dimension
- A valid user account with execution permissions

---

## Using the NL Input Bar in the Dashboard

### Step 1: Locate the Input Bar

After logging in to the WebManager dashboard, you will see the NL input bar at the top of the page. It has placeholder text: *"Describe what you want to do..."*

### Step 2: Type Your Request

Enter a natural language description of the task:

```
Run health check on all web servers
```

### Step 3: Review the Resolution

The system resolves your input and presents a confirmation dialog:

```
Resolved Intent:
  Orchestration:  health_check (v2)
  Targets:        web-01, web-02, web-03
  Parameters:     (none)

[Confirm & Run]  [Cancel]
```

### Step 4: Confirm and Execute

Click **Confirm & Run** to execute. Click **Cancel** to go back and refine your request.

---

## How Intent Resolution Works

The NL Runner uses a three-stage matching process to identify what you want to do.

### Stage 1: Exact Name Matching

If your input contains a string that exactly matches an orchestration name, it is selected immediately.

| Input | Match |
|-------|-------|
| "Run health_check" | Exact match: `health_check` |
| "Execute deploy_app on web-01" | Exact match: `deploy_app` |

### Stage 2: Fuzzy Matching Against the Orchestration Catalog

If no exact match is found, the system performs fuzzy matching against orchestration names. This handles typos, partial names, and natural phrasing.

| Input | Fuzzy Match |
|-------|-------------|
| "Run the health check" | Matches: `health_check` (score: 0.92) |
| "Do a deploy" | Matches: `deploy_app` (score: 0.85) |

### Stage 3: Description Keyword Matching

If fuzzy matching does not produce a confident result, the system searches orchestration descriptions for keywords from your input.

| Input | Description Match |
|-------|-------------------|
| "Check disk space on all servers" | Matches: `system_diagnostics` (description: "Checks CPU, memory, and disk space") |
| "Rotate the logs" | Matches: `log_rotation` (description: "Rotates and compresses application logs") |

---

## Target Extraction

The NL Runner resolves natural descriptions of targets to actual server names or granule groups.

| Natural Language | Resolved Targets |
|------------------|------------------|
| "all web servers" | web-01, web-02, web-03 (servers with granule `role=web`) |
| "production databases" | db-prod-01, db-prod-02 (servers with granules `role=database`, `env=production`) |
| "web-01" | web-01 (direct name match) |
| "the staging servers" | staging-01, staging-02 (servers with granule `env=staging`) |

Target resolution uses the registered server names and granule metadata in your dimension.

---

## Parameter Extraction

Parameters embedded in your natural language input are automatically extracted as key=value pairs.

| Input | Extracted Parameters |
|-------|---------------------|
| "Deploy v3 to production with rollback=true" | `rollback=true` |
| "Backup databases with retention=30" | `retention=30` |
| "Run stress test with duration=60 threads=4" | `duration=60`, `threads=4` |

Parameters are matched against the orchestration's parameter schema. Unknown parameters generate a warning in the confirmation dialog.

---

## Disambiguation

When multiple orchestrations match your input, the system presents a selection list instead of executing immediately.

### Example

Input: "Run deploy"

```
Multiple orchestrations match your request:

  1. deploy_app        - Deploy the application to target servers
  2. deploy_config     - Deploy configuration files
  3. deploy_database   - Deploy database migrations

Select an orchestration (1-3) or refine your request:
```

Select a number to proceed with that orchestration, or type a more specific request.

---

## Confirmation Dialog

Every NL execution shows a confirmation dialog before running. This is a safety measure -- the system never executes automatically from natural language input.

```
Resolved Intent:
  Orchestration:  deploy_app (v3)
  Targets:        web-01, web-02
  Parameters:
    rollback = true
    version  = 3.1.0

  Warnings:
    - Parameter "version" was inferred from "v3" in your input.
      Verify this is correct.

[Confirm & Run]  [Cancel]
```

Review the resolved orchestration, targets, and parameters carefully before confirming.

---

## API Reference

The NL Runner exposes two API endpoints for programmatic use.

### Resolve Intent

**POST** `/dm-webmanager/api/ai/resolve`

Parses natural language input and returns the resolved orchestration, targets, and parameters without executing.

#### Request

```bash
curl -X POST https://dm.example.com:5000/dm-webmanager/api/ai/resolve \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "input": "Run health check on all web servers"
  }'
```

#### Response (200 OK)

```json
{
  "orchestration": {
    "id": "orch-7f3a9b12",
    "name": "health_check",
    "version": 2,
    "description": "Runs CPU, memory, and disk checks on target servers"
  },
  "targets": [
    {"name": "web-01", "ip": "192.168.1.10"},
    {"name": "web-02", "ip": "192.168.1.11"},
    {"name": "web-03", "ip": "192.168.1.12"}
  ],
  "parameters": {},
  "confidence": 0.95,
  "alternatives": []
}
```

#### Response with Disambiguation (200 OK)

When multiple orchestrations match, `confidence` is lower and `alternatives` is populated:

```json
{
  "orchestration": {
    "id": "orch-7f3a9b12",
    "name": "deploy_app",
    "version": 3,
    "description": "Deploy the application to target servers"
  },
  "targets": [
    {"name": "web-01", "ip": "192.168.1.10"}
  ],
  "parameters": {"rollback": "true"},
  "confidence": 0.62,
  "alternatives": [
    {
      "id": "orch-8e4b0c23",
      "name": "deploy_config",
      "description": "Deploy configuration files",
      "confidence": 0.58
    },
    {
      "id": "orch-9f5c1d34",
      "name": "deploy_database",
      "description": "Deploy database migrations",
      "confidence": 0.41
    }
  ]
}
```

---

### Execute from NL Resolution

**POST** `/dm-webmanager/api/ai/execute`

Execute an orchestration after the user has reviewed and confirmed the resolution.

#### Request

```bash
curl -X POST https://dm.example.com:5000/dm-webmanager/api/ai/execute \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "orchestration_id": "orch-7f3a9b12",
    "targets": ["web-01", "web-02", "web-03"],
    "params": {},
    "confirmed": true
  }'
```

The `confirmed` field must be `true`. Requests with `confirmed: false` or the field omitted are rejected.

#### Response (202 Accepted)

```json
{
  "execution_id": "exec-4d5e6f78",
  "orchestration": "health_check",
  "status": "running",
  "targets": ["web-01", "web-02", "web-03"],
  "started_at": "2026-04-07T14:30:00Z"
}
```

#### Error Response (400 Bad Request)

```json
{
  "error": "Confirmation required",
  "message": "Set 'confirmed': true after reviewing the resolved intent."
}
```

---

## Complete curl Examples

### Example 1: Health Check

```bash
# Authenticate
TOKEN=$(curl -s -X POST https://dm.example.com:5000/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "your_password"}' \
  | jq -r '.access_token')

# Resolve the natural language input
RESOLUTION=$(curl -s -X POST https://dm.example.com:5000/dm-webmanager/api/ai/resolve \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"input": "Run health check on all web servers"}')

echo "$RESOLUTION" | jq .

# Extract the orchestration ID and targets
ORCH_ID=$(echo "$RESOLUTION" | jq -r '.orchestration.id')
TARGETS=$(echo "$RESOLUTION" | jq -c '[.targets[].name]')

# Execute after confirming
curl -s -X POST https://dm.example.com:5000/dm-webmanager/api/ai/execute \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"orchestration_id\": \"$ORCH_ID\",
    \"targets\": $TARGETS,
    \"params\": {},
    \"confirmed\": true
  }" | jq .
```

### Example 2: Deploy with Parameters

```bash
# Resolve
curl -s -X POST https://dm.example.com:5000/dm-webmanager/api/ai/resolve \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"input": "Deploy v3 to production with rollback=true"}' | jq .

# Execute (after reviewing the resolution)
curl -s -X POST https://dm.example.com:5000/dm-webmanager/api/ai/execute \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "orchestration_id": "orch-7f3a9b12",
    "targets": ["prod-web-01", "prod-web-02"],
    "params": {"rollback": "true", "version": "3.0.0"},
    "confirmed": true
  }' | jq .
```

### Example 3: Backup with Retention

```bash
# Resolve
curl -s -X POST https://dm.example.com:5000/dm-webmanager/api/ai/resolve \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"input": "Backup databases with retention=30"}' | jq .

# Execute
curl -s -X POST https://dm.example.com:5000/dm-webmanager/api/ai/execute \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "orchestration_id": "orch-2b3c4d56",
    "targets": ["db-01", "db-02"],
    "params": {"retention": "30"},
    "confirmed": true
  }' | jq .
```

---

## Tips

- **Be specific**: "Run health check on web servers" resolves better than "check servers."
- **Use key=value for parameters**: The extractor recognizes `key=value` patterns reliably. Natural phrasing like "with a 30-day retention" may also work but is less predictable.
- **Review before confirming**: Always check the confirmation dialog, especially the target list, to avoid running orchestrations on unintended servers.
- **Low confidence means ambiguity**: If the API returns a confidence below 0.7, consider refining your input or selecting from the alternatives list.
- **DShell support**: The NL Runner also works from DShell. Use `run "health check on web servers"` (with quotes around the natural language portion).

---

## Next Steps

- [Tutorial 20: Training and Feedback Loop](20-training-feedback.md) -- Help the AI improve over time
- [Tutorial 17: Context-Aware AI](17-context-aware-ai.md) -- Understand the AI engine behind NL resolution
