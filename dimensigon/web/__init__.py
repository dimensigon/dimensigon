import time
import typing as t

from flask import Flask, g
from flask_jwt_extended import JWTManager
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import MetaData, select, func
from sqlalchemy.pool import StaticPool

from dimensigon.utils.event_handler import EventHandler
from dimensigon.web import errors, threading
from dimensigon.web.config import config_by_name
from .extensions.flask_executor.executor import Executor
from .helpers import BaseQueryJSON, run_in_background, get_root_auth
from ..utils.helpers import bind2gate

if t.TYPE_CHECKING:
    from ..core import Dimensigon

meta = MetaData(naming_convention={
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_key)s",
    "ck": "ck_%(table_name)s_%(column_0_N_key)s",
    "fk": "fk_%(table_name)s_%(column_0_N_key)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
})

# Flask-SQLAlchemy 3.x compatibility
# Note: query_class parameter removed in 3.x, use model.query directly
db = SQLAlchemy(
    metadata=meta,
    engine_options={
        'connect_args': {'check_same_thread': False},
        'isolation_level': 'READ UNCOMMITTED'
    }
)

# Add BaseQueryJSON functionality via model base class instead
# This maintains backward compatibility while supporting Flask-SQLAlchemy 3.x
db.Query = BaseQueryJSON

jwt = JWTManager()
executor = Executor()

try:
    from flask_sock import Sock
    sock = Sock()
except ImportError:
    sock = None


class DimensigonFlask(Flask):
    dm: t.ClassVar['Dimensigon'] = None

    def bootstrap(self):
        """ bootstraps the application. Gunicorn is still not listening on sockets
        """
        with self.app_context():
            from dimensigon.domain.entities import Server, Parameter
            import dimensigon.web.network as ntwrk
            from dimensigon.domain.entities import Locker

            # reset scopes
            Locker.set_initial(unlock=True)

            # check gates
            me = Server.get_current()
            if me is None:
                raise RuntimeError("No server set as 'current'")

            input_gates = bind2gate(self.dm.config.http_conf.get('bind'))
            current_gates = [(gate.dns or str(gate.ip), gate.port) for gate in me.gates]
            new_gates = set(input_gates).difference(set(current_gates))
            self.server_id_with_new_gates = None
            if new_gates:
                if Parameter.get('join_server'):
                    join_server = db.session.get(Server, Parameter.get('join_server'))
                else:
                    join_server = None
                servers = Server.get_neighbours()
                if join_server in servers:
                    servers.pop(servers.index(join_server))
                    servers.append(join_server)
                else:
                    self.logger.warning(f'Join server {join_server} is not a neighbour')
                start = time.time()
                resp = None
                server = True
                while len(servers) > 0 and server and (time.time() - start) < 900:
                    server_retries = 0
                    server = servers[-1]
                    self.logger.debug(f"Sending new gates {new_gates} to {server}...")
                    resp = ntwrk.patch(server, 'api_1_0.serverresource',
                                       view_data=dict(server_id=str(Server.get_current().id)),
                                       json={'gates': [{'dns_or_ip': ip, 'port': port} for ip, port in new_gates]},
                                       timeout=60,
                                       auth=get_root_auth())
                    if not resp.ok:
                        self.logger.debug(f"Unable to send new gates to {server}. Reason: {resp}")
                        self.logger.info(f"Unable to create new gates. Trying to send again in 5 seconds...")
                        time.sleep(5)
                        if resp.code == 409:
                            # try with the same server
                            server_retries += 1
                        elif resp.code == 500:

                            # try with another server
                            i = servers.index(server) - 1
                            if i >= 0:
                                server = servers[i]
                                server_retries = 0
                            else:
                                server = None
                        if server_retries == 3:
                            # changing server
                            i = servers.index(server) - 1
                            if i >= 0:
                                server = servers[i]
                                server_retries = 0
                            else:
                                server = None
                    else:
                        self.logger.debug("New gates created succesfully")
                        Parameter.set('new_gates_server', server.id)
                        break

                if not servers:
                    if db.session.execute(select(func.count()).select_from(Server)).scalar() == 1:
                        self.logger.info(f"Creating new gates {new_gates} without performing a lock on catalog")
                        for gate in new_gates:
                            g = me.add_new_gate(gate[0], gate[1])
                            db.session.add(g)

                else:
                    if resp and not resp.ok:
                        self.logger.warning(f"Remote servers may not connect with {me}. ")
                db.session.commit()

    def run(self, host=None, port=None, debug=None, **options):
        super(DimensigonFlask, self).run(host=host, port=port, debug=debug, use_reloader=False, **options)


def _initialize_blueprint(app):
    from dimensigon.web.routes import root_bp
    from dimensigon.web.api_1_0 import api_bp as api_1_0_bp
    from dimensigon.web.health import health_bp
    # DM-WebManager GUI components
    from dimensigon.web.admin.data_dictionary import data_dict_bp
    from dimensigon.web.admin.executions_viewer import executions_bp
    from dimensigon.web.admin.routes import admin_routes_bp

    # Health endpoint registered first — no auth required
    app.register_blueprint(health_bp, url_prefix='/health')

    # Prometheus metrics endpoint
    try:
        from dimensigon.web.metrics import metrics_bp
        app.register_blueprint(metrics_bp)
    except ImportError:
        pass

    app.register_blueprint(root_bp)
    handle_exception = app.handle_exception
    handle_user_exception = app.handle_user_exception
    app.register_blueprint(api_1_0_bp)

    # Register new API v2 endpoints and admin GUI routes
    app.register_blueprint(data_dict_bp)
    app.register_blueprint(executions_bp)
    app.register_blueprint(admin_routes_bp)

    app.handle_exception = handle_exception
    app.handle_user_exception = handle_user_exception


def _initialize_errorhandlers(app):
    '''
    Initialize error handlers
    '''
    from dimensigon.web.errors import bp_errors
    app.register_blueprint(bp_errors)


def create_app(config_name):
    app = DimensigonFlask('dm')
    if isinstance(config_name, t.Mapping):
        app.config.from_mapping(config_name)
    elif config_name in config_by_name:
        app.config.from_object(config_by_name[config_name])
        config_by_name[config_name].init_app(app)
    else:
        app.config.from_object(config_name)
        if hasattr(config_name, 'init_app'):
            config_name.init_app(app)

    # EXTENSIONS
    db.init_app(app)
    jwt.init_app(app)
    executor.init_app(app)
    if sock is not None:
        sock.init_app(app)
        _register_ws_routes(app)
    app.events = EventHandler()

    # Initialize DM-WebManager Admin GUI
    from dimensigon.web.admin import init_admin
    init_admin(app)

    # with app.app_context():
    #     def do_connect(dbapi_connection, connection_record):
    #         # disable pysqlite's emitting of the BEGIN statement entirely.
    #         # also stops it from emitting COMMIT before any DDL.
    #         dbapi_connection.isolation_level = None
    #
    #     def do_begin(conn):
    #         # emit our own BEGIN
    #         conn.execute("BEGIN")
    #     event.listen(db.get_engine(), "connect", do_connect)
    #     event.listen(db.get_engine(), "begin", do_begin)

    # Register token blacklist check
    from dimensigon.web.admin.auth import token_blacklist

    @jwt.token_in_blocklist_loader
    def check_if_token_revoked(jwt_header, jwt_payload):
        return token_blacklist.is_blacklisted(jwt_payload.get('jti', ''))

    app.before_request(load_global_data_into_context)
    # if not app.config['TESTING']:
    # app.before_first_request(app.dm.cluster_manager.notify_cluster)
    # app.before_first_request(app.cluster_manager.start)
    # app.before_first_request(app.file_sync.start)
    _initialize_blueprint(app)
    _initialize_errorhandlers(app)

    # Register Prometheus metrics hooks
    try:
        from dimensigon.web.metrics import register_metrics_hooks
        register_metrics_hooks(app)
    except ImportError:
        pass

    _register_security_headers(app)

    return app


def _register_security_headers(app):
    """Add baseline browser-hardening response headers on every response.

    Defense-in-depth at the application layer so the headers are present on
    every node regardless of the fronting proxy (openresty/nginx). Existing
    upstream values are not overwritten, so an edge proxy can still tighten
    them. See CWE-693 / OWASP A05:2021 (Security Misconfiguration).
    """
    default_headers = {
        'Strict-Transport-Security': 'max-age=63072000; includeSubDomains; preload',
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
        'Referrer-Policy': 'strict-origin-when-cross-origin',
        'Content-Security-Policy': (
            "default-src 'self'; frame-ancestors 'none'; "
            "base-uri 'self'; form-action 'self'; object-src 'none'"
        ),
    }

    @app.after_request
    def set_security_headers(response):
        for name, value in default_headers.items():
            response.headers.setdefault(name, value)
        return response


def _register_ws_routes(app):
    """Register WebSocket routes for real-time monitoring."""
    from dimensigon.web.admin.ws import ws_manager
    import json

    @sock.route('/ws/executions/<execution_id>')
    def execution_ws(ws, execution_id):
        """WebSocket endpoint for real-time execution monitoring.

        Clients connect to receive live step execution events.

        Access control (fail-closed): the caller must present a valid,
        non-revoked JWT (cookies or headers) for a user with at least the
        'readonly' role. A 'readonly' user may only view executions they
        launched; 'operator'/'administrator' may view any execution. The
        broadcast stream carries raw step stdout/stderr, so an
        unauthenticated/unauthorized connection is closed immediately.
        """
        from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity, get_jwt
        from dimensigon.web.admin.auth import (
            get_user_role_level, ROLE_HIERARCHY, token_blacklist,
        )
        from dimensigon.domain.entities import User, OrchExecution

        try:
            verify_jwt_in_request(locations=['cookies', 'headers'])
            jwt_data = get_jwt()
            if token_blacklist.is_blacklisted(jwt_data.get('jti', '')):
                ws.close()
                return
            identity = get_jwt_identity()
            user = db.session.get(User, identity)
            if not user or get_user_role_level(user) < ROLE_HIERARCHY['readonly']:
                ws.close()
                return
            # Authorize access to this specific execution.
            if get_user_role_level(user) < ROLE_HIERARCHY['operator']:
                # readonly user: only their own executions
                execution = db.session.get(OrchExecution, execution_id)
                if execution is None or str(execution.executor_id) != str(identity):
                    ws.close()
                    return
        except Exception:
            try:
                ws.close()
            except Exception:
                pass
            return

        ws_manager.connect(execution_id, ws)
        try:
            while True:
                # Keep connection alive; client can send ping/commands
                data = ws.receive(timeout=30)
                if data is None:
                    # Send keepalive
                    try:
                        ws.send(json.dumps({'type': 'ping'}))
                    except Exception:
                        break
        except Exception:
            pass
        finally:
            ws_manager.disconnect(execution_id, ws)


def load_global_data_into_context():
    from flask import request, current_app
    # Skip heavy setup for health and WebManager endpoints (they have their own auth)
    if request.path.startswith('/health') or request.path.startswith('/metrics') or request.path.startswith('/dm-webmanager'):
        return
    from dimensigon.domain.entities import Server, Dimension
    from dimensigon.web.decorators import set_source
    global _dimension, _server
    set_source()
    g.server = _get_current_server_cached(current_app, Server)
    # Dimension.get_current() already caches per-app internally.
    g.dimension = Dimension.get_current()


def _get_current_server_cached(app, Server):
    """Resolve the local Server, caching its id on the app to keep it off the
    per-request hot path.

    The local node's identity (the ``_me=True`` row) is fixed for the process
    lifetime, so we resolve it once via the filtered query and thereafter fetch
    by primary key (``db.session.get`` — an identity-map lookup) instead of
    re-running the ``_me=True``/``deleted=False`` scan on every request.
    """
    cached_id = getattr(app, '_cached_current_server_id', None)
    if cached_id is not None:
        server = db.session.get(Server, cached_id)
        if server is not None and not server.deleted:
            return server
        # Cache went stale (row deleted/replaced); fall through to re-resolve.
    server = Server.get_current()
    try:
        app._cached_current_server_id = server.id
    except Exception:
        pass
    return server
