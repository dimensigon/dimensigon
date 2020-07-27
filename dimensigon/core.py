import logging
import os
from typing import Optional

from gunicorn.app.base import Application

from dimensigon.exceptions import DimensigonError
from dimensigon.web import DimensigonFlask, create_app

_LOGGER = logging.getLogger(__name__)


class GunicornApp(Application):

    def __init__(self, application, options=None):
        """ Construct the Application. Default gUnicorn configuration is loaded """

        self.application = application
        self.options = options or {}

        # if port, or host isn't set-- run from os.environments
        #
        super(GunicornApp, self).__init__()

    def init(self, parser, opts, args):
        """ Apply our custom settings """

        cfg = {}
        for k, v in self.options.items():
            if k.lower() in self.cfg.settings and v is not None:
                cfg[k.lower()] = v
        return cfg

    def load(self):
        return self.application


class Dimensigon:
    def __init__(self):
        self.flask_app: Optional[DimensigonFlask] = None
        self.http_server: Optional[GunicornApp] = None
        self.config = Config(self)
        self.engine = None
        self.get_session = None

    def instantiate_flask_gunicorn(self):
        if self.flask_app is None:
            self.flask_app = create_app(self.config.flask_conf)
        if self.http_server is None:
            self.http_server = GunicornApp(self.flask_app, self.config.http_conf)

    def start(self):
        """starts dimensigon server"""
        self.instantiate_flask_gunicorn()
        self.http_server.run()

class Config:

    def __init__(self, dm: Dimensigon):
        self.dm = dm

        # Directory that holds the configuration
        self.config_dir: Optional[str] = None

        # If set, process should upgrade as soon as a neighbour has a higher version
        self.auto_upgrade: bool = True

        # sets a security layer on top of HTTP
        self.security_layer: bool = True

        # allow pass through security layer without encrypt packet with header D-Securizer: plain
        self.security_layer_antidote: bool = False

        # runs the scheduler
        self.scheduler: bool = True

        # database uri
        self.db_uri = None

        # http configuration
        self.http_conf = {}

        # flask configuration
        self.flask_conf = {}

    def path(self, *path: str) -> str:
        """Generate path to the file within the configuration directory.
        """
        if self.config_dir is None:
            raise DimensigonError("config_dir is not set")
        return os.path.join(self.config_dir, *path)