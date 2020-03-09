import itertools
import os
import socket

import netifaces

DATETIME_FORMAT = "%m/%d/%Y, %H:%M:%S"
DATEMARK_FORMAT = "%Y%m%d%H%M%S%f"
HOME = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOSTNAME = socket.getfqdn()

ips = list(filter(lambda x: x != '127.0.0.1', itertools.chain(
    *[[ip['addr'] for ip in netifaces.ifaddresses(iface).get(netifaces.AF_INET, [])] for iface in
      netifaces.interfaces()])))

IP = ips[0]
LOOPBACK_PORT = 20194
MAX_WAITING_TIME = 300  # time in seconds waiting tasks to finish

TIMEOUT_REQUEST = 60
TIMEOUT_PREVENTING_LOCK = 600  # max time in seconds locker will be in PREVENTING_LOCK before returning to UNLOCK
