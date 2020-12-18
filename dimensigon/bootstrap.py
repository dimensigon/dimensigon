import logging
import logging.config
import multiprocessing
import os
import sys
from copy import deepcopy

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


default_logconfig_dict = {
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
        "urllib3": {
            "level": "ERROR",
            "propagate": False,
        },
        # "dimensigon": {
        #     "level": "DEBUG",
        #     "qualname": "dimensigon"
        # },
        # "dm.lock": {
        #     "level": "DEBUG",
        # },
        # "dm.fileSync": {
        #     "level": "DEBUG",
        # },
        # "dm.cluster": {
        #     "level": "DEBUG",
        # },
        # "dm.logfed": {
        #     "level": "DEBUG",
        # },
        # "dm.db": {
        #     "level": "DEBUG",
        # },
        # "dm.routing": {
        #     "level": "DEBUG",
        # },
        # "dm.cluster": {
        #     "level": "DEBUG",
        # },
        # "dm.catalog": {
        #     "level": "DEBUG",
        # },
        # "dm.network": {
        #     "level": "INFO",
        # },
        # "dm.query": {
        #     "level": "DEBUG",
        #     "handlers": ["query_file"],
        #     "propagate": False
        # },
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
        # "sqlalchemy.engine": {
        #     "level": "INFO"
        # }
    },
    'handlers': {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "detailed",
            "stream": "ext://sys.stdout"
        },
        "error_file": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "maxBytes": 20 * 1024 * 1024,
            "backupCount": 5,
            "formatter": "detailed",
            "filename": "dimensigon.log"
        },
        "query_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "maxBytes": 20 * 1024 * 1024,
            "backupCount": 5,
            "formatter": "detailed",
            "filename": "query.log"
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
            "format": "%(asctime)s %(levelname)-8s %(name)-24s %(message)s",
            "datefmt": "[%Y-%m-%d %H:%M:%S %z]",
            "class": "logging.Formatter"
        },
        "detailed": {
            "format": "%(asctime)s %(processName)-20s %(levelname)-8s %(name)-30s %(message)s",
            "datefmt": "[%Y-%m-%d %H:%M:%S %z]",
            "class": "logging.Formatter"
        },
        "access": {
            "format": "%(message)s",
            "class": "logging.Formatter"
        }
    }
}

logconfig = {}


def _setup_dimensigon_config(run_config: RuntimeConfig, config: Config):
    global logconfig
    # save arguments passed
    config.args = sys.argv

    config.config_dir = run_config.config_dir or get_default_config_dir()
    ensure_config_path(config.config_dir)

    config.debug = run_config.debug
    config.flask = run_config.flask
    # config.refresh_interval = dt.timedelta(minutes=run_config.refresh_interval)
    config.force_scan = run_config.force_scan

    if run_config.pid_file:
        if not os.path.dirname(run_config.pid_file):
            config.pidfile = config.path(run_config.pid_file)
        else:
            config.pidfile = os.path.abspath(run_config.pid_file)
    else:
        config.pidfile = config.path(defaults.PID_FILE)

    logconfig = deepcopy(default_logconfig_dict)

    for k, v in run_config.logconfig.items():
        if k in logconfig:
            logconfig[k].update(v)
        else:
            logconfig[k] = v

    for name, handler in logconfig['handlers'].items():
        if name == 'error_file':
            handler['filename'] = run_config.errorlog or config.path(defaults.LOG_FOLDER, defaults.ERROR_LOGFILE)
        elif name == 'access_file':
            handler['filename'] = run_config.accesslog or config.path(defaults.LOG_FOLDER, defaults.ACCESS_LOGFILE)
        else:
            if 'filename' in handler and not os.path.dirname(handler['filename']):
                handler['filename'] = config.path(defaults.LOG_FOLDER, handler['filename'])

    logconfig['root']['level'] = 'DEBUG' if run_config.debug else 'INFO'

    # in case log gunicorn not called
    logging.config.dictConfig(logconfig)


def setup_database_uri(run_config: RuntimeConfig, config: Config):
    db_path = os.path.join(config.config_dir, defaults.DEFAULT_DB_FILE)
    config.db_uri = defaults.DEFAULT_DB_URL.format(db_file=db_path)


def _setup_http_config(run_config: RuntimeConfig, config: Config):
    # def on_exit(server):
    #     server.app.dm.shutdown()

    bind = []
    for ip in run_config.ips or ['0.0.0.0']:
        bind.append(f"{ip}:{run_config.port or defaults.DEFAULT_PORT}")

    config.http_conf.update(  # Logging
        access_log_format='%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s %(L)s "%(f)s" "%(a)s"',
        capture_output=False,
        logconfig_dict=logconfig,
        enable_stdio_inheritance=True,
        # Process Naming
        proc_name=defaults.PROC_NAME,
        # SSL
        # do_handshake_on_connect=False,
        # Server Hooks
        # on_exit=on_exit,
        # Server Mechanics
        preload_app=True,
        # daemon=run_config.daemon,
        # pidfile=os.path.join(run_config.pid_file or config.config_dir, defaults.PID_FILE),
        # Server Socket
        bind=bind,
        # Worker Processes
        workers=1,
        worker_class='gthread',
        threads=run_config.threads or max(12, 4 * multiprocessing.cpu_count()),
        # threads=4,
        # max_requests=100,
        timeout=300,
        graceful_timeout=60,
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


def _setup_flask_config(run_config: RuntimeConfig, dm: Dimensigon):
    flask_config = config_by_name['gunicorn']
    flask_config.SQLALCHEMY_DATABASE_URI = dm.config.db_uri
    if run_config.debug:
        flask_config.DEBUG = run_config.debug

    dm.config.flask_conf = flask_config

    result = dm.engine.execute(Dimension.__table__.select().where(Dimension.current == True))
    result = result.fetchall()
    if len(result) == 1:
        dm.config.flask_conf.SECRET_KEY = result[0][0]
    elif len(result) > 1:
        raise ValueError('More than one dimension are set to current.')
    else:
        dm.config.flask_conf.SECRET_KEY = 'my_precious_key'


def setup_dm(run_config: RuntimeConfig) -> Dimensigon:
    dm = Dimensigon()

    # set dimensigon configuration
    _setup_dimensigon_config(run_config, dm.config)

    # set http configuration. Before setup_db to get ip binds
    _setup_http_config(run_config, dm.config)

    # set database uri
    setup_database_uri(run_config, dm.config)

    # set database to allow queries
    setup_db(dm)

    # set flask configuration
    _setup_flask_config(run_config, dm)

    return dm


def _write_default_config(config_dir: str) -> bool:
    """Write the default config."""

    software_repo_path = os.path.join(config_dir, defaults.SOFTWARE_REPO)
    log_folder_path = os.path.join(config_dir, defaults.LOG_FOLDER)
    log_sender_repo_path = os.path.join(config_dir, defaults.LOG_SENDER_REPO)
    ssl_path = os.path.join(config_dir, defaults.SSL_DIR)
    offset_path = os.path.join(config_dir, defaults.OFFSET_DIR)

    try:
        os.makedirs(software_repo_path, exist_ok=True)
        os.makedirs(log_folder_path, exist_ok=True)
        os.makedirs(log_sender_repo_path, exist_ok=True)
        os.makedirs(ssl_path, exist_ok=True)
        os.makedirs(offset_path, exist_ok=True)
    except OSError:
        print("Unable to create default configuration", config_dir)
        return False
