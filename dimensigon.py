import datetime
import os
import platform
import sys

from dotenv import load_dotenv

from dm.utils.helpers import generate_symmetric_key

basedir = os.path.dirname(os.path.abspath(__file__))
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')

if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)

PLATFORM = platform.system()

COV = None
if os.environ.get('FLASK_COVERAGE'):
    import coverage

    COV = coverage.coverage(branch=True, include='app/*')
    COV.start()

import click
import requests
import rsa
from flask import Flask
from flask.cli import with_appcontext
from flask_migrate import Migrate

from dm.domain.entities import *
from dm.domain.entities import Dimension
from dm.domain.entities.orchestration import Step
from dm.network.gateway import pack_msg, unpack_msg
from dm.web import create_app, db
from flask_jwt_extended import create_access_token

app: Flask = create_app(os.getenv('FLASK_CONFIG') or 'default')
migrate = Migrate(app, db)


#
# @click.group(cls=FlaskGroup, create_app=create_app)
# def cli():
#     """Management script for the Wiki application."""


@app.shell_context_processor
def make_shell_context():
    return dict(db=db, app=app, ActionTemplate=ActionTemplate, Step=Step, Orchestration=Orchestration, Catalog=Catalog,
                Dimension=Dimension, Execution=Execution, Log=Log, Route=Route, Server=Server, Service=Service,
                Software=Software, SoftwareFamily=SoftwareFamily, SoftwareServerAssociation=SoftwareServerAssociation,
                Transfer=Transfer, create_access_token=create_access_token)


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
    protocol = "https" if ssl else "http"
    resp = requests.get(f"{protocol}://{server}/api/v1.0/join/public", headers={'Authorization': 'Bearer ' + token},
                        verify=verify)
    resp.raise_for_status()
    pub_key = rsa.PublicKey.load_pkcs1(resp.content)

    # Generate Public and Private Temporal Keys
    tmp_pub, tmp_priv = rsa.newkeys(2048, poolsize=8)
    symmetric_key = generate_symmetric_key()
    data = pack_msg(data={}, pub_key=pub_key, priv_key=tmp_priv, symmetric_key=symmetric_key, add_key=True)
    data.update(my_pub_key=tmp_pub.save_pkcs1().decode('ascii'))
    click.echo("Joining to dimension")
    resp = requests.post(f"{protocol}://{server}/api/v1.0/join", json=data,
                         headers={'Authorization': 'Bearer ' + token}, verify=verify)
    resp.raise_for_status()
    resp_data = unpack_msg(resp.json(), pub_key=pub_key, priv_key=tmp_priv, symmetric_key=symmetric_key)
    if 'id' in resp_data:
        priv_key = rsa.PrivateKey.load_pkcs1(resp_data.get('private'))
        dim = Dimension(id=resp_data.get('id'), name=resp_data.get('name'), public=pub_key, private=priv_key,
                        created_at=resp_data.get('created_at'), current=True)
        db.session.add(dim)

        db.session.commit()

    click.echo('Joined to the dimension')


@dm.command(help="""Create a token for joining the dimension.""")
def token():
    click.echo(create_access_token('join', expires_delta=datetime.timedelta(minutes=15)))


@dm.command(help="""Create a dimension from scratch. Must provide a name for the dimension""")
@click.argument('name', nargs=1)
@with_appcontext
def new(name):
    from cryptography import x509
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
    import datetime

    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=4096,
        backend=default_backend()
    )
    priv_pem = private_key.private_bytes(encoding=serialization.Encoding.PEM,
                                         format=serialization.PrivateFormat.TraditionalOpenSSL,
                                         encryption_algorithm=serialization.NoEncryption())
    pub_pem = private_key.public_key().public_bytes(encoding=serialization.Encoding.PEM,
                                                    format=serialization.PublicFormat.PKCS1)
    count = Dimension.query.count()
    dim = Dimension(name=name, private=priv_pem, public=pub_pem, current=count == 0)
    db.session.add(dim)

    now = datetime.datetime.utcnow()

    cert = x509.CertificateBuilder().subject_name(x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, name),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, u'KnowTrade S.L.'),
        x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, u'CA Dimension ' + name)])) \
        .issuer_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)])) \
        .not_valid_before(now - datetime.timedelta(1, 0, 0)) \
        .not_valid_after(now + datetime.timedelta(days=365 * 10)) \
        .serial_number(x509.random_serial_number()) \
        .public_key(private_key.public_key()) \
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True, ) \
        .sign(
        private_key=private_key, algorithm=hashes.SHA256(),
        backend=default_backend()
    )

    ssl_dir = os.path.join(basedir, 'ssl')
    os.makedirs(ssl_dir, exist_ok=True)

    with open(os.path.join(ssl_dir, "ca.crt"), "wb") as f:
        f.write(cert.public_bytes(
            encoding=serialization.Encoding.PEM,
        ))

    db.session.commit()

    click.echo(f"New dimension created successfully")


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


@dm.command(help="""Generates a self signed certificate""")
@click.option('--hostname')
@click.option('--ip', multiple=True)
@with_appcontext
def certs(hostname, ip):
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    import ipaddress

    d = Dimension.get_current()
    s = Server.get_current()
    if not d:
        click.echo('You must join to a dimension in order to generate a certificate')
        sys.exit(1)

    ssl_dir = os.path.join(basedir, 'ssl')
    # get CA crt and private key
    with open(os.path.join(ssl_dir, 'ca.crt'), 'rb') as fd:
        ca = x509.load_pem_x509_certificate(fd.read(), default_backend())
    ca_priv_key = serialization.load_pem_private_key(data=d.private.save_pkcs1(), password=None,
                                                     backend=default_backend())

    hostname = hostname or s.name

    # Generate our key
    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend(),
    )

    name = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, hostname),
        x509.NameAttribute(NameOID.COUNTRY_NAME, u"ES"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, u"Barcelona"),
        x509.NameAttribute(NameOID.LOCALITY_NAME, u"Barcelona"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, u"KnowTrade S.L."),
        x509.NameAttribute(NameOID.COMMON_NAME, u"dimensigon.com"),
    ])

    # best practice seem to be to include the hostname in the SAN, which *SHOULD* mean COMMON_NAME is ignored.
    alt_names = [x509.DNSName(hostname)]

    # allow addressing by IP, for when you don't have real DNS (common in most testing scenarios
    if ip:
        for addr in ip:
            # openssl wants DNSnames for ips...
            alt_names.append(x509.DNSName(addr))
            # ... whereas golang's crypto/tls is stricter, and needs IPAddresses
            # note: older versions of cryptography do not understand ip_address objects
            alt_names.append(x509.IPAddress(ipaddress.ip_address(addr)))

    san = x509.SubjectAlternativeName(alt_names)

    now = datetime.datetime.utcnow()
    csr = x509.CertificateSigningRequestBuilder() \
        .subject_name(name) \
        .add_extension(san, critical=False) \
        .sign(private_key=key, algorithm=hashes.SHA256(), backend=default_backend())

    crt = x509.CertificateBuilder() \
        .subject_name(csr.subject) \
        .issuer_name(ca.subject) \
        .public_key(csr.public_key()) \
        .serial_number(x509.random_serial_number()) \
        .not_valid_before(now - datetime.timedelta(1, 0, 0)) \
        .not_valid_after(now + datetime.timedelta(days=10 * 365)) \
        .sign(private_key=ca_priv_key, algorithm=hashes.SHA256(), backend=default_backend())

    cert_pem = crt.public_bytes(encoding=serialization.Encoding.PEM)
    key_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),

    )

    with open(os.path.join(ssl_dir, 'cert.pem'), 'wb') as file:
        file.write(cert_pem)

    with open(os.path.join(ssl_dir, 'key.pem'), 'wb') as file:
        file.write(key_pem)
    os.chmod(os.path.join(ssl_dir, 'key.pem'), 0o600)


@dm.command(help='Fill initial server')
@with_appcontext
def populate_db():
    # migrate database to latest revision
    # alembic_dir = os.path.join(basedir, 'migrations')
    #
    # if not os.path.exists(alembic_dir):
    #     init()
    #
    # upgrade()

    # Generate Server
    # db.create_all()
    Server.set_initial()
