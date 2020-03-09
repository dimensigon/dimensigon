import hashlib
import os
import uuid
from unittest import TestCase
from unittest.mock import patch

from flask import url_for
from flask_jwt_extended import create_access_token

from dm.domain.entities import Software, SoftwareServerAssociation, Server, Transfer, TransferStatus
from dm.network.gateway import pack_msg, unpack_msg
from dm.web import create_app, set_variables, db


class TestTransferURL(TestCase):

    def setUp(self) -> None:
        self.app = create_app(dict(TESTING=True,
                                   SERVER_NAME='localhost',
                                   PORT=24000,
                                   SQLALCHEMY_DATABASE_URI='sqlite://',
                                   DM_PLAIN_DATA=True,
                                   SQLALCHEMY_TRACK_MODIFICATIONS=False,
                                   SECRET_KEY='my precious key'))
        with self.app.app_context():
            self.jwt_token = create_access_token(identity='test')
            self.auth_header = {'Authorization': f'Bearer {self.jwt_token}'}

        self.filename = 'test_software_v1'
        self.content = b'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'

        self.checksum_file = hashlib.md5(self.content).hexdigest()

        with self.app.app_context():
            db.create_all()
            set_variables()
            server = Server.query.get(self.app.server_id)
            soft = Software(name='test_software', version=1, size_bytes=62,
                            checksum=self.checksum_file)

            ssa = SoftwareServerAssociation(software=soft, server=server, path=os.path.join(os.getcwd(), self.filename))
            db.session.add(soft)
            db.session.add(ssa)
            db.session.commit()
            self.software_id = str(soft.id)

    def tearDown(self) -> None:
        from dm.web.api_1_0.urls.transfer import TEMPORAL_DIRECTORY
        import shutil
        if os.path.exists(os.path.join(os.getcwd(), self.filename)):
            os.remove(os.path.join(os.getcwd(), self.filename))
        if os.path.exists(os.path.join(os.getcwd(), TEMPORAL_DIRECTORY)):
            shutil.rmtree(TEMPORAL_DIRECTORY)
            # os.rmdir(TEMPORAL_DIRECTORY)

    @patch('flask_jwt_extended.view_decorators.verify_jwt_in_request')
    @patch('dm.web.api_1_0.resources.transfer.os.path.exists', return_value=False)
    @patch('dm.web.api_1_0.resources.transfer.os.makedirs', return_value=True)
    @patch('dm.web.api_1_0.resources.transfer.os.mkdir', return_value=True)
    def test_post_create_transfer(self, mock_mkdir, mock_makedirs, mock_exists, mock_jwt_required):

        client = self.app.test_client()
        with self.app.app_context():
            resp = client.post(url_for('api_1_0.transfers'),
                               json=pack_msg({"software_id": self.software_id, 'dest_path': os.getcwd(),
                                              'filename': self.filename, 'num_chunks': 16}), headers=self.auth_header)
            mock_mkdir.assert_called_once()
            self.assertEqual(202, resp.status_code)
            data = unpack_msg(resp.json)
            t: Transfer = Transfer.query.get(data.get('transfer_id'))
            self.assertEqual(self.filename, t.filename)
            self.assertEqual(uuid.UUID(self.software_id), t.software.id)
            self.assertEqual(16, t.num_chunks)
            self.assertEqual(os.getcwd(), t.dest_path)
            self.assertEqual(t.status, TransferStatus.WAITING_CHUNKS)

    def test_create_file(self):
        client = self.app.test_client()
        with self.app.app_context():
            resp = client.post(url_for('api_1_0.transfers'),
                               json=pack_msg({"software_id": self.software_id, 'dest_path': os.getcwd(),
                                              'filename': self.filename, 'num_chunks': 16}), headers=self.auth_header)

            self.assertEqual(202, resp.status_code)
            data = unpack_msg(resp.json)
            t: Transfer = Transfer.query.get(data.get('transfer_id'))
            self.assertEqual(self.filename, t.filename)
            self.assertEqual(uuid.UUID(self.software_id), t.software.id)
            self.assertEqual(16, t.num_chunks)
            self.assertEqual(os.getcwd(), t.dest_path)
            self.assertEqual(t.status, TransferStatus.WAITING_CHUNKS)
            # Generate put with files
            for chunk_content, chunk_id in zip([self.content[i:i + 4] for i in range(0, len(self.content), 4)],
                                               range(0, 16)):
                resp = client.post(url_for('api_1_0.transfer', transfer_id=str(t.id)),
                                   json=pack_msg(
                                       {"transfer_id": str(t.id), 'chunk': chunk_id, 'chunk_content': chunk_content}),
                                   headers=self.auth_header)
                self.assertEqual(resp.status_code, 201)

            self.assertEqual(t.status, TransferStatus.IN_PROGRESS)

            resp = client.patch(url_for('api_1_0.transfer', transfer_id=str(t.id), _external=False),
                                json={},
                                headers=self.auth_header)

            self.assertEqual(204, resp.status_code)
            self.assertEqual(t.status, TransferStatus.COMPLETED)

    def test_error_checksum(self):
        client = self.app.test_client()
        with self.app.app_context():
            resp = client.post(url_for('api_1_0.transfers'),
                               json=pack_msg({"software_id": self.software_id, 'dest_path': os.getcwd(),
                                              'filename': self.filename, 'num_chunks': 16}), headers=self.auth_header)

            self.assertEqual(202, resp.status_code)
            data = unpack_msg(resp.json)
            t: Transfer = Transfer.query.get(data.get('transfer_id'))
            self.assertEqual(self.filename, t.filename)
            self.assertEqual(uuid.UUID(self.software_id), t.software.id)
            self.assertEqual(16, t.num_chunks)
            self.assertEqual(os.getcwd(), t.dest_path)

            # Generate put with files
            self.content = b'abcdefghijklmnopqrstuvwxyzXXXDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
            for chunk_content, chunk_id in zip([self.content[i:i + 4] for i in range(0, len(self.content), 4)],
                                               range(0, 16)):
                resp = client.post(url_for('api_1_0.transfer', transfer_id=str(t.id)),
                                   json=pack_msg(
                                       {"transfer_id": str(t.id), 'chunk': chunk_id, 'chunk_content': chunk_content}),
                                   headers=self.auth_header)
                self.assertEqual(resp.status_code, 201)

            resp = client.patch(url_for('api_1_0.transfer', transfer_id=str(t.id), _external=False),
                                json={},
                                headers=self.auth_header)

            self.assertEqual(404, resp.status_code)
            self.assertDictEqual(
                {"error": f"Error on transfer '{str(t.id)}': Checksum error"},
                resp.get_json())
            self.assertEqual(t.status, TransferStatus.CHECKSUM_ERROR)

    def test_error_size_file(self):
        client = self.app.test_client()
        with self.app.app_context():
            resp = client.post(url_for('api_1_0.transfers'),
                               json=pack_msg({"software_id": self.software_id, 'dest_path': os.getcwd(),
                                              'filename': self.filename, 'num_chunks': 16}), headers=self.auth_header)

            self.assertEqual(202, resp.status_code)
            data = unpack_msg(resp.json)
            t: Transfer = Transfer.query.get(data.get('transfer_id'))
            self.assertEqual(self.filename, t.filename)
            self.assertEqual(uuid.UUID(self.software_id), t.software.id)
            self.assertEqual(16, t.num_chunks)
            self.assertEqual(os.getcwd(), t.dest_path)

            # Generate put with files
            self.content = b'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ012345678'
            for chunk_content, chunk_id in zip([self.content[i:i + 4] for i in range(0, len(self.content), 4)],
                                               range(0, 16)):
                resp = client.post(url_for('api_1_0.transfer', transfer_id=str(t.id)),
                                   json=pack_msg(
                                       {"transfer_id": str(t.id), 'chunk': chunk_id, 'chunk_content': chunk_content}),
                                   headers=self.auth_header)
                self.assertEqual(resp.status_code, 201)

            resp = client.patch(url_for('api_1_0.transfer', transfer_id=str(t.id), _external=False),
                                json={},
                                headers=self.auth_header)

            self.assertEqual(404, resp.status_code)
            self.assertDictEqual(
                {"error": f"Error on transfer '{str(t.id)}': Final file size does not match expected size"},
                resp.get_json())
            self.assertEqual(t.status, TransferStatus.SIZE_ERROR)