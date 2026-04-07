# Prometheus Metrics Endpoint

- **Priority:** 24
- **Category:** Infrastructure
- **Effort:** 2-3 days
- **Dependencies:** None

## Context

dimensigon has no integration with standard observability stacks. Prometheus is the de facto
standard for infrastructure monitoring, and adding a `/metrics` endpoint enables operators
to use existing Grafana dashboards, alerting rules, and monitoring workflows. This is
essential for production deployments where dimensigon itself must be monitored.

## Scope

- Add `/metrics` endpoint exposing Prometheus-format metrics.
- Metrics to expose:
  - `dm_orchestration_executions_total` (counter, labels: orchestration_name, status).
  - `dm_step_execution_duration_seconds` (histogram, labels: step_name, status).
  - `dm_cluster_nodes_alive` (gauge: count of reachable nodes).
  - `dm_api_requests_total` (counter, labels: method, endpoint, status_code).
  - `dm_api_request_duration_seconds` (histogram, labels: method, endpoint).
  - `dm_websocket_connections_active` (gauge: current WS connections).
- No authentication on `/metrics` (standard for Prometheus scrape targets).
- Include a sample Grafana dashboard JSON.

## Files to Modify

- `dimensigon/web/metrics.py` (new: metrics definitions, collection, /metrics endpoint)
- `dimensigon/web/__init__.py` (register metrics blueprint, add request hooks)
- `dimensigon/use_cases/execution.py` (instrument execution with counters/histograms)
- `requirements.txt` (add `prometheus-client`)

## Implementation Steps

1. Add `prometheus-client` to requirements.
2. Create `metrics.py`: define all Counter, Histogram, and Gauge metrics.
3. Register a Flask blueprint with `/metrics` endpoint using `generate_latest()`.
4. Add `before_request` / `after_request` hooks to track API request count and duration.
5. Instrument execution engine: increment `dm_orchestration_executions_total` on completion.
6. Instrument step execution: observe `dm_step_execution_duration_seconds` on step completion.
7. Add background task to update `dm_cluster_nodes_alive` gauge periodically (every 30s).
8. Exclude `/metrics` and `/health` from the API request metrics to avoid self-scraping noise.
9. Create a sample Grafana dashboard JSON file at `examples/grafana-dashboard.json`.
10. Write tests: execute orchestration, scrape /metrics, verify counter incremented.

## Verification

- `curl http://localhost:5000/metrics` returns valid Prometheus exposition format.
- After running an orchestration, `dm_orchestration_executions_total` shows correct count.
- Configure Prometheus to scrape the endpoint: metrics appear in Prometheus UI.
- Import sample Grafana dashboard: panels render with live data.

## Breaking Changes

- None. New endpoint and dependency. The `/metrics` endpoint is unauthenticated by design
  for Prometheus compatibility; ensure it is not exposed on public networks without protection.
