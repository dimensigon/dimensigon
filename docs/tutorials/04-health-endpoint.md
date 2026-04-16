# Health Endpoint Tutorial

## Overview

Dimensigon 3.0 exposes a lightweight, unauthenticated health check endpoint at
`/health`. It is designed for container orchestrators (Docker, Kubernetes),
load balancers, and monitoring systems that need to verify whether a node is
alive and operational.

The endpoint is deliberately separated from the existing authenticated
`/healthcheck` endpoint (which provides cluster-level information) so that
infrastructure tooling can probe it without JWT tokens or encryption.

## Prerequisites

- A running Dimensigon node
- `curl` or equivalent HTTP client
- Optional: Docker, Kubernetes, Prometheus, or Nagios for integration examples

## 1. Basic Health Check

### Request

```bash
curl -s http://localhost:5000/health
```

### Response (HTTP 200)

```json
{
  "status": "ok",
  "version": "2.1.0",
  "node": "web01",
  "neighbours": 3
}
```

### Response fields

| Field | Type | Description |
|---|---|---|
| `status` | string | Always `"ok"` if the node is responding. |
| `version` | string | Dimensigon version (from `dimensigon/__init__.py`). |
| `node` | string | The name of the current server, or the `HOSTNAME` environment variable if the server entity is not yet initialized. |
| `neighbours` | integer | Number of alive neighbours in the mesh cluster. Uses a cached value (see section 7). |

## 2. Extended Diagnostics

Add `?detail=true` to get additional system information.

### Request

```bash
curl -s 'http://localhost:5000/health?detail=true'
```

### Response (HTTP 200)

```json
{
  "status": "ok",
  "version": "2.1.0",
  "node": "web01",
  "neighbours": 3,
  "detail": {
    "uptime_seconds": 84201.3,
    "db_ok": true,
    "memory_mb": 142.5
  }
}
```

### Detail fields

| Field | Type | Description |
|---|---|---|
| `uptime_seconds` | float | Seconds since the health module was loaded (approximately when the process started). Rounded to one decimal. |
| `db_ok` | boolean | `true` if a `SELECT 1` query succeeds against the database. `false` on connection failure. |
| `memory_mb` | float | Peak resident set size (RSS) in megabytes, from `resource.getrusage()`. Rounded to one decimal. |

## 3. No Authentication Required

The `/health` endpoint is explicitly excluded from Dimensigon's request
middleware. In `dimensigon/web/__init__.py`, the `load_global_data_into_context`
function skips heavy setup for health requests:

```python
def load_global_data_into_context():
    if request.path.startswith('/health') or ...:
        return
```

This means:

- No JWT token is needed.
- No `D-Source` header is needed.
- No securizer encryption is applied.
- No server/dimension context is loaded.

The endpoint always returns HTTP 200 as long as the Flask process is running.

## 4. Using with Docker HEALTHCHECK

The Dimensigon Dockerfile already includes a health check:

```dockerfile
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health')" || exit 1
```

If you prefer to use `curl` (available in the production image):

```dockerfile
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1
```

### Docker Compose example

```yaml
services:
  dimensigon:
    image: dimensigon:3.0
    ports:
      - "5000:5000"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5000/health"]
      interval: 30s
      timeout: 5s
      start_period: 30s
      retries: 3
```

Verify health status:

```bash
docker inspect --format='{{.State.Health.Status}}' dimensigon
# healthy
```

## 5. Using with Kubernetes Readiness and Liveness Probes

### Liveness probe (is the process alive?)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: dimensigon
spec:
  template:
    spec:
      containers:
        - name: dimensigon
          image: dimensigon:3.0
          ports:
            - containerPort: 5000
          livenessProbe:
            httpGet:
              path: /health
              port: 5000
            initialDelaySeconds: 30
            periodSeconds: 30
            timeoutSeconds: 5
            failureThreshold: 3
```

### Readiness probe (is the node ready to serve traffic?)

Use the detailed endpoint to check database connectivity:

```yaml
          readinessProbe:
            httpGet:
              path: /health?detail=true
              port: 5000
            initialDelaySeconds: 10
            periodSeconds: 10
            timeoutSeconds: 5
            failureThreshold: 3
```

Note: the readiness probe will succeed even if `db_ok` is `false`, because the
endpoint always returns HTTP 200. If you need the probe to fail when the
database is down, add a custom health check script:

```bash
#!/bin/bash
response=$(curl -s http://localhost:5000/health?detail=true)
db_ok=$(echo "$response" | python3 -c "import sys,json; print(json.load(sys.stdin)['detail']['db_ok'])")
if [ "$db_ok" = "True" ]; then
  exit 0
else
  exit 1
fi
```

### Startup probe (for slow-starting nodes)

```yaml
          startupProbe:
            httpGet:
              path: /health
              port: 5000
            initialDelaySeconds: 5
            periodSeconds: 5
            failureThreshold: 30   # 5s * 30 = 150s max startup time
```

## 6. Using with Monitoring Tools

### Prometheus

If you are using Prometheus with the Blackbox Exporter, add a probe target:

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'dimensigon-health'
    metrics_path: /probe
    params:
      module: [http_2xx]
    static_configs:
      - targets:
          - http://node1:5000/health
          - http://node2:5000/health
          - http://node3:5000/health
    relabel_configs:
      - source_labels: [__address__]
        target_label: __param_target
      - source_labels: [__param_target]
        target_label: instance
      - target_label: __address__
        replacement: blackbox-exporter:9115
```

Dimensigon also provides a `/metrics` endpoint with Prometheus-format metrics
(if the metrics module is installed). See `dimensigon/web/metrics.py`.

### Nagios / Icinga

Use `check_http` to monitor the health endpoint:

```bash
/usr/lib/nagios/plugins/check_http \
  -H node1 -p 5000 -u /health \
  -s '"status": "ok"' \
  --ssl
```

This checks that the response contains `"status": "ok"`.

For a more detailed check that includes database status:

```bash
/usr/lib/nagios/plugins/check_http \
  -H node1 -p 5000 -u '/health?detail=true' \
  -s '"db_ok": true' \
  --ssl
```

### Simple shell script monitor

```bash
#!/bin/bash
# check_dimensigon_health.sh
NODES="node1:5000 node2:5000 node3:5000"

for node in $NODES; do
  status=$(curl -s --max-time 5 "http://$node/health" | python3 -c \
    "import sys,json; print(json.load(sys.stdin).get('status','FAIL'))" 2>/dev/null)
  if [ "$status" = "ok" ]; then
    echo "$node: OK"
  else
    echo "$node: FAILED" >&2
  fi
done
```

## 7. Neighbour Count Caching (5-Second TTL)

The `neighbours` field in the health response uses a cached value to avoid
querying the cluster manager on every probe request. The cache has a 5-second
TTL, implemented with a thread-safe double-check pattern:

```python
CACHE_TTL = 5  # seconds

def _get_neighbour_count():
    now = time.monotonic()
    if now < _neighbour_cache['expires']:
        return _neighbour_cache['count']

    with _cache_lock:
        # Double-check after acquiring lock
        if now < _neighbour_cache['expires']:
            return _neighbour_cache['count']
        # ... fetch from cluster_manager ...
        _neighbour_cache['count'] = count
        _neighbour_cache['expires'] = now + CACHE_TTL
        return count
```

This means:

- Health checks at any frequency up to 5 per second will hit the cache.
- The cluster manager is queried at most once every 5 seconds.
- The lock prevents thundering-herd effects when multiple probes arrive
  simultaneously after cache expiry.

## 8. curl Examples Summary

```bash
# Basic health check
curl -s http://localhost:5000/health

# Extended diagnostics
curl -s 'http://localhost:5000/health?detail=true'

# With timing info
curl -s -w "\nTime: %{time_total}s\n" http://localhost:5000/health

# Check HTTP status code only
curl -s -o /dev/null -w "%{http_code}" http://localhost:5000/health

# Pretty-printed output
curl -s http://localhost:5000/health | python3 -m json.tool

# With jq (if installed)
curl -s 'http://localhost:5000/health?detail=true' | jq '.detail'
```

## Troubleshooting

### Health endpoint returns 404

The `/health` blueprint must be registered. Verify that
`dimensigon/web/__init__.py` contains:

```python
from dimensigon.web.health import health_bp
app.register_blueprint(health_bp, url_prefix='/health')
```

### `neighbours` always shows 0

This is normal during startup before the cluster manager has discovered
neighbours. If it persists:

1. Check that the cluster manager is running (`current_app.dm.cluster_manager`).
2. Verify that neighbour nodes are reachable on the mesh port.
3. Check the discovery configuration (`DM_DISCOVERY_DNS`, `DM_AUTO_JOIN`).

### `db_ok` is `false` in detailed response

The database connectivity check runs `SELECT 1`. If this fails:

1. Verify the database file exists (for SQLite) or the database server is
   reachable (for PostgreSQL).
2. Check `SQLALCHEMY_DATABASE_URI` in the configuration.
3. Look for connection pool exhaustion in the application logs.

### High memory usage reported by `memory_mb`

The value is peak RSS from `resource.getrusage()`, not current RSS. It will
only ever increase over the lifetime of the process. If it is unexpectedly
high, profile the application with `tracemalloc` or a memory profiler.

## Related Features

- [Authentication Tutorial](05-authentication.md) -- the authenticated
  `/healthcheck` endpoint provides richer cluster data
- [Security Layer Tutorial](02-security-layer.md) -- `/health` bypasses the
  securizer
- Source code: `dimensigon/web/health.py`
- Source code: `dimensigon/web/routes.py` (`/healthcheck` -- authenticated)
