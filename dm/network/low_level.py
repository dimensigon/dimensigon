import socket
import ssl
import time
from contextlib import closing


def is_open(host: str, port: int, timeout: float = 1.0):
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.settimeout(timeout)
        if sock.connect_ex((host, port)) == 0:
            return True
        else:
            return False


def is_ssl_open(host: str, port: int, timeout: float = 1.0):
    context = ssl.SSLContext()
    try:
        with socket.create_connection((host, port)) as sock:
            sock.settimeout(timeout)
            with context.wrap_socket(sock, server_hostname=host) as ssock:
                return True
    except (ConnectionRefusedError, TimeoutError):
        return False
    except socket.timeout:
        return False


def is_open2(host: str, port: int, timeout: float = 1.0):
    context = ssl.SSLContext()
    try:
        with socket.create_connection((host, port)) as sock:
            sock.settimeout(timeout)
            with context.wrap_socket(sock, server_hostname=host) as ssock:
                return True
    except (ConnectionRefusedError, TimeoutError):
        return False
    except socket.timeout:
        return True


def check_host(host: str, port: int, retry=3, delay=2, timeout=1.0):
    ipup = False
    for i in range(retry):
        if is_open2(host, port, timeout):
            ipup = True
            break
        time.sleep(delay)
    return ipup
