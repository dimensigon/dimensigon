import datetime as dt
import logging
import multiprocessing as mp
import os
import signal
import time
import typing as t

from gunicorn.app.base import Application
from gunicorn.pidfile import Pidfile

from dimensigon import defaults
from dimensigon.exceptions import DimensigonError
from dimensigon.use_cases.base import default_signal_handler, init_signals, TerminateInterrupt
from dimensigon.use_cases.clustering import ClusterManager
from dimensigon.use_cases.file_sync import FileSync
# from dimensigon.use_cases.log_sender import LogSender
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
    MAX_TERMINATE_CALLED = 3
    int_handler = staticmethod(default_signal_handler)
    term_handler = staticmethod(default_signal_handler)
    _logger = _logger

    def __init__(self):
        self.flask_app: t.Optional[DimensigonFlask] = None
        self.gunicorn: t.Optional[GunicornApp] = None
        self.server: t.Optional[mp.Process] = None
        self.config = Config(self)
        self.cluster_manager: t.Optional[ClusterManager] = None
        self.file_sync: t.Optional[FileSync] = None
        # self.log_sender: t.Optional[LogSender] = None  # log sender embedded in file_sync process
        self.shutdown_event = mp.Event()
        self.STOP_WAIT_SECS = 90
        self.engine = None  # set on setup_dm function
        self.get_session = None  # set on setup_dm function
        self.procs = []
        self.pid = None
        self.pidfile = None

    def _init_signals(self):
        signal_object = init_signals(self.shutdown_event, self.int_handler, self.term_handler)
        return signal_object

    def create_flask_instance(self):
        if self.flask_app is None:
            self.flask_app = create_app(self.config.flask_conf)
            self.flask_app.dm = self

    def create_gunicorn_instance(self):
        if self.gunicorn is None:
            self.gunicorn = GunicornApp(self.flask_app, self.config.http_conf)
            self.gunicorn.dm = self

    def create_processes(self):
        self.cluster_manager = ClusterManager(self,
                                              zombie_threshold=defaults.COMA_NODE_FACTOR * defaults.REFRESH_PERIOD * 60)
        self.file_sync = FileSync(self)
        # self.log_sender = LogSender(self)  # log sender embedded in file_sync process
        if self.config.flask:
            self.server = mp.Process(target=self.flask_app.run, name="Flask server",
                                     kwargs=dict(host='0.0.0.0', port=defaults.DEFAULT_PORT, ssl_context='adhoc'))
        else:
            self.server = mp.Process(target=self.gunicorn.run, name="Gunicorn server")

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
                    time.sleep(2)
                else:
                    break

    def start_server(self):
        if hasattr(self.cluster_manager, 'notify_cluster'):
            self.flask_app.before_first_request(self.cluster_manager.notify_cluster)
        th = threading.Timer(interval=4, function=self.make_first_request)
        th.start()
        self.server.start()

    def start(self):
        """starts dimensigon server"""
        _logger.info(f"Starting Dimensigon ({os.getpid()})")
        self.pid = os.getpid()
        pidname = self.config.pidfile
        self.pidfile = Pidfile(pidname)
        self.pidfile.create(self.pid)
        self.bootstrap()
        self.flask_app.bootstrap()
        self.cluster_manager.start()
        self.file_sync.start()
        # self.log_sender.start() # log sender embedded in file_sync process
        self.start_server()
        try:
            while not self.shutdown_event.is_set():
                time.sleep(0.2)
        except (TerminateInterrupt, KeyboardInterrupt):
            pass
        self.shutdown()

    def shutdown(self):
        _logger.info(f"Shutting down Dimensigon")
        self.flask_app.shutdown()
        self.shutdown_event.set()
        os.kill(self.server.pid, signal.SIGTERM)

        procs = []
        # procs.append(self.log_sender.process)  # log sender embedded in file_sync process
        procs.append(self.file_sync.process)
        procs.append(self.cluster_manager.process)
        procs.append(self.server)
        end_time = time.time() + self.STOP_WAIT_SECS

        for proc in procs:
            _logger.debug(f"Joining process {proc.name}")
            join_secs = _sleep_secs(self.STOP_WAIT_SECS, end_time)
            proc.join(join_secs)

        still_running = []
        while procs:
            proc = procs.pop()
            if proc.exitcode is None:
                _logger.debug(f"{proc.name} still alive. Terminating...")
                if not proc.terminate():
                    still_running.append(proc)
            else:
                exitcode = proc.exitcode
                if exitcode:
                    _logger.error(f"Process {proc.name} ended with exitcode {exitcode}")
                else:
                    _logger.debug(f"Process {proc.name} stopped successfully")


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
        self.refresh_interval: dt.timedelta = defaults.REFRESH_PERIOD

    def path(self, *path: str) -> str:
        """Generate path to the file within the configuration directory.
        """
        if self.config_dir is None:
            raise DimensigonError("config_dir is not set")
        return os.path.join(self.config_dir, *path)