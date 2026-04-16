# Tutorial 06: Real-Time Execution Monitoring

## Overview

Dimensigon 3.0 provides real-time monitoring of orchestration executions through
WebSocket connections and the DM-WebManager dashboard. Operators can watch
executions unfold live, see step-level progress on an interactive DAG, stream
stdout/stderr output, and cancel running executions -- all without polling.

This tutorial covers the WebSocket protocol, event types, the dashboard
execution detail view, and the cancellation API.

## Prerequisites

- A running Dimensigon 3.0 cluster with at least one node.
- Access to the DM-WebManager dashboard (`http://<host>:5000/dm-webmanager/dashboard`).
- A valid operator or administrator account.
- For command-line examples: `curl`, `wscat` (install via `npm install -g wscat`),
  or any WebSocket client library.

## 1. Connecting to the WebSocket

Every orchestration execution exposes a WebSocket endpoint that streams events
in real time.

### Endpoint

```
ws://<host>:5000/ws/executions/<execution_id>
```

Replace `<execution_id>` with the UUID of the orchestration execution you want
to monitor.

### Authentication

The WebSocket handshake requires the same JWT token used by the REST API.  Pass
it as a query parameter or in the `Authorization` header, depending on your
client.

### wscat example

```bash
# Obtain a token first
TOKEN=$(curl -s -X POST http://localhost:5000/dm-webmanager/login \
  -H "Content-Type: application/json" \
  -d '{"username":"operator","password":"secret"}' | jq -r '.access_token')

# Connect to the WebSocket
wscat -c "ws://localhost:5000/ws/executions/abcd1234-5678-90ef-ghij-klmnopqrstuv" \
      -H "Authorization: Bearer $TOKEN"
```

### Python example

```python
import asyncio
import websockets

async def watch(execution_id, token):
    uri = f"ws://localhost:5000/ws/executions/{execution_id}"
    headers = {"Authorization": f"Bearer {token}"}
    async with websockets.connect(uri, extra_headers=headers) as ws:
        async for message in ws:
            print(message)

asyncio.run(watch("abcd1234-...", "eyJhbG..."))
```

## 2. Event Types

The WebSocket emits JSON-encoded events. Every event has a `type` field and a
`timestamp` in ISO-8601 format.

### step_started

Emitted when a step begins executing on a target server.

```json
{
  "type": "step_started",
  "timestamp": "2026-04-07T14:00:01.123Z",
  "execution_id": "abcd1234-5678-90ef-ghij-klmnopqrstuv",
  "step_id": "step-001",
  "step_name": "checkout-code",
  "target": "web-server-01",
  "action_type": "SHELL"
}
```

### step_completed

Emitted when a step finishes successfully.

```json
{
  "type": "step_completed",
  "timestamp": "2026-04-07T14:00:12.456Z",
  "execution_id": "abcd1234-5678-90ef-ghij-klmnopqrstuv",
  "step_id": "step-001",
  "step_name": "checkout-code",
  "target": "web-server-01",
  "rc": 0,
  "duration_seconds": 11.333,
  "stdout": "Cloning into '/opt/app'...\nDone.",
  "stderr": ""
}
```

### step_failed

Emitted when a step exits with a non-zero return code or throws an exception.

```json
{
  "type": "step_failed",
  "timestamp": "2026-04-07T14:00:25.789Z",
  "execution_id": "abcd1234-5678-90ef-ghij-klmnopqrstuv",
  "step_id": "step-002",
  "step_name": "run-migrations",
  "target": "db-server-01",
  "rc": 1,
  "duration_seconds": 13.210,
  "stdout": "",
  "stderr": "ERROR: relation \"users\" already exists",
  "error": "Step exited with return code 1"
}
```

### orch_completed

Emitted once when the entire orchestration finishes (success or failure).

```json
{
  "type": "orch_completed",
  "timestamp": "2026-04-07T14:01:00.000Z",
  "execution_id": "abcd1234-5678-90ef-ghij-klmnopqrstuv",
  "orchestration_name": "deploy-app",
  "success": false,
  "total_duration_seconds": 58.877,
  "steps_total": 5,
  "steps_succeeded": 3,
  "steps_failed": 1,
  "steps_skipped": 1
}
```

### orch_cancelled

Emitted when an operator cancels a running execution.

```json
{
  "type": "orch_cancelled",
  "timestamp": "2026-04-07T14:00:45.000Z",
  "execution_id": "abcd1234-5678-90ef-ghij-klmnopqrstuv",
  "orchestration_name": "deploy-app",
  "cancelled_by": "operator",
  "steps_completed": 2,
  "steps_cancelled": 3
}
```

## 3. Using the Dashboard Execution Detail View

### Opening the detail view

1. Navigate to **DM-WebManager > Executions**.
2. Click on any execution row to open the detail view.
3. If the execution is still running, the view automatically opens a WebSocket
   connection and begins streaming events.

### What you see

The execution detail view is split into three panels:

| Panel             | Description                                        |
|-------------------|----------------------------------------------------|
| **DAG View**      | Interactive directed acyclic graph of all steps.   |
| **Log Stream**    | Live stdout/stderr output from the active step.    |
| **Summary Bar**   | Elapsed time, step counters, and status indicator. |

## 4. Live DAG Visualization

The DAG panel renders the orchestration steps as a directed graph using vis.js.
Each node represents a step, and edges represent execution dependencies.

### Color codes

| Color    | Meaning                            |
|----------|------------------------------------|
| **Green**  | Step completed successfully.     |
| **Yellow** | Step is currently executing.     |
| **Red**    | Step failed.                     |
| **Grey**   | Step has not started yet or was skipped. |

As WebSocket events arrive, node colors update in real time. When a
`step_started` event arrives the node turns yellow; on `step_completed` it turns
green; on `step_failed` it turns red.

### Interaction

- **Hover** over a node to see the step name, target server, and current status.
- **Click** a node to switch the Log Stream panel to that step's output.
- **Zoom and pan** with mouse wheel and drag.

## 5. Live stdout/stderr Streaming

The Log Stream panel shows stdout and stderr from the currently selected step
in real time.

- stdout is rendered in white/light text.
- stderr is rendered in red text.
- Lines are appended as they arrive via the WebSocket.
- You can scroll up to review earlier output without losing new lines; new
  output appears at the bottom with an auto-scroll indicator.

## 6. Cancelling an Execution

### From the dashboard

1. Open the execution detail view for a running execution.
2. Click the **Cancel** button in the top-right corner of the Summary Bar.
3. Confirm in the dialog that appears.
4. The system sends a cancellation request and you will see an `orch_cancelled`
   event in the WebSocket stream.

### Cancel API

```
POST /dm-webmanager/executions/<execution_id>/cancel
```

**Authentication:** Requires a valid session (JWT cookie or Authorization header).

**Response (200 OK):**

```json
{
  "message": "Cancellation requested",
  "execution_id": "abcd1234-5678-90ef-ghij-klmnopqrstuv"
}
```

**Response (404 Not Found):**

```json
{
  "error": "Execution not found"
}
```

**Response (409 Conflict):** Returned if the execution has already finished.

```json
{
  "error": "Execution is not running"
}
```

### curl example

```bash
# Cancel a running execution
curl -X POST http://localhost:5000/dm-webmanager/executions/abcd1234-5678-90ef-ghij-klmnopqrstuv/cancel \
  -b cookies.txt

# With token auth
curl -X POST http://localhost:5000/dm-webmanager/executions/abcd1234-5678-90ef-ghij-klmnopqrstuv/cancel \
  -H "Authorization: Bearer $TOKEN"
```

### Cancellation flow

1. Operator sends `POST .../cancel`.
2. Server marks the execution as `cancelling`.
3. Currently running steps are sent a SIGTERM signal.
4. Steps that have not started are marked as `skipped`.
5. An `orch_cancelled` event is emitted on the WebSocket.
6. The DAG view updates: running steps turn red, pending steps turn grey.

## 7. Elapsed Time Tracking

The Summary Bar displays a live elapsed-time counter that starts when the
execution begins and stops when it completes, fails, or is cancelled. The
counter updates every second using a client-side timer synchronized with the
`start_time` from the execution metadata.

Completed executions display the total duration (e.g., "Duration: 58.9s")
instead of a running counter.

## 8. Multiple Browser Tabs

Multiple browser tabs (or multiple users) can watch the same execution
simultaneously. Each tab opens its own WebSocket connection. The server
broadcasts events to all connected clients for a given execution. There is no
limit on the number of concurrent watchers.

The Prometheus metric `dm_websocket_connections_active` (see Tutorial 24) tracks
the total number of open WebSocket connections across all executions.

## 9. Configuration Options

| Setting                             | Default   | Description                              |
|-------------------------------------|-----------|------------------------------------------|
| `WS_HEARTBEAT_INTERVAL`            | `30`      | Seconds between WebSocket ping frames.   |
| `WS_MAX_CONNECTIONS_PER_EXECUTION` | `50`      | Max concurrent watchers per execution.   |
| `EXECUTION_LOG_BUFFER_SIZE`        | `1000`    | Max lines buffered for late joiners.     |

Set these in your Dimensigon configuration file or as environment variables.

## 10. Troubleshooting

**WebSocket connection refused**
- Verify the execution ID exists: `GET /api/v2/executions/<id>`.
- Ensure WebSocket support is enabled on any reverse proxy in front of
  Dimensigon (e.g., `proxy_set_header Upgrade $http_upgrade;` in nginx).

**Events stop arriving**
- Check the heartbeat. If the connection is idle for longer than
  `WS_HEARTBEAT_INTERVAL * 2`, the server may have closed the socket.
- Reconnect and the server will replay buffered events from the log buffer.

**Cancel button greyed out**
- The execution has already completed or been cancelled. Refresh the page to
  confirm the current status.

## Related Features

- [Tutorial 08: Topology Visualization](08-topology-visualization.md) -- see which nodes are executing steps.
- [Tutorial 09: Execution History and Diff](09-execution-history-diff.md) -- compare completed executions.
- [Tutorial 24: Prometheus Metrics](24-prometheus-metrics.md) -- monitor WebSocket connection counts.
