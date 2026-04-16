# Real-time Execution Monitoring

- **Priority:** 6
- **Category:** WebManager
- **Effort:** 4-5 days
- **Dependencies:** #5 (Authentication Flow Rework)

## Context

Currently there is no way to watch an orchestration execute in real time from the WebManager.
Operators must poll API endpoints or check logs after the fact. Real-time visibility into
step-by-step progress is essential for debugging, confidence during deployments, and quick
reaction to failures.

## Scope

- Establish a WebSocket connection between the browser and the backend for live updates.
- Stream `StepExecution` progress events as they occur.
- Render a visual DAG where each node represents a step, colored by status:
  green (success), yellow (running), red (failed), grey (pending).
- Display live stdout/stderr output per step in a collapsible panel.
- Add a cancel button that sends an abort signal to the running orchestration.
- Show elapsed time per step and total orchestration runtime.

## Files to Modify

- `dimensigon/web/admin/routes.py` (WebSocket endpoint, cancel endpoint)
- `dimensigon/web/admin/ws.py` (new: WebSocket handler and event broadcasting)
- `templates/admin/dashboard.html` (DAG visualization, live output panels)
- `dimensigon/use_cases/execution.py` (emit events on step state transitions)
- `dimensigon/web/__init__.py` (register WebSocket support, e.g., flask-sock)

## Implementation Steps

1. Add `flask-sock` or `flask-socketio` dependency for WebSocket support.
2. Create `ws.py` with a connection manager that tracks active viewers per execution.
3. Instrument `StepExecution` state transitions to emit events to the WS manager.
4. Build the DAG rendering component in the dashboard using a lightweight JS library (dagre-d3).
5. Wire WS messages to update node colors, add stdout/stderr lines, and update timers.
6. Implement the cancel button: sends POST to `/dm-webmanager/executions/<id>/cancel`.
7. Backend cancel handler sets an abort flag checked between steps.
8. Add authentication to the WebSocket handshake (validate JWT from cookie).
9. Write integration test: start execution, connect WS, verify events stream correctly.

## Verification

- Start an orchestration and open the monitoring page: DAG appears with all steps grey.
- Steps transition yellow -> green/red as execution proceeds.
- stdout/stderr appears in real time without manual refresh.
- Cancel button stops execution and marks remaining steps as "cancelled".
- Multiple browser tabs can watch the same execution simultaneously.

## Breaking Changes

- None. This is additive UI functionality. Existing API endpoints remain unchanged.
