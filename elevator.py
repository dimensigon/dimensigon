# Futures


# Generic/Built-in


# Owned
import os
# Other Libs
import platform
import re
import time
import zipfile
from datetime import datetime

import psutil
import requests

__author__ = "Joan Prat "
__copyright__ = "Copyright 2019, The Dimensigon project"
__credits__ = ["Joan Prat", "Daniel Moya"]
__license__ = ""
__version__ = "0.0.1"
__maintainer__ = "Joan Prat"
__email__ = "joan.prat@dimensigon.com"
__status__ = "Dev"

# Script variables
HOME = os.path.dirname(os.path.abspath(__file__))
DM_HOME = os.path.join(HOME, 'dm')
SOFTWARE = os.path.join(HOME, 'software')
TMP = os.environ.get('TMP')
BACKUP_FILENAME = "dm_" + datetime.now().strftime("%Y%m%d%H%M%S") + ".bkp"
INCLUDE_PATTERN = ".*"
EXCLUDE_PATTERN = r"(\.pyc$|\.ini$)"
PROTOCOL = "HTTP"
DM_PORT = 80
DM_URI = '/healtcheck'  # healt check URI
SOFTWARE_URI = '/software'
MAIN_REPOSITORY = "https://www.dimensigon.com/api/software"  # internet URL to obtain the software
MAX_TIME_WAITING = 180  # max time elevator will wait for the process to start and ask for the health check response
TRY_GET_NEW_VERSION = 500  # tries to get the new version from neighbours or internet every TRY_GET_NEW_VERSION seconds
if platform.system() == "Windows":
    DAEMON_NAME = 'dm.exe'
else:
    DAEMON_NAME = 'dm'
NEIGHBOURS = [('server1', 80), ('server2', 80)]

inc_pattern = re.compile(INCLUDE_PATTERN)
exc_pattern = re.compile(EXCLUDE_PATTERN)

exc_dirs = ('__pycache__',)


# FUNCTIONS
def unzip_software(file, dest):
    with zipfile.ZipFile(file, 'r') as zip_ref:
        zip_ref.extractall(path=dest)


def find_process_by_name(process_name):
    '''
    Check if there is any running process that contains the given name processName.
    '''
    # Iterate over the all the running process
    for proc in psutil.process_iter():
        try:
            # Check if process name contains the given name string.
            if process_name.lower() in proc.name().lower():
                return proc
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return None


def get_healtcheck(tries=1, delay=3, backoff=1):
    mtries, mdelay = tries, delay
    hc = {}
    while mtries > 0:
        try:
            url = f'{PROTOCOL}://127.0.0.1:{DM_PORT}{DM_URI}'
            r = requests.get(url)
            hc = r.json()
        except Exception as e:
            msg = "%s, Retrying in %d seconds..." % (str(e), mdelay)
            print(msg)
            time.sleep(mdelay)
            mtries -= 1
            mdelay *= backoff
    if mtries == 0:
        return {}
    else:
        return hc


def get_version(health_check):
    return tuple(health_check.get('version', '..').split('.'))


def check_services(health_check):
    status = False
    for service in health_check.get('services'):
        if service.get('status') != 'ALIVE':
            status = False
            break
        else:
            status = True
    return status


def check_process():
    # check if process is running
    status = False
    iterations = MAX_TIME_WAITING // 5
    while not status or iterations > 0:
        status = True if find_process_by_name(DAEMON_NAME) else False
        time.sleep(5)
        iterations -= 1
    return status


def start_daemon():
    # TODO spawn program via subprocess or fork

    return check_process()


def start_daemon_and_check(version=None):
    daemon_running = start_daemon()
    version_running = False
    sc = False
    hc = False

    if daemon_running:
        d = 5
        tries = MAX_TIME_WAITING // d
        hc = get_healtcheck(tries=tries, delay=d)
        if hc:
            if version is not None:
                version_running = version == get_version(hc)

            sc = check_services(hc)

    return hc and version_running and sc


def stop_daemon():
    proc = find_process_by_name(DAEMON_NAME)
    if proc:
        proc.kill()
        time.sleep(1)
        proc = find_process_by_name(DAEMON_NAME)
        if proc:
            proc.kill()
            time.sleep(1)
            proc = find_process_by_name(DAEMON_NAME)
    return False if proc else True


def get_software_from(url, ver):
    data = {'packages': ['dm>' + '.'.join([f'{v}' for v in ver])]}

    response = requests.get(url, data)
    if response.status_code == 200:
        cd = response.headers.get('Content-Disposition')
        match = re.match('attachment; filename="(?P<filename>.+)"', cd)
        if match:
            name = match.groupdict().get('filename')
        else:
            name = data.get('packages')
        with open(os.path.join(SOFTWARE, name), "wb") as handle:
            for data in response.iter_content(chunk_size=1024 * 1024):
                handle.write(data)
        return os.path.join(SOFTWARE, name)
    else:
        return None


###################################
#             MAIN                #
###################################
def main():
    hc = get_healtcheck(5, 5)
    old_version = tuple(hc.get('version', '').split('.'))

    ##########
    # backup #
    ##########
    zf = zipfile.ZipFile(os.path.join(TMP, BACKUP_FILENAME), "w")
    for dirname, subdirs, files in os.walk(DM_HOME):
        if not os.path.basename(dirname) in exc_dirs:
            zf.write(dirname.replace(DM_HOME, ''))
            for filename in files:
                if inc_pattern.search(filename) and not exc_pattern.search(filename):
                    zf.write(os.path.join(dirname.replace(DM_HOME, ''), filename))
    zf.close()

    ##################
    # try dm upgrade #
    ##################
    # TODO get file to unzip

    hc = get_healtcheck()
    current_version = tuple(hc.get('version', '..').split('.'))

    # TODO get new version from file name
    new_version = (0, 0, 1)

    program_healthy = start_daemon_and_check(new_version)

    ##################
    # restore backup #
    ##################
    if program_healthy is False:
        stop_daemon()

        backup_file = os.path.join(TMP, BACKUP_FILENAME)

        # remove old files
        for dirname, subdirs, files in os.walk(DM_HOME):
            if not os.path.basename(dirname) in exc_dirs:
                for filename in files:
                    if inc_pattern.search(filename) and not exc_pattern.search(filename):
                        os.remove(os.path.join(dirname, filename))

        with zipfile.ZipFile(backup_file, 'r') as zip_ref:
            zip_ref.extractall(path=DM_HOME)

        program_healthy = start_daemon_and_check(version=old_version)

    if not program_healthy:
        stop_daemon()

        ##########################################
        # try to get new version from neighbours #
        ##########################################
        file = None
        while not file or not program_healthy:
            for server, port in NEIGHBOURS:
                file = get_software_from(f"{PROTOCOL}://{server}:{port}{SOFTWARE_URI}", new_version)

            if file is None:
                # TODO try to get new version from internet #
                file = get_software_from(MAIN_REPOSITORY, new_version)

            if file is None:
                # TODO make a SOS call #
                ...
            time.sleep(TRY_GET_NEW_VERSION)

            if file:
                # remove old files
                for dirname, subdirs, files in os.walk(DM_HOME):
                    if not os.path.basename(dirname) in exc_dirs:
                        for filename in files:
                            if inc_pattern.search(filename) and not exc_pattern.search(filename):
                                os.remove(os.path.join(dirname, filename))

                with zipfile.ZipFile(file, 'r') as zip_ref:
                    zip_ref.extractall(path=DM_HOME)

                # TODO get new version from file
                program_healthy = start_daemon_and_check()
