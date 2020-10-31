import datetime as dt
import logging
import os
import sys
import time
import typing as t

from gunicorn.app.base import Application

from dimensigon import defaults
from dimensigon.exceptions import DimensigonError
from dimensigon.use_cases.file_sync import FileSync
from dimensigon.web import DimensigonFlask, create_app, threading

_LOGGER = logging.getLogger(__name__)


class GunicornApp(Application):
    dm = None

    def __init__(self, application, options=None):
        """ Construct the Application. Default gUnicorn configuration is loaded """

        self.application = application
        self.options = options or {}

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
        self.http_server: t.Optional[GunicornApp] = None
        self.config = Config(self)
        self.file_sync: t.Optional[FileSync] = None
        self.engine = None        # set on setup_dm function
        self.get_session = None   # set on setup_dm function

    def create_flask_instance(self):
        if self.flask_app is None:
            self.flask_app = create_app(self.config.flask_conf)
            self.flask_app.dm = self

    def create_gunicorn_instance(self):
        if self.http_server is None:
            self.http_server = GunicornApp(self.flask_app, self.config.http_conf)
            self.http_server.dm = self

    def create_instances(self):
        self.create_flask_instance()
        self.create_gunicorn_instance()
        self.file_sync = FileSync(self.engine, app=self.flask_app)

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

    def start(self):
        """starts dimensigon server"""
        self.create_instances()
        self.flask_app.bootstrap()
        self.file_sync.start()
        th = threading.Timer(interval=4, function=self.make_first_request)
        th.start()
        if self.config.flask:
            self.flask_app.run(host='0.0.0.0', port=defaults.DEFAULT_PORT, ssl_context='adhoc')
            self.shutdown()
            sys.exit(0)
        else:
            self.http_server.run()
            self.shutdown()

    def shutdown(self):
        self.flask_app.shutdown()
        self.file_sync.stop()

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