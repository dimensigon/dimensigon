import socket
import ssl as mod_ssl
import time
from contextlib import closing

from dimensigon.utils import asyncio


def is_open(host: str, port: int, timeout: float = 1.0):
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.settimeout(timeout)
        if sock.connect_ex((host, port)) == 0:
            return True
        else:
            return False


def is_ssl_open(host: str, port: int, timeout: float = 1.0):
    context = mod_ssl.SSLContext()
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            with context.wrap_socket(sock, server_hostname=host) as ssock:
                return True
    except (ConnectionRefusedError, TimeoutError, OSError):
        return False
    except socket.timeout:
        return False


def is_open2(host: str, port: int, timeout: float = 1.0):
    context = mod_ssl.SSLContext()
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            with context.wrap_socket(sock, server_hostname=host) as ssock:
                return True
    except (ConnectionRefusedError, TimeoutError, OSError):
        return False
    except socket.timeout:
        return True


def check_host(host: str, port: int, retry=3, delay=2, timeout=1.0):
    ipup = False
    for i in range(retry):
        if is_ssl_open(host, port, timeout):
            ipup = True
            break
        # elif is_open(host, port, timeout):
        #     ipup = True
        #     break
        time.sleep(delay)
    return ipup


async def async_check_host(host: str, port: int, retry=3, delay=2, timeout=1.0):
    ipup = False
    for i in range(retry):
        if await async_is_open2(host, port, timeout):
            ipup = True
            break
        # elif is_open(host, port, timeout):
        #     ipup = True
        #     break
        await asyncio.sleep(delay)
    return ipup

async def async_is_open2(host: str, port: int, timeout: float = 1.0, ssl=True):
    writer = None
    kwargs = {}
    if ssl:
        kwargs['ssl'] = mod_ssl.SSLContext()
    conn = asyncio.open_connection(host, port, **kwargs)
    try:
        reader, writer = await asyncio.wait_for(conn, timeout)
    except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
        return False
    finally:
        if writer:
            writer.close()
    return True