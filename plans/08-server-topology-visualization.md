# Server Topology Visualization

- **Priority:** 8
- **Category:** WebManager
- **Effort:** 3-4 days
- **Dependencies:** #4 (Lightweight Health Endpoint), #5 (Authentication Flow Rework)

## Context

Operators have no visual representation of the node mesh. Understanding which nodes are alive,
how they route to each other, and where proxy hops occur requires reading raw API output or
logs. A topology graph provides instant situational awareness of the entire dimension.

## Scope

- Interactive network graph showing all registered nodes in the dimension.
- Each node displays: name, IP/gate, health status (live via /health polling).
- Edges represent routes between nodes, colored by cost (green=direct, orange=1 hop, red=2+ hops).
- Click a node to open a detail drawer: gates, granules, recent executions, uptime.
- Proxy route visualization: dashed lines showing indirect routing paths.
- Auto-refresh on a configurable interval (default 30 seconds).
- Zoom, pan, and search by node name.

## Files to Modify

- `templates/admin/dashboard.html` (topology graph section)
- `dimensigon/web/admin/routes.py` (API endpoint returning topology data)
- `dimensigon/web/admin/topology.py` (new: aggregate node/route data for the graph)

## Implementation Steps

1. Create backend endpoint `GET /dm-webmanager/api/topology` that returns nodes and edges.
2. For each node, include: name, gates, health status (from cached /health poll), granules.
3. For each edge, include: source, target, cost, is_proxy flag.
4. Build the graph UI using a force-directed layout library (vis.js or d3-force).
5. Color-code nodes by health: green=healthy, yellow=degraded, red=unreachable.
6. Color-code edges by route cost.
7. Implement click-to-inspect drawer with node details and recent execution summary.
8. Add auto-refresh timer and manual refresh button.
9. Add search/filter bar for finding nodes by name or gate IP.

## Verification

- Open topology page: all known nodes appear with correct health colors.
- Click a node: detail drawer shows gates, granules, and last 5 executions.
- Take a node offline: within 30 seconds, its color changes to red.
- Proxy routes display as dashed lines with correct hop visualization.

## Breaking Changes

- None. This is a new read-only UI component.
