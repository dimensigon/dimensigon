import datetime as dt
import json
import logging
import os
import random
import time
import typing as t

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, g
from flask_jwt_extended import JWTManager
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import MetaData

from dimensigon.utils.event_handler import EventHandler
from dimensigon.web import errors, threading
from dimensigon.web.config import config_by_name
from .extensions.flask_executor.executor import Executor
from .helpers import BaseQueryJSON, run_in_background
from .. import defaults
from ..utils import asyncio
from ..utils.helpers import get_now, bind2gate

if t.TYPE_CHECKING:
    from ..core import Dimensigon
    from ..use_cases.clustering import ClusterManager


meta = MetaData(naming_convention={
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(column_0_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
})

db = SQLAlchemy(query_class=BaseQueryJSON, metadata=meta,
                engine_options={'connect_args': {'check_same_thread': False}, 'pool_recycle': 60})
# db = SQLAlchemy(query_class=BaseQueryJSON, metadata=meta)
# db = SQLAlchemy(query_class=BaseQueryJSON)
jwt = JWTManager()
executor = Executor()


class DimensigonFlask(Flask):
    dm: t.ClassVar['Dimensigon'] = None
    cluster_manager: t.ClassVar['ClusterManager']

    def shutdown(self):
        with self.app_context():
            from dimensigon.domain.entities import Server, Parameter
            import dimensigon.web.network as ntwrk
            from dimensigon.use_cases.helpers import get_root_auth

            self.cluster_manager.stop()

            # shutdown executor
            executor.shutdown()
            if self.extensions.get('scheduler', None):
                self.extensions.get('scheduler').shutdown()

            Parameter.set('last_graceful_shutdown', get_now())
            db.session.commit()
            servers = Server.get_neighbours()
            if servers:
                self.logger.debug(f"Sending shutdown to {', '.join([s.name for s in servers])}")
            else:
                self.logger.debug("No server to send shutdown information")
            if servers:
                responses = asyncio.run(
                    ntwrk.parallel_requests(servers, 'post',
                                            view_or_url='api_1_0.cluster_out',
                                            view_data=dict(server_id=str(Server.get_current().id)),
                                            json={'death': get_now().strftime(defaults.DATEMARK_FORMAT)},
                                            timeout=2, auth=get_root_auth()))
                if self.logger.level <= logging.DEBUG:
                    for r in responses:
                        if not r.ok:
                            self.logger.warning(f"Unable to send data to {r.server}: {r}")

    def bootstrap_start(self):
        with self.app_context():
            from dimensigon.domain.entities import Server, Parameter, Route
            import dimensigon.web.network as ntwrk
            from dimensigon.use_cases.helpers import get_root_auth
            from dimensigon.use_cases import routing
            from dimensigon.domain.entities import Locker
            from ..use_cases.clustering import ClusterManager

            self.cluster_manager = ClusterManager(self,
                                                  threshold=self.dm.config.refresh_interval * defaults.COMA_NODE_FACTOR * 0.85,
                                                  start=False)

            # reset scopes
            Locker.set_initial(unlock=True)

            last_shutdown = Parameter.get('last_graceful_shutdown', defaults.INITIAL_DATEMARK) - dt.timedelta(hours=1)

            if self.dm.config.force_scan or last_shutdown < get_now() - self.dm.config.refresh_interval:
                scan = True
            else:
                scan = False
            asyncio.run(
                routing.async_update_routes_send(discover_new_neighbours=scan, check_current_neighbours=scan,
                                                 send=False))

            route_table = []
            for route in Route.query.join(Server.route).order_by(
                    Server.name).filter(Server.deleted == False).all():
                route_table.append(route.to_json(human=True))
            routing.logger.debug("Routing table: " + json.dumps(route_table, indent=2))

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
                    join_server = Server.query.get(Parameter.get('join_server'))
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
                        self.server_id_with_new_gates = server.id
                        break

                if not servers:
                    if Server.query.count() == 1:
                        self.logger.info(f"Creating new gates {new_gates} without performing a lock on catalog")
                        for gate in new_gates:
                            g = me.add_new_gate(gate[0], gate[1])
                            db.session.add(g)
                        db.session.commit()
                else:
                    if resp and not resp.ok:
                        self.logger.warning(f"Remote servers may not connect with {me}. ")

        self.start_background_tasks()

    def make_first_request(self):
        from dimensigon.domain.entities import Server
        import dimensigon.web.network as ntwrk

        with self.app_context():
            start = time.time()
            while True:
                resp = ntwrk.get(Server.get_current(), 'root.home', timeout=1)
                if not resp.ok and time.time() - start < 30:
                    time.sleep(2)
                else:
                    break

    def notify_cluster(self):
        from dimensigon.domain.entities import Server
        import dimensigon.web.network as ntwrk
        from dimensigon.use_cases.helpers import get_root_auth
        from dimensigon.use_cases import routing
        from dimensigon.domain.entities import Parameter

        with self.app_context():
            cluster_logger = logging.getLogger('dimensigon.cluster')
            not_notify = set()
            me = Server.get_current()
            msg, debug_msg = routing.format_routes_message()

            neighbours = Server.get_neighbours()

            if Parameter.get('join_server'):
                join_server = Server.query.get(Parameter.get('join_server'))
            else:
                join_server = None

            if neighbours:
                random.shuffle(neighbours)
                first = [s for s in neighbours if s.id == self.server_id_with_new_gates]
                if first:
                    neighbours.pop(neighbours.index(first))
                    neighbours = first + neighbours
                elif join_server in neighbours:
                        neighbours.pop(neighbours.index(join_server))
                        neighbours = [join_server] + neighbours
                for s in neighbours:
                    if s.id not in not_notify:
                        self.logger.debug(f"Sending 'Cluster IN' message to {s}")
                        resp = ntwrk.post(s, 'api_1_0.cluster_in', view_data=dict(server_id=str(me.id)),
                                          json=msg, timeout=10, auth=get_root_auth())
                        if resp.ok:
                            self.cluster_manager.cluster.update_cluster(resp.msg['cluster'])
                            not_notify.update(resp.msg.get('neighbours', []))
                        else:
                            self.logger.debug(f"Unable to send 'Cluster IN' message to {s} . Response: {resp}")
                    else:
                        self.logger.debug(f"Skiping server {s} from sending 'Cluster IN' message")
                else:
                    self.cluster_manager.set_alive(me.id)
                alive = [(getattr(Server.query.get(s_id), 'name', None) or s_id) for s_id in
                         self.cluster_manager.cluster.get_alive()]
                cluster_logger.info(f"Alive servers: {', '.join(alive)}")
            else:
                self.logger.debug("No neighbour to send 'Cluster IN'")
                self.cluster_manager.set_alive(me.id)

    def start_background_tasks(self):
        from ..use_cases.log_sender import LogSender
        from dimensigon.web.background_tasks import process_catalog_route_table
        if not self.config['TESTING'] or os.getenv('WERKZEUG_RUN_MAIN') == 'true':
            if self.extensions.get('scheduler') is None and self.config['SCHEDULER']:
                bs = BackgroundScheduler()
                self.extensions['scheduler'] = bs
                ls = LogSender()
                self.extensions['log_sender'] = ls
                bs.start()

                # if self.config.get('AUTOUPGRADE'):
                # bs.add_job(func=process_get_new_version_from_gogs, args=(self,), trigger="interval",
                #            id='upgrader',
                #            hours=6)
                if self.dm.config.refresh_interval:
                    bs.add_job(func=process_catalog_route_table, name="catalog & route upgrade",
                               args=(self,),
                               id='routing_cluster_catalog_refresh',
                               trigger="interval", minutes=self.dm.config.refresh_interval.seconds / 60)
                bs.add_job(func=run_in_background, name="log_sender", args=(ls.send_new_data, self),
                           id='log_sender',
                           trigger="interval",
                           minutes=2, next_run_time=get_now() + dt.timedelta(seconds=30))

    def run(self, host=None, port=None, debug=None, **options):
        super(DimensigonFlask, self).run(host=host, port=port, debug=debug, use_reloader=False, **options)


def _initialize_blueprint(app):
    from dimensigon.web.routes import root_bp
    from dimensigon.web.api_1_0 import api_bp as api_1_0_bp

    app.register_blueprint(root_bp)
    handle_exception = app.handle_exception
    handle_user_exception = app.handle_user_exception
    app.register_blueprint(api_1_0_bp)
    app.handle_exception = handle_exception
    app.handle_user_exception = handle_user_exception


def _initialize_errorhandlers(app):
    '''
    Initialize error handlers
    '''
    from dimensigon.web.errors import bp_errors
    app.register_blueprint(bp_errors)


def create_app(config_name):
    app = DimensigonFlask('dimensigon')
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
    app.events = EventHandler()

    app.before_request(load_global_data_into_context)
    app.before_first_request(start_cluster_manager)
    _initialize_blueprint(app)
    _initialize_errorhandlers(app)

    return app


def start_cluster_manager():
    from flask import current_app
    current_app.notify_cluster()
    current_app.cluster_manager.start()


# @jwt.user_loader_callback_loader
# def user_loader_callback(identity):
#     from ..domain.entities import User
#     return User.query.get(identity)


def load_global_data_into_context():
    from dimensigon.domain.entities import Server, Dimension
    from dimensigon.web.decorators import set_source
    global _dimension, _server
    set_source()
    g.server = Server.get_current()
    g.dimension = Dimension.get_current()