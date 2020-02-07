import argparse
import atexit
import logging
import multiprocessing
import os
import platform
import signal
import sys
import time

import psutil
from dotenv import load_dotenv

basedir = os.path.dirname(os.path.abspath(__file__))
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')

if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)

PLATFORM = platform.system()
PIDFILE = 'dimensigon.pid'

COV = None
if os.environ.get('FLASK_COVERAGE'):
    import coverage

    COV = coverage.coverage(branch=True, include='app/*')
    COV.start()

import click
import requests
import rsa
from flask import url_for, Flask
from flask.cli import with_appcontext
from flask_migrate import Migrate
from flask_migrate.cli import upgrade, init, migrate

from dm.domain.entities import *
from dm.domain.entities import Dimension
from dm.domain.entities.orchestration import Step
from dm.network.gateway import pack_msg, unpack_msg
from dm.web import create_app, db
from dm import defaults

app: Flask = create_app(os.getenv('FLASK_CONFIG') or 'default')
migrate = Migrate(app, db)

# gunicorn_logger = logging.getLogger('gunicorn.error')
# app.logger.handlers = gunicorn_logger.handlers
# app.logger.setLevel(gunicorn_logger.level)


#
# @click.group(cls=FlaskGroup, create_app=create_app)
# def cli():
#     """Management script for the Wiki application."""


@app.shell_context_processor
def make_shell_context():
    return dict(db=db, app=app, ActionTemplate=ActionTemplate, Step=Step, Orchestration=Orchestration, Catalog=Catalog,
                Dimension=Dimension, Execution=Execution, Log=Log, Route=Route, Server=Server, Service=Service,
                Software=Software, SoftwareFamily=SoftwareFamily, SoftwareServerAssociation=SoftwareServerAssociation,
                Transfer=Transfer)


@app.cli.command()
@click.option('--coverage/--no-coverage', default=False,
              help='Run tests under code coverage.')
@click.argument('test_names', nargs=-1)
def test(coverage, test_names):
    """Run the unit tests."""
    if coverage and not os.environ.get('FLASK_COVERAGE'):
        import subprocess
        os.environ['FLASK_COVERAGE'] = '1'
        sys.exit(subprocess.call(sys.argv))

    import unittest
    if test_names:
        tests = unittest.TestLoader().loadTestsFromNames(test_names)
    else:
        tests = unittest.TestLoader().discover('tests')
    unittest.TextTestRunner(verbosity=2).run(tests)
    if COV:
        COV.stop()
        COV.save()
        print('Coverage Summary:')
        COV.report()
        basedir = os.path.abspath(os.path.dirname(__file__))
        covdir = os.path.join(basedir, 'tmp/coverage')
        COV.html_report(directory=covdir)
        print('HTML version: file://%s/index.html' % covdir)
        COV.erase()


@app.cli.command()
@click.option('--length', default=25,
              help='Number of functions to include in the profiler report.')
@click.option('--profile-dir', default=None,
              help='Directory where profiler data files are saved.')
def profile(length, profile_dir):
    """Start the application under the code profiler."""
    from werkzeug.contrib.profiler import ProfilerMiddleware
    app.wsgi_app = ProfilerMiddleware(app.wsgi_app, restrictions=[length],
                                      profile_dir=profile_dir)
    app.run()


@app.cli.group()
def dm():
    """Perform dimensigon actions."""
    pass


@dm.command(help="""Joins to the dimension. Two arguments must be given: server and token.

server: Reference Server which will allow to join the dimension. You must specify server name or IP and port separated by colon. Ex: 10.10.10.10:80

token: Authentication Token used for authentication to the reference server""")
@click.argument('server', nargs=1)
@click.argument('token', nargs=1)
# @click.argument('local_server', nargs=1)
# @click.option('--home', default='.', help='Folder to unpack the software')
# @click.option('--url', default='https://{server}/software/dimensigon/latest/dimensigon.tar.gz',
#               help='Specific url to download the software')
def join(server, token):
    # click.echo('Beginning software download')
    # url = url.replace('{server}', server) if '{server}' in url else url
    # # Streaming, so we can iterate over the response.
    # r = requests.get(url, stream=True)
    # # Total size in bytes.
    # total_size = int(r.headers.get('content-length', 0))
    # block_size = 1024  # 1 Kibibyte
    # t = tqdm.tqdm(total=total_size, unit='B', unit_scale=True)
    # with open(os.path.join(tempfile.gettempdir(), 'dimensigon.tar.gz'), 'wb') as f:
    #     for data in r.iter_content(block_size):
    #         t.update(len(data))
    #         f.write(data)
    # t.close()
    # if total_size != 0 and t.n != total_size:
    #     click.echo("Error while trying to download the software")
    #     sys.exit(1)
    # # unpack software
    with open('dimension.pem', mode='rb') as publicfile:
        keydata = publicfile.read()
    d_pub_key = rsa.PublicKey.load_pkcs1(keydata)
    # Generate Public and Private Temporal Keys
    priv, pub = rsa.newkeys(2048, poolsize=8)
    msg = {'pub': pub.save_pkcs1().encode('ascii'), 'access_token': token}
    data = pack_msg(pub_key=d_pub_key, data=msg)
    click.echo("Joining to dimension")
    resp = requests.post(f"https://{server}" + url_for('api_1_0.join'), json=data)
    resp.raise_for_status()
    resp_data = unpack_msg(resp.json, pub_key=d_pub_key, priv_key=priv)
    if 'dim' in resp_data:
        dim = Dimension(**resp_data.get('dim'))
        db.session.add(dim)

        db.session.commit()

    print('Joined to the dimension')


@dm.command(help="""Create a dimension from scratch. Must provide a name for the dimension""")
@click.argument('name', nargs=1)
@with_appcontext
def new(name):
    priv, pub = rsa.newkeys(4096, poolsize=8)
    dim = Dimension(**{'name': name, 'pub': pub, 'priv': priv})
    db.session.add(dim)
    db.session.commit()
    click.echo('The UUID for the dimension is %s' % dim.id)


@app.cli.command(help='Fill initial database data.')
@with_appcontext
def init_db():
    # migrate database to latest revision
    # alembic_dir = os.path.join(basedir, 'migrations')
    #
    # if not os.path.exists(alembic_dir):
    #     init()
    #
    # upgrade()

    # Generate Server
    Server.set_initial()


if PLATFORM == 'Linux':
    import gunicorn.app.base


    class StandaloneApplication(gunicorn.app.base.BaseApplication):

        def __init__(self, app, options=None):
            self.options = options or {}
            self.application = app
            super().__init__()

        def load_config(self):
            config = {key: value for key, value in self.options.items()
                      if key in self.cfg.settings and value is not None}
            for key, value in config.items():
                self.cfg.set(key.lower(), value)

        def load(self):
            return self.application


    class Daemon:
        """
        A generic daemon class.

        Usage: subclass the Daemon class and override the run() method
        """

        def __init__(self, pidfile, stdin='/dev/null', stdout='/dev/null', stderr='/dev/null', daemon=True):
            self.stdin = stdin
            self.stdout = stdout
            self.stderr = stderr
            self.pidfile = pidfile
            self.daemon = daemon

        def daemonize(self):
            """
            do the UNIX double-fork magic, see Stevens' "Advanced
            Programming in the UNIX Environment" for details (ISBN 0201563177)
            http://www.erlenstar.demon.co.uk/unix/faq_2.html#SEC16
            """
            try:
                pid = os.fork()
                if pid > 0:
                    # exit first parent
                    return pid
            except OSError as e:
                sys.stderr.write("fork #1 failed: %d (%s)\n" % (e.errno, e.strerror))
                sys.exit(1)

            # decouple from parent environment
            os.chdir("/")
            os.setsid()
            os.umask(0)

            # do second fork
            try:
                pid = os.fork()
                if pid > 0:
                    # exit from second parent
                    sys.exit(0)
            except OSError as e:
                sys.stderr.write("fork #2 failed: %d (%s)\n" % (e.errno, e.strerror))
                sys.exit(1)

            os.chdir(basedir)
            # redirect standard file descriptors
            sys.stdout.flush()
            sys.stderr.flush()
            si = open(self.stdin, 'r')
            so = open(self.stdout, 'a+')
            se = open(self.stderr, 'a+', 1)
            os.dup2(si.fileno(), sys.stdin.fileno())
            os.dup2(so.fileno(), sys.stdout.fileno())
            os.dup2(se.fileno(), sys.stderr.fileno())

            self.set_pid()
            return 0

        def delpid(self):
            try:
                os.remove(self.pidfile)
            except FileNotFoundError:
                pass

        def set_pid(self):
            # write pidfile
            atexit.register(self.delpid)
            pid = str(os.getpid())
            with open(self.pidfile, 'w') as pidfile:
                pidfile.write(f"{pid}\n")

        def get_pid(self):
            try:
                with open(self.pidfile, 'r') as pf:
                    pid = int(pf.read().strip())
            except IOError:
                pid = None
            return pid

        def start(self, daemon=False):
            """
            Start the daemon
            """
            # Check for a pidfile to see if the daemon already runs
            rc = self.status(silently=True)
            if rc == 10:
                sys.stdout.write(f"Process already running with pid {self.get_pid()}")
                sys.exit(10)
            elif rc == 11:
                sys.stdout.write(
                    f"Process already running with pid {self.get_pid()} but not responding. Kill it before starting again\n")
                sys.exit(11)

            # Start the daemon
            if self.daemon:
                pid = self.daemonize()
            else:
                self.set_pid()
                pid = 0
            if pid > 0:
                initial = time.time()
                while True:
                    rc = self.status(silently=True)
                    if rc != 10:
                        time.sleep(0.1)
                    else:
                        break
                    if time.time() - initial > 30:
                        break
                if rc == 10:
                    return 0
                else:
                    return 1
            else:
                self.run()

        def stop(self, timeout=30):
            """
            Stop the daemon
            """
            # Get the pid from the pidfile

            pid = self.get_pid()

            if not pid:
                message = "pidfile %s does not exist. Daemon not running?\n"
                sys.stderr.write(message % self.pidfile)
                return 1

            # Try killing the daemon process
            try:
                start = time.time()
                while int(time.time() - start) < timeout:
                    os.kill(pid, signal.SIGTERM)
                    time.sleep(0.1)
                if int(time.time() - start) >= timeout:
                    os.kill(pid, signal.SIGKILL)
            except OSError as err:
                err = str(err)
                if err.find("No such process") > 0:
                    if os.path.exists(self.pidfile):
                        os.remove(self.pidfile)
                else:
                    print(str(err))
                    sys.exit(1)
            sys.stdout.write('Process stopped\n')
            return 0

        def restart(self):
            """
            Restart the daemon
            """
            rc = self.stop()
            if rc == 1:
                sys.stdout.write("Process already stopped.\n")
            return self.start()

        def status(self, silently=False):
            # Check for a pidfile to see if the daemon already runs
            pid = self.get_pid()

            if pid:
                if psutil.pid_exists(pid):
                    # process running. Check if responding to a request
                    return 1
                else:
                    sys.stdout.write(f"Process death but pidfile exists\n") if not silently else None
                    return 2
            else:
                sys.stdout.write(f"Process stopped\n") if not silently else None
                return 0

        def run(self):
            """
            You should override this method when you subclass Daemon. It will be called after the process has been
            daemonized by start() or restart().
            """
            raise NotImplemented

list_of_choices = ['start', 'stop', 'restart', 'status']


def main():
    # set initial variables
    parser = argparse.ArgumentParser(description='Starts dimensigon process.')
    parser.add_argument('--attached', '-a', action='store_true',
                        help='run server attached to current terminal')
    parser.add_argument('action', choices=list_of_choices, help='Action to perform.')

    args = parser.parse_args()

    port = os.environ.get('FLASK_RUN_PORT') or app.config.get('FLASK_RUN_PORT') or defaults.LOOPBACK_PORT
    host = os.environ.get('SERVER_IP') or app.config.get('SERVER_HOST') or '0.0.0.0'
    keyfile = os.environ.get('KEY_FILE')
    certfile = os.environ.get('CERT_FILE')
    ca_certs = os.environ.get('CA_CERTS')
    listen = [f'127.0.0.1:{defaults.LOOPBACK_PORT}', f'{host}:{port}']
    workers = os.environ.get('WORKERS') or multiprocessing.cpu_count() * 2
    threads = os.environ.get('THREADS') or multiprocessing.cpu_count() * 2
    detached = False if os.environ.get('DETACHED').lower() == 'false' else not args.attached
    stdout = os.environ.get('STDOUT') or 'dimensigon.out'
    stderr = os.environ.get('STDERR') or 'dimensigon.err'

    if PLATFORM == 'Windows':
        raise NotImplementedError('use flask instead')
        # from waitress import serve
        #
        # options = {'host': host,
        #            'port': port,
        #            'threads': threads}
        # serve(app, **options)
    elif PLATFORM == 'Linux':

        options = {
            'bind': listen,
            'threads': threads,
            'workers': workers,
            'keyfile': keyfile,
            'certfile': certfile,
            'ca_certs': ca_certs
        }

        class Dimensigon(Daemon):
            def run(self):
                StandaloneApplication(app, options).run()

            def status(self, silently=False):
                rc = super().status(silently)
                if rc == 1:
                    pid = self.get_pid()
                    try:
                        if certfile:
                            r = requests.get(f"https://127.0.0.1:{defaults.LOOPBACK_PORT}/healthcheck", timeout=10,
                                             verify=False)
                        else:
                            r = requests.get(f"http://127.0.0.1:{defaults.LOOPBACK_PORT}/healthcheck", timeout=10,
                                             verify=False)
                    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                        sys.stdout.write(
                            f"Process running with pid {pid} but not responding to requests\n") if not silently else None
                        return 11
                    else:
                        sys.stdout.write(f"Process running with pid {pid}\n") if not silently else None
                        return 10
                return rc

        daemon = Dimensigon(pidfile=PIDFILE, stdout=stdout, stderr=stderr, daemon=detached)

        rc = 1
        if args.action == 'start':
            rc = daemon.start()
            if rc == 0:
                sys.stdout.write("Process started.\n")
            else:
                sys.stdout.write(f"Unable to start process. Check {stdout}\n")
        elif args.action == 'stop':
            rc = daemon.stop()
        elif args.action == 'restart':
            rc = daemon.restart()
        elif args.action == 'status':
            rc = daemon.status()

        sys.exit(rc)


if __name__ == "__main__":
    main()
