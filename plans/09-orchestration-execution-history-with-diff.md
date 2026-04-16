# Orchestration Execution History with Diff

- **Priority:** 9
- **Category:** WebManager
- **Effort:** 3-4 days
- **Dependencies:** #5 (Authentication Flow Rework), #6 (Real-time Execution Monitoring)

## Context

When an orchestration that previously succeeded starts failing, operators need to compare
execution runs side by side to identify what changed. Currently this requires manually
querying the API for each execution and diffing results by eye. A built-in comparison tool
dramatically speeds up root-cause analysis.

## Scope

- Execution history list view: filterable by orchestration, date range, status.
- Side-by-side comparison: select two executions and view them in a split pane.
- Diff highlighting: steps that succeeded in one run but failed in the other are flagged.
- Duration trends chart: line graph showing execution time over the last N runs.
- Parameter diff: show which input parameters differed between runs.
- Exportable as JSON for offline analysis.

## Files to Modify

- `templates/admin/dashboard.html` (history list, comparison UI, trend chart)
- `dimensigon/web/admin/routes.py` (history API, comparison data endpoint)
- `dimensigon/web/admin/executions_viewer.py` (new: execution comparison logic)

## Implementation Steps

1. Create `GET /dm-webmanager/api/executions` with filtering and pagination.
2. Create `GET /dm-webmanager/api/executions/compare?a=<id>&b=<id>` returning diff data.
3. Build the history list UI with sortable columns and status filter chips.
4. Implement the comparison view: two execution panels side by side.
5. Highlight differing steps: green border for newly passing, red for newly failing.
6. Compute parameter diff using a simple JSON diff algorithm.
7. Add duration trend chart using Chart.js or a lightweight charting lib.
8. Add export button that downloads the comparison as a JSON file.
9. Write tests: compare two executions with known differences, verify diff output.

## Verification

- History page shows all past executions with correct status indicators.
- Select two runs: split view shows step-by-step comparison with diff highlights.
- Duration chart renders with accurate data points for the last 20 runs.
- Parameter diff correctly identifies changed inputs between runs.

## Breaking Changes

- None. All existing execution data is read from the current database schema.
