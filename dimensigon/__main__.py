import argparse
import base64
import datetime as dt
import functools
import ipaddress
import logging
import os
import platform
import random
import sys
import time

import coolname
import prompt_toolkit
import requests
import rsa
import yaml
from dataclasses import dataclass
from flask import Flask
from flask_jwt_extended import create_access_token
from sqlalchemy import exc, sql

from dimensigon import defaults
from dimensigon.core import Dimensigon
from dimensigon.dshell.output import dprint

basedir = os.path.abspath(os.path.dirname(__file__))

PLATFORM = platform.system()

from dimensigon.domain.entities import *
from dimensigon.web.network import pack_msg2, unpack_msg2
from dimensigon.web import create_app, db, get_root_auth
from dimensigon.utils.helpers import generate_symmetric_key, generate_dimension, get_now

app: Flask = create_app(os.getenv('FLASK_CONFIG') or 'default')


def new(dm: Dimensigon, name: str):
    dm.create_flask_instance()
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

        dim_name = name or coolname.generate_slug(2)
        dim = generate_dimension(dim_name)

        private_key = serialization.load_pem_private_key(dim.private.save_pkcs1(), password=None,
                                                         backend=default_backend())
        dim.current = count == 0
        db.session.add(dim)

        now = get_now()

        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, u"LU"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, u"California"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, u"San Francisco"),
            x509.NameAttribute(NameOID.COMMON_NAME, dim_name),
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

        ssl_dir = os.path.join(dm.config.config_dir, defaults.SSL_DIR)
        os.makedirs(ssl_dir, exist_ok=True)

        with open(os.path.join(ssl_dir, defaults.CERT_FILE), "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))

        with open(os.path.join(ssl_dir, defaults.KEY_FILE), 'wb') as file:
            file.write(private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),

            ))

        os.chmod(os.path.join(ssl_dir, defaults.KEY_FILE), 0o600)

        db.session.commit()

        user = User.get_by_name('root')
        if user is None:
            User.set_initial()
            user = User.get_by_name('root')

        p = False
        p2 = True
        while p != p2:
            p = prompt_toolkit.prompt("Password for root user: ", is_password=True)
            p2 = prompt_toolkit.prompt("Re-type same password: ", is_password=True)
            if p != p2:
                print('Password mismatch')
        user.set_password(p)
        del p, p2

        db.session.commit()

        print(f"New dimension created successfully")
        print("")
        print("----- JOIN TOKEN (valid for {} minutes) -----".format(defaults.JOIN_TOKEN_EXPIRE_TIME))
        token(dm, dim.id)
        print("---------------- END TOKEN --------------------")


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
    def str_resp(resp: requests.Response):
        try:
            return resp.json()
        except ValueError:
            return resp.text

    logger = logging.getLogger('dm.join')
    dm.create_flask_instance()
    dm.set_catalog_manager()
    with dm.flask_app.app_context():
        Server.set_initial()
        db.session.commit()
        protocol = "https" if ssl else "http"

        resp = None
        times = 5
        for i in range(times):
            try:
                resp = requests.get(f"{protocol}://{server}:{port}/api/v1.0/join/public",
                                    headers={'Authorization': 'Bearer ' + token},
                                    verify=verify, timeout=20)
            except requests.exceptions.ConnectionError as e:
                logger.error(f"Unable to contact to {server}.")
            except requests.exceptions.Timeout as e:
                logger.error(f"Timeout of 20s reached while trying to contact to {server}.")
            except Exception as e:
                logger.exception(f"Error trying to get dimensigon public key.")
            else:
                if resp.status_code != 200:
                    if resp.status_code in (401, 422):
                        logger.error(f"Error on authentication: {str_resp(resp)}")
                        sys.exit(1)
                    else:
                        logger.error(f"Error trying to get dimensigon public key: {str_resp(resp)}")
                else:
                    continue
            if i < times - 1:
                d = int(random.random() * 25 * (i + 1))
                logger.info(f"Retrying in {d} seconds.")
                time.sleep(d)
            else:
                sys.exit(1)

        pub_key = rsa.PublicKey.load_pkcs1(resp.content)

        # Generate Public and Private Temporal Keys
        tmp_pub, tmp_priv = rsa.newkeys(2048, poolsize=2)
        symmetric_key = generate_symmetric_key()
        s = Server.get_current()
        data = s.to_json(add_gates=True)
        data = pack_msg2(data=data, pub_key=pub_key, priv_key=tmp_priv, symmetric_key=symmetric_key, add_key=True)
        data.update(my_pub_key=tmp_pub.save_pkcs1().decode('ascii'))
        logger.info("Joining to dimension...")

        resp = None
        times = 5
        for i in range(times):
            try:
                resp = requests.post(f"{protocol}://{server}:{port}/api/v1.0/join", json=data,
                                     headers={'Authorization': 'Bearer ' + token}, verify=verify, timeout=45)

                from dimensigon.web import errors
                if resp.ok:
                    break
                else:
                    logger.error(f"Error while trying to join. {str_resp(resp)}")
            except Exception as e:
                logger.exception(f"Error while trying to join.")
                resp = None
            if i < times - 1:
                d = int(random.random() * 25 * (i + 1))
                logger.info(f"Retrying in {d} seconds.")
                time.sleep(d)

        if resp is None:
            resp_data = {}
        elif resp.status_code != 200:
            db.session.rollback()
            logger.info(f"Error while trying to join the dimension: {str_resp(resp)}")
            resp_data = {}
        else:
            resp_data = unpack_msg2(resp.json(), pub_key=pub_key, priv_key=tmp_priv,
                                    symmetric_key=symmetric_key)
            logger.log(1, resp_data)
        if 'Dimension' in resp_data:
            json_dim = resp_data.pop('Dimension')
            dim = Dimension.query.get(json_dim.get('id'))
            if not dim:
                dim = Dimension.from_json(json_dim)
                dim.current = True
                db.session.add(dim)

                keyfile_content = base64.b64decode(resp_data.pop('keyfile').encode())
                with open(dm.config.http_conf['keyfile'], 'wb') as fh:
                    fh.write(keyfile_content)
                    del keyfile_content
                certfile_content = base64.b64decode(resp_data.pop('certfile').encode())
                with open(dm.config.http_conf['certfile'], 'wb') as fh:
                    fh.write(certfile_content)
                    del certfile_content

                logger.info('Updating Catalog...')
                reference_server_id = resp_data.pop('me')
                # remove catalog
                for c in Catalog.query.all():
                    db.session.delete(c)
                try:
                    dm.catalog_manager.db_update_catalog(resp_data['catalog'])  # implicit commit
                except Exception as e:
                    logger.exception(f"Unable to upgrade catalog.")
                    exit(1)
                else:
                    logger.info('Catalog updated.')
                # set reference server as a neighbour
                reference_server = Server.query.get(reference_server_id)
                if not reference_server:
                    db.session.rollback()
                    logger.info(f"Server id {reference_server_id} not found in catalog.")
                    exit(1)
                Route(destination=reference_server, cost=0)
                # update_route_table_cost(True)
                Parameter.set("join_server", f'{reference_server.id}')

            resp = None
            times = 5
            for i in range(times):
                try:
                    resp = requests.post(f"{protocol}://{server}:{port}/api/v1.0/join/acknowledge/{s.id}",
                                         headers={'Authorization': 'Bearer ' + token}, verify=verify, timeout=120)

                    from dimensigon.web import errors
                    if resp.ok:
                        break
                    elif resp.status_code == 404:
                        if resp.json().get('error', {}).get('type', None) == 'EntityNotFound':
                            break
                    else:
                        logger.error(f"Error while trying to join. Error: {resp.status_code}, "
                                     f"{resp.content}")
                except Exception as e:
                    logger.exception(f"Error while trying to join.")
                    resp = None
                if i < times - 1:
                    d = int(random.random() * 25 * (i + 1))
                    logger.info(f"Retrying in {d} seconds.")
                    time.sleep(d)

            if resp.ok:
                logger.info('Joined to the dimension.')
            else:
                logger.error("Unable to confirm join.")

            db.session.commit()
        else:
            logger.error(f"No dimension in response data.")


def token(dm: Dimensigon, dimension_id_or_name: str, applicant=None, expire_time=None):
    dm.create_flask_instance()
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

        if dimension_id_or_name:
            dm.flask_app.config['SECRET_KEY'] = dim.id
        else:
            if dm.flask_app.config['SECRET_KEY'] != dim.id:
                exit('Secret key mismatch')

        join_user = User.get_by_name('join')
        if not join_user:
            exit("Unable to create join token. Populate database first.")
        print(create_access_token(join_user.id,
                                  expires_delta=dt.timedelta(
                                      minutes=expire_time or defaults.JOIN_TOKEN_EXPIRE_TIME),
                                  user_claims={'applicant': applicant}))


def catalog(dm: Dimensigon, ip, port, http=False):
    import dimensigon.dshell.network as dshell_ntwrk
    dm.create_flask_instance()
    dm.set_catalog_manager()
    with dm.flask_app.app_context():
        print("Updating catalog...")
        catalog_datamark = Catalog.max_catalog(str)

        resp = dshell_ntwrk.request('get', dshell_ntwrk.generate_url('api_1_0.catalog',
                                                                     view_data=dict(data_mark=catalog_datamark),
                                                                     ip=ip,
                                                                     port=port,
                                                                     scheme='http' if http else 'https'),
                                    auth=get_root_auth())
        if resp.ok:
            try:
                dm.catalog_manager.catalog_update(resp.msg)
            except Exception as e:
                exit(f"Unable to upgrade data. Exception: {e}")
        else:
            exit(f"Unable to get catalog from {resp.url}: {resp}")


def gate(dm: Dimensigon, action, ip_or_dns, port, hidden=True):
    dm.create_flask_instance()
    with dm.flask_app.app_context():

        if action == 'create':
            ip, dns = None, None
            try:
                ip = ipaddress.ip_address(ip_or_dns)
            except:
                dns = ip_or_dns
            g = Gate(server=Server.get_current(), ip=ip, dns=dns, port=port, hidden=hidden)
            db.session.add(g)
            try:
                db.session.commit()
            except exc.IntegrityError:
                exit(f"{ip or dns}:{port} already exists")
            else:
                print(f"{g.ip or g.dns}:{g.port}{' (hidden)' if g.hidden else ''} created succesfully")
        elif action == 'port':
            db.engine.execute(sql.text(f"UPDATE D_gate set port = :port WHERE main.D_gate.server_id = :server_id"),
                              port=port,
                              server_id=Server.get_current().id)
            db.session.commit()
        elif action == 'list':
            dprint([f"{g.ip or g.dns}:{g.port}{' (hidden)' if g.hidden else ''}" for g in
                    Gate.query.filter_by(server_id=Server.get_current().id).all()])
        elif action == 'delete':
            ip, dns = None, None
            try:
                ip = ipaddress.ip_address(ip_or_dns)
            except:
                dns = ip_or_dns

            query = Gate.query
            if ip or dns:
                query = query.filter_by(ip=ip, dns=dns)
            if port:
                query = query.filter_by(port=port)
            if hidden:
                query = query.filter_by(hidden=hidden)
            [g.delete() for g in query.all()]
            db.session.commit()

def run(dm: Dimensigon):
    # check if there is a dimension
    result = dm.engine.execute(Dimension.__table__.select())
    count = len(result.fetchall())
    if count == 0:
        exit("No dimension created. Create or join to a dimension")
    try:
        dm.start()
    except RuntimeError as e:
        print("\nError: %s\n" % e, file=sys.stderr)
        sys.stderr.flush()
        sys.exit(1)


def get_arguments() -> argparse.Namespace:
    from dimensigon import __version__
    parser = argparse.ArgumentParser(prog='dimensigon')
    parser.add_argument('--version', action='version',
                        version='%(prog)s {version}'.format(version=__version__))
    parser.add_argument(
        "-c",
        "--config-dir",
        metavar="path_to_config_dir",
        help="Directory that contains the dimensigon configuration",
    )
    parser.add_argument(
        "--pid-file",
        metavar="path_name_to_pid_file",
        default=None,
        help="Path and/or filename to PID file. If not set, default config path and default name will be used",
    )
    parser.add_argument(
        "--port",
        metavar="listen_port",
        default=defaults.DEFAULT_PORT,
        help="Listen HTTP port",
    )
    parser.add_argument(
        "--ip",
        default=None,
        dest='ips',
        action='append',
        help="IP to listen",
    )
    parser.add_argument(
        "--key-file",
        dest='keyfile',
        default=None,
        help="SSL key file",
    )
    parser.add_argument(
        "--cert-file",
        dest='certfile',
        default=None,
        help="SSL certificate file",
    )
    parser.add_argument(
        "--threads",
        default=None,
        help="The number of worker threads for handling requests.",
    )
    parser.add_argument(
        "--debug",
        action='store_true',
        help="Runs the Flask app without gunicorn.",
    )
    parser.add_argument(
        "--access-logfile",
        dest='accesslog',
        metavar="FILE",
        help="The Access log file to write to.",
    )
    parser.add_argument(
        "--error-logfile",
        dest='errorlog',
        metavar="FILE",
        help="The Error log file to write to.",
    )
    parser.add_argument(
        "--logconfig-file",
        metavar="FILE",
        type=argparse.FileType('r'),
        help="The log configuration in yaml format to load.",
    )
    # parser.add_argument(
    #     "--dm-refresh-interval",
    #     help="Period time in minutes to execute the routing and catalog refresh.",
    #     default=defaults.REFRESH_PERIOD,
    #     type=int
    # )
    parser.add_argument(
        "--force-scan",
        help="forces the process to check current and scan for new neighbours.",
        action='store_true',
    )
    parser.add_argument(
        "--flask",
        action='store_true',
        help="run the process with flask http.",
    )
    # if os.name == "posix":
    #     parser.add_argument(
    #         "--daemon", action="store_true", help="Run Dimensigon as daemon"
    #     )

    subparser = parser.add_subparsers(dest='command')
    join_parser = subparser.add_parser("join", help="Joins to the dimension.")
    join_parser.add_argument(
        "SERVER",
        help="Reference Server which will allow to join the dimension. You must specify server name or IP"
    )
    join_parser.add_argument(
        "TOKEN",
        help="Authentication Token used for authentication to the reference server"
    )
    join_parser.add_argument(
        '--port', '-p',
        help="port used to contact the server. Defaults to 5000",
        default=defaults.DEFAULT_PORT,
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

    new_parser = subparser.add_parser('new', help="Creates a new dimension")
    new_parser.add_argument('dimension', nargs='?', default=None, help="name of the dimension")

    token_parser = subparser.add_parser('token', help="Generates a join token.")
    token_parser.add_argument(
        'dimension',
        nargs='?',
        default=None
    )
    token_parser.add_argument("--expire-time",
                              metavar='MINUTES',
                              type=int,
                              help="Join token expire time in minutes")
    token_parser.add_argument(
        '--applicant',
        help="applicant identifier used for join operations",
        action='store'
    )

    catalog_parser = subparser.add_parser("catalog", help="Forces updates catalog with specified ip and port.")
    catalog_parser.add_argument("IP",
                                help="ip to force catalog update")
    catalog_parser.add_argument("--port",
                                type=int,
                                default=defaults.DEFAULT_PORT)
    catalog_parser.add_argument("--http",
                                action='store_true')

    gate_parser = subparser.add_parser("gate", help="handle server gates")
    gate_subparser = gate_parser.add_subparsers(dest='subcommand')

    gate_create_parser = gate_subparser.add_parser("create", help="create a new gate for the current server")
    gate_create_parser.add_argument("IP_DNS", metavar="(IP | DNS)")
    gate_create_parser.add_argument("port", metavar='[port]', nargs='?', type=int, default=defaults.DEFAULT_PORT)
    gate_create_parser.add_argument("--hidden", action="store_true", )

    gate_list_parser = gate_subparser.add_parser("list", help="list all server gates")

    gate_port_parser = gate_subparser.add_parser("port", help="update port from all gates in the current server")
    gate_port_parser.add_argument("port", type=int, help="sets the port on all gates")

    gate_delete_parser = gate_subparser.add_parser("delete", help="delete a current server gate")
    gate_delete_parser.add_argument("IP_DNS", metavar="(IP | DNS)")
    gate_delete_parser.add_argument("port", metavar='[port]', nargs='?', type=int)
    gate_delete_parser.add_argument("--hidden", action="store_true", )

    arguments = parser.parse_args()

    # if os.name != "posix":
    #     setattr(arguments, "daemon", False)

    return arguments


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
    # daemon: bool = None
    accesslog: str = None
    errorlog: str = None
    logconfig: dict = None
    flask: bool = None
    # refresh_interval: int = None
    force_scan: bool = None


def main():
    args = get_arguments()

    from dimensigon import bootstrap

    dm = bootstrap.setup_dm(RuntimeConfig(config_dir=args.config_dir,
                                          debug=args.debug,
                                          pid_file=args.pid_file,
                                          port=args.port,
                                          ips=args.ips,
                                          keyfile=args.keyfile,
                                          certfile=args.certfile,
                                          threads=args.threads,
                                          # daemon=args.daemon,
                                          accesslog=args.accesslog,
                                          errorlog=args.errorlog,
                                          logconfig=yaml.load(args.logconfig_file,
                                                              Loader=yaml.FullLoader) if args.logconfig_file else {},
                                          flask=args.flask,
                                          # refresh_interval=args.dm_refresh_interval,
                                          force_scan=args.force_scan))

    if args.command is None:
        run(dm)
    elif args.command == 'join':
        join(dm, server=args.SERVER, token=args.TOKEN, port=args.port, ssl=args.ssl, verify=args.verify)
    elif args.command == 'token':
        token(dm, dimension_id_or_name=args.dimension, applicant=args.applicant, expire_time=args.expire_time)
    elif args.command == 'new':
        new(dm, args.dimension)
    elif args.command == 'catalog':
        catalog(dm, ip=args.IP, port=args.port, http=args.http)
    elif args.command == 'gate':
        gate(dm, action=args.subcommand, ip_or_dns=getattr(args, 'IP_DNS', None), port=getattr(args, 'port', None),
             hidden=getattr(args, 'hidden', None))
    else:
        exit("Use -h to show help")


if __name__ == '__main__':
    main()
