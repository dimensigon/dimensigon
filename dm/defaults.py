import itertools
import os
import socket
from datetime import datetime

import netifaces

DATETIME_FORMAT = "%m/%d/%Y, %H:%M:%S"
DATEMARK_FORMAT = "%Y%m%d.%H%M%S.%f"
HOME = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOSTNAME = socket.gethostname()

ips = list(filter(lambda x: x != '127.0.0.1', itertools.chain(
    *[[ip['addr'] for ip in netifaces.ifaddresses(iface).get(netifaces.AF_INET, [])] for iface in
      netifaces.interfaces()])))

INITIAL_DATEMARK = datetime(2019,4,1)
DEFAULT_PORT = 8000
LOOPBACK_PORT = 20194
MAX_WAITING_TIME = 300  # time in seconds waiting tasks to finish

TIMEOUT_REQUEST = 60
TIMEOUT_PREVENTING_LOCK = 60  # max time in seconds locker will be in PREVENTING_LOCK before returning to UNLOCK
TIMEOUT_ORCHESTRATION = 600  # max time waiting for an orchestration to finish

CHUNK_SIZE = 20971520  # 20 MB
MAX_SENDERS = 4
