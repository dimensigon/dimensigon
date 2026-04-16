# Tutorial 24: Prometheus Metrics

## Overview

Dimensigon 3.0 exposes a `/metrics` endpoint in Prometheus exposition format,
providing counters, histograms, and gauges for orchestration executions, step
durations, API request performance, cluster health, and WebSocket activity.
SREs can scrape this endpoint with Prometheus, build Grafana dashboards, and
configure alerting rules.

## Prerequisites

- A running Dimensigon 3.0 instance.
- Prometheus server (2.x or later) with network access to the Dimensigon host.
- Optionally: Grafana for dashboard visualization.
- For quick testing: `curl`.

## 1. Accessing the /metrics Endpoint

The metrics endpoint is available at:

```
http://<host>:5000/metrics
```

No authentication is required. The endpoint returns plain-text Prometheus
exposition format data.

### curl example

```bash
curl -s http://localhost:5000/metrics
```

**Sample output (abbreviated):**

```
# HELP dm_orchestration_executions_total Total orchestration executions
# TYPE dm_orchestration_executions_total counter
dm_orchestration_executions_total{orchestration_name="deploy-app",status="success"} 142.0
dm_orchestration_executions_total{orchestration_name="deploy-app",status="failed"} 8.0
dm_orchestration_executions_total{orchestration_name="backup-db",status="success"} 365.0

# HELP dm_step_execution_duration_seconds Step execution duration in seconds
# TYPE dm_step_execution_duration_seconds histogram
dm_step_execution_duration_seconds_bucket{le="0.1",step_name="checkout-code",status="success"} 0.0
dm_step_execution_duration_seconds_bucket{le="0.5",step_name="checkout-code",status="success"} 2.0
dm_step_execution_duration_seconds_bucket{le="1.0",step_name="checkout-code",status="success"} 15.0
dm_step_execution_duration_seconds_bucket{le="5.0",step_name="checkout-code",status="success"} 120.0
dm_step_execution_duration_seconds_bucket{le="10.0",step_name="checkout-code",status="success"} 138.0
dm_step_execution_duration_seconds_bucket{le="30.0",step_name="checkout-code",status="success"} 142.0
dm_step_execution_duration_seconds_bucket{le="60.0",step_name="checkout-code",status="success"} 142.0
dm_step_execution_duration_seconds_bucket{le="120.0",step_name="checkout-code",status="success"} 142.0
dm_step_execution_duration_seconds_bucket{le="300.0",step_name="checkout-code",status="success"} 142.0
dm_step_execution_duration_seconds_bucket{le="600.0",step_name="checkout-code",status="success"} 142.0
dm_step_execution_duration_seconds_bucket{le="+Inf",step_name="checkout-code",status="success"} 142.0
dm_step_execution_duration_seconds_count{step_name="checkout-code",status="success"} 142.0
dm_step_execution_duration_seconds_sum{step_name="checkout-code",status="success"} 487.5

# HELP dm_cluster_nodes_alive Number of alive cluster nodes
# TYPE dm_cluster_nodes_alive gauge
dm_cluster_nodes_alive 5.0

# HELP dm_api_requests_total Total API requests
# TYPE dm_api_requests_total counter
dm_api_requests_total{endpoint="admin_routes.dashboard",method="GET",status_code="200"} 340.0
dm_api_requests_total{endpoint="api_1_0.orchestrations",method="GET",status_code="200"} 128.0
dm_api_requests_total{endpoint="api_1_0.orchestrations",method="POST",status_code="201"} 12.0

# HELP dm_api_request_duration_seconds API request duration in seconds
# TYPE dm_api_request_duration_seconds histogram
dm_api_request_duration_seconds_bucket{le="0.01",endpoint="admin_routes.dashboard",method="GET"} 280.0
dm_api_request_duration_seconds_bucket{le="0.05",endpoint="admin_routes.dashboard",method="GET"} 330.0
dm_api_request_duration_seconds_bucket{le="0.1",endpoint="admin_routes.dashboard",method="GET"} 338.0
dm_api_request_duration_seconds_bucket{le="0.25",endpoint="admin_routes.dashboard",method="GET"} 340.0
dm_api_request_duration_seconds_bucket{le="+Inf",endpoint="admin_routes.dashboard",method="GET"} 340.0
dm_api_request_duration_seconds_count{endpoint="admin_routes.dashboard",method="GET"} 340.0
dm_api_request_duration_seconds_sum{endpoint="admin_routes.dashboard",method="GET"} 8.75

# HELP dm_websocket_connections_active Active WebSocket connections
# TYPE dm_websocket_connections_active gauge
dm_websocket_connections_active 3.0
```

## 2. Available Metrics

### dm_orchestration_executions_total

| Property | Value |
|----------|-------|
| **Type** | Counter |
| **Description** | Total number of orchestration executions since the process started. |
| **Labels** | `orchestration_name`, `status` |

**Label values:**

- `orchestration_name`: Name of the orchestration (e.g., `deploy-app`).
- `status`: `success` or `failed`.

**Example queries:**

```promql
# Total executions of deploy-app
dm_orchestration_executions_total{orchestration_name="deploy-app"}

# Failure rate over the last hour
rate(dm_orchestration_executions_total{status="failed"}[1h])
  / rate(dm_orchestration_executions_total[1h])

# Top 5 most executed orchestrations
topk(5, sum by (orchestration_name) (dm_orchestration_executions_total))
```

### dm_step_execution_duration_seconds

| Property | Value |
|----------|-------|
| **Type** | Histogram |
| **Description** | Duration of individual step executions in seconds. |
| **Labels** | `step_name`, `status` |
| **Buckets** | 0.1, 0.5, 1, 5, 10, 30, 60, 120, 300, 600 |

**Example queries:**

```promql
# p95 step duration for checkout-code
histogram_quantile(0.95,
  rate(dm_step_execution_duration_seconds_bucket{step_name="checkout-code"}[5m])
)

# Average step duration
rate(dm_step_execution_duration_seconds_sum{step_name="run-migrations"}[5m])
  / rate(dm_step_execution_duration_seconds_count{step_name="run-migrations"}[5m])
```

### dm_cluster_nodes_alive

| Property | Value |
|----------|-------|
| **Type** | Gauge |
| **Description** | Number of cluster nodes currently reachable. |
| **Labels** | (none) |

**Example queries:**

```promql
# Current alive nodes
dm_cluster_nodes_alive

# Alert if fewer than 3 nodes are alive
dm_cluster_nodes_alive < 3
```

### dm_api_requests_total

| Property | Value |
|----------|-------|
| **Type** | Counter |
| **Description** | Total API requests processed. |
| **Labels** | `method`, `endpoint`, `status_code` |

The `endpoint` label uses the Flask endpoint name (e.g., `admin_routes.dashboard`)
rather than the raw URL path, to avoid high cardinality from path parameters.

**Example queries:**

```promql
# Request rate by endpoint
sum by (endpoint) (rate(dm_api_requests_total[5m]))

# Error rate (5xx responses)
rate(dm_api_requests_total{status_code=~"5.."}[5m])

# Top endpoints by request volume
topk(10, sum by (endpoint) (rate(dm_api_requests_total[5m])))
```

### dm_api_request_duration_seconds

| Property | Value |
|----------|-------|
| **Type** | Histogram |
| **Description** | API request duration in seconds. |
| **Labels** | `method`, `endpoint` |
| **Buckets** | 0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10 |

**Example queries:**

```promql
# p99 API latency
histogram_quantile(0.99,
  sum by (le) (rate(dm_api_request_duration_seconds_bucket[5m]))
)

# Average latency per endpoint
rate(dm_api_request_duration_seconds_sum[5m])
  / rate(dm_api_request_duration_seconds_count[5m])
```

### dm_websocket_connections_active

| Property | Value |
|----------|-------|
| **Type** | Gauge |
| **Description** | Number of currently active WebSocket connections across all executions. |
| **Labels** | (none) |

**Example queries:**

```promql
# Current active connections
dm_websocket_connections_active

# Alert on connection spike
dm_websocket_connections_active > 100
```

## 3. Configuring Prometheus to Scrape

Add a scrape job to your `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'dimensigon'
    scrape_interval: 15s
    metrics_path: '/metrics'
    static_configs:
      - targets:
          - 'dimensigon-node-1:5000'
          - 'dimensigon-node-2:5000'
          - 'dimensigon-node-3:5000'
        labels:
          cluster: 'production'
```

### Multi-node clusters

In a Dimensigon cluster, each node exposes its own `/metrics` endpoint. Add all
nodes as targets so Prometheus collects metrics from every member. Use the
`instance` label (automatically added by Prometheus) to distinguish nodes.

### Behind a reverse proxy

If Dimensigon is behind nginx or another reverse proxy, make sure the proxy
passes through the `/metrics` path. Example nginx snippet:

```nginx
location /metrics {
    proxy_pass http://127.0.0.1:5000/metrics;
    proxy_set_header Host $host;
}
```

### Relabeling

Optionally add relabel configs to extract the node name from the target:

```yaml
scrape_configs:
  - job_name: 'dimensigon'
    scrape_interval: 15s
    metrics_path: '/metrics'
    static_configs:
      - targets: ['node-1:5000', 'node-2:5000']
    relabel_configs:
      - source_labels: [__address__]
        regex: '(.+):5000'
        target_label: node
        replacement: '${1}'
```

## 4. Building Grafana Dashboards

### Suggested panels

**Overview row:**

| Panel                    | Visualization | Query                                         |
|--------------------------|---------------|-----------------------------------------------|
| Total Executions (24h)   | Stat          | `increase(dm_orchestration_executions_total[24h])` |
| Success Rate (24h)       | Gauge         | See formula below.                            |
| Alive Nodes              | Stat          | `dm_cluster_nodes_alive`                      |
| Active WebSockets        | Stat          | `dm_websocket_connections_active`             |

**Success rate formula:**

```promql
(
  sum(increase(dm_orchestration_executions_total{status="success"}[24h]))
  /
  sum(increase(dm_orchestration_executions_total[24h]))
) * 100
```

**Execution details row:**

| Panel                      | Visualization  | Query                                                       |
|----------------------------|----------------|-------------------------------------------------------------|
| Executions by Orchestration| Time series    | `sum by (orchestration_name) (rate(dm_orchestration_executions_total[5m]))` |
| Step Duration p95          | Time series    | `histogram_quantile(0.95, sum by (le, step_name) (rate(dm_step_execution_duration_seconds_bucket[5m])))` |
| Failure Rate               | Time series    | `sum(rate(dm_orchestration_executions_total{status="failed"}[5m]))` |

**API performance row:**

| Panel                    | Visualization | Query                                                        |
|--------------------------|---------------|--------------------------------------------------------------|
| Request Rate             | Time series   | `sum(rate(dm_api_requests_total[5m]))`                       |
| API Latency p99          | Time series   | `histogram_quantile(0.99, sum by (le) (rate(dm_api_request_duration_seconds_bucket[5m])))` |
| Error Rate               | Time series   | `sum(rate(dm_api_requests_total{status_code=~"5.."}[5m]))`   |

### Importing the dashboard

1. Open Grafana and go to **Dashboards > Import**.
2. Create a new dashboard or use the panel suggestions above.
3. Select your Prometheus data source.
4. Adjust time ranges and refresh intervals as needed.

## 5. Alert Examples

### High failure rate

Fire an alert when more than 10% of executions fail over a 15-minute window:

```yaml
groups:
  - name: dimensigon-alerts
    rules:
      - alert: HighOrchestrationFailureRate
        expr: |
          (
            sum(rate(dm_orchestration_executions_total{status="failed"}[15m]))
            /
            sum(rate(dm_orchestration_executions_total[15m]))
          ) > 0.10
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Dimensigon orchestration failure rate is above 10%"
          description: >
            {{ $value | humanizePercentage }} of orchestrations have failed
            in the last 15 minutes.
```

### Slow steps

Fire an alert when the p95 duration of any step exceeds 120 seconds:

```yaml
      - alert: SlowStepExecution
        expr: |
          histogram_quantile(0.95,
            sum by (le, step_name) (rate(dm_step_execution_duration_seconds_bucket[15m]))
          ) > 120
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Step {{ $labels.step_name }} is slow (p95 > 120s)"
          description: >
            The 95th percentile duration for step {{ $labels.step_name }}
            has exceeded 120 seconds for the last 10 minutes.
```

### Cluster node down

Fire an alert when the number of alive nodes drops below the expected count:

```yaml
      - alert: ClusterNodeDown
        expr: dm_cluster_nodes_alive < 3
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Dimensigon cluster has fewer than 3 alive nodes"
          description: >
            Only {{ $value }} nodes are alive. Expected at least 3.
```

### API error spike

Fire an alert on a spike in 5xx responses:

```yaml
      - alert: HighAPIErrorRate
        expr: |
          sum(rate(dm_api_requests_total{status_code=~"5.."}[5m])) > 1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Dimensigon API is returning 5xx errors"
          description: >
            The API 5xx error rate is {{ $value }} req/s over the last 5 minutes.
```

### WebSocket connection spike

Fire an alert when an unusual number of WebSocket connections are open:

```yaml
      - alert: HighWebSocketConnections
        expr: dm_websocket_connections_active > 100
        for: 5m
        labels:
          severity: info
        annotations:
          summary: "High number of active WebSocket connections"
          description: >
            {{ $value }} WebSocket connections are currently active.
```

## 6. Implementation Details

The metrics are implemented in `dimensigon/web/metrics.py` using the
`prometheus_client` Python library:

- **Counters** (`Counter`) are monotonically increasing and reset only when the
  process restarts. Use `rate()` or `increase()` in PromQL to get useful values.
- **Histograms** (`Histogram`) track value distributions using pre-defined
  buckets. Use `histogram_quantile()` for percentile calculations.
- **Gauges** (`Gauge`) represent a single numeric value that can go up or down.

API request metrics are automatically recorded via Flask `before_request` and
`after_request` hooks registered by `register_metrics_hooks()`. The `/metrics`
and `/health` endpoints are excluded from API metric collection to avoid
self-referential noise.

The `endpoint` label uses the Flask endpoint name rather than the raw URL path
to prevent high-cardinality label explosion from UUID path parameters.

## 7. Configuration

| Setting                 | Default | Description                                    |
|-------------------------|---------|------------------------------------------------|
| `METRICS_ENABLED`       | `true`  | Enable or disable the `/metrics` endpoint.     |
| `METRICS_PATH`          | `/metrics` | URL path for the metrics endpoint.          |

## 8. Troubleshooting

**`/metrics` returns 404**
- Ensure the `metrics_bp` blueprint is registered. Check that
  `dimensigon/web/__init__.py` includes the metrics blueprint.

**Metrics values are all zero**
- Counters start at zero after a process restart. Run some orchestrations to
  generate data.
- Gauges like `dm_cluster_nodes_alive` require the cluster health check loop
  to be running.

**High cardinality warning in Prometheus**
- If you see "too many time series" warnings, check the `endpoint` label.
  The implementation uses Flask endpoint names to keep cardinality low, but
  custom blueprints with many routes could increase it.

## Related Features

- [Tutorial 06: Real-Time Monitoring](06-realtime-monitoring.md) -- `dm_websocket_connections_active` tracks live watchers.
- [Tutorial 08: Topology Visualization](08-topology-visualization.md) -- `dm_cluster_nodes_alive` reflects topology health.
- [Tutorial 10: Dashboard Widgets](10-dashboard-widgets.md) -- widgets provide in-app views of similar data.
