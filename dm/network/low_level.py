import socket
import time


def is_open(ip, port, timeout=1):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((ip, int(port)))
        s.shutdown(socket.SHUT_RDWR)
        return True
    except:
        return False
    finally:
        s.close()


def check_host(ip, port, retry=3, delay=2, **kwargs):
    ipup = False
    for i in range(retry):
        if is_open(ip, port, **kwargs):
            ipup = True
            break
        else:
            time.sleep(delay)
    return ipup
