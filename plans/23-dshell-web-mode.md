# DShell Web Mode

- **Priority:** 23
- **Category:** DShell
- **Effort:** 4-5 days
- **Dependencies:** #5 (Authentication Flow Rework), #6 (Real-time Execution Monitoring)

## Context

DShell currently runs only as a local terminal application. Operators who access dimensigon
through the WebManager cannot use DShell without SSH access to the server. A web-based
terminal brings the full DShell experience into the browser, making it accessible from
anywhere without requiring local tooling or SSH credentials.

## Scope

- Embed an xterm.js terminal in the WebManager dashboard.
- Full DShell functionality: all commands, auto-completion, debug mode.
- Custom DM theme: colors matching the dimensigon brand.
- Syntax highlighting for JSON output (orchestration definitions, execution results).
- Clickable IDs: orchestration IDs, execution IDs, and node names are clickable links
  that navigate to the corresponding detail view.
- Command history search: Ctrl+R reverse search through command history.
- Split pane mode: command input on the left, live execution visualization on the right.

## Files to Modify

- `dimensigon/web/admin/routes.py` (WebSocket endpoint for terminal I/O)
- `dimensigon/web/admin/terminal.py` (new: terminal session manager, PTY bridge)
- `templates/admin/dashboard.html` (xterm.js component, split pane layout)
- `dimensigon/dshell/interactive.py` (adapter for WebSocket-based I/O instead of local TTY)
- `dimensigon/web/__init__.py` (register terminal routes)

## Implementation Steps

1. Add xterm.js and xterm-addon-fit dependencies (CDN or bundled).
2. Create terminal component in dashboard: xterm.js instance with DM theme colors.
3. Build WebSocket endpoint for terminal I/O: receives keystrokes, sends output.
4. Create `terminal.py` session manager: spawns a DShell instance per connection,
   bridges WebSocket to the DShell I/O streams.
5. Adapt DShell interactive.py to accept a generic I/O interface (local TTY or WebSocket).
6. Implement JSON syntax highlighting: detect JSON in output, apply color formatting.
7. Implement clickable IDs: regex-detect UUIDs and known patterns, wrap in clickable spans.
8. Implement split pane: terminal on left, execution DAG visualization on right.
9. Add Ctrl+R history search using xterm.js addon.
10. Authenticate terminal sessions: require valid JWT, limit concurrent sessions per user.
11. Write tests: open web terminal, execute a command, verify output renders correctly.

## Verification

- Open DShell from the dashboard: terminal renders with DM theme.
- Run an orchestration: output appears with JSON syntax highlighting.
- Click an orchestration ID in the output: navigates to the orchestration detail page.
- Split pane: execution DAG updates in real time while commands run in the terminal.

## Breaking Changes

- None. Web mode is an additional access method; the local DShell remains fully functional.
