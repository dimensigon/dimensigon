import logging
import multiprocessing as mp
import os
import time
import typing as t

from gunicorn.app.base import Application
from gunicorn.pidfile import Pidfile

from dimensigon import defaults
from dimensigon.exceptions import DimensigonError
from dimensigon.use_cases.base import TerminateInterrupt
from dimensigon.use_cases.catalog import CatalogManager
from dimensigon.use_cases.cluster import ClusterManager
from dimensigon.use_cases.file_sync import FileSync
# from dimensigon.use_cases.log_sender import LogSender
from dimensigon.use_cases.mptools import MainContext
from dimensigon.use_cases.mptools_events import EventMessage
from dimensigon.use_cases.routing import RouteManager
from dimensigon.utils.typos import Id
from dimensigon.web import DimensigonFlask, create_app, threading

_logger = logging.getLogger("dm")


def _sleep_secs(max_sleep, end_time=999999999999999.9):
    # Calculate time left to sleep, no less than 0
    return max(0.0, min(end_time - time.time(), max_sleep))


class GunicornApp(Application):
    dm = None

    def __init__(self, application, options=None):
        """ Construct the Application. Default gUnicorn configuration is loaded """

        self.application = application
        self.options = options or {}
        self.process = None

        # if port, or host isn't set-- run from os.environments
        #
        super(GunicornApp, self).__init__()

    def init(self, parser, opts, args):
        pass

    def load_config(self):
        # Load up the any app specific configuration
        for k, v in self.options.items():
            self.cfg.set(k.lower(), v)

    def load(self):
        return self.application


class Dimensigon:
    def __init__(self):
        self.flask_app: t.Optional[DimensigonFlask] = None
        self.gunicorn: t.Optional[GunicornApp] = None
        self.server: t.Optional[mp.Process] = None
        self.config = Config(self)

        # processes
        self.manager = mp.Manager()  # shared memory between processes
        self.cluster_manager: t.Optional[ClusterManager] = None
        self.file_sync: t.Optional[FileSync] = None
        self.route_manager: t.Optional[RouteManager] = None
        self.catalog_manager: t.Optional[CatalogManager] = None

        self.STOP_WAIT_SECS = 90
        self.engine = None  # set on setup_dm function
        self.get_session = None  # set on setup_dm function
        self._main_ctx = MainContext()
        self.server_id: t.Optional[Id] = None
        self.pid = None
        self.pidfile = None

    def create_flask_instance(self):
        if self.flask_app is None:
            self.flask_app = create_app(self.config.flask_conf)
            self.flask_app.dm = self

    def create_gunicorn_instance(self):
        if self.gunicorn is None:
            self.gunicorn = GunicornApp(self.flask_app, self.config.http_conf)
            self.gunicorn.dm = self

    def set_catalog_manager(self):
        if self.catalog_manager is None:
            self.catalog_manager = CatalogManager(None, None, None, None, None, self)

    def create_processes(self):
        self.cluster_manager = self._main_ctx.Proc(ClusterManager, self)
        self.cluster_manager.SHUTDOWN_WAIT_SECS = 90

        self.route_manager = self._main_ctx.Proc(RouteManager, self)
        self.file_sync = self._main_ctx.Proc(FileSync, self)
        self.catalog_manager = self._main_ctx.Thread(CatalogManager, self)
        # self.log_sender = LogSender(self)  # log sender embedded in file_sync process
        if self.config.flask:
            self.http_server = mp.Process(target=self.flask_app.run, name="Flask server",
                                          kwargs=dict(host='0.0.0.0', port=defaults.DEFAULT_PORT, ssl_context='adhoc'))
        else:
            self.http_server = mp.Process(target=self.gunicorn.run, name="Gunicorn server")

    def bootstrap(self):
        self.create_flask_instance()
        self.create_gunicorn_instance()
        self.create_processes()

    def make_first_request(self):
        from dimensigon.domain.entities import Server
        import dimensigon.web.network as ntwrk

        with self.flask_app.app_context():
            start = time.time()
            while True:
                resp = ntwrk.get(Server.get_current(), 'root.home', timeout=1)
                if not resp.ok and time.time() - start < 30:
                    time.sleep(0.5)
                else:
                    break
            self._main_ctx.publish_q.safe_put(EventMessage("Listening", source="Dimensigon"))

    def start_server(self):
        # if hasattr(self.cluster_manager, 'notify_cluster'):
        #     self.flask_app.before_first_request(self.cluster_manager.notify_cluster)
        th = threading.Timer(interval=4, function=self.make_first_request)
        th.start()
        self.http_server.start()

    def start(self):
        """starts dimensigon server"""
        _logger.info(f"Starting Dimensigon ({os.getpid()})")
        self._main_ctx.init_signals()
        self.pid = os.getpid()
        pidname = self.config.pidfile
        self.pidfile = Pidfile(pidname)
        self.pidfile.create(self.pid)
        self.bootstrap()
        self.flask_app.bootstrap()

        # self.cluster_manager.start()
        # self.file_sync.start()
        # self.log_sender.start() # log sender embedded in file_sync process
        self.start_server()
        try:
            while not self._main_ctx.shutdown_event.is_set():
                self._main_ctx.forward_events()
        except (TerminateInterrupt, KeyboardInterrupt):
            pass
        self.shutdown()

    def shutdown(self):
        _logger.info(f"Shutting down Dimensigon")
        self.http_server.terminate()
        self.http_server.terminate()
        self.http_server.join(90)
        if self.http_server.is_alive():
            self.http_server.kill()
        self._main_ctx.stop()


class Config:

    def __init__(self, dm: Dimensigon):
        self.dm = dm

        # Directory that holds the configuration
        self.config_dir: t.Optional[str] = None

        # If set, process should upgrade as soon as a neighbour has a higher version
        self.auto_upgrade: bool = True

        # sets a security layer on top of HTTP
        self.security_layer: bool = True

        # allow pass through security layer without encrypt packet with header D-Securizer: plain
        self.security_layer_antidote: bool = False

        # pidfile name
        self.pidfile: str = None

        # runs the scheduler
        self.scheduler: bool = True

        # database uri
        self.db_uri: t.Optional[str] = None

        # http configuration
        self.http_conf = {}

        # flask configuration
        self.flask_conf = {}

        # Run configuration (used for elevator to load same configuration)
        self.run_config = {}

        self.debug: bool = False

        self.flask: bool = False

        # forces the process to scan on startup
        self.force_scan: bool = False

        # Run route table, catalog and cluster refresh every minutes
        # self.refresh_interval: dt.timedelta = defaults.

    def path(self, *path: str) -> str:
        """Generate path to the file within the configuration directory.
        """
        if self.config_dir is None:
            raise DimensigonError("config_dir is not set")
        return os.path.join(self.config_dir, *path)
