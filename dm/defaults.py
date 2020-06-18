import itertools
import os
import socket
from datetime import datetime, timezone

import netifaces

DATETIME_FORMAT = "%m/%d/%Y, %H:%M:%S.%f %z"
DATEMARK_FORMAT = "%Y%m%d.%H%M%S.%f%z"
HOME = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOSTNAME = socket.gethostname()

ips = list(filter(lambda x: x != '127.0.0.1', itertools.chain(
    *[[ip['addr'] for ip in netifaces.ifaddresses(iface).get(netifaces.AF_INET, [])] for iface in
      netifaces.interfaces()])))

MIN_SERVERS_QUORUM = 5  # minimum servers to run quorum algorithm
INITIAL_DATEMARK = datetime(2019, 4, 1, tzinfo=timezone.utc)
DEFAULT_PORT = 8000
LOOPBACK_PORT = 20194

MAX_WAITING_TIME = 300  # time in seconds waiting tasks to finish
MAX_TIME_WAITING_SERVERS = 600  # max time waiting for servers to be created

TIMEOUT_REQUEST = 60
TIMEOUT_PREVENTING_LOCK = 60  # max time in seconds locker will be in PREVENTING_LOCK before returning to UNLOCK
TIMEOUT_ORCHESTRATION = 1800  # max time waiting for an orchestration to finish
TIMEOUT_COMMAND = 20  # max time waiting for a command execution

CHUNK_SIZE = 2*1024  # in MB
MAX_SENDERS = 4
