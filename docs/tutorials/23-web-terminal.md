# Tutorial 23: Web Terminal (Browser-Based DShell)

Access the full DShell experience from your browser without SSH or local tooling.

---

## Overview

The Web Terminal embeds an interactive DShell session inside the Dimensigon WebManager dashboard. It provides the same command set, auto-completion, and debug capabilities as the local DShell, delivered through an xterm.js terminal component over WebSocket. Operators can manage orchestrations, inspect servers, and debug failures directly from any modern browser.

## Prerequisites

- Dimensigon 3.0 installed with WebManager enabled
- A valid user account with dashboard access
- A modern browser (Chrome, Firefox, Edge, Safari) with JavaScript enabled
- WebSocket connectivity to the Dimensigon server (default port 5000)

---

## Accessing the Web Terminal

### From the Dashboard Sidebar

1. Log in to the Dimensigon WebManager at `https://<your-server>:5000/dm-webmanager/`.
2. In the left sidebar, click **Terminal**.
3. A terminal panel opens with the DShell prompt:

```
Welcome to DShell v3.0 (web mode)
Type "help" for available commands.

dm>
```

A new session is created automatically when the terminal view opens. No additional setup is required.

---

## Available Commands

The web terminal supports the full DShell command set. Here are the most common commands:

| Command | Description |
|---------|-------------|
| `help` | List all available commands and their usage |
| `version` | Display the Dimensigon and DShell version |
| `whoami` | Show the currently authenticated user and role |
| `history` | Display command history for the current session |
| `clear` | Clear the terminal screen |
| `run <orchestration>` | Execute an orchestration |
| `list orchestrations` | List available orchestrations |
| `list servers` | List servers in the dimension |
| `show <orchestration>` | Display orchestration details |

### Example Session

```
dm> version
Dimensigon 3.0.0 | DShell 3.0 (web mode)

dm> whoami
User: admin | Role: administrator | Dimension: production

dm> list servers
NAME          IP              STATUS    LAST SEEN
web-01        192.168.1.10    online    2s ago
web-02        192.168.1.11    online    3s ago
db-01         192.168.1.20    online    1s ago

dm> run health_check --target web-01
[step 1/3] check_cpu ... OK
[step 2/3] check_memory ... OK
[step 3/3] check_disk ... OK
Orchestration "health_check" completed successfully.

dm> history
  1  version
  2  whoami
  3  list servers
  4  run health_check --target web-01
  5  history
```

---

## Command History Navigation

The web terminal supports standard terminal history navigation:

- **Up Arrow**: Recall the previous command
- **Down Arrow**: Move forward through command history
- **Ctrl+R**: Reverse search through command history (type to filter)

History is stored per session on the server side and is available through the history API endpoint.

---

## Session Limits

Each user is limited to **5 concurrent web terminal sessions**. This prevents resource exhaustion on the server.

| Scenario | Behavior |
|----------|----------|
| Open a 6th terminal tab | Error: "Session limit reached. Close an existing session first." |
| Close a terminal tab or navigate away | Session is automatically closed after a brief timeout |
| Click the close button | Session is closed immediately |
| Browser crash or disconnect | Session is cleaned up after the idle timeout (default: 5 minutes) |

To see active sessions, use the terminal API (see API section below).

---

## Closing Sessions

Sessions can be closed in three ways:

1. **Close button**: Click the X button in the terminal panel header.
2. **Navigate away**: Leave the Terminal page. The session is released after a short timeout.
3. **API call**: Send a DELETE request to the session endpoint (see below).

---

## API Endpoints

The web terminal can also be driven programmatically through REST endpoints. All endpoints require a valid JWT token in the `Authorization` header.

### Create a Session

**POST** `/dm-webmanager/api/terminal/create`

Creates a new terminal session and returns the session ID.

#### Request

```bash
curl -X POST https://dm.example.com:5000/dm-webmanager/api/terminal/create \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json"
```

#### Response (201 Created)

```json
{
  "session_id": "ts-a1b2c3d4",
  "created_at": "2026-04-07T14:30:00Z",
  "user": "admin",
  "status": "active"
}
```

#### Error Response (429 Too Many Requests)

```json
{
  "error": "Session limit reached",
  "message": "Maximum 5 concurrent sessions per user. Close an existing session first.",
  "active_sessions": 5
}
```

---

### Execute a Command

**POST** `/dm-webmanager/api/terminal/<id>/execute`

Execute a command in an existing terminal session.

#### Request

```bash
curl -X POST https://dm.example.com:5000/dm-webmanager/api/terminal/ts-a1b2c3d4/execute \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "command": "list servers"
  }'
```

#### Response (200 OK)

```json
{
  "session_id": "ts-a1b2c3d4",
  "command": "list servers",
  "output": "NAME          IP              STATUS    LAST SEEN\nweb-01        192.168.1.10    online    2s ago\nweb-02        192.168.1.11    online    3s ago\ndb-01         192.168.1.20    online    1s ago\n",
  "exit_code": 0,
  "executed_at": "2026-04-07T14:31:05Z"
}
```

#### Error Response (404 Not Found)

```json
{
  "error": "Session not found",
  "message": "Session 'ts-a1b2c3d4' does not exist or has expired."
}
```

---

### Get Command History

**GET** `/dm-webmanager/api/terminal/<id>/history`

Retrieve the command history for a session.

#### Request

```bash
curl -X GET https://dm.example.com:5000/dm-webmanager/api/terminal/ts-a1b2c3d4/history \
  -H "Authorization: Bearer $TOKEN"
```

#### Response (200 OK)

```json
{
  "session_id": "ts-a1b2c3d4",
  "history": [
    {
      "index": 1,
      "command": "version",
      "executed_at": "2026-04-07T14:30:10Z"
    },
    {
      "index": 2,
      "command": "list servers",
      "executed_at": "2026-04-07T14:31:05Z"
    },
    {
      "index": 3,
      "command": "run health_check --target web-01",
      "executed_at": "2026-04-07T14:32:00Z"
    }
  ],
  "total": 3
}
```

---

### Delete a Session

**DELETE** `/dm-webmanager/api/terminal/<id>`

Close and clean up a terminal session.

#### Request

```bash
curl -X DELETE https://dm.example.com:5000/dm-webmanager/api/terminal/ts-a1b2c3d4 \
  -H "Authorization: Bearer $TOKEN"
```

#### Response (200 OK)

```json
{
  "session_id": "ts-a1b2c3d4",
  "status": "closed",
  "closed_at": "2026-04-07T14:45:00Z"
}
```

---

## Complete curl Workflow Example

This example demonstrates a full session lifecycle using the API.

```bash
# Authenticate and obtain a token
TOKEN=$(curl -s -X POST https://dm.example.com:5000/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "your_password"}' \
  | jq -r '.access_token')

# Create a terminal session
SESSION_ID=$(curl -s -X POST https://dm.example.com:5000/dm-webmanager/api/terminal/create \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  | jq -r '.session_id')

echo "Session: $SESSION_ID"

# Execute commands
curl -s -X POST "https://dm.example.com:5000/dm-webmanager/api/terminal/$SESSION_ID/execute" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"command": "list servers"}' | jq .

curl -s -X POST "https://dm.example.com:5000/dm-webmanager/api/terminal/$SESSION_ID/execute" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"command": "run health_check --target web-01"}' | jq .

# View command history
curl -s -X GET "https://dm.example.com:5000/dm-webmanager/api/terminal/$SESSION_ID/history" \
  -H "Authorization: Bearer $TOKEN" | jq .

# Close the session
curl -s -X DELETE "https://dm.example.com:5000/dm-webmanager/api/terminal/$SESSION_ID" \
  -H "Authorization: Bearer $TOKEN" | jq .
```

---

## Tips

- **Browser tabs**: Each browser tab that opens the Terminal view creates a separate session. Keep this in mind with the 5-session limit.
- **Long-running commands**: Commands that take a long time (such as orchestrations with many steps) stream output in real time. The terminal remains responsive during execution.
- **Debug mode works**: The step debugger (Tutorial 21) is fully functional in the web terminal. Use `--debug` just as you would in a local DShell session.
- **JSON highlighting**: JSON output from commands like `show` is syntax-highlighted automatically in the web terminal.
- **Clickable IDs**: Orchestration IDs, execution IDs, and server names in the output are clickable links that navigate to their detail pages in the dashboard.

---

## Next Steps

- [Tutorial 21: Interactive Step Debugger](21-step-debugger.md) -- Debug orchestrations step by step
- [Tutorial 19: Natural Language Runner](19-natural-language-runner.md) -- Run orchestrations using plain English
