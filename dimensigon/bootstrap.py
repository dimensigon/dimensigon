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
        except OSError:
            print(
                "Fatal Error: Unable to create default configuration "
                f"directory {config_dir}"
            )
            sys.exit(1)

        _write_default_config(config_dir)

logconfig_dict = {
    'version': 1,
    'disable_existing_loggers': False,
    'loggers': {
        "root": {"level": "INFO", "handlers": ["console"]},
        "gunicorn.error": {
            "level": "INFO",
            "handlers": ["console"],
            "propagate": False,
            "qualname": "gunicorn.error"
        },
        "gunicorn.access": {
            "level": "INFO",
            "handlers": ["access_file"],
            "propagate": False,
            "qualname": "gunicorn.access"
        },
        "dimensigon": {
            "level": "INFO",
            "handlers": ["console"],
            "propagate": False,
            "qualname": "dimensigon"
        },
        # "dimensigon.background": {
        #     "level": "INFO",
        #     "handlers": ["console"],
        #     "propagate": False,
        #     "qualname": "dimensigon.background"
        # },
        # "dimensigon.background.routing": {
        #     "level": "INFO",
        #     "handlers": ["console"],
        #     "propagate": False,
        #     "qualname": "dimensigon.background"
        # },
        # "dimensigon.background.catalog": {
        #     "level": "INFO",
        #     "handlers": ["console"],
        #     "propagate": False,
        #     "qualname": "dimensigon.background"
        # },
        "dimensigon.network": {
            "level": "INFO",
            "handlers": ["console"],
            "propagate": False,
            "qualname": "dimensigon.network"
        },
        "apscheduler": {
            "level": "INFO",
            "handlers": [],
            "propagate": False,
            "qualname": "apscheduler"
        },
        "apscheduler.scheduler": {
            "level": "INFO",
            "handlers": [],
            "propagate": False,
            "qualname": "apscheduler.scheduler"
        },
        "apscheduler.executors": {
            "level": "INFO",
            "handlers": [],
            "propagate": False,
            "qualname": "apscheduler.executors.default"
        },
        "sqlalchemy.engine": {
            "level": "INFO",
            "handlers": [],
            "propagate": False,
        }
    },
    'handlers': {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "generic",
            "stream": "ext://sys.stdout"
        },
        "error_file": {
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


def _setup_dimensigon_config(run_config: RuntimeConfig, config: Config):
    config.config_dir = run_config.config_dir or get_default_config_dir()


def _setup_http_config(run_config: RuntimeConfig, config: Config):
    bind = []
    for ip in run_config.ips or ['0.0.0.0']:
        bind.append(f"{ip}:{run_config.port or defaults.DEFAULT_PORT}")

    config.http_conf.update(proc_name=defaults.PROC_NAME,
                            threads=run_config.threads or 3 * multiprocessing.cpu_count(),
                            pidfile=os.path.join(run_config.pid_file or config.config_dir, defaults.PID_FILE),
                            timeout=3000,
                            enable_stdio_inheritance=True,
                            capture_output=True,
                            logconfig_dict=logconfig_dict,
                            bind=bind
                            )

    if run_config.certfile:
        if not os.path.exists(run_config.certfile):
            raise FileNotFoundError(run_config.certfile)
        else:
            config.http_conf.update(certfile=run_config.certfile)
    else:
        cert_file = os.path.join(config.config_dir, defaults.DEFAULT_SSL_DIR, defaults.DEFAULT_CERT_FILE)
        if os.path.exists(cert_file):
            config.http_conf.update(certfile=cert_file)
    if run_config.keyfile:
        if not os.path.exists(run_config.keyfile):
            raise FileNotFoundError(run_config.keyfile)
        else:
            config.http_conf.update(keyfile=run_config.keyfile)
    else:
        key_file = os.path.join(config.config_dir, defaults.DEFAULT_SSL_DIR, defaults.DEFAULT_KEY_FILE)
        if os.path.exists(key_file):
            config.http_conf.update(keyfile=key_file)


def setup_dm(run_config: RuntimeConfig) -> Dimensigon:
    dm = Dimensigon()

    # set dimensigon configuration
    _setup_dimensigon_config(run_config, dm.config)

    ensure_config_path(dm.config.config_dir)

    # set http configuration. Before setup_db to get ip binds
    _setup_http_config(run_config, dm.config)

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

    try:
        os.mkdir(software_repo_path)
        os.mkdir(log_repo_path)
    except OSError:
        print("Unable to create default configuration file", config_dir)
        return False
