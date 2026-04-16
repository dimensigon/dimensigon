from flask import Blueprint, Response, request, g
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
import time

metrics_bp = Blueprint('metrics', __name__)

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
            # Use a simplified endpoint label to avoid high cardinality
            endpoint = request.endpoint or 'unknown'
            API_REQUESTS.labels(
                method=request.method,
                endpoint=endpoint,
                status_code=response.status_code
            ).inc()
            API_REQUEST_DURATION.labels(
                method=request.method,
                endpoint=endpoint
            ).observe(duration)

        return response
