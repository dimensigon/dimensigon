# Tutorial 18: AI-Powered Troubleshooting for Failed Steps

## Overview

When a step execution fails in Dimensigon, the AI troubleshooting system automatically analyzes the failure output and provides actionable diagnosis. The system uses a rule-based engine that matches 10 built-in error patterns against the combined stdout and stderr output, returning a root cause explanation, a fix suggestion, a confidence level, and optionally a modified command that addresses the problem.

The troubleshooting system works without any external AI backend. It ships ready to use with pattern-matching rules covering the most common infrastructure failure scenarios. For organizations that want deeper analysis, a `TROUBLESHOOT_PROMPT` template is provided for integration with an LLM backend.

Two actions are available after diagnosis: **Apply Fix** patches the step command in the orchestration, and **Apply & Re-run** patches the command and immediately re-executes the failed step.

---

## Prerequisites

- A running Dimensigon 3.0 instance with DM-WebManager accessible
- A user account with at least **operator** privileges (required for the apply-fix endpoint)
- An orchestration with at least one step that has been executed

---

## How It Triggers

The troubleshooting system engages automatically when a step execution fails:

1. You run an orchestration through the DM-WebManager execution monitor or via API.
2. One or more steps fail (non-zero return code, or marked as failed by post-processing validation).
3. The execution monitor displays the failed step with a **Troubleshoot** button.
4. Clicking **Troubleshoot** sends the step execution data to the troubleshooting API.
5. The response is displayed inline, showing the root cause, suggestion, confidence level, and (if applicable) a corrected command.

You can also invoke the troubleshooting API directly with ad-hoc data, without referencing a stored step execution.

---

## Supported Error Patterns

The rule-based engine includes 10 built-in error patterns, checked in priority order against the combined stdout and stderr output:

### 1. Permission Denied

**Pattern:** `permission denied` (case-insensitive)

**Root cause:** The command failed due to insufficient permissions.

**Suggestion:** Run the command with elevated privileges (sudo) or adjust file/directory permissions with chmod/chown.

**Auto-fix:** If the command does not already start with `sudo`, prepends `sudo` to the command.

**Confidence:** high

**Example stderr:**
```
cat: /etc/shadow: Permission denied
```

**Modified command:** `sudo cat /etc/shadow`

---

### 2. Command Not Found

**Pattern:** `command not found` (case-insensitive)

**Root cause:** The command or binary is not installed or not in PATH.

**Suggestion:** Install the missing package or specify the full path to the executable. Verify PATH includes the binary location.

**Auto-fix:** None (requires manual investigation).

**Confidence:** high

**Example stderr:**
```
bash: foobar: command not found
```

---

### 3. No Such File or Directory

**Pattern:** `no such file or directory` (case-insensitive)

**Root cause:** A referenced file or directory does not exist.

**Suggestion:** Verify the file/directory path is correct. Ensure prerequisite steps have created the expected files before this step runs.

**Auto-fix:** None.

**Confidence:** high

**Example stderr:**
```
cat: /nonexistent/file.txt: No such file or directory
```

---

### 4. Connection Refused

**Pattern:** `connection refused` (case-insensitive)

**Root cause:** The target service refused the connection.

**Suggestion:** Check that the target service is running and listening on the expected port. Verify firewall rules allow the connection.

**Auto-fix:** None.

**Confidence:** high

**Example stderr:**
```
curl: (7) Failed to connect to localhost port 9999: Connection refused
```

---

### 5. Timeout

**Pattern:** `connection timed out`, `timed out`, `timeout` (case-insensitive)

**Root cause:** The operation timed out waiting for a response.

**Suggestion:** Increase the timeout value, check network connectivity to the target host, and verify the remote service is responsive.

**Auto-fix:** None.

**Confidence:** medium

**Example stderr:**
```
curl: (28) Connection timed out after 5001 milliseconds
```

---

### 6. Disk Full

**Pattern:** `disk full`, `no space left on device` (case-insensitive)

**Root cause:** The target filesystem has run out of disk space.

**Suggestion:** Free up disk space on the target server. Check for large log files, temporary files, or unused packages that can be removed.

**Auto-fix:** None.

**Confidence:** high

**Example stderr:**
```
dd: error writing /tmp/bigfile: No space left on device
```

---

### 7. DNS Resolution Failure

**Pattern:** `name or service not known`, `could not resolve` (case-insensitive)

**Root cause:** DNS resolution failed for the target hostname.

**Suggestion:** Verify the hostname is correct and DNS is properly configured. Check /etc/resolv.conf and try using an IP address instead.

**Auto-fix:** None.

**Confidence:** high

**Example stderr:**
```
Could not resolve host: nonexistent.invalid
```

---

### 8. Authentication Failure

**Pattern:** `authentication fail`, `login fail`, `access denied`, `unauthorized` (case-insensitive)

**Root cause:** Authentication or authorization failed.

**Suggestion:** Verify the credentials are correct and the account has not been locked. Check that the user has the required privileges.

**Auto-fix:** None.

**Confidence:** high

**Example stderr:**
```
ERROR 1045 (28000): Access denied for user 'root'@'localhost'
```

---

### 9. Syntax Error

**Pattern:** `syntax error`, `unexpected token`, `parse error` (case-insensitive)

**Root cause:** The command or script contains a syntax error.

**Suggestion:** Review the command for typos, missing quotes, or incorrect shell syntax. Test the command manually before re-running.

**Auto-fix:** None.

**Confidence:** medium

**Example stderr:**
```
bash: syntax error near unexpected token '('
```

---

### 10. Out of Memory / OOM Killed

**Pattern:** `killed`, `out of memory`, `oom`, `cannot allocate memory` (case-insensitive)

**Root cause:** The process was killed, likely due to insufficient memory.

**Suggestion:** Increase available memory on the target server or reduce the memory footprint of the command. Check system OOM logs.

**Auto-fix:** None.

**Confidence:** medium

**Example stderr:**
```
Killed
```

---

### Fallback (No Pattern Matched)

When none of the 10 patterns match, the system returns a generic fallback:

- **Root cause:** "The command exited with return code {rc}."
- **Suggestion:** Review the command output for error details. Try running the command manually on the target server.
- **Confidence:** low
- **Modified command:** None

**Special case:** If the return code is 0 but the step is marked as failed, the system notes this anomaly and suggests checking the post-processing validation logic. Confidence is set to medium.

---

## Confidence Levels

| Level | Meaning |
|---|---|
| **high** | The error pattern is well-known and the suggestion is almost certainly relevant. |
| **medium** | The pattern is recognized but the root cause may have nuances. Manual verification is recommended. |
| **low** | No known pattern matched. The suggestion is generic guidance. |

---

## Applying Fixes

### Apply Fix Button

When the troubleshooting response includes a `modified_command` (non-null), the UI displays an **Apply Fix** button. Clicking it:

1. Sends a `POST /dm-webmanager/api/ai/apply-fix` request with the step ID, orchestration ID, and new command.
2. The backend updates the step's `code` field in the database.
3. The response confirms the change by returning both the old and new command.
4. The orchestration builder refreshes to show the updated step.

### Apply & Re-run

The **Apply & Re-run** button combines two actions:

1. Applies the suggested fix (same as Apply Fix above).
2. Immediately triggers re-execution of the failed step.

This is useful for quick iteration on permission-denied or similar straightforward fixes.

---

## Step-by-Step: Troubleshooting a Failed Execution

### Step 1: Run an Orchestration

Execute an orchestration through the UI or API:

```bash
curl -k -b cookies.txt -X POST \
  https://localhost:20194/api/v1.0/orchestrations/deploy-app/1/execute \
  -H "Content-Type: application/json" \
  -d '{}'
```

### Step 2: Observe the Failure

In the Execution Monitor, a failed step displays:

- Red status indicator
- Return code (e.g., `rc: 1`)
- stdout and stderr output
- A **Troubleshoot** button

### Step 3: Click Troubleshoot

The system sends the step execution data (command, stdout, stderr, return code, server name, step name, orchestration name) to the troubleshooting API.

### Step 4: Review the Diagnosis

The response card shows:

```
Root Cause: The command failed due to insufficient permissions.
Suggestion: Run the command with elevated privileges (sudo) or adjust
            file/directory permissions with chmod/chown.
Confidence: high
Modified Command: sudo apt install nginx
```

### Step 5: Apply the Fix

Click **Apply Fix** to update the step command, or **Apply & Re-run** to fix and immediately re-execute.

---

## API Reference

### POST /dm-webmanager/api/ai/troubleshoot

Analyze a failed step execution and return troubleshooting suggestions.

**Authentication:** Required (session cookie or JWT)

**Request Body (ad-hoc data):**

```json
{
  "command": "apt install nginx",
  "stdout": "",
  "stderr": "bash: apt: command not found",
  "rc": 127
}
```

**Request Body (referencing a stored step execution):**

```json
{
  "step_execution_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

When `step_execution_id` is provided, the system looks up the step execution in the database and extracts the command, stdout, stderr, rc, server name, step name, and orchestration name automatically. Returns `404` if the step execution is not found.

When ad-hoc fields are provided, they are used directly without a database lookup.

**Response (200 OK):**

```json
{
  "root_cause": "The command or binary is not installed or not in PATH.",
  "suggestion": "Install the missing package or specify the full path to the executable. Verify PATH includes the binary location.",
  "confidence": "high",
  "modified_command": null
}
```

**Response fields:**

| Field | Type | Description |
|---|---|---|
| `root_cause` | string | Concise explanation of why the command failed |
| `suggestion` | string | Actionable steps the operator should take |
| `confidence` | string | One of: `high`, `medium`, `low` |
| `modified_command` | string/null | A corrected command, or null if no auto-fix is possible |

**Error Responses:**

| Status | Condition |
|---|---|
| `401/302` | Not authenticated |
| `404` | Referenced `step_execution_id` not found |

---

### POST /dm-webmanager/api/ai/apply-fix

Apply a suggested fix by updating a step's command in the orchestration.

**Authentication:** Required, must have **operator** role.

**Request Body:**

```json
{
  "step_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "orchestration_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
  "new_command": "sudo apt install nginx"
}
```

**Fields:**

| Field | Type | Required | Description |
|---|---|---|---|
| `step_id` | string (UUID) | Yes | The ID of the step to update |
| `orchestration_id` | string (UUID) | Yes | The ID of the orchestration containing the step |
| `new_command` | string | Yes | The corrected command to set |

**Response (200 OK):**

```json
{
  "step_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "orchestration_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
  "old_command": "apt install nginx",
  "new_command": "sudo apt install nginx"
}
```

**Error Responses:**

| Status | Condition |
|---|---|
| `400` | Missing `step_id`, `orchestration_id`, or `new_command` |
| `400` | Step does not belong to the specified orchestration |
| `401/302` | Not authenticated |
| `403` | User does not have operator role |
| `404` | Orchestration or step not found |

---

## curl Examples

### Troubleshoot a permission denied error

```bash
curl -k -b cookies.txt -X POST \
  https://localhost:20194/dm-webmanager/api/ai/troubleshoot \
  -H "Content-Type: application/json" \
  -d '{
    "command": "cat /etc/shadow",
    "stdout": "",
    "stderr": "cat: /etc/shadow: Permission denied",
    "rc": 1
  }'
```

**Response:**

```json
{
  "root_cause": "The command failed due to insufficient permissions.",
  "suggestion": "Run the command with elevated privileges (sudo) or adjust file/directory permissions with chmod/chown.",
  "confidence": "high",
  "modified_command": "sudo cat /etc/shadow"
}
```

### Troubleshoot a connection refused error

```bash
curl -k -b cookies.txt -X POST \
  https://localhost:20194/dm-webmanager/api/ai/troubleshoot \
  -H "Content-Type: application/json" \
  -d '{
    "command": "curl http://localhost:9999/health",
    "stdout": "",
    "stderr": "curl: (7) Failed to connect to localhost port 9999: Connection refused",
    "rc": 7
  }'
```

### Troubleshoot using a stored step execution ID

```bash
curl -k -b cookies.txt -X POST \
  https://localhost:20194/dm-webmanager/api/ai/troubleshoot \
  -H "Content-Type: application/json" \
  -d '{
    "step_execution_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
  }'
```

### Apply a suggested fix

```bash
curl -k -b cookies.txt -X POST \
  https://localhost:20194/dm-webmanager/api/ai/apply-fix \
  -H "Content-Type: application/json" \
  -d '{
    "step_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "orchestration_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
    "new_command": "sudo cat /etc/shadow"
  }'
```

### Full troubleshoot-and-fix workflow

```bash
# Step 1: Log in
curl -k -c cookies.txt -X POST \
  https://localhost:20194/dm-webmanager/login \
  -H "Content-Type: application/json" \
  -d '{"username": "root", "password": "your_password"}'

# Step 2: Troubleshoot the failure
RESULT=$(curl -k -b cookies.txt -s -X POST \
  https://localhost:20194/dm-webmanager/api/ai/troubleshoot \
  -H "Content-Type: application/json" \
  -d '{
    "command": "systemctl restart nginx",
    "stdout": "",
    "stderr": "Failed to restart nginx.service: Permission denied",
    "rc": 1
  }')

echo "$RESULT" | python3 -m json.tool

# Step 3: Extract the modified command and apply it
NEW_CMD=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('modified_command',''))")

if [ -n "$NEW_CMD" ]; then
  curl -k -b cookies.txt -X POST \
    https://localhost:20194/dm-webmanager/api/ai/apply-fix \
    -H "Content-Type: application/json" \
    -d "{
      \"step_id\": \"YOUR_STEP_ID\",
      \"orchestration_id\": \"YOUR_ORCH_ID\",
      \"new_command\": \"$NEW_CMD\"
    }"
fi
```

---

## Preparing for LLM Backend Integration

The troubleshooting system includes a `TROUBLESHOOT_PROMPT` template designed for use with an external LLM when deeper analysis is needed. The template is defined in `dimensigon/ai/troubleshoot.py` and contains the following placeholders:

| Placeholder | Description |
|---|---|
| `{orchestration_name}` | Name of the parent orchestration |
| `{step_name}` | Human-readable label of the failed step |
| `{server_name}` | Name of the server where the step executed |
| `{command}` | The command that was executed |
| `{rc}` | The return code |
| `{stdout}` | Captured standard output |
| `{stderr}` | Captured standard error |

The prompt instructs the LLM to respond in JSON with the same four fields used by the rule-based engine: `root_cause`, `suggestion`, `confidence`, and `modified_command`.

To integrate an LLM backend:

1. Implement a handler that formats `TROUBLESHOOT_PROMPT` with the step execution data.
2. Send the formatted prompt to your LLM API.
3. Parse the JSON response.
4. Return it through the existing troubleshoot endpoint.

The rule-based engine continues to work as a fast first-pass. The LLM can be used as a fallback when the rule-based engine returns `low` confidence.

---

## Troubleshooting the Troubleshooter

| Problem | Solution |
|---|---|
| Always returns "low" confidence | The error output does not match any of the 10 built-in patterns. Check that stderr/stdout actually contains the error text. |
| `modified_command` is always null | Only the "permission denied" pattern currently generates auto-fix commands. Other patterns require manual intervention. |
| 404 when using step_execution_id | The step execution ID does not exist in the database. Verify the ID is correct and the execution has been recorded. |
| 400 on apply-fix | Ensure all three required fields (`step_id`, `orchestration_id`, `new_command`) are provided and that the step belongs to the specified orchestration. |
| 403 on apply-fix | The apply-fix endpoint requires the `operator` role. Check your user's group membership. |

---

**Document Version**: 1.0.0
**Last Updated**: 2026-04-07
**Dimensigon Version**: 3.0
