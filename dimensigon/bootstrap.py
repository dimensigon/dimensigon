import logging
import logging.config
import multiprocessing
import os
import sys

from dimensigon import defaults
from dimensigon.__main__ import RuntimeConfig, Dimension
from dimensigon.core import Config
from dimensigon.core import Dimensigon
from dimensigon.db import setup_db
from dimensigon.web import config_by_name


def get_default_config_dir() -> object:
    """Put together the default configuration directory based on the OS."""
    data_dir = os.getenv("APPDATA") if os.name == "nt" else os.path.expanduser("~")
    return os.path.join(data_dir, defaults.CONFIG_DIR_NAME)  # type: ignore


def ensure_config_path(config_dir: str) -> None:
    """Validate the configuration directory."""

    # Test if configuration directory exists
    if not os.path.isdir(config_dir):
        if config_dir != get_default_config_dir():
            print(
                f"Fatal Error: Specified configuration directory {config_dir} "
                "does not exist"
            )
            sys.exit(1)

        try:
            os.mkdir(config_dir)
        except OSError as e:
            print(
                "Fatal Error: Unable to create default configuration "
                f"directory {config_dir}. Error: {e}"
            )
            sys.exit(1)

        _write_default_config(config_dir)

logconfig_dict = {
    'version': 1,
    'disable_existing_loggers': False,
    "root": {"level": "INFO", "handlers": ["console", "error_file"]},
    'loggers': {
        "gunicorn.error": {
            "level": "INFO",
            "propagate": True,
            "qualname": "gunicorn.error"
        },
        "gunicorn.access": {
            "level": "INFO",
            "handlers": ["access_file"],
            "propagate": False,
            "qualname": "gunicorn.access"
        },
        # "dimensigon": {
        #     "level": "DEBUG",
        #     "qualname": "dimensigon"
        # },
        # "dimensigon.db": {
        #     "level": "DEBUG",
        #     "qualname": "dimensigon.dm"
        # },
        # "dimensigon.routing": {
        #     "level": "DEBUG",
        #     "qualname": "dimensigon.routing"
        # },
        "dimensigon.cluster": {
            "level": "ERROR",
            "qualname": "dimensigon.cluster"
        },
        "dimensigon.catalog": {
            "level": "INFO",
            "qualname": "dimensigon.catalog"
        },
        # "dimensigon.network": {
        #     "level": "INFO",
        #     "qualname": "dimensigon.network"
        # },
        #
        "apscheduler": {
            "level": "ERROR",
            "qualname": "apscheduler"
        },
        # "apscheduler.scheduler": {
        #     "level": "INFO",
        #     "qualname": "apscheduler.scheduler"
        # },
        # "apscheduler.executors": {
        #     "level": "INFO",
        #     "qualname": "apscheduler.executors.default"
        # },
        # "sqlalchemy.engine": {
        #     "level": "ERROR",
        # }
        "asyncio": {
            "propagate": False
        },
    },
    'handlers': {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "generic",
            "stream": "ext://sys.stdout"
        },
        "error_file": {
            "level": "DEBUG",
            "class": "logging.handlers.RotatingFileHandler",
            "maxBytes": 20 * 1024 * 1024,
            "backupCount": 5,
            "formatter": "detailed",
            "filename": "dimensigon.log"
        },
        "access_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "maxBytes": 20 * 1024 * 1024,
            "backupCount": 5,
            "formatter": "access",
            "filename": "access.log",
        }
    },
    'formatters': {
        "generic": {
            "format": "%(asctime)s [%(process)d] %(levelname)-8s %(name)-24s %(message)s",
            "datefmt": "[%Y-%m-%d %H:%M:%S %z]",
            "class": "logging.Formatter"
        },
        "detailed": {
            "format": "%(asctime)s [%(process)-d] [%(threadName)-24s] %(levelname)-8s %(name)-30s %(message)s",
            "datefmt": "[%Y-%m-%d %H:%M:%S %z]",
            "class": "logging.Formatter"
        },
        "access": {
            "format": "%(message)s",
            "class": "logging.Formatter"
        }
    }
}


def setup_database_uri(run_config: RuntimeConfig, config: Config):
    db_path = os.path.join(config.config_dir, defaults.DEFAULT_DB_FILE)
    config.db_uri = defaults.DEFAULT_DB_URL.format(db_file=db_path)


def _setup_flask_config(run_config: RuntimeConfig, dm: Dimensigon):
    flask_config = config_by_name['gunicorn']
    flask_config.SQLALCHEMY_DATABASE_URI = dm.config.db_uri
    if run_config.debug:
        flask_config.DEBUG = run_config.debug

    dm.config.flask_conf = flask_config

    result = dm.engine.execute(Dimension.__table__.select(Dimension.current).where(Dimension.current == True))
    result = result.fetchall()
    if len(result) == 1:
        dm.config.flask_conf.SECRET_KEY = result[0][0]
    elif len(result) > 1:
        raise ValueError('More than one dimension are set to current.')
    else:
        dm.config.flask_conf.SECRET_KEY = 'my_precious_key'


def _setup_dimensigon_config(run_config: RuntimeConfig, config: Config):
    config.config_dir = run_config.config_dir or get_default_config_dir()

    config.debug = run_config.debug


def _setup_http_config(run_config: RuntimeConfig, config: Config):
    def on_exit(server):
        server.app.dm.flask_app.shutdown()

    def on_starting(server):
        server.app.dm.flask_app.start()

    def when_ready(server):
        server.app.dm.flask_app.notify_cluster()

    bind = []
    for ip in run_config.ips or ['0.0.0.0']:
        bind.append(f"{ip}:{run_config.port or defaults.DEFAULT_PORT}")

    logconfig_dict['handlers']['error_file']['filename'] = run_config.errorlog or \
                                                           config.path(defaults.LOG_REPO, defaults.ERROR_LOGFILE)
    logconfig_dict['handlers']['access_file']['filename'] = run_config.accesslog or \
                                                            config.path(defaults.LOG_REPO, defaults.ACCESS_LOGFILE)
    logconfig_dict['root']['level'] = 'DEBUG' if run_config.debug else 'INFO'
    config.http_conf.update(proc_name=defaults.PROC_NAME,
                            threads=run_config.threads or 3 * multiprocessing.cpu_count(),
                            pidfile=os.path.join(run_config.pid_file or config.config_dir, defaults.PID_FILE),
                            timeout=3000,
                            graceful_timeout=60,
                            enable_stdio_inheritance=True,
                            capture_output=False,
                            logconfig_dict=logconfig_dict,
                            bind=bind,
                            daemon=run_config.daemon,
                            on_starting=on_starting,
                            when_ready=when_ready,
                            on_exit=on_exit,
                            )

    if run_config.certfile:
        if not os.path.exists(run_config.certfile):
            raise FileNotFoundError(run_config.certfile)
        else:
            config.http_conf.update(certfile=run_config.certfile)
    else:
        cert_file = os.path.join(config.config_dir, defaults.SSL_DIR, defaults.CERT_FILE)
        config.http_conf.update(certfile=cert_file)
    if run_config.keyfile:
        if not os.path.exists(run_config.keyfile):
            raise FileNotFoundError(run_config.keyfile)
        else:
            config.http_conf.update(keyfile=run_config.keyfile)
    else:
        key_file = os.path.join(config.config_dir, defaults.SSL_DIR, defaults.KEY_FILE)
        config.http_conf.update(keyfile=key_file)


def setup_dm(run_config: RuntimeConfig) -> Dimensigon:
    dm = Dimensigon()

    # set dimensigon configuration
    _setup_dimensigon_config(run_config, dm.config)

    ensure_config_path(dm.config.config_dir)

    # set http configuration. Before setup_db to get ip binds
    _setup_http_config(run_config, dm.config)

    # initializing logs
    logging.config.dictConfig(dm.config.http_conf['logconfig_dict'])

    # set database
    setup_database_uri(run_config, dm.config)

    setup_db(dm)

    # set flask configuration
    _setup_flask_config(run_config, dm)

    return dm


def _write_default_config(config_dir: str) -> bool:
    """Write the default config."""

    software_repo_path = os.path.join(config_dir, defaults.SOFTWARE_REPO)
    log_repo_path = os.path.join(config_dir, defaults.LOG_REPO)
    ssl_path = os.path.join(config_dir, defaults.SSL_DIR)

    try:
        os.makedirs(software_repo_path, exist_ok=True)
        os.makedirs(log_repo_path, exist_ok=True)
        os.makedirs(ssl_path, exist_ok=True)
    except OSError:
        print("Unable to create default configuration", config_dir)
        return False
