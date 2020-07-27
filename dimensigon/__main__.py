import argparse
import datetime
import functools
import os
import platform
import sys
from dataclasses import dataclass

import click
import dotenv
import flask
import requests
import rsa
from flask import Flask
from flask.cli import with_appcontext
from flask_jwt_extended import create_access_token

from dimensigon import defaults
from dimensigon.core import Dimensigon

dotenv.load_dotenv(dotenv.find_dotenv())
basedir = os.path.abspath(os.path.dirname(__file__))

PLATFORM = platform.system()

COV = None
if os.environ.get('FLASK_COVERAGE'):
    import coverage

    COV = coverage.coverage(branch=True, include='app/*')
    COV.start()

from dimensigon.domain.entities import *
from dimensigon.web.network import pack_msg2, unpack_msg2
from dimensigon.web import create_app, db

from dimensigon.use_cases.use_cases import upgrade_catalog
from dimensigon.utils.helpers import generate_symmetric_key, generate_dimension, get_now

app: Flask = create_app(os.getenv('FLASK_CONFIG') or 'default')


@app.shell_context_processor
def make_shell_context():
    return dict(db=db, app=app, ActionTemplate=ActionTemplate, ActionType=ActionType, Step=Step,
                Orchestration=Orchestration, Catalog=Catalog,
                Dimension=Dimension, StepExecution=StepExecution, Log=Log, Route=Route, Server=Server, Service=Service,
                Software=Software, SoftwareServerAssociation=SoftwareServerAssociation, User=User,
                Transfer=Transfer, Locker=Locker, Scope=Scope, State=State, Gate=Gate,
                create_access_token=create_access_token)


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
        tests = unittest.TestLoader().discover('../tests')
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


def new(dm: Dimensigon, name: str):
    dm.instantiate_flask_gunicorn()
    with dm.flask_app.app_context():
        from cryptography import x509
        from cryptography.hazmat.backends import default_backend
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.x509.oid import NameOID
        import datetime
        Server.set_initial()
        count = Dimension.query.count()

        if count > 0:
            exit("Only one dimension can be created")
        dim = generate_dimension(name)

        private_key = serialization.load_pem_private_key(dim.private.save_pkcs1(), password=None,
                                                         backend=default_backend())
        dim.current = count == 0
        db.session.add(dim)

        now = get_now()

        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, u"LU"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, u"California"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, u"San Francisco"),
            x509.NameAttribute(NameOID.COMMON_NAME, name),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, u"KnowTrade S.L."),

        ])

        cert = x509.CertificateBuilder().subject_name(subject) \
            .issuer_name(issuer) \
            .not_valid_before(now) \
            .not_valid_after(now + datetime.timedelta(days=365 * 10)) \
            .serial_number(x509.random_serial_number()) \
            .public_key(private_key.public_key()) \
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=False, ) \
            .sign(private_key=private_key, algorithm=hashes.SHA256(),
                  backend=default_backend()
                  )

        ssl_dir = os.path.join(dm.config.config_dir, defaults.DEFAULT_SSL_DIR)
        os.makedirs(ssl_dir, exist_ok=True)

        with open(os.path.join(ssl_dir, defaults.DEFAULT_CERT_FILE), "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))

        with open(os.path.join(ssl_dir, defaults.DEFAULT_KEY_FILE), 'wb') as file:
            file.write(private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),

            ))

        os.chmod(os.path.join(ssl_dir, defaults.DEFAULT_KEY_FILE), 0o600)

        db.session.commit()
        click.echo(f"New dimension created successfully")


@dm.command(help="""Activates the dimension""")
@click.argument('dim', nargs=1)
@with_appcontext
@flask.cli.pass_script_info
def activate(dim):
    d = Dimension.query.get(dim).one_or_none()
    if not d:
        d = Dimension.query.filter_by(name=dim).one_or_none()
    if not d:
        click.echo(f"Dimension '{dim}' not found.")
        sys.exit(1)
    Dimension.query.update({Dimension.current: False})
    d.current = True
    db.session.commit()
    click.echo(f"dimension '{dim}' activated")


def server_port():
    if 'PORT' not in os.environ:
        return '5000'
    else:
        return os.environ['PORT']


def server_bind_address():
    if 'HTTP_HOST' not in os.environ:
        return '127.0.0.1'
    else:
        return os.environ['HTTP_HOST']


def app_context(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        with app.app_context():
            f(*args, **kwargs)

    return wrapper


def join(dm: Dimensigon, server: str, token: str, port: int = None, ssl: bool = True, verify: bool = False):
    dm.instantiate_flask_gunicorn()
    with dm.flask_app.app_context():
        Server.set_initial()
        db.session.commit()
        protocol = "https" if ssl else "http"
        with requests.Session() as session:
            # TODO: send ca.cert from the dimension
            try:
                resp = session.get(f"{protocol}://{server}:{port}/api/v1.0/join/public",
                                   headers={'Authorization': 'Bearer ' + token},
                                   verify=verify, timeout=5)
            except requests.exceptions.ConnectionError as e:
                exit(f"Unable to contact to {server}")
            except requests.exceptions.Timeout as e:
                exit(f"Timeout of 5s reached while trying to contact to {server}")
            if resp.status_code != 200:
                exit(f"Error trying to get dimensigon public key: {resp.content}")
            pub_key = rsa.PublicKey.load_pkcs1(resp.content)

            # Generate Public and Private Temporal Keys
            tmp_pub, tmp_priv = rsa.newkeys(2048, poolsize=8)
            symmetric_key = generate_symmetric_key()
            s = Server.get_current()
            data = s.to_json(add_gates=True)
            data = pack_msg2(data=data, pub_key=pub_key, priv_key=tmp_priv, symmetric_key=symmetric_key, add_key=True)
            data.update(my_pub_key=tmp_pub.save_pkcs1().decode('ascii'))
            click.echo("Joining to dimension")
            try:
                resp = session.post(f"{protocol}://{server}:{port}/api/v1.0/join", json=data,
                                    headers={'Authorization': 'Bearer ' + token}, verify=verify)
            except requests.exceptions.ConnectionError as e:
                print(f"Error while trying to join the dimension: {e}")
                resp_data = {}
            except requests.exceptions.Timeout as e:
                print(f"Timeout of 5s reached while trying join the dimension")
                resp_data = {}
            else:
                if resp.status_code != 200:
                    db.session.rollback()
                    print(f"Error while trying to join the dimension: {resp.status_code}, {resp.content}")
                    resp_data = {}
                else:
                    resp_data = unpack_msg2(resp.json(), pub_key=pub_key, priv_key=tmp_priv,
                                            symmetric_key=symmetric_key)
            if 'Dimension' in resp_data:
                dim = Dimension.from_json(resp_data.pop('Dimension'))
                dim.current = True
                db.session.add(dim)

                dotenv.set_key(dotenv.find_dotenv(), 'SECRET_KEY', str(dim.id))

                print('Joined to the dimension')
                print('Updating Catalog')
                reference_server_id = resp_data.pop('me')
                # remove catalog
                for c in Catalog.query.all():
                    db.session.delete(c)
                upgrade_catalog(resp_data)
                # set reference server as a neighbour
                reference_server = Server.query.get(reference_server_id)
                if not reference_server:
                    db.session.rollback()
                    exit(f"Server id {reference_server_id} not found in catalog")
                Route(destination=reference_server, cost=0)
                # update_table_routing_cost(True)
                db.session.commit()
                print('Catalog updated')


def token(dm: Dimensigon, dimension_id_or_name: str):
    dm.instantiate_flask_gunicorn()
    with dm.flask_app.app_context():
        if dimension_id_or_name is not None:
            dim = Dimension.query.get(dimension_id_or_name)
            if dim is None:
                dim = Dimension.query.filter_by(name=dimension_id_or_name)
                if dim is None:
                    exit(f"{dimension_id_or_name} is not a valid dimension")
        else:
            count = Dimension.query.count()
            if count == 1:
                dim = Dimension.query.all()[0]
            else:
                exit("No dimension specified. Please specify a dimension")
        if dm.flask_app.config['SECRET_KEY'] != dim.id:
            exit('Secret key mismatch')

        join_user = User.get_by_user('join')
        if not join_user:
            exit("Unable to create join token. Populate database first.")
        print(create_access_token(join_user.id, expires_delta=datetime.timedelta(minutes=15)))


def run(dm: Dimensigon):
    # check if there is a dimension
    result = dm.engine.execute(Dimension.__table__.select())
    count = len(result.fetchall())
    if count == 0:
        exit("No dimension created. Create or join to a dimension")
    dm.start()


def get_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog='dimensigon')
    parser.add_argument(
        "-c",
        "--config",
        dest='config_dir',
        metavar="path_to_config_dir",
        help="Directory that contains the dimensigon configuration",
    )
    parser.add_argument(
        "--pid-file",
        metavar="path_to_pid_file",
        default=None,
        help="Path to PID file useful for running as daemon. If not set, default config path will be used",
    )
    parser.add_argument(
        "--port",
        metavar="listen_port",
        default=defaults.DEFAULT_PORT,
        help="Listen HTTP port",
    )
    parser.add_argument(
        "--ip",
        default=['0.0.0.0'],
        dest='ips',
        action='append',
        help="IP to listen",
    )
    parser.add_argument(
        "--key-file",
        default=None,
        help="SSL key file",
    )
    parser.add_argument(
        "--cert-file",
        default=None,
        help="SSL certificate file",
    )
    parser.add_argument(
        "--threads",
        default=None,
        help="The number of worker threads for handling requests.",
    )
    if os.name == "posix":
        parser.add_argument(
            "--daemon", action="store_true", help="Run Dimensigon as daemon"
        )

    subparser = parser.add_subparsers(dest='command')
    join_parser = subparser.add_parser("join", help="Joins to the dimension.")
    join_parser.add_argument(
        "SERVER",
        help="Reference Server which will allow to join the dimension. You must specify server name or IP and "
             "port separated by colon. Ex: 10.10.10.10:80"
    )
    join_parser.add_argument(
        "TOKEN",
        help="Authentication Token used for authentication to the reference server"
    )
    join_parser.add_argument(
        '--port', '-p',
        help="port used to contact the server. Defaults to 5000"
    )
    join_parser.add_argument(
        '--no-ssl',
        dest='ssl',
        help="makes connection with HTTP protocol", action='store_false'
    )
    join_parser.add_argument(
        '--verify',
        help="verifies certificate",
        action='store_true'
    )

    dim_parser = subparser.add_parser("dim", help="Command to create dimension.")
    subparser_dim_parser = dim_parser.add_subparsers(dest='subcommand')
    token_subparser = subparser_dim_parser.add_parser('token')
    token_subparser.add_argument(
        'dimension',
        nargs='?',
        default=None
    )
    new_subparser = subparser_dim_parser.add_parser('new')
    new_subparser.add_argument('dimension')

    args = parser.parse_args()

    if os.name != "posix":
        args.__dict__['daemon'] = False

    return args


@dataclass
class RuntimeConfig:
    config_dir: str = None
    debug: bool = None
    pid_file: str = None
    port: str = None
    ips: list = None
    keyfile: str = None
    certfile: str = None
    threads: int = None
    daemon: bool = None


def main():
    args = get_arguments()

    run_config = RuntimeConfig(config_dir=args.config_dir,
                               debug=False,
                               pid_file=args.pid_file,
                               port=args.port,
                               ips=args.ips,
                               keyfile=args.key_file,
                               certfile=args.cert_file,
                               threads=args.threads,
                               daemon=args.daemon)

    from dimensigon import bootstrap
    dm = bootstrap.setup_dm(run_config)

    if args.command is None:
        run(dm)
    elif args.command == 'join':
        join(dm, server=args.SERVER, token=args.TOKEN, port=args.port, ssl=args.ssl, verify=args.verify)
    elif args.command == 'dim':
        if args.subcommand == 'token':
            token(dm, args.dimension)
        elif args.subcommand == 'new':
            new(dm, args.dimension)
        else:
            exit("Use -h to show help")
    else:
        exit("Use -h to show help")


if __name__ == '__main__':
    main()
