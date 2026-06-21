from flask import Blueprint, Response, request, g
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
import time

metrics_bp = Blueprint('metrics', __name__)

# Bounded set of HTTP methods used for metric labels (cardinality guard).
_KNOWN_METHODS = frozenset(
    {'GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS', 'TRACE', 'CONNECT'}
)

# Define metrics
ORCHESTRATION_EXECUTIONS = Counter(
    'dm_orchestration_executions_total',
    'Total orchestration executions',
    ['orchestration_name', 'status']
)

STEP_EXECUTION_DURATION = Histogram(
    'dm_step_execution_duration_seconds',
    'Step execution duration in seconds',
    ['step_name', 'status'],
    buckets=[0.1, 0.5, 1, 5, 10, 30, 60, 120, 300, 600]
)

CLUSTER_NODES_ALIVE = Gauge(
    'dm_cluster_nodes_alive',
    'Number of alive cluster nodes'
)

API_REQUESTS = Counter(
    'dm_api_requests_total',
    'Total API requests',
    ['method', 'endpoint', 'status_code']
)

API_REQUEST_DURATION = Histogram(
    'dm_api_request_duration_seconds',
    'API request duration in seconds',
    ['method', 'endpoint'],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10]
)

WS_CONNECTIONS_ACTIVE = Gauge(
    'dm_websocket_connections_active',
    'Active WebSocket connections'
)

@metrics_bp.route('/metrics')
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)


def register_metrics_hooks(app):
    """Register before/after request hooks for API metrics."""

    @app.before_request
    def start_timer():
        # Skip metrics for /metrics and /health endpoints
        if request.path in ('/metrics', '/health', '/health/'):
            return
        g._metrics_start_time = time.monotonic()

    @app.after_request
    def record_metrics(response):
        if request.path in ('/metrics', '/health', '/health/'):
            return response

        start = getattr(g, '_metrics_start_time', None)
        if start is not None:
            duration = time.monotonic() - start
            # Cardinality guard: label by the Flask *rule name* (request.endpoint),
            # which is a bounded set, NOT the request path (unbounded). When no
            # rule matched (404 on an arbitrary path), request.endpoint is None;
            # collapse those to a single 'unmatched' bucket so a flood of 404s on
            # random paths cannot create unbounded label series.
            endpoint = request.endpoint or 'unmatched'
            # request.method is bounded by Werkzeug to known HTTP verbs, but be
            # defensive: only emit recognized methods, else collapse to 'other'.
            method = request.method if request.method in _KNOWN_METHODS else 'other'
            API_REQUESTS.labels(
                method=method,
                endpoint=endpoint,
                status_code=response.status_code
            ).inc()
            API_REQUEST_DURATION.labels(
                method=method,
                endpoint=endpoint
            ).observe(duration)

        return response
