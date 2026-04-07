# Dashboard Widgets

- **Priority:** 10
- **Category:** WebManager
- **Effort:** 3 days
- **Dependencies:** #5 (Authentication Flow Rework)

## Context

The dashboard currently shows minimal information. Operators need at-a-glance operational
awareness: what is succeeding, what is failing, which nodes need attention. Configurable
widgets turn the dashboard into a proper operations center.

## Scope

- Widget framework: a grid layout where users can add, remove, and rearrange widgets.
- Pre-built widgets:
  - Execution success rate trend (7-day and 30-day line charts).
  - Top 5 failing orchestrations (bar chart with failure counts).
  - Node health heatmap (grid of colored squares, one per node).
  - Recent activity feed (last 20 events: executions, logins, config changes).
  - Resource usage per node (CPU/memory sparklines if data is available).
- User preference persistence: widget layout saved per user.
- Responsive design: widgets reflow on smaller screens.

## Files to Modify

- `templates/admin/dashboard.html` (widget grid, individual widget components)
- `dimensigon/web/admin/routes.py` (widget data endpoints)
- `dimensigon/web/admin/widgets.py` (new: widget data aggregation logic)

## Implementation Steps

1. Implement a CSS grid-based widget container with drag-to-rearrange (e.g., gridstack.js).
2. Create `GET /dm-webmanager/api/widgets/<type>` endpoint pattern for widget data.
3. Build success rate widget: query executions table, group by day, compute percentages.
4. Build top failures widget: query failed executions, group by orchestration name, count.
5. Build node health widget: poll /health on all nodes, render as colored grid squares.
6. Build activity feed widget: query audit log (or execution log) for recent events.
7. Build resource widget: aggregate available metrics per node into sparklines.
8. Save widget layout to user preferences (localStorage + optional server-side sync).
9. Add "Add Widget" button with a picker showing available widget types.

## Verification

- Dashboard loads with default widget set for new users.
- Drag a widget to a new position, refresh page: position is preserved.
- Success rate chart shows accurate data matching manual DB query.
- Node health heatmap updates when a node goes offline.

## Breaking Changes

- The existing dashboard layout is replaced with the widget grid. Any custom CSS overrides
  targeting the old layout will need updating.
