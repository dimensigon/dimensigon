import os
import socket

DATETIME_FORMAT = "%m/%d/%Y, %H:%M:%S"
HOME = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOSTNAME = socket.getfqdn()
IP = socket.gethostbyname_ex(HOSTNAME)
LOOPBACK_PORT = 20194
MAX_WAITING_TIME = 300 # time in seconds waiting tasks to finish
