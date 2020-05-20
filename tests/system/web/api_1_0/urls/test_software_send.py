import functools
import os
import re
import shutil
import time
import traceback
from functools import partial
from unittest import TestCase

import responses
from aioresponses import CallbackResult
from aioresponses import aioresponses
from flask import url_for
from flask_jwt_extended import create_access_token

from dm.domain.entities import Server, Dimension, Software, SoftwareServerAssociation, Transfer, TransferStatus, Route
from dm.domain.entities.bootstrap import set_initial
from dm.utils.helpers import generate_dimension, md5
from dm.web import create_app, db
from dm.web.network import unpack_msg, pack_msg

basedir = os.path.dirname(os.path.abspath(__file__))


class TestApi(TestCase):
    def setUp(self):
        """Create and configure a new app instance for each test."""
        # create the app with common test config
        self.app = create_app('test')
        self.app.config['SECURIZER'] = True
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.dim = generate_dimension('test')
        self.dim.current = True
        self.json_dim = self.dim.to_json()
        self.client = self.app.test_client()
        self.headers = {"Authorization": f"Bearer {create_access_token('test')}"}
        self.software_content = b"new data"
        self.filename = 'test.tar.gz'
        self.src_path = os.path.join(basedir, 'src')
        self.file = os.path.join(self.src_path, self.filename)
        os.makedirs(self.src_path, exist_ok=True)
        with open(self.file, 'wb') as fd:
            fd.write(self.software_content)
        self.dst_path = os.path.join(basedir, 'dst')
        try:
            shutil.rmtree(self.dst_path)
        except FileNotFoundError:
            pass
        os.makedirs(self.dst_path, exist_ok=True)

        self.software_checksum = md5(self.file)

        set_initial(server=False)
        server = Server('src', port=8000, me=True)
        soft = Software(name='test', version=1, family='DB', size=8, filename=self.filename,
                        checksum=self.software_checksum)
        ssa = SoftwareServerAssociation(software=soft, server=server, path=self.src_path)
        db.session.add_all([server, soft, ssa, self.dim])

        db.session.commit()

        self.json_src_server = server.to_json(add_gates=True)
        self.json_soft = soft.to_json()
        self.json_ssa = ssa.to_json()

        self.dest_app = create_app('test')
        self.dest_app.config['SECURIZER'] = True
        self.dest_app_client = self.dest_app.test_client()
        with self.dest_app.app_context():
            set_initial(server=False)
            me = Server('dest', port=8000, me=True)
            db.session.add(me)
            src_server = Server.from_json(self.json_src_server)
            Route(src_server, cost=0)
            db.session.add(src_server)
            db.session.add(Software.from_json(self.json_soft))
            db.session.add(SoftwareServerAssociation.from_json(self.json_ssa))
            dim = Dimension.from_json(self.json_dim)
            dim.current = True
            db.session.add(dim)
            db.session.commit()
            self.json_dest_server = me.to_json(add_gates=True)

        dest = Server.from_json(self.json_dest_server)
        Route(dest, cost=0)
        db.session.add(dest)
        db.session.commit()

    def tearDown(self) -> None:
        with self.dest_app.app_context():
            db.session.remove()
            db.drop_all()

        db.session.remove()
        db.drop_all()
        self.app_context.pop()

        try:

            shutil.rmtree(self.dst_path)
        except:
            pass

        try:
            shutil.rmtree(self.src_path)
        except:
            pass

    @responses.activate
    @aioresponses()
    def test_software_send(self, m):
        def requests_callback_client(client, request):
            method_func = getattr(client, request.method.lower())
            try:
                resp = method_func(request.path_url, data=request.body, headers=dict(request.headers))
            except Exception as e:
                return 500, {}, traceback.format_exc()

            return resp.status_code, resp.headers, resp.data

        responses.add_callback(responses.POST, re.compile('https?://dest:.*'),
                               callback=partial(requests_callback_client, self.dest_app.test_client()))
        responses.add_callback(responses.GET, re.compile('https?://dest:.*'),
                               callback=partial(requests_callback_client, self.dest_app.test_client()))

        def callback_client(method, client, url, **kwargs):
            kwargs.pop('allow_redirects')
            # passing headers as a workarround for https://github.com/pnuckowski/aioresponses/issues/111
            func = getattr(client, method.lower())
            r = func(url.path, headers=kwargs['headers'], json=kwargs['json'])

            return CallbackResult(method.upper(), status=r.status_code, body=r.data, content_type=r.content_type,
                                  headers=r.headers)

        m.get(re.compile('https?://dest:.*'),
              callback=functools.partial(callback_client, 'GET', self.dest_app.test_client()), repeat=True)
        m.post(re.compile('https?://dest:.*'),
               callback=functools.partial(callback_client, 'POST', self.dest_app.test_client()), repeat=True)
        m.patch(re.compile('https?://dest:.*'),
                callback=functools.partial(callback_client, 'PATCH', self.dest_app.test_client()), repeat=True)

        resp = self.client.post(url_for('api_1_0.software_send'), headers=self.headers,
                                json=pack_msg(dict(software_id=self.json_soft['id'],
                                                   dest_server_id=self.json_dest_server['id'],
                                                   chunk_size=4,
                                                   dest_path=self.dst_path)))
        data = unpack_msg(resp.json)
        self.assertIn('transfer_id', data)
        trans_id = data['transfer_id']

        with self.dest_app.app_context():
            t = Transfer.query.get(trans_id)
            while t.status != TransferStatus.COMPLETED:
                time.sleep(1)
                db.session.refresh(t)

        with open(self.file, 'rb') as fd:
            content = fd.read()

        self.assertEqual(self.software_content, content)
