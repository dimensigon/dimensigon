import datetime as dt
import itertools
import os
import socket

import netifaces

# Global defaults
CONFIG_DIR_NAME = ".dimensigon"
HOME = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ips = list(filter(lambda x: x != '127.0.0.1', itertools.chain(
    *[[ip['addr'] for ip in netifaces.ifaddresses(iface).get(netifaces.AF_INET, [])] for iface in
      netifaces.interfaces()])))

# Gunicorn Defaults
DEFAULT_PORT = 20194
HOSTNAME = socket.gethostname()
GUNICORN_CONF_FILE = '_gunicorn.conf.py'
PID_FILE = 'dimensigon.pid'
PROC_NAME = 'dimensigon'
ACCESS_LOGFILE = 'access.log'
ERROR_LOGFILE = 'dimensigon.log'
SSL_DIR = '.ssl'
KEY_FILE = 'key.pem'
CERT_FILE = 'cert.pem'

# Database
DB_PREFIX = 'sqlite:///'
DEFAULT_DB_URL = f"{DB_PREFIX}{{db_file}}"
DEFAULT_DB_FILE = "dimensigon.db"

# Dimensigon Defaults
MAX_TIME_WAITING_SERVERS = 1800  # max time waiting for servers to be created
JOIN_TOKEN_EXPIRE_TIME = 15  # join token expire time in minutes
ROUTE_REFRESH_PERIOD = 300  # route table refresh process
ROUTE_SEND_PERIOD = 10  # send changed routes every ROUTE_SEND_PERIOD seconds
CATALOG_REFRESH_PERIOD = 300  # catalog table refresh process
ZOMBIE_NODE = CATALOG_REFRESH_PERIOD * 2  # a node is considered zombie if we do not get a keepalive after ZOMBIE_NODE
CLUSTER_SEND_PERIOD = 10  # send cluster changes every CLUSTER_SEND_PERIOD seconds
FILE_SYNC_PERIOD = 5  # sync files every FILE_SYNC_PERIOD seconds

# quorum algorithm
ADULT_NODES = dt.timedelta(hours=24)  # age of a node to be selectable for the quorum
MAJORITY = 0.51  # ratio of servers to be selectable from selectable population in order to perform a lock

TIMEOUT_REQUEST = 60
TIMEOUT_PREVENTING_LOCK = 60  # max time in seconds locker will be in PREVENTING_LOCK before returning to UNLOCK
TIMEOUT_COMMAND = 20  # max time waiting for a command execution
TIMEOUT_REMOTE_COMMAND = 2*60*60  # max time waiting for a command execution
TIMEOUT_LOCK_REQUEST = 60  # timeout on lock/unlock/prevent_lock HTTP request

CHUNK_SIZE = 2  # in MB
MAX_SENDERS = 4

MIN_SERVERS_QUORUM = 5  # minimum servers to run quorum algorithm
INITIAL_DATEMARK = dt.datetime(2019, 4, 1, tzinfo=dt.timezone.utc)

DATETIME_FORMAT = "%m/%d/%Y, %H:%M:%S.%f %z"
DATEMARK_FORMAT = "%Y%m%d.%H%M%S.%f%z"

SOFTWARE_REPO = 'software'
DIMENSIGON_DIR = os.path.join(SOFTWARE_REPO, 'dimensigon')
LOG_FOLDER = 'logs'
LOG_SENDER_REPO = 'logfed'
OFFSET_DIR = 'offset'
