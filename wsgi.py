import os

import click
import requests
import rsa
from coverage import Coverage
from flask import url_for
from flask.cli import with_appcontext
from flask_migrate import MigrateCommand

from dm.domain.entities import *
from dm.domain.entities.orchestration import Step
from dm.network.gateway import pack_msg, unpack_msg
from dm.domain.entities import Dimension

cov = Coverage(source=('dm',))
cov.start()

from dm.web import create_app, db, set_variables

app = create_app(os.getenv('FLASK_CONFIG') or 'dev')


@app.shell_context_processor
def make_shell_context():
    db.create_all()
    set_variables()
    return dict(db=db, app=app, ActionTemplate=ActionTemplate, Step=Step, Orchestration=Orchestration, Catalog=Catalog,
                Dimension=Dimension, Execution=Execution, Log=Log, Route=Route, Server=Server, Service=Service)


@app.cli.command(help='executes the specified tests')
@click.option('--coverage/--no-coverage', default=False, help='Enable code coverage')
@click.argument('test_names', nargs=-1)
def test(test_names, coverage):
    import unittest
    if test_names:
        tests = unittest.TestLoader().loadTestsFromNames(test_names)
    else:
        tests = unittest.TestLoader().discover('tests')
    if not coverage:
        cov.stop()
        cov.erase()
    result = unittest.TextTestRunner(verbosity=2).run(tests)
    if result.wasSuccessful() and coverage:
        cov.stop()
        cov.save()
        print('Coverage Summary:')
        cov.report()
        basedir = os.path.abspath(os.path.dirname(__file__))
        covdir = os.path.join(basedir, 'tmp/coverage')
        cov.html_report(directory=covdir)
        print('HTML version: file://%s/index.html' % covdir)
        cov.erase()


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
