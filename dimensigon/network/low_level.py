import time

import aiohttp
import requests

from dimensigon.utils import asyncio


# def is_open(host: str, port: int, timeout: float = 1.0):
#     with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
#         sock.settimeout(timeout)
#         if sock.connect_ex((host, port)) == 0:
#             return True
#         else:
#             return False
#
#
# def is_ssl_open(host: str, port: int, timeout: float = 1.0):
#     context = mod_ssl.SSLContext()
#     try:
#         with socket.create_connection((host, port), timeout=timeout) as sock:
#             with context.wrap_socket(sock, server_hostname=host) as ssock:
#                 return True
#     except (ConnectionRefusedError, TimeoutError, OSError):
#         return False
#     except socket.timeout:
#         return False


def is_open2(host: str, port: int, timeout: float = 5.0, ssl=True):
    url = f"{'https' if ssl else 'http'}://{host}:{port}/"
    try:
        resp = requests.get(url, verify=False, timeout=timeout)
    except (requests.ConnectionError, requests.Timeout):
        return False
    else:
        return resp.ok


def check_host(host: str, port: int, retry=3, delay=2, timeout=5.0):
    ipup = False
    for i in range(retry):
        if is_open2(host, port, timeout):
            ipup = True
            break
        # elif is_open(host, port, timeout):
        #     ipup = True
        #     break
        time.sleep(delay)
    return ipup


###########
#  ASYNC  #
###########


# async def async_is_open(host: str, port: int, timeout: float = 1.0, ssl=True):
#     writer = None
#     kwargs = {}
#     if ssl:
#         kwargs['ssl'] = mod_ssl.SSLContext()
#     conn = asyncio.open_connection(host, port, **kwargs)
#     try:
#         reader, writer = await asyncio.wait_for(conn, timeout)
#     except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
#         return False
#     finally:
#         if writer:
#             writer.close()
#     return True


async def async_is_open2(host: str, port: int, timeout: float = 5.0, ssl=True):
    url = f"{'https' if ssl else 'http'}://{host}:{port}/"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout), verify_ssl=False) as response:
                if 200 <= response.status < 300:
                    return True
                else:
                    return False
    except (aiohttp.ClientResponseError,
            aiohttp.ClientOSError,
            aiohttp.ServerDisconnectedError,
            aiohttp.ServerTimeoutError,
            asyncio.TimeoutError) as e:
        return False


async def async_check_host(host: str, port: int, retry=3, delay=2, timeout=5.0):
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
