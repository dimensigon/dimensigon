import hashlib
import os
import re

from aioresponses import aioresponses, CallbackResult
from flask_jwt_extended import create_access_token
from pyfakefs.fake_filesystem_unittest import TestCase

from dm.domain.entities import Server, Route, Dimension, Transfer, TransferStatus
from dm.domain.entities.bootstrap import set_initial
from dm.utils.asyncio import run
from dm.utils.helpers import generate_dimension, md5
from dm.web import create_app, db
from dm.web.async_functions import async_send_file
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

        with self.app1.app_context():
            db.create_all()
            set_initial()
            s = Server.get_current()
            s.gates = []
            s.add_new_gate('node1', 5000)
            dim = generate_dimension('dimension')
            dim.current = True
            db.session.add(dim)
            db.session.commit()
            self.s1_json = Server.get_current().to_json()
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
            db.session.commit()

        self.context = self.app1.app_context()
        self.context.push()
        s = Server.from_json(self.s2_json)
        s.add_new_gate('node2', 5000)
        Route(s, cost=0)
        db.session.add(s)

        self.remote = s

        self.source_path = '/software'
        self.filename = 'filename.zip'
        self.content = b'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
        self.size = len(self.content)
        self.checksum = hashlib.md5(self.content).hexdigest()
        self.dest_path = '/dest_repo'

        db.session.commit()

        self.setUpPyfakefs()
        self.fs.create_dir(self.source_path)
        self.fs.create_dir(self.dest_path)
        self.fs.create_file(os.path.join(self.source_path, self.filename), contents=self.content)

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

        m.post(re.compile(Server.query.filter_by(name='node2').one().url() + '.*'), callback=post_callback_client,
               repeat=True)

        def patch_callback_client(url, **kwargs):
            kwargs.pop('allow_redirects')

            r = self.client2.patch(url.path, json=kwargs['json'], headers=kwargs['headers'])

            return CallbackResult('PATCH', status=r.status_code, body=r.data, content_type=r.content_type,
                                  headers=r.headers)

        m.patch(re.compile(Server.query.filter_by(name='node2').one().url() + '.*'), callback=patch_callback_client,
                repeat=True)

    @aioresponses()
    def test_async_send_file(self, m):
        self.set_callbacks(m)

        with self.app2.app_context():
            transfer = Transfer(software=self.filename,
                                size=self.size,
                                checksum=self.checksum,
                                dest_path=self.dest_path,
                                num_chunks=16,
                                status=TransferStatus.WAITING_CHUNKS)
            db.session.add(transfer)
            db.session.commit()
            transfer_id = transfer.id

        self.assertFalse(os.path.exists(os.path.join(self.dest_path, self.filename)))

        run(async_send_file(dest_server=self.remote, transfer_id=transfer_id,
                            file=os.path.join(self.source_path, self.filename), chunk_size=4,
                            auth=self.auth))

        self.assertTrue(os.path.exists(os.path.join(self.dest_path, self.filename)))
        self.assertEqual(self.size, os.path.getsize(os.path.join(self.dest_path, self.filename)))
        self.assertEqual(self.checksum, md5(os.path.join(self.dest_path, self.filename)))

    @aioresponses()
    def test_async_send_file_one_chunk(self, m):
        self.set_callbacks(m)

        with self.app2.app_context():
            transfer = Transfer(software=self.filename,
                                size=self.size,
                                checksum=self.checksum,
                                dest_path=self.dest_path,
                                num_chunks=1,
                                status=TransferStatus.WAITING_CHUNKS)
            db.session.add(transfer)
            db.session.commit()
            transfer_id = transfer.id

        self.assertFalse(os.path.exists(os.path.join(self.dest_path, self.filename)))

        run(async_send_file(dest_server=self.remote, transfer_id=transfer_id,
                            file=os.path.join(self.source_path, self.filename), chunk_size=80,
                            auth=self.auth))

        self.assertTrue(os.path.exists(os.path.join(self.dest_path, self.filename)))
        self.assertEqual(self.size, os.path.getsize(os.path.join(self.dest_path, self.filename)))
        self.assertEqual(self.checksum, md5(os.path.join(self.dest_path, self.filename)))

    @aioresponses()
    def test_async_send_retry(self, m):
        def post_callback_client(url, **kwargs):
            kwargs.pop('allow_redirects')

            r = self.client2.post(url.path, json=kwargs['json'], headers=kwargs['headers'])

            return CallbackResult('POST', status=r.status_code, body=r.data, content_type=r.content_type,
                                  headers=r.headers)

        m.post(re.compile(Server.query.filter_by(name='node2').one().url() + '.*'), callback=post_callback_client)
        m.post(re.compile(Server.query.filter_by(name='node2').one().url() + '.*'), callback=post_callback_client)
        m.post(re.compile(Server.query.filter_by(name='node2').one().url() + '.*'), exception=ConnectionError)
        m.post(re.compile(Server.query.filter_by(name='node2').one().url() + '.*'), exception=ConnectionError)
        m.post(re.compile(Server.query.filter_by(name='node2').one().url() + '.*'), callback=post_callback_client)
        m.post(re.compile(Server.query.filter_by(name='node2').one().url() + '.*'), callback=post_callback_client)
        m.post(re.compile(Server.query.filter_by(name='node2').one().url() + '.*'), exception=ConnectionError)
        m.post(re.compile(Server.query.filter_by(name='node2').one().url() + '.*'), callback=post_callback_client)

        def patch_callback_client(url, **kwargs):
            kwargs.pop('allow_redirects')

            r = self.client2.patch(url.path, json=kwargs['json'], headers=kwargs['headers'])

            return CallbackResult('PATCH', status=r.status_code, body=r.data, content_type=r.content_type,
                                  headers=r.headers)

        m.patch(re.compile(Server.query.filter_by(name='node2').one().url() + '.*'), callback=patch_callback_client,
                repeat=True)

        with self.app2.app_context():
            transfer = Transfer(software=self.filename,
                                size=self.size,
                                checksum=self.checksum,
                                dest_path=self.dest_path,
                                num_chunks=5,
                                status=TransferStatus.WAITING_CHUNKS)
            db.session.add(transfer)
            db.session.commit()
            transfer_id = transfer.id

        self.assertFalse(os.path.exists(os.path.join(self.dest_path, self.filename)))

        run(async_send_file(dest_server=self.remote, transfer_id=transfer_id,
                            file=os.path.join(self.source_path, self.filename), chunk_size=14,
                            auth=self.auth, retries=3))

        self.assertTrue(os.path.exists(os.path.join(self.dest_path, self.filename)))
        self.assertEqual(self.size, os.path.getsize(os.path.join(self.dest_path, self.filename)))
        self.assertEqual(self.checksum, md5(os.path.join(self.dest_path, self.filename)))

        os.remove(os.path.join(self.dest_path, self.filename))

        m.post(re.compile(Server.query.filter_by(name='node2').one().url() + '.*'), callback=post_callback_client)
        m.post(re.compile(Server.query.filter_by(name='node2').one().url() + '.*'), callback=post_callback_client)
        m.post(re.compile(Server.query.filter_by(name='node2').one().url() + '.*'), exception=ConnectionError)
        m.post(re.compile(Server.query.filter_by(name='node2').one().url() + '.*'), exception=ConnectionError)
        m.post(re.compile(Server.query.filter_by(name='node2').one().url() + '.*'), callback=post_callback_client)

        data = run(async_send_file(dest_server=self.remote, transfer_id=transfer_id,
                                   file=os.path.join(self.source_path, self.filename), chunk_size=14,
                                   auth=self.auth, retries=1))

        self.assertIn(1, data)
        self.assertIn(2, data)
