import multiprocessing

bind = ["0.0.0.0:5050"]
threads = 3*multiprocessing.cpu_count()
# keyfile = 'ssl/cert.pem'
# certfile = 'ssl/key.pem'
# ca_certs = 'ssl/ca.crt'
capture_output = True
pidfile = 'gunicorn.pid'
timeout = 3000
enable_stdio_inheritance = True
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
            "level": "DEBUG",
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

