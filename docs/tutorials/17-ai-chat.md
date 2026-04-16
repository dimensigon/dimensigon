# Tutorial 17: AI-Assisted Orchestration Chat

## Overview

Dimensigon 3.0 includes an AI chat assistant that integrates directly into the orchestration builder within DM-WebManager. The assistant operates in two modes: **Review** mode, which analyzes your orchestration and offers improvement suggestions, and **Modify** mode, which generates modified orchestration JSON based on your natural-language instructions.

The AI chat sidebar provides context-aware assistance by injecting the current state of the orchestration builder into every request. This means the assistant always knows exactly what you are working on and can give relevant, actionable advice.

When the AI backend is not configured, the system returns helpful mock responses indicating how to enable the feature, so the UI workflow remains functional for testing and development.

---

## Prerequisites

- A running Dimensigon 3.0 instance with DM-WebManager accessible
- A user account with at least **operator** privileges
- Browser access to the DM-WebManager dashboard (`https://<server>:20194/dm-webmanager/dashboard`)
- (Optional) An AI backend configured if you want live LLM-powered responses

---

## Step-by-Step Instructions

### Step 1: Open the AI Chat Sidebar

1. Navigate to the DM-WebManager dashboard in your browser.
2. Open the **Orchestration Builder** by creating a new orchestration or editing an existing one.
3. Locate the **robot icon** in the top navigation bar.
4. Click the robot icon to open the AI chat sidebar panel on the right side of the screen.

The sidebar will slide into view, showing a chat interface with a text input field and mode selector.

### Step 2: Select a Chat Mode

The chat assistant supports two modes, selectable via a toggle or dropdown at the top of the sidebar:

- **Review** -- Analyzes the current orchestration and returns structured improvement suggestions.
- **Modify** -- Accepts a natural-language instruction and returns a modified version of the orchestration.

Choose the mode appropriate to your task before sending a message.

### Step 3: Using Review Mode

Type a review request into the chat input. Examples:

```
Review this orchestration
```

```
Check for parallelization opportunities
```

```
Are there any error handling issues?
```

The assistant evaluates the orchestration across four categories:

| Category | What it checks |
|---|---|
| **Error handling** | `stop_on_error` and `undo_on_error` configuration, presence of undo steps |
| **Parallelization** | Steps that are unnecessarily sequential but could run in parallel |
| **Best practices** | Descriptive step names, specified targets, clean DAG structure |
| **Potential issues** | Circular dependencies, missing dependencies, single points of failure |

The response is a structured list of **suggestion cards**, each containing:

- **Category** (one of: `error_handling`, `parallelization`, `best_practice`, `potential_issue`)
- **Severity** (`info`, `warning`, or `critical`)
- **Title** -- Short summary of the suggestion
- **Description** -- Detailed explanation
- **Affected steps** -- List of step IDs related to the suggestion

A brief overall **summary** is also returned.

### Step 4: Using Modify Mode

Switch to Modify mode and type a natural-language instruction. Examples:

```
Add error handling to all steps
```

```
Add a rollback step after the deployment step
```

```
Make steps 2 and 3 run in parallel instead of sequentially
```

The assistant returns a complete modified orchestration JSON that preserves existing structure and IDs unless your instruction specifically requires changes. Each step in the modified orchestration includes: `id`, `action_template_id`, `target`, `parents`, `children`, and `undo` fields. When new steps are added, they receive temporary IDs in the format `step-N`.

### Step 5: Accept or Reject Suggestions

After the assistant responds:

- **Review mode**: Each suggestion card has **Accept** and **Reject** buttons. Accepting a suggestion queues the recommended change; rejecting it dismisses the card.
- **Modify mode**: The full modified orchestration is displayed with a diff view. Click **Accept** to replace the current orchestration in the builder, or **Reject** to discard the proposed changes.

---

## How Context Injection Works

Every time you send a message through the AI chat sidebar, the system automatically captures the **current builder state** and includes it in the request as `orchestration_context`. This means:

1. The frontend serializes the orchestration currently loaded in the builder (steps, dependencies, targets, configuration) into JSON.
2. This JSON is sent alongside your message in the API request.
3. The AI prompt template receives the full orchestration JSON, so it has complete context about step ordering, action templates, targets, and DAG structure.
4. The assistant response is always grounded in your actual orchestration, not a generic answer.

You do not need to manually paste or describe your orchestration -- context injection handles this automatically.

---

## Rate Limiting

To prevent abuse, the AI chat endpoint enforces a rate limit:

- **20 requests per user per hour**
- The limit is tracked per user ID using a sliding window
- When the limit is exceeded, the API returns HTTP `429 Too Many Requests`
- Old timestamps (older than 1 hour) are pruned automatically, so the window resets naturally

If you hit the rate limit, wait for your oldest requests to age out of the 1-hour window before sending new ones.

---

## Configuration

### Enabling the AI Backend

By default, the AI chat feature operates in **mock mode**, returning placeholder responses that indicate the feature is not yet configured with a real AI backend.

To enable a live AI backend:

1. Set the environment variable before starting Dimensigon:

   ```bash
   export DM_AI_ENABLED=true
   ```

2. Ensure your AI backend service is reachable from the Dimensigon server.

3. Restart Dimensigon:

   ```bash
   dimensigon run
   ```

When `DM_AI_ENABLED` is set to `true`, the system attempts to call the AI handler (`dimensigon.ai.handler.handle_ai_chat`). If the handler is unavailable or raises an exception, the system falls back to mock mode gracefully.

### Configuration in config.py

The setting is defined in the application configuration:

```python
DM_AI_ENABLED = os.environ.get('DM_AI_ENABLED', 'false').lower() == 'true'
```

For testing environments, the default is `false`.

---

## API Reference

### POST /dm-webmanager/api/ai/chat

Send a message to the AI chat assistant.

**Authentication:** Required (session cookie or JWT)

**Request Body:**

```json
{
  "message": "Add error handling to all steps",
  "mode": "modify",
  "orchestration_context": {
    "name": "deploy-app",
    "steps": [
      {
        "id": "step-1",
        "action_template_id": "at-001",
        "target": ["web-prod-01"],
        "parents": [],
        "children": ["step-2"],
        "undo": false
      },
      {
        "id": "step-2",
        "action_template_id": "at-002",
        "target": ["web-prod-01"],
        "parents": ["step-1"],
        "children": [],
        "undo": false
      }
    ]
  }
}
```

**Fields:**

| Field | Type | Required | Description |
|---|---|---|---|
| `message` | string | Yes | The user instruction or question. Must not be empty. |
| `mode` | string | Yes | Either `"review"` or `"modify"`. |
| `orchestration_context` | object/null | No | Current orchestration JSON from the builder. |

**Response (Review Mode):**

```json
{
  "type": "review",
  "message": "Analysis complete.",
  "suggestions": [
    {
      "category": "error_handling",
      "severity": "warning",
      "title": "Missing undo steps for critical actions",
      "description": "Steps step-1 and step-2 perform deployment actions but have no corresponding undo steps. If a failure occurs mid-deployment, there is no automated rollback path.",
      "affected_steps": ["step-1", "step-2"]
    },
    {
      "category": "parallelization",
      "severity": "info",
      "title": "Sequential steps could run in parallel",
      "description": "Steps step-1 and step-2 target different servers and have no data dependency. Consider removing the parent-child relationship to allow parallel execution.",
      "affected_steps": ["step-1", "step-2"]
    }
  ],
  "summary": "The orchestration has 2 improvement opportunities. Focus on adding undo steps for production safety."
}
```

**Response (Modify Mode):**

```json
{
  "type": "modify",
  "message": "Orchestration modified successfully.",
  "modified_orchestration": {
    "name": "deploy-app",
    "steps": [
      {
        "id": "step-1",
        "action_template_id": "at-001",
        "target": ["web-prod-01"],
        "parents": [],
        "children": ["step-2"],
        "undo": false
      },
      {
        "id": "step-2",
        "action_template_id": "at-002",
        "target": ["web-prod-01"],
        "parents": ["step-1"],
        "children": ["step-3"],
        "undo": false
      },
      {
        "id": "step-3",
        "action_template_id": "at-003",
        "target": ["web-prod-01"],
        "parents": ["step-2"],
        "children": [],
        "undo": true
      }
    ]
  }
}
```

**Error Responses:**

| Status | Condition |
|---|---|
| `400` | Missing or empty `message`, or invalid `mode` |
| `401` | Not authenticated |
| `429` | Rate limit exceeded (20 requests/hour/user) |
| `500` | AI backend error (falls back to mock response) |

---

## curl Examples

### Review an orchestration

```bash
# First, log in and capture the session cookie
curl -k -c cookies.txt -X POST \
  https://localhost:20194/dm-webmanager/login \
  -H "Content-Type: application/json" \
  -d '{"username": "root", "password": "your_password"}'

# Send a review request
curl -k -b cookies.txt -X POST \
  https://localhost:20194/dm-webmanager/api/ai/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Review this orchestration for best practices",
    "mode": "review",
    "orchestration_context": {
      "name": "cluster-health-check",
      "steps": [
        {
          "id": "step-1",
          "action_template_id": "at-disk-check",
          "target": ["all"],
          "parents": [],
          "children": ["step-2"],
          "undo": false
        },
        {
          "id": "step-2",
          "action_template_id": "at-mem-check",
          "target": ["all"],
          "parents": ["step-1"],
          "children": [],
          "undo": false
        }
      ]
    }
  }'
```

### Modify an orchestration

```bash
curl -k -b cookies.txt -X POST \
  https://localhost:20194/dm-webmanager/api/ai/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Add a cleanup step that removes temporary files after deployment",
    "mode": "modify",
    "orchestration_context": {
      "name": "deploy-app",
      "steps": [
        {
          "id": "step-1",
          "action_template_id": "at-deploy",
          "target": ["web-prod-01"],
          "parents": [],
          "children": [],
          "undo": false
        }
      ]
    }
  }'
```

### Send a message without orchestration context

```bash
curl -k -b cookies.txt -X POST \
  https://localhost:20194/dm-webmanager/api/ai/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What are best practices for error handling in orchestrations?",
    "mode": "review"
  }'
```

### Handle rate limit response

```bash
# When rate limited, you will receive:
# HTTP 429
# {"error": "Rate limit exceeded. Maximum 20 requests per hour."}

# Check the response code and wait before retrying
```

---

## Prompt Templates

The AI chat feature uses two prompt templates defined in `dimensigon/ai/prompts.py`:

### Modify Orchestration Prompt

Used when `mode` is `"modify"`. The template receives the full orchestration JSON and the user instruction. It instructs the AI to:

- Return only valid JSON representing the modified orchestration
- Preserve existing structure and IDs unless the instruction requires changes
- Ensure each step has `id`, `action_template_id`, `target`, `parents`, `children`, and `undo` fields
- Keep the step DAG acyclic after modifications
- Generate temporary IDs in the format `step-N` for new steps

### Review Orchestration Prompt

Used when `mode` is `"review"`. The template instructs the AI to evaluate the orchestration across the four categories listed above and return structured JSON with suggestions, severity levels, and a summary.

---

## Troubleshooting

| Problem | Solution |
|---|---|
| Chat sidebar does not appear | Ensure you are in the Orchestration Builder view, not the dashboard. The robot icon only appears in the builder context. |
| Responses say "not currently configured" | This is the mock mode. Set `DM_AI_ENABLED=true` and restart. |
| HTTP 429 errors | You have exceeded 20 requests in the past hour. Wait for the window to reset. |
| Empty suggestions array | The orchestration may already follow best practices, or the AI backend could not identify specific improvements. |
| Modified orchestration is identical to original | The AI could not determine how to apply your instruction. Try rephrasing with more specific details. |

---

**Document Version**: 1.0.0
**Last Updated**: 2026-04-07
**Dimensigon Version**: 3.0
