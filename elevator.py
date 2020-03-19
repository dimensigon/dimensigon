# Futures


# Generic/Built-in
import functools
import json
import logging
import os
import platform
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from enum import Enum

import click
import psutil
import requests
from pkg_resources import parse_version

import dm.defaults as defaults
import gunicorn_conf as conf

__author__ = "Joan Prat "
__copyright__ = "Copyright 2019, The Dimensigon project"
__credits__ = ["Joan Prat", "Daniel Moya"]
__license__ = ""
__version__ = "0.0.1"
__maintainer__ = "Joan Prat"
__email__ = "joan.prat@dimensigon.com"
__status__ = "Dev"

import warnings

warnings.filterwarnings("ignore")

# Script variables
HOME = os.path.dirname(os.path.abspath(__file__))
DM_ROOT = os.path.dirname(HOME)
DM_HOME = os.path.join(HOME, 'dm')
SOFTWARE = os.path.join(HOME, 'software')
TMP = tempfile.gettempdir()
BACKUP_FILENAME = "dm_" + datetime.now().strftime("%Y%m%d%H%M%S") + ".bkp"
EXCLUDE_PATTERN = r"(\.pyc|\.ini)$"  # files to be excluded from backup
HEALTHCHECK_URI = '/healthcheck'  # health check URI
SOFTWARE_URI = '/software'
FAILED_VERSIONS = '.failed_versions'
MAX_TIME_WAITING = 5
SSL_VERIFY = False
PACKAGE_NAME = 'dimensigon'

# max time elevator will wait for the process to start and ask for the health check response


exc_dirs = ('__pycache__', '.git', '.idea', 'tests', 'migrations', 'tmp', 'bin')

exc_pattern = re.compile(EXCLUDE_PATTERN)
config_files = ['.env', 'sqlite.db', 'gunicorn_conf.py', 'ssl', 'migrations']
pid_file = os.path.join(HOME, conf.pidfile)

FORMAT = '%(asctime)-15s %(filename)s %(levelname)-8s %(message)s'
logging.basicConfig(format=FORMAT, level=logging.DEBUG)


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


def get_hc(url, token=None, tries=1, delay=3, backoff=1):
    mtries, mdelay = tries, delay
    hc = {}
    while mtries > 0:
        try:
            headers = {"Authentication": f"Bearer {token}"} if token else None
            r = requests.get(url, headers=headers, timeout=2, verify=SSL_VERIFY)
            if r.status_code == 401:
                r = requests.get(url + "/healthcheck", verify=SSL_VERIFY, timeout=2)
            r.raise_for_status()
            hc = r.json()
            break
        except Exception as e:
            msg = "%s, Retrying in %d seconds..." % (str(e), mdelay)
            logging.debug(msg)
            time.sleep(mdelay)
            mtries -= 1
            mdelay *= backoff
    if mtries == 0:
        return {}
    else:
        return hc


def daemon_running():
    if os.path.exists(pid_file):
        with open(pid_file) as fd:
            pid = int(fd.read())
        return len([proc for proc in psutil.process_iter() if proc.pid == pid]) > 0
    else:
        return False


def get_func_find_proc():
    if platform.system() == 'Linux':
        func = functools.partial(find_python_file_executed, 'dimensigon.py')
    elif platform.system() == 'Windows':
        func = functools.partial(find_python_file_executed, 'flask.exe')
    return func


def start_daemon(cwd=None, silently=True):
    cwd = cwd or HOME
    # cp = subprocess.run(['python', 'dimensigon.py', 'start'], capture_output=True, env=os.environ, timeout=10)
    cmd = ['gunicorn',
           '-c', os.path.join(cwd, 'gunicorn_conf.py'),
           '--keyfile', os.path.join(cwd, 'ssl', 'key.pem'),
           '--certfile', os.path.join(cwd, 'ssl', 'cert.pem'),
           '--daemon',
           'dimensigon:app']
    logging.debug('Running ' + ' '.join(cmd))
    cp = subprocess.run(
        cmd,
        cwd=cwd, timeout=10)

    sys.stdout.write(cp.stdout.decode()) if not silently and cp.stdout else None
    if cp.stderr:
        sys.stderr.write(cp.stderr.decode())
    return cp.returncode


def start_and_check(url, cwd=None, tries=MAX_TIME_WAITING // 5):
    # start new version & check health
    start_daemon(cwd, logging.root.level != logging.DEBUG)
    # wait to be able to create pid file
    time.sleep(0.2)
    if daemon_running():
        hc = get_hc(url, tries=tries, delay=5)
        logging.debug(f"Healthcheck from {url}: {json.dumps(hc, indent=4)}")

        if 'version' in hc:
            version_running = hc.get('version', False)

            # sc = check_services(hc)
            sc = True
            if sc is True:
                logging.info(f"New version '{version_running}' up & running with all services alive")
            else:
                logging.info(f"New version '{version_running}' up & running with services not alive")
        else:
            return False
    else:
        return False
    return True


def stop_daemon():
    # cp = subprocess.run(['python', 'dimensigon.py', 'stop'], capture_output=True, env=os.environ, timeout=10)
    def get_procs():
        return [proc for proc in psutil.process_iter() if
                proc.name() == 'gunicorn' and len(proc.cmdline()) > 1 and 'dimensigon:app' in proc.cmdline()]

    if os.path.exists('gunicorn.pid'):
        with open('gunicorn.pid') as fd:
            pid = int(fd.read())
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            logging.warning("pid file exists but no process running. Removing pid file")
            try:
                os.remove('gunicorn.pid')
            except:
                pass
    else:
        for proc in get_procs():
            os.kill(proc.pid, signal.SIGTERM)
    procs = get_procs()
    now = time.time()
    while procs and time.time() - now < 30:
        time.sleep(0.2)
        procs = get_procs()
    if len(procs) > 0:
        for proc in procs:
            os.kill(proc.pid, signal.SIGKILL)
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


def get_version_from_file(root=''):
    current_version = None
    with open(os.path.join(root, 'dm/__init__.py'), 'r') as fd:
        for line in fd.readlines():
            if line.startswith('__version__'):
                current_version = line.split('=')[1].strip().strip('"')
                break
    return current_version


def get_current_version(url, token=None):
    hc = get_hc(url, token)
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


def _upgrade(config):
    # backup data

    # logging.info(f"Backing up data")
    # backup_filename = shutil.make_archive(os.path.join(TMP, BACKUP_FILENAME), 'gztar', HOME)

    old_version = get_current_version(config.get('dm_url') + '/healthcheck', config.get('token'))

    # deploy new version

    logging.info(f"Unzipping file {config['deployable']}")
    new_home = os.path.join(DM_ROOT, 'dimensigon_' + config['version'])
    try:
        shutil.rmtree(new_home)
    except FileNotFoundError:
        pass

    # extract new version
    shutil.unpack_archive(config['deployable'], TMP)
    shutil.copytree(os.path.join(TMP, 'dimensigon'), new_home)
    shutil.rmtree(os.path.join(TMP, 'dimensigon'))
    os.rmdir(os.path.join(TMP, 'dimensigon'))

    # copy config files and DB from old version to new version
    logging.info("Importing configuration and database from current_version")
    for file in [os.path.join(HOME, f) for f in config_files]:
        if os.path.isfile(file):
            shutil.copy2(file, new_home)
        else:
            if os.path.exists(file):
                shutil.copytree(file, os.path.join(new_home, os.path.basename(file)))

    # stop old version
    logging.info("Stopping old version")
    stopped = stop_daemon()

    # change working dir to new home
    os.chdir(new_home)
    logging.debug(f"changed working directory to {os.getcwd()}")

    # TODO: execute DB migrations

    #####################
    # start NEW version #
    #####################
    if not start_and_check(config.get('dm_url'), cwd=new_home):

        logging.info(f"New version not running. Reverting changes to version '{old_version}'")

        # kill daemon if running
        stop_daemon()

        os.chdir(HOME)
        logging.debug(f"changed working directory to {os.getcwd()}")

        # save failed version
        with open(FAILED_VERSIONS, 'a') as fd:
            fd.write(f"{config['version']}\n")

        #####################
        # start old version #
        #####################
        logging.info("Starting old version")
        if not start_and_check(config.get('dm_url')):
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


@click.group()
def cli():
    pass


@cli.command()
@click.argument('deployable')
@click.argument('version')
def upgrade(deployable, version):
    # dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
    # if os.path.exists(dotenv_path):
    #     load_dotenv(dotenv_path)
    #

    if not os.path.exists(os.path.abspath(deployable)):
        click.echo(f"deployable '{deployable}' does not exist")
        sys.exit(1)

    with open(FAILED_VERSIONS, 'r') as fd:
        failed_versions = parse_version(fd.readlines())

    if parse_version(version) in failed_versions:
        click.echo(f"version {version} already tried with error. Waiting next version")
        sys.exit(2)

    sys.exit(_upgrade(
        dict(deployable=deployable, version=version, git_repo=os.environ.get('GIT_REPO'),
             dm_url=f"https://127.0.0.1:{defaults.LOOPBACK_PORT}")))


@cli.command()
def start():
    if not start_and_check(f"https://127.0.0.1:{defaults.LOOPBACK_PORT}/healthcheck"):
        logging.info('Unable to start process. Check log for more info')
        stop_daemon()
        sys.exit(1)
    else:
        sys.exit(0)


@cli.command()
def stop():
    stop_daemon()


if __name__ == '__main__':
    cli()
