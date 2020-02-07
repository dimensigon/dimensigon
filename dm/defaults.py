import itertools
import os
import socket

import netifaces

DATETIME_FORMAT = "%m/%d/%Y, %H:%M:%S"
HOME = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOSTNAME = socket.getfqdn()

ips = list(filter(lambda x: x != '127.0.0.1', itertools.chain(
    *[[ip['addr'] for ip in netifaces.ifaddresses(iface)[netifaces.AF_INET]] for iface in netifaces.interfaces()])))

IP = ips[0]
LOOPBACK_PORT = 20194
MAX_WAITING_TIME = 300  # time in seconds waiting tasks to finish
