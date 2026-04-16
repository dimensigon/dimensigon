"""Lightweight health endpoint for container orchestrators and monitoring."""
import os
import time
import threading

from flask import Blueprint, jsonify, request

from dimensigon import __version__

health_bp = Blueprint('health', __name__)

_start_time = time.monotonic()
_neighbour_cache = {'count': 0, 'expires': 0}
_cache_lock = threading.Lock()
CACHE_TTL = 5  # seconds


def _get_neighbour_count():
    """Get cached neighbour count with 5-second TTL."""
    now = time.monotonic()
    if now < _neighbour_cache['expires']:
        return _neighbour_cache['count']

    with _cache_lock:
        # Double-check after acquiring lock
        if now < _neighbour_cache['expires']:
            return _neighbour_cache['count']
        try:
            from flask import current_app
            if hasattr(current_app, 'dm') and current_app.dm and hasattr(current_app.dm, 'cluster_manager'):
                count = len(current_app.dm.cluster_manager.get_alive())
            else:
                count = 0
        except Exception:
            count = 0
        _neighbour_cache['count'] = count
        _neighbour_cache['expires'] = now + CACHE_TTL
        return count


def _get_node_name():
    """Get the current node name."""
    try:
        from flask import current_app
        if hasattr(current_app, 'dm') and current_app.dm:
            from dimensigon.domain.entities import Server
            server = Server.get_current()
            if server:
                return server.name
    except Exception:
        pass
    return os.environ.get('HOSTNAME', 'unknown')


@health_bp.route('', methods=['GET'])
@health_bp.route('/', methods=['GET'])
def health_check():
    """Unauthenticated health check endpoint.

    Returns basic status info. Add ?detail=true for extended diagnostics.
    """
    payload = {
        'status': 'ok',
        'version': __version__,
        'node': _get_node_name(),
        'neighbours': _get_neighbour_count(),
    }

    if request.args.get('detail') == 'true':
        import resource
        payload['detail'] = {
            'uptime_seconds': round(time.monotonic() - _start_time, 1),
            'db_ok': _check_db(),
            'memory_mb': round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1),
        }

    return jsonify(payload), 200


def _check_db():
    """Quick DB connectivity check."""
    try:
        from dimensigon.web import db
        from sqlalchemy import text
        db.session.execute(text('SELECT 1'))
        return True
    except Exception:
        return False
