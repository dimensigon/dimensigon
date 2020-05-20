import hashlib
import os
import re
import time
from functools import partial

import responses
from aioresponses import CallbackResult, aioresponses
from flask import url_for
from flask_jwt_extended import create_access_token
from pyfakefs.fake_filesystem_unittest import TestCase

from dm.domain.entities import Server, Route, Dimension, Software, SoftwareServerAssociation, Transfer, TransferStatus
from dm.domain.entities.bootstrap import set_initial
from dm.utils.helpers import generate_dimension, md5
from dm.web import create_app, db
from dm.web.network import HTTPBearerAuth


class TestAsyncSendFile(TestCase):
    def setUp(self) -> None:
        # create the app with common test config
        self.app1 = create_app('test')
        self.app1.config['SERVER_NAME'] = 'node1'
        # self.app1.config['SECURIZER'] = True
        self.client1 = self.app1.test_client()
        self.app2 = create_app('test')
        self.app2.config['SERVER_NAME'] = 'node2'
        # self.app2.config['SECURIZER'] = True
        self.client2 = self.app2.test_client()

        self.source_path = '/software'
        self.filename = 'filename.zip'
        self.content = b'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
        self.size = len(self.content)
        self.checksum = hashlib.md5(self.content).hexdigest()
        self.dest_path = '/dest_repo'

        with self.app1.app_context():
            db.create_all()
            set_initial()
            s = Server.get_current()
            s.gates = []
            s.add_new_gate('node1', 5000)
            soft = Software(name='test_software', version=1, filename=self.filename, size=self.size,
                            checksum=self.checksum)
            ssa = SoftwareServerAssociation(software=soft, server=s, path=self.source_path)
            dim = generate_dimension('dimension')
            dim.current = True
            db.session.add_all([s, dim, soft, ssa])
            db.session.commit()
            self.s1_json = Server.get_current().to_json()
            self.soft_json = soft.to_json()
            self.ssa_json = ssa.to_json()
            self.dim_json = dim.to_json()
            self.auth = HTTPBearerAuth(create_access_token('test'))

        with self.app2.app_context():
            db.create_all()
            set_initial()
            s = Server.get_current()
            s.gates = []
            s.add_new_gate('node2', 5000)
            db.session.commit()
            self.s2_json = Server.get_current().to_json()
            s = Server.from_json(self.s1_json)
            s.add_new_gate('node1', 5000)
            Route(s, cost=0)

            db.session.add(s)
            dim = Dimension.from_json(self.dim_json)
            dim.current = True
            db.session.add(dim)

            soft = Software.from_json(self.soft_json)
            db.session.add(soft)

            ssa = SoftwareServerAssociation.from_json(self.ssa_json)
            db.session.add(ssa)
            db.session.commit()

        self.context = self.app1.app_context()
        self.context.push()
        s = Server.from_json(self.s2_json)
        s.add_new_gate('node2', 5000)
        Route(s, cost=0)
        db.session.add(s)

        self.remote = s

        self.setUpPyfakefs()
        self.fs.create_dir(self.source_path)
        self.fs.create_dir(self.dest_path)
        self.fs.create_file(os.path.join(self.source_path, self.filename), contents=self.content)

        db.session.commit()

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        self.context.pop()

        with self.app2.app_context():
            db.session.remove()
            db.drop_all()

    def set_callbacks(self, m):
        def post_callback_client(url, **kwargs):
            kwargs.pop('allow_redirects')

            r = self.client2.post(url.path, json=kwargs['json'], headers=kwargs['headers'])

            return CallbackResult('POST', status=r.status_code, body=r.data, content_type=r.content_type,
                                  headers=r.headers)

        m.post(re.compile('https?://node2.*'), callback=post_callback_client,
               repeat=True)

        def patch_callback_client(url, **kwargs):
            kwargs.pop('allow_redirects')

            r = self.client2.patch(url.path, json=kwargs['json'], headers=kwargs['headers'])

            return CallbackResult('PATCH', status=r.status_code, body=r.data, content_type=r.content_type,
                                  headers=r.headers)

        m.patch(re.compile('https?://node2.*'), callback=patch_callback_client,
                repeat=True)

        def requests_callback_client(client, request):
            method_func = getattr(client, request.method.lower())
            resp = method_func(request.path_url, data=request.body, headers=dict(request.headers))

            return resp.status_code, resp.headers, resp.data

        responses.add_callback(responses.POST, re.compile('https?://node2.*'),
                               callback=partial(requests_callback_client, self.client2))

    @aioresponses()
    @responses.activate
    def test_software_send(self, m):
        self.set_callbacks(m)

        server = Server.query.filter_by(name='node2').one()

        self.assertFalse(os.path.exists(os.path.join(self.dest_path, self.filename)))

        resp = self.client1.post(url_for('api_1_0.software_send'),
                                 json=dict(software_id=self.soft_json['id'], dest_server_id=server.id,
                                           dest_path=self.dest_path),
                                 headers=self.auth.header)
        self.assertEqual(202, resp.status_code)
        self.assertIn('transfer_id', resp.get_json())

        with self.app2.app_context():
            t = Transfer.query.get(resp.get_json().get('transfer_id'))
            start = time.time()
            while t.status != TransferStatus.COMPLETED and (time.time() - start) < 5:
                time.sleep(0.1)
                db.session.refresh(t)

        self.assertTrue(os.path.exists(os.path.join(self.dest_path, self.filename)))
        self.assertEqual(self.size, os.path.getsize(os.path.join(self.dest_path, self.filename)))
        self.assertEqual(self.checksum, md5(os.path.join(self.dest_path, self.filename)))

    @responses.activate
    def test_software_send_error_on_create_transfer(self):
        def requests_callback_client(client, request):
            method_func = getattr(client, request.method.lower())
            resp = method_func(request.path_url, data=request.body, headers=dict(request.headers))

            return resp.status_code, resp.headers, resp.data

        responses.add(responses.POST, re.compile('https?://node2.*'), body=ConnectionError('No connection'))

        server = Server.query.filter_by(name='node2').one()

        self.assertFalse(os.path.exists(os.path.join(self.dest_path, self.filename)))

        resp = self.client1.post(url_for('api_1_0.software_send'),
                                 json=dict(software_id=self.soft_json['id'], dest_server_id=server.id,
                                           dest_path=self.dest_path),
                                 headers=self.auth.header)
        self.assertEqual(400, resp.status_code)
        self.assertDictEqual({'error': f'unable to create transfer on {server}',
                              'message': 'No connection',
                              'code': None}, resp.get_json())