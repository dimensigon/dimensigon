# Futures


# Generic/Built-in
import argparse
import functools
import logging
import os
import platform
import re
import shutil
import signal
import subprocess
import sys
import time
from collections import ChainMap
from datetime import datetime
from enum import Enum

import psutil
import requests
from dotenv import load_dotenv

import dm.defaults as defaults

__author__ = "Joan Prat "
__copyright__ = "Copyright 2019, The Dimensigon project"
__credits__ = ["Joan Prat", "Daniel Moya"]
__license__ = ""
__version__ = "0.0.1"
__maintainer__ = "Joan Prat"
__email__ = "joan.prat@dimensigon.com"
__status__ = "Dev"

# Script variables
PYPI_URL = 'https://pypi.org/pypi/{PACKAGE}/json'

HOME = os.path.dirname(os.path.abspath(__file__))
DM_HOME = os.path.join(HOME, 'dm')
SOFTWARE = os.path.join(HOME, 'software')
TMP = os.environ.get('TMP')
BACKUP_FILENAME = "dm_" + datetime.now().strftime("%Y%m%d%H%M%S") + ".bkp"
EXCLUDE_PATTERN = r"(\.pyc|\.ini)$"  # files to be excluded from backup
HEALTHCHECK_URI = '/healthcheck'  # health check URI
SOFTWARE_URI = '/software'
FAILED_VERSIONS = '.failed_versions'
MAX_TIME_WAITING = 300
VERIFY_SSL = False
PACKAGE_NAME = 'dimensigon'

# max time elevator will wait for the process to start and ask for the health check response


exc_dirs = ('__pycache__', '.git', '.idea', 'tests', 'migrations', 'tmp', 'bin')

exc_pattern = re.compile(EXCLUDE_PATTERN)
config_files = ['.env', 'sqlite.db']

FORMAT = '%(asctime)-15s %(filename)s %(levelname)-8s %(message)s'
logging.basicConfig(format=FORMAT, level=logging.INFO)


# FUNCTIONS

#
# def unzip_software(file, dest):
#     with zipfile.ZipFile(file, 'r') as zip_ref:
#         zip_ref.extractall(path=dest)


def find_python_file_executed(file):
    '''
    Check if there is any running process that contains the given name processName.
    '''
    # Iterate over the all the running process
    return [proc for proc in psutil.process_iter() if
            proc.name().startswith('python') and len(proc.cmdline()) > 1 and os.path.basename(
                proc.cmdline()[1]) == file]

    # try:
    #     # Check if process name contains the given name string.
    #     if proc.name().startswith('python') and len(proc.cmdline()) > 1 and os.path.basename(
    #             proc.cmdline()[1]).startswith(file):
    #         return proc
    # except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
    #     pass


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


def get_healtcheck(url, token=None, tries=1, delay=3, backoff=1):
    mtries, mdelay = tries, delay
    hc = {}
    while mtries > 0:
        try:
            r = requests.get(url + "/healthcheck", headers={"Authentication": f"Bearer {token}"}, timeout=2,
                             verify=VERIFY_SSL)
            if r.status_code == 401:
                r = requests.get(url + "/healthcheck", verify=VERIFY_SSL, timeout=2)
            r.raise_for_status()
            hc = r.json()
            break
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


def check_services(health_check):
    status = None
    for service in health_check.get('services', []):
        if service.get('status') != 'ALIVE':
            status = False
            break
        else:
            status = True
    return status


def check_daemon():
    cp = subprocess.run(['python', 'dimensigon.py', 'status'], env=os.environ)
    return cp.returncode


def get_func_find_proc():
    if platform.system() == 'Linux':
        func = functools.partial(find_python_file_executed, 'dimensigon.py')
    elif platform.system() == 'Windows':
        func = functools.partial(find_python_file_executed, 'flask.exe')
    return func


#
#
# def collect_initial_config():
#     if platform.system() == 'Windows':
#         func = get_func_find_proc()
#         proc_list = func()
#         for p in proc_list:
#             args = p.cmdline()
#             host_op = '-h' if '-h' in args else '--host' if '--host' in args else None
#             if host_op:
#                 ip = args[args.index(host_op) + 1]
#             else:
#                 ip = '127.0.0.1'
#             port_op = '-p' if '-p' in args else '--port' if '--port' in args else None
#             if port_op:
#                 port = args[args.index(port_op) + 1]
#             else:
#                 if 'FLASK_RUN_PORT' in p.environ():
#                     port = p.environ()['FLASK_RUN_PORT']
#                 else:
#                     port = 5000
#             protocol = 'https' if '--cert' in args else 'http'
#
#             config = {'protocol': protocol, 'ip': ip, 'port': port, 'venv': config.get('venv', None)}
#
#     else:
#         config = load_config_wsgi()
#     with open('config.yaml') as fd:
#         yaml_config = yaml.load(fd, Loader=yaml.FullLoader)
#     config = ChainMap(yaml_config[0], config)
#
#     config['elevator'].update(localhost=f"{config['protocol']}://{config['ip']}:{config['port']}")
#
#     return config

def start_daemon():
    cp = subprocess.run(['python', 'dimensigon.py', 'start'], capture_output=True, env=os.environ, timeout=10)
    return cp.returncode


def start_and_check():
    # start new version & check health
    try:
        rc = start_daemon()
    except Exception as e:
        logging.exception("Unable to start daemon.")
        return False
    else:
        logging.debug("Daemon started")

    rc = check_daemon()
    if rc == 10:
        d = 5
        tries = MAX_TIME_WAITING // d
        hc = get_healtcheck(config['dm_url'], tries=tries, delay=d)
        if hc:
            version_running = hc.get('version', False)

            sc = check_services(hc)
            if sc is True:
                logging.info(f"New version {version_running} up & running with all services alive")
            else:
                logging.info(f"New version {version_running} up & running with services not alive")

    return True


def stop_daemon():
    # cp = subprocess.run(['python', 'dimensigon.py', 'stop'], capture_output=True, env=os.environ, timeout=10)
    if os.path.exists('gunicorn.pid'):
        with open('gunicorn.pid') as fd:
            pid = int(fd.read())
        os.kill(signal.SIGTERM, pid)
    procs = [1]
    now = time.time()
    while procs and time.time() - now < 30:
        time.sleep(0.2)
        procs = [proc for proc in psutil.process_iter() if
                 proc.name() == 'gunicorn' and len(proc.cmdline()) > 1 and 'dimensigon:app' in proc.cmdline()]
    if len(procs) > 0:
        for proc in procs:
            os.kill(signal.SIGKILL, proc.pid)
    return 0


def kill_daemons():
    func = get_func_find_proc()
    proc_list = func()
    if proc_list:
        for proc in proc_list:
            try:
                proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        time.sleep(1)
        proc_list = func()
        if proc_list:
            for proc in proc_list:
                try:
                    proc.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass
            time.sleep(2)
            proc_list = func()
    return False if proc_list else True


# def install(package, version=None, capture_output=True):
#     if version:
#         spec_pkg = [f"{package}=={version}"]
#     else:
#         if isinstance(package, (list, tuple)):
#             spec_pkg = list(package)
#         else:
#             spec_pkg = [package]
#     cmd = [sys.executable, "-m", "pip", "install", "--upgrade"]
#     cmd.extend(spec_pkg)
#     return subprocess.run(cmd, capture_output=capture_output, timeout=300)
#
#
# def pull_software(git_repo=None):
#     try:
#         repo = git.Repo()
#     except git.exc.InvalidGitRepositoryError:
#         repo = None
#     if repo is None:
#         # first time. Clone from remote
#         repo = git.Repo.clone_from(git_repo, HOME)
#     pull_info = repo.remote('origin').pull('master')[0]


# def clone_repo(source: str, dest: str, branch: str = 'master', ssl: bool = False) -> git.Repo:
#     return git.Repo.clone_from(source, dest,
#                                branch=branch, config=f'http.sslVerify={str(ssl).lower()}',
#                                )

# def get_software_from(url, ver):
#     data = {'packages': ['dm>' + '.'.join([f'{v}' for v in ver])]}
#
#     response = requests.get(url, data)
#     if response.status_code == 200:
#         cd = response.headers.get('Content-Disposition')
#         match = re.match('attachment; filename="(?P<filename>.+)"', cd)
#         if match:
#             name = match.groupdict().get('filename')
#         else:
#             name = data.get('packages')
#         with open(os.path.join(config['SOFTWARE'], name), "wb") as handle:
#             for data in response.iter_content(chunk_size=1024 * 1024):
#                 handle.write(data)
#         return os.path.join(config['SOFTWARE'], name)
#     else:
#         return None

#
# def get_software_data(config):
#     from pkg_resources import parse_version
#     resp = requests.get(f"{config['elevator']['localhost']}{config['SOFTWARE_URI']}?filter[name]=Dimensigon",
#                         headers={f"Authorization: Bearer {config['elevator']['token']}"}, verify=VERIFY_SSL)
#     soft = (None, None)
#     if resp.status_code == 200:
#         data = resp.json()
#         soft = max(data, key=lambda x: parse_version(['version']))
#         if resp.status_code == 200:
#             return soft, config['elevator']['localhost']
#     else:
#         # try with neighbours
#         for neighbour in config['elevator']['neighbours']:
#             resp = requests.get(f"{neighbour}{config['SOFTWARE_URI']}?filter[name]=Dimensigon",
#                                 headers={f"Authorization: Bearer {config['elevator']['token']}"}, verify=VERIFY_SSL)
#             if resp == 200:
#                 data = resp.json()
#                 soft = max(data, key=lambda x: parse_version(['version']))
#                 return soft, neighbour
#     return soft


def get_version_from_file():
    current_version = None
    with open('dm/__init__.py', 'r') as fd:
        for line in fd.readlines():
            if line.startswith('__version__'):
                current_version = line.split('=')[1].strip().strip('"')
                break
    return current_version


def get_current_version(url, token=None):
    hc = get_healtcheck(url, token)
    current_version = hc.get('version', None)
    if current_version is None:
        # try to get version from file
        current_version = get_version_from_file()
    return current_version


# def backup_data(origin, dest, compress_type=zipfile.ZIP_DEFLATED):
#     zf = zipfile.ZipFile(dest, "w", compress_type)
#     for root, dirs, files in os.walk(origin, topdown=True):
#         dirs[:] = [d for d in dirs if d not in exc_dirs]
#         for file in files:
#             if not exc_pattern.search(file):
#                 zf.write(os.path.join(root, file))
#     zf.close()

class ReturnCodes(Enum):
    NO_NEW_VERSION = 2
    ERROR_INSTALLING_PACKAGE = 3
    ERROR_IMPORTING_PACKAGE = 4
    ERROR_STARTING_OLD_VERSION = 5


###################################
#             MAIN                #
###################################
def main(config):
    # backup data

    logging.info(f"Backing up data")
    backup_filename = shutil.make_archive(os.path.join(TMP, BACKUP_FILENAME), 'gztar', HOME)

    old_version = get_current_version(config.get('dm_url'), config.get('token'))

    # deploy new version
    dest_folder = os.path.join(os.path.dirname(HOME), 'dimensigon_new')
    os.mkdir(dest_folder)
    logging.info(f"Unzipping file {config['file']}")
    shutil.unpack_archive(config['file'], dest_folder)

    # copy config files and DB from old version to new version
    logging.info("Importing configuration and database from current_version")
    for file in config_files:
        shutil.copy2(file, dest_folder)

    # stop old version
    rc = check_daemon()
    if 9 < rc < 20:
        logging.info("Stopping old version")
        stopped = stop_daemon()

    os.chdir(dest_folder)
    new_version = get_version_from_file()

    # TODO: execute DB migrations

    # if new version not running
    if not start_and_check():
        logging.info(f"New version not running. Reverting changes to version '{old_version}'")
        os.chdir(config['HOME'])

        # save failed version
        with open(FAILED_VERSIONS, 'a') as fd:
            fd.write(f'{new_version}\n')

        # kill daemon if running
        stop_daemon()

        # restore backup

        unzip_software(backup_filename, DM_HOME)

        # start old version
        logging.info("Starting old version")
        if not start_and_check():
            logging.error(f"Unable to start old version {old_version}")
            stop_daemon()
            return ReturnCodes.ERROR_STARTING_OLD_VERSION

            ##########################################
            # try to get new version from neighbours #
            ##########################################
            # file = None
            # program_healthy = False
            # while not file or not program_healthy:
            #     for name_or_ip, port in config['elevator']['neighbours']:
            #         file = get_software_from(f"{PROTOCOL}://{name_or_ip}:{port}{SOFTWARE_URI}", new_version)
            #
            #     if file is None:
            #         # TODO try to get new version from internet #
            #         file = get_software_from(MAIN_REPOSITORY, new_version)
            #
            #     if file is None:
            #         # TODO make a SOS call #
            #         ...
            #     time.sleep(TRY_GET_NEW_VERSION)
            #
            #     if file:
            #         # remove old files
            #         for dirname, subdirs, files in os.walk(DM_HOME):
            #             if not os.path.basename(dirname) in exc_dirs:
            #                 for filename in files:
            #                     if inc_pattern.search(filename) and not exc_pattern.search(filename):
            #                         os.remove(os.path.join(dirname, filename))
            #
            #         with zipfile.ZipFile(file, 'r') as zip_ref:
            #             zip_ref.extractall(path=DM_HOME)
            #
            #         # TODO get new version from file
            #         program_healthy = start_daemon_check_health()


if __name__ == '__main__':

    dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(dotenv_path):
        load_dotenv(dotenv_path)

    parser = argparse.ArgumentParser(description='Process some integers.')
    # parser.add_argument('--token', '-t', required=True,
    #                     help='token used for communication with dimensigon')
    parser.add_argument('--deployable', '-d', required=True,
                        help='new file to be installed')
    parser.add_argument('--verify-ssl', action='store_true',
                        help='new file to be installed')

    args = parser.parse_args()
    VERIFY_SSL = args.verify_ssl
    command_line_args = {k: v for k, v in vars(args).items() if v is not None}

    combined = ChainMap(command_line_args, os.environ)
    local_config = {'dm_url': f"http://127.0.0.1:{defaults.LOOPBACK_PORT}/"}

    local_config.update(git_repo=os.environ.get('GIT_REPO'))
    config = ChainMap(local_config, command_line_args)

    sys.exit(main(config))
