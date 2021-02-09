import hashlib
import os
import time
from unittest import mock
from uuid import uuid4

from flask import url_for
from pyfakefs.fake_filesystem_unittest import TestCase

from dimensigon.domain.entities import Server, Software, SoftwareServerAssociation, Transfer, \
    TransferStatus
from dimensigon.utils.helpers import md5
from dimensigon.web import db
from tests.base import ValidateResponseMixin, VirtualNetworkMixin, TwoNodeMixin


class TestSend(TwoNodeMixin, VirtualNetworkMixin, ValidateResponseMixin, TestCase):
    def setUp(self) -> None:
        # create the app with common test config
        self.source_path = '/software'
        self.filename = 'filename.zip'
        self.content = b'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
        self.size = len(self.content)
        self.checksum = hashlib.md5(self.content).hexdigest()
        self.dest_path = '/dest_repo'
        self.soft_id = str(uuid4())
        super().setUp()
        self.setUpPyfakefs()
        self.fs.create_dir(self.source_path)
        self.fs.create_dir(self.dest_path)
        self.fs.create_file(os.path.join(self.source_path, self.filename), contents=self.content)

    def fill_database(self):
        soft = Software(name='test_software', version=1, filename=self.filename, size=self.size,
                        checksum=self.checksum, id=self.soft_id)
        ssa = SoftwareServerAssociation(software=soft, server_id=self.SERVER1, path=self.source_path)
        db.session.add_all([soft, ssa])

    @mock.patch('dimensigon.web.api_1_0.resources.transfer.current_app')
    def test_send(self, mock_current_app):
        mock_current_app.dm.config.path.return_value = self.source_path
        server = Server.query.filter_by(name='node2').one()

        self.assertFalse(os.path.exists(os.path.join(self.dest_path, self.filename)))

        resp = self.client.post(url_for('api_1_0.send'),
                                json=dict(software_id=self.soft_id, dest_server_id=server.id,
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
