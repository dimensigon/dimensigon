import datetime as dt
import json
import logging
import os
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

meta = MetaData(naming_convention={
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(column_0_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
})

db = SQLAlchemy(query_class=BaseQueryJSON, metadata=meta,
                engine_options={'connect_args': {'check_same_thread': True}})
# db = SQLAlchemy(query_class=BaseQueryJSON, metadata=meta)
# db = SQLAlchemy(query_class=BaseQueryJSON)
jwt = JWTManager()
executor = Executor()

class DimensigonFlask(Flask):
    dm: t.ClassVar['Dimensigon'] = None

    def bootstrap(self):
        """ bootstraps the application. Gunicorn is still not listening on sockets
        """
        with self.app_context():
            from dimensigon.domain.entities import Server, Parameter, Route
            import dimensigon.web.network as ntwrk
            from dimensigon.use_cases.helpers import get_root_auth
            from dimensigon.use_cases import routing
            from dimensigon.domain.entities import Locker

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
                        Parameter.set('new_gates_server', server.id)
                        break

                if not servers:
                    if Server.query.count() == 1:
                        self.logger.info(f"Creating new gates {new_gates} without performing a lock on catalog")
                        for gate in new_gates:
                            g = me.add_new_gate(gate[0], gate[1])
                            db.session.add(g)

                else:
                    if resp and not resp.ok:
                        self.logger.warning(f"Remote servers may not connect with {me}. ")
                db.session.commit()
        self.start_background_tasks()

    def start_background_tasks(self):
        from ..use_cases.log_sender import LogSender
        from dimensigon.web.background_tasks import process_catalog_route_table
        if not self.config['TESTING'] or os.getenv('WERKZEUG_RUN_MAIN') == 'true':
            if self.extensions.get('scheduler') is None and self.config['SCHEDULER']:
                # passing timezone="UTC" to solve problems with systems where get_localzone() returns an object with
                # local zone
                bs = self.extensions['scheduler'] = BackgroundScheduler(timezone="UTC", daemon=False)
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


    def stop_background_tasks(self):
        bs = self.extensions.get('scheduler')
        if bs:
            bs.shutdown(wait=False)
        executor.shutdown(wait=False)
        # ls = self.extensions.get('log_sender')
        # if ls:
        #     ls.stop()
        # fs = self.extensions.get('file_sync')
        # if fs:
        #     fs.stop()


    def shutdown(self):
        with self.app_context():
            from dimensigon.domain.entities import Server, Parameter
            import dimensigon.web.network as ntwrk
            from dimensigon.use_cases.helpers import get_root_auth

            self.stop_background_tasks()

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
    app.events = EventHandler()

    app.before_request(load_global_data_into_context)
    # if not app.config['TESTING']:
    # app.before_first_request(app.dm.cluster_manager.notify_cluster)
    # app.before_first_request(app.cluster_manager.start)
    # app.before_first_request(app.file_sync.start)
    _initialize_blueprint(app)
    _initialize_errorhandlers(app)

    return app



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