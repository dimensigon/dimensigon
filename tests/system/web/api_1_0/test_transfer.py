import base64
import hashlib
import os
from unittest import TestCase
from unittest.mock import patch

from flask import url_for
from flask_jwt_extended import create_access_token

from dm.domain.entities import Software, SoftwareServerAssociation, Server, Transfer, TransferStatus
from dm.domain.entities.bootstrap import set_initial
from dm.web import create_app, db
from dm.web.network import HTTPBearerAuth


class TestTransferURL(TestCase):

    def setUp(self) -> None:
        self.app = create_app('test')
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        self.auth = HTTPBearerAuth(create_access_token('test'))

        db.create_all()
        set_initial()
        db.session.commit()

        self.filename = 'test_software_v1'
        self.content = b'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
        self.size = len(self.content)

        self.checksum_file = hashlib.md5(self.content).hexdigest()

        self.server = Server.get_current()
        self.soft = Software(name='test_software', version=1, filename=self.filename, size=self.size,
                             checksum=self.checksum_file)

        self.ssa = SoftwareServerAssociation(software=self.soft, server=self.server,
                                             path=os.getcwd())
        db.session.add(self.soft)
        db.session.add(self.ssa)
        db.session.commit()

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()

        for folder, dirnames, filenames in os.walk(os.getcwd()):
            for filename in filenames:
                if filename.startswith(self.filename):
                    os.remove(os.path.join(folder, filename))

    @patch('flask_jwt_extended.view_decorators.verify_jwt_in_request')
    @patch('dm.web.api_1_0.urls.transfer.os.path.exists', return_value=False)
    @patch('dm.web.api_1_0.urls.transfer.os.makedirs', return_value=True)
    def test_post_create_transfer(self, mock_makedirs, mock_exists, mock_jwt_required):

        resp = self.client.post(url_for('api_1_0.transfers'),
                                json={"software_id": str(self.soft.id), 'dest_path': os.getcwd(),
                                      'num_chunks': 16}, headers=self.auth.header)
        self.assertEqual(202, resp.status_code)
        data = resp.json
        t: Transfer = Transfer.query.get(data.get('transfer_id'))
        self.assertEqual(self.soft.id, t.software.id)
        self.assertEqual(16, t.num_chunks)
        self.assertEqual(os.getcwd(), t.dest_path)
        self.assertEqual(t.status, TransferStatus.WAITING_CHUNKS)

    def test_send_software(self):

        resp = self.client.post(url_for('api_1_0.transfers'),
                                json={"software_id": str(self.soft.id), 'dest_path': os.getcwd(),
                                      'num_chunks': 16}, headers=self.auth.header)

        self.assertEqual(202, resp.status_code)
        data = resp.json
        t: Transfer = Transfer.query.get(data.get('transfer_id'))
        self.assertEqual(self.soft.id, t.software.id)
        self.assertEqual(16, t.num_chunks)
        self.assertEqual(os.getcwd(), t.dest_path)
        self.assertEqual(t.status, TransferStatus.WAITING_CHUNKS)
        # Generate put with files
        for chunk_content, chunk_id in zip([self.content[i:i + 4] for i in range(0, len(self.content), 4)],
                                           range(0, 16)):
            resp = self.client.post(url_for('api_1_0.transfer', transfer_id=str(t.id)),
                                    json={"transfer_id": str(t.id), 'chunk': chunk_id,
                                          'content': base64.b64encode(chunk_content).decode('ascii')},
                                    headers=self.auth.header)
            self.assertEqual(resp.status_code, 201)

        self.assertEqual(t.status, TransferStatus.IN_PROGRESS)

        resp = self.client.patch(url_for('api_1_0.transfer', transfer_id=str(t.id), _external=False),
                                 json={},
                                 headers=self.auth.header)

        self.assertEqual(204, resp.status_code)
        self.assertEqual(t.status, TransferStatus.COMPLETED)

    def test_send_file(self):

        resp = self.client.post(url_for('api_1_0.transfers'),
                                json={'dest_path': os.getcwd(), 'filename': self.filename, 'size': self.size,
                                      'checksum': self.checksum_file,
                                      'num_chunks': 16}, headers=self.auth.header)

        self.assertEqual(202, resp.status_code)
        data = resp.json
        t: Transfer = Transfer.query.get(data.get('transfer_id'))
        self.assertEqual(16, t.num_chunks)
        self.assertEqual(os.getcwd(), t.dest_path)
        self.assertEqual(t.status, TransferStatus.WAITING_CHUNKS)
        # Generate put with files
        for chunk_content, chunk_id in zip([self.content[i:i + 4] for i in range(0, len(self.content), 4)],
                                           range(0, 16)):
            resp = self.client.post(url_for('api_1_0.transfer', transfer_id=str(t.id)),
                                    json={"transfer_id": str(t.id), 'chunk': chunk_id,
                                          'content': base64.b64encode(chunk_content).decode('ascii')},
                                    headers=self.auth.header)
            self.assertEqual(resp.status_code, 201)

        self.assertEqual(t.status, TransferStatus.IN_PROGRESS)

        resp = self.client.patch(url_for('api_1_0.transfer', transfer_id=str(t.id), _external=False),
                                 json={},
                                 headers=self.auth.header)

        self.assertEqual(204, resp.status_code)
        self.assertEqual(t.status, TransferStatus.COMPLETED)

    def test_create_file_error_chunks(self):
        resp = self.client.post(url_for('api_1_0.transfers'),
                                json={"software_id": str(self.soft.id), 'dest_path': os.getcwd(),
                                      'num_chunks': 16}, headers=self.auth.header)

        self.assertEqual(202, resp.status_code)
        data = resp.json
        t: Transfer = Transfer.query.get(data.get('transfer_id'))
        self.assertEqual(self.soft.id, t.software.id)
        self.assertEqual(16, t.num_chunks)
        self.assertEqual(os.getcwd(), t.dest_path)
        self.assertEqual(t.status, TransferStatus.WAITING_CHUNKS)
        # Generate put with files
        for chunk_content, chunk_id in zip([self.content[i:i + 4] for i in range(0, len(self.content), 4)],
                                           [0, 1, 2, 3, 4, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]):
            resp = self.client.post(url_for('api_1_0.transfer', transfer_id=str(t.id)),
                                    json=
                                    {"transfer_id": str(t.id), 'chunk': chunk_id,
                                     'content': base64.b64encode(chunk_content).decode('ascii')},
                                    headers=self.auth.header)
            self.assertEqual(resp.status_code, 201)

        self.assertEqual(t.status, TransferStatus.IN_PROGRESS)

        resp = self.client.patch(url_for('api_1_0.transfer', transfer_id=str(t.id), _external=False),
                                 json={},
                                 headers=self.auth.header)

        self.assertEqual(404, resp.status_code)
        self.assertDictEqual({"error": f"Not enough chunks to generate file"}, resp.json)
        self.assertEqual(t.status, TransferStatus.IN_PROGRESS)

    def test_error_checksum(self):

        resp = self.client.post(url_for('api_1_0.transfers'),
                                json=({"software_id": str(self.soft.id), 'dest_path': os.getcwd(),
                                       'num_chunks': 16}), headers=self.auth.header)

        self.assertEqual(202, resp.status_code)
        data = resp.json
        t: Transfer = Transfer.query.get(data.get('transfer_id'))
        self.assertEqual(self.soft.id, t.software.id)
        self.assertEqual(16, t.num_chunks)
        self.assertEqual(os.getcwd(), t.dest_path)

        # Generate put with files
        self.content = b'abcdefghijklmnopqrstuvwxyzXXXDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
        for chunk_content, chunk_id in zip([self.content[i:i + 4] for i in range(0, len(self.content), 4)],
                                           range(0, 16)):
            resp = self.client.post(url_for('api_1_0.transfer', transfer_id=str(t.id)),
                                    json=
                                    {"transfer_id": str(t.id), 'chunk': chunk_id,
                                     'content': base64.b64encode(chunk_content).decode('ascii')},
                                    headers=self.auth.header)
            self.assertEqual(resp.status_code, 201)

        resp = self.client.patch(url_for('api_1_0.transfer', transfer_id=str(t.id), _external=False),
                                 json={},
                                 headers=self.auth.header)

        self.assertEqual(404, resp.status_code)
        self.assertDictEqual(
            {"error": f"Error on transfer '{str(t.id)}': Checksum error"},
            resp.get_json())
        self.assertEqual(t.status, TransferStatus.CHECKSUM_ERROR)

    def test_error_size_file(self):

        resp = self.client.post(url_for('api_1_0.transfers'),
                                json={"software_id": str(self.soft.id), 'dest_path': os.getcwd(),
                                      'num_chunks': 16}, headers=self.auth.header)

        self.assertEqual(202, resp.status_code)
        data = resp.json
        t: Transfer = Transfer.query.get(data.get('transfer_id'))
        self.assertEqual(self.soft.id, t.software.id)
        self.assertEqual(16, t.num_chunks)
        self.assertEqual(os.getcwd(), t.dest_path)

        # Generate put with files
        self.content = b'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ012345678'
        for chunk_content, chunk_id in zip([self.content[i:i + 4] for i in range(0, len(self.content), 4)],
                                           range(0, 16)):
            resp = self.client.post(url_for('api_1_0.transfer', transfer_id=str(t.id)),
                                    json=
                                    {"transfer_id": str(t.id), 'chunk': chunk_id,
                                     'content': base64.b64encode(chunk_content).decode('ascii')},
                                    headers=self.auth.header)
            self.assertEqual(resp.status_code, 201)

        resp = self.client.patch(url_for('api_1_0.transfer', transfer_id=str(t.id), _external=False),
                                 json={},
                                 headers=self.auth.header)

        self.assertEqual(404, resp.status_code)
        self.assertDictEqual(
            {"error": f"Error on transfer '{str(t.id)}': Final file size does not match expected size"},
            resp.get_json())
        self.assertEqual(t.status, TransferStatus.SIZE_ERROR)

    @patch('dm.web.api_1_0.urls.transfer.os.path.exists')
    def test_error_file_already_exists(self, mock_exists):
        mock_exists.return_value = True

        resp = self.client.post(url_for('api_1_0.transfers'),
                                json={"software_id": str(self.soft.id), 'dest_path': os.getcwd(),
                                      'num_chunks': 16}, headers=self.auth.header)

        self.assertEqual(409, resp.status_code)

    @patch('dm.web.api_1_0.urls.transfer.os.remove')
    @patch('dm.web.api_1_0.urls.transfer.os.path.exists')
    def test_force(self, mock_exists, mock_remove):
        mock_exists.return_value = True

        resp = self.client.post(url_for('api_1_0.transfers'),
                                json={"software_id": str(self.soft.id), 'dest_path': os.getcwd(),
                                      'num_chunks': 16, 'force': True}, headers=self.auth.header)

        self.assertEqual(202, resp.status_code)
        mock_remove.assert_called_once_with(os.path.join(os.getcwd(), self.soft.filename))
