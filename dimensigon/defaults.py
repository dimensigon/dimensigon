import itertools
import os
import socket
from datetime import datetime, timezone

import netifaces

# Global defaults
CONFIG_DIR_NAME = ".dimensigon"
HOME = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


ips = list(filter(lambda x: x != '127.0.0.1', itertools.chain(
    *[[ip['addr'] for ip in netifaces.ifaddresses(iface).get(netifaces.AF_INET, [])] for iface in
      netifaces.interfaces()])))

# Gunicorn Defaults
DEFAULT_PORT = 5000
HOSTNAME = socket.gethostname()
GUNICORN_CONF_FILE = '_gunicorn.conf.py'
PID_FILE = 'dimensigon.pid'
PROC_NAME = 'dimensigon'
DEFAULT_SSL_DIR = '.ssl'
DEFAULT_KEY_FILE = 'key.pem'
DEFAULT_CERT_FILE = 'cert.pem'


# Database
DEFAULT_DB_URL = "sqlite:///{db_file}"
DEFAULT_DB_FILE = "dimensigon.db"


# Dimensigon Defaults
MAX_WAITING_TIME = 300  # time in seconds waiting tasks to finish
MAX_TIME_WAITING_SERVERS = 600  # max time waiting for servers to be created

TIMEOUT_REQUEST = 60
TIMEOUT_PREVENTING_LOCK = 60  # max time in seconds locker will be in PREVENTING_LOCK before returning to UNLOCK
TIMEOUT_ORCHESTRATION = 1800  # max time waiting for an orchestration to finish
TIMEOUT_COMMAND = 20  # max time waiting for a command execution

CHUNK_SIZE = 2*1024  # in MB
MAX_SENDERS = 4

MIN_SERVERS_QUORUM = 5  # minimum servers to run quorum algorithm
INITIAL_DATEMARK = datetime(2019, 4, 1, tzinfo=timezone.utc)

DATETIME_FORMAT = "%m/%d/%Y, %H:%M:%S.%f %z"
DATEMARK_FORMAT = "%Y%m%d.%H%M%S.%f%z"

SOFTWARE_REPO = 'software'
DIMENSIGON_DIR = os.path.join(SOFTWARE_REPO, 'dimensigon')
LOG_REPO = 'logs'
