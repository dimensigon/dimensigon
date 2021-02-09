import hashlib
import os
import re

from aioresponses import aioresponses, CallbackResult
from pyfakefs.fake_filesystem_unittest import TestCase

from dimensigon.domain.entities import Server, Transfer, TransferStatus
from dimensigon.utils.asyncio import run
from dimensigon.utils.helpers import md5
from dimensigon.web import db
from dimensigon.web.async_functions import async_send_file
from tests.base import TwoNodeMixin, virtual_network


class TestAsyncSendFile(TwoNodeMixin, TestCase):
    def setUp(self) -> None:
        self.source_path = '/software'
        self.filename = 'filename.zip'
        self.content = b'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
        self.size = len(self.content)
        self.checksum = hashlib.md5(self.content).hexdigest()
        self.dest_path = '/dest_repo'
        super().setUp()

        self.setUpPyfakefs()
        self.fs.create_dir(self.source_path)
        self.fs.create_dir(self.dest_path)
        self.fs.create_file(os.path.join(self.source_path, self.filename), contents=self.content)

    def test_async_send_file(self):
        with virtual_network(self.app, self.app2):
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

            run(async_send_file(dest_server=self.s2, transfer_id=transfer_id,
                                file=os.path.join(self.source_path, self.filename), chunk_size=4,
                                auth=self.auth))

            self.assertTrue(os.path.exists(os.path.join(self.dest_path, self.filename)))
            self.assertEqual(self.size, os.path.getsize(os.path.join(self.dest_path, self.filename)))
            self.assertEqual(self.checksum, md5(os.path.join(self.dest_path, self.filename)))

    def test_async_send_file_one_chunk(self):
        with virtual_network(self.app, self.app2):
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

            run(async_send_file(dest_server=self.s2, transfer_id=transfer_id,
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

        def put_callback_client(url, **kwargs):
            kwargs.pop('allow_redirects')

            r = self.client2.put(url.path, json=kwargs['json'], headers=kwargs['headers'])

            return CallbackResult('PUT', status=r.status_code, body=r.data, content_type=r.content_type,
                                  headers=r.headers)

        m.put(re.compile(Server.query.filter_by(name='node2').one().url() + '.*'), callback=put_callback_client,
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

        run(async_send_file(dest_server=self.s2, transfer_id=transfer_id,
                            file=os.path.join(self.source_path, self.filename), chunk_size=14,
                            auth=self.auth, retries=3))

        self.assertTrue(os.path.exists(os.path.join(self.dest_path, self.filename)))
        self.assertEqual(self.size, os.path.getsize(os.path.join(self.dest_path, self.filename)))
        self.assertEqual(self.checksum, md5(os.path.join(self.dest_path, self.filename)))
