import datetime
import os
import platform
import sys

import click
import dotenv
import requests
import rsa
from flask import Flask
from flask.cli import with_appcontext
from flask_jwt_extended import create_access_token
from flask_migrate import Migrate

from dm.domain.entities.bootstrap import set_initial

dotenv.load_dotenv(dotenv.find_dotenv())
basedir = os.path.abspath(os.path.dirname(__file__))

PLATFORM = platform.system()

COV = None
if os.environ.get('FLASK_COVERAGE'):
    import coverage

    COV = coverage.coverage(branch=True, include='app/*')
    COV.start()

from dm.domain.entities import *
from dm.web.network import pack_msg2, unpack_msg2
from dm.web import create_app, db

from dm.use_cases.use_cases import upgrade_catalog
from dm.utils.helpers import generate_symmetric_key, generate_dimension

app: Flask = create_app(os.getenv('FLASK_CONFIG') or 'default')
migrate = Migrate(db, user_module_prefix="sa.")

with app.app_context():
    if db.engine.url.drivername == 'sqlite':
        migrate.init_app(app, db, render_as_batch=True)
    else:
        migrate.init_app(app, db)


@app.shell_context_processor
def make_shell_context():
    return dict(db=db, app=app, ActionTemplate=ActionTemplate, ActionType=ActionType, Step=Step,
                Orchestration=Orchestration, Catalog=Catalog,
                Dimension=Dimension, StepExecution=StepExecution, Log=Log, Route=Route, Server=Server, Service=Service,
                Software=Software, SoftwareServerAssociation=SoftwareServerAssociation, User=User,
                Transfer=Transfer, Locker=Locker, Scope=Scope, State=State, Gate=Gate,
                create_access_token=create_access_token,
                set_initial=set_initial)


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
@click.option('--ssl/--no-ssl', help="makes connection with HTTP protocol", default=True)
@click.option('--verify/--no-verify', help="verifies certificate", default=False)
@with_appcontext
def join(server, token, ssl, verify):
    Server.set_initial()
    db.session.commit()
    protocol = "https" if ssl else "http"
    with requests.Session() as session:
        # TODO: send ca.cert from the dimension
        try:
            resp = session.get(f"{protocol}://{server}/api/v1.0/join/public", headers={'Authorization': 'Bearer ' + token},
                           verify=verify, timeout=5)
        except requests.exceptions.ConnectionError as e:
            click.echo(f"Unable to contact to {server}")
            exit(1)
        except requests.exceptions.Timeout as e:
            click.echo(f"Timeout of 5s reached while trying to contact to {server}")
            exit(1)
        if resp.status_code != 200:
            click.echo(f"Error trying to get dimensigon public key: {resp.content}")
            exit(1)
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
            resp = session.post(f"{protocol}://{server}/api/v1.0/join", json=data,
                                headers={'Authorization': 'Bearer ' + token}, verify=verify)
        except requests.exceptions.ConnectionError as e:
            click.echo(f"Error while trying to join the dimension: {e}")
            resp_data = {}
        except requests.exceptions.Timeout as e:
            click.echo(f"Timeout of 5s reached while trying join the dimension")
            resp_data = {}
        else:
            if resp.status_code != 200:
                click.echo(f"Error while trying to join the dimension: {resp.status_code}, {resp.content}")
                resp_data = {}
            else:
                resp_data = unpack_msg2(resp.json(), pub_key=pub_key, priv_key=tmp_priv, symmetric_key=symmetric_key)
        if 'Dimension' in resp_data:
            dim = Dimension.from_json(resp_data.pop('Dimension'))
            dim.current = True
            db.session.add(dim)

            dotenv.set_key(dotenv.find_dotenv(), 'SECRET_KEY', str(dim.id))

            click.echo('Joined to the dimension')
            click.echo('Updating Catalog')
            reference_server_id = resp_data.pop('me')
            # remove catalog
            for c in Catalog.query.all():
                db.session.delete(c)
            upgrade_catalog(resp_data)
            # set reference server as a neighbour
            reference_server = Server.query.get(reference_server_id)
            if not reference_server:
                raise ValueError(f"Server id {reference_server_id} not found in catalog")
            Route(destination=reference_server, cost=0)
            # update_table_routing_cost(True)
            db.session.commit()



@dm.command(help="""Create a token for joining the dimension.""")
def token():
    click.echo(create_access_token(User.get_by_user('join').id, expires_delta=datetime.timedelta(minutes=15)))


@dm.command(help="""Create a dimension from scratch. Must provide a name for the dimension""")
@click.argument('name', nargs=1)
@with_appcontext
def new(name):
    from cryptography import x509
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.x509.oid import NameOID
    import datetime
    Server.set_initial()
    count = Dimension.query.count()
    dim = generate_dimension(name)

    private_key = serialization.load_pem_private_key(dim.private.save_pkcs1(), password=None, backend=default_backend())
    dim.current = count == 0
    db.session.add(dim)
    User.set_initial()

    now = datetime.datetime.utcnow()

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

    ssl_dir = os.path.join(basedir, 'ssl')
    os.makedirs(ssl_dir, exist_ok=True)

    with open(os.path.join(ssl_dir, f"cert.pem"), "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

    with open(os.path.join(ssl_dir, 'key.pem'), 'wb') as file:
        file.write(private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),

        ))

    os.chmod(os.path.join(ssl_dir, 'key.pem'), 0o600)

    if 'SECRET_KEY' not in dotenv.dotenv_values() or count == 0:
        dotenv.set_key(dotenv.find_dotenv(), 'SECRET_KEY', str(dim.id))

    click.echo(f"New dimension created successfully")
    db.session.commit()


@dm.command(help="""Activates the dimension""")
@click.argument('dim', nargs=1)
@with_appcontext
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
