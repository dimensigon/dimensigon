import base64
import hashlib
import os
from unittest.mock import patch

from flask import url_for
from flask_jwt_extended import create_access_token
from pyfakefs.fake_filesystem_unittest import TestCase

from dimensigon.domain.entities import Software, SoftwareServerAssociation, Server, Transfer, TransferStatus
from dimensigon.domain.entities.bootstrap import set_initial
from dimensigon.network.auth import HTTPBearerAuth
from dimensigon.web import create_app, db


class TestTransferList(TestCase):

    def setUp(self) -> None:
        self.app = create_app('test')
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        self.auth = HTTPBearerAuth(create_access_token('00000000-0000-0000-0000-000000000001'))

        db.create_all()
        set_initial()
        db.session.commit()

        self.source_path = '/software'
        self.filename = 'filename.zip'
        self.content = b'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
        self.size = len(self.content)
        self.checksum = hashlib.md5(self.content).hexdigest()

        self.server = Server.get_current()
        self.soft = Software(name='test_software', version=1, filename='software.zip', size=self.size,
                             checksum=self.checksum)

        self.ssa = SoftwareServerAssociation(software=self.soft, server=self.server,
                                             path=self.source_path)

        self.dest_path = '/dest_repo'

        db.session.add(self.soft)
        db.session.add(self.ssa)
        db.session.commit()

        self.setUpPyfakefs()
        self.fs.create_dir(self.source_path)
        self.fs.create_dir(self.dest_path)
        self.fs.create_file(os.path.join(self.source_path, self.filename), contents=self.content)
        self.fs.create_file(os.path.join(self.source_path, self.soft.filename), contents=self.content)

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()

    def test_get_transfers(self):
        t = Transfer(software=self.soft, dest_path=self.dest_path, num_chunks=16, status=TransferStatus.IN_PROGRESS)
        db.session.add(t)
        db.session.commit()
        resp = self.client.get(url_for('api_1_0.transferlist'), headers=self.auth.header)

        self.assertEqual(200, resp.status_code)
        self.assertListEqual([t.to_json()], resp.get_json())

    def test_post_create_software_transfer(self):
        self.fs.create_file(os.path.join('/new_dest_path', self.soft.filename + '_chunk.1'))
        resp = self.client.post(url_for('api_1_0.transferlist'),
                                json={"software_id": str(self.soft.id),
                                      'dest_path': '/new_dest_path',
                                      'num_chunks': 16}, headers=self.auth.header)
        self.assertEqual(202, resp.status_code)
        data = resp.json
        t: Transfer = Transfer.query.get(data.get('id'))
        self.assertEqual(self.soft.id, t.software.id)
        self.assertEqual(16, t.num_chunks)
        self.assertEqual('/new_dest_path', t.dest_path)
        self.assertEqual(t.status, TransferStatus.WAITING_CHUNKS)

        self.assertFalse(os.path.exists(os.path.join('/new_dest_path', self.soft.filename + '_chunk.1')))

    def test_post_create_software_transfer_with_chunks_already_inside(self):
        self.fs.create_file(os.path.join(self.dest_path, self.soft.filename + '_chunk.1'))
        resp = self.client.post(url_for('api_1_0.transferlist'),
                                json={"software_id": str(self.soft.id),
                                      'dest_path': self.dest_path,
                                      'num_chunks': 16}, headers=self.auth.header)
        self.assertEqual(202, resp.status_code)
        data = resp.json
        t: Transfer = Transfer.query.get(data.get('id'))
        self.assertEqual(self.soft.id, t.software.id)
        self.assertEqual(16, t.num_chunks)
        self.assertEqual(self.dest_path, t.dest_path)
        self.assertEqual(t.status, TransferStatus.WAITING_CHUNKS)

        self.assertFalse(os.path.exists(os.path.join(self.dest_path, self.soft.filename + '_chunk.1')))

    def test_post_create_software_transfer_with_pending_transfer(self, ):
        t = Transfer(software=self.soft, dest_path=self.dest_path, num_chunks=16, status=TransferStatus.IN_PROGRESS)
        db.session.add(t)
        db.session.commit()

        resp = self.client.post(url_for('api_1_0.transferlist'),
                                json={"software_id": str(self.soft.id), 'dest_path': self.dest_path,
                                      'num_chunks': 16}, headers=self.auth.header)
        self.assertEqual(409, resp.status_code)
        self.assertDictEqual({"error": f"There is already a transfer sending software {self.soft.id}"}, resp.get_json())

    def test_post_create_software_transfer_with_pending_transfer_cancel(self):
        t = Transfer(software=self.soft, dest_path=self.dest_path, num_chunks=16, status=TransferStatus.IN_PROGRESS)
        db.session.add(t)
        db.session.commit()

        resp = self.client.post(url_for('api_1_0.transferlist'),
                                json={"software_id": str(self.soft.id), 'dest_path': self.dest_path,
                                      'num_chunks': 16, 'cancel_pending': True}, headers=self.auth.header)
        self.assertEqual(202, resp.status_code)
        self.assertEqual(TransferStatus.CANCELLED, t.status)

    def test_post_create_filename_transfer_with_pending_transfer(self):
        t = Transfer(software=self.filename, size=self.size, checksum=self.checksum, dest_path=self.dest_path,
                     num_chunks=16, status=TransferStatus.IN_PROGRESS)
        db.session.add(t)
        db.session.commit()

        resp = self.client.post(url_for('api_1_0.transferlist'),
                                json={"filename": self.filename,
                                      'size': self.size,
                                      'checksum': self.checksum,
                                      'dest_path': self.dest_path,
                                      'num_chunks': 16}, headers=self.auth.header)
        self.assertEqual(409, resp.status_code)
        self.assertDictEqual(
            {"error": f"There is already a transfer sending file {os.path.join(self.dest_path, self.filename)}"},
            resp.get_json())

    def test_post_create_filename_transfer_with_pending_transfer_cancel(self):
        t = Transfer(software=self.filename, size=self.size, checksum=self.checksum, dest_path=self.dest_path,
                     num_chunks=16, status=TransferStatus.IN_PROGRESS)
        db.session.add(t)
        db.session.commit()

        resp = self.client.post(url_for('api_1_0.transferlist'),
                                json={"filename": self.filename,
                                      'size': self.size,
                                      'checksum': self.checksum,
                                      'dest_path': self.dest_path,
                                      'num_chunks': 16,
                                      'cancel_pending': True}, headers=self.auth.header)
        self.assertEqual(202, resp.status_code)
        self.assertEqual(TransferStatus.CANCELLED, t.status)

    def test_post_filename_and_software_not_specified(self, ):
        resp = self.client.post(url_for('api_1_0.transferlist'),
                                json={'filename': self.filename,
                                      'dest_path': self.dest_path,
                                      'num_chunks': 16}, headers=self.auth.header)
        self.assertEqual(404, resp.status_code)
        self.assertDictEqual({'error': 'size and checksum must be specified when a filename set'}, resp.get_json())

        resp = self.client.post(url_for('api_1_0.transferlist'),
                                json={'filename': self.filename,
                                      'size': self.size,
                                      'dest_path': self.dest_path,
                                      'num_chunks': 16}, headers=self.auth.header)
        self.assertEqual(404, resp.status_code)
        self.assertDictEqual({'error': 'size and checksum must be specified when a filename set'}, resp.get_json())

        resp = self.client.post(url_for('api_1_0.transferlist'),
                                json={'filename': self.filename,
                                      'checksum': self.checksum,
                                      'dest_path': self.dest_path,
                                      'num_chunks': 16}, headers=self.auth.header)
        self.assertEqual(404, resp.status_code)
        self.assertDictEqual({'error': 'size and checksum must be specified when a filename set'}, resp.get_json())

    def test_post_filename_without_size_or_checksum(self):
        resp = self.client.post(url_for('api_1_0.transferlist'),
                                json={'dest_path': self.dest_path,
                                      'num_chunks': 16}, headers=self.auth.header)
        self.assertEqual(404, resp.status_code)
        self.assertDictEqual({'error': 'Neither filename nor software specified for the transfer'}, resp.get_json())

    def test_post_file_exists(self):
        self.fs.create_file(os.path.join(self.dest_path, self.filename))
        self.fs.create_file(os.path.join(self.dest_path, self.soft.filename))

        resp = self.client.post(url_for('api_1_0.transferlist'),
                                json={"filename": self.filename,
                                      'size': self.size,
                                      'checksum': self.checksum,
                                      'dest_path': self.dest_path,
                                      'num_chunks': 16}, headers=self.auth.header)
        self.assertEqual(409, resp.status_code)
        self.assertDictEqual({"error": "File already exists. Use force=True if needed"}, resp.get_json())

        resp = self.client.post(url_for('api_1_0.transferlist'),
                                json={"software_id": str(self.soft.id),
                                      'dest_path': self.dest_path,
                                      'num_chunks': 16}, headers=self.auth.header)
        self.assertEqual(409, resp.status_code)
        self.assertDictEqual({"error": "File already exists. Use force=True if needed"}, resp.get_json())

    def test_post_file_exists_force(self):
        self.fs.create_file(os.path.join(self.dest_path, self.filename))
        resp = self.client.post(url_for('api_1_0.transferlist'),
                                json={"filename": self.filename,
                                      'size': self.size,
                                      'checksum': self.checksum,
                                      'dest_path': self.dest_path,
                                      'num_chunks': 16,
                                      'force': False}, headers=self.auth.header)
        self.assertEqual(409, resp.status_code)
        self.assertDictEqual({"error": "File already exists. Use force=True if needed"}, resp.get_json())

        resp = self.client.post(url_for('api_1_0.transferlist'),
                                json={"filename": self.filename,
                                      'size': self.size,
                                      'checksum': self.checksum,
                                      'dest_path': self.dest_path,
                                      'num_chunks': 16,
                                      'force': True}, headers=self.auth.header)
        self.assertEqual(202, resp.status_code)
        self.assertFalse(os.path.exists(os.path.join(self.dest_path, self.filename)))

        self.fs.create_file(os.path.join(self.dest_path, self.soft.filename))

        with patch('dimensigon.web.api_1_0.resources.transfer.os.remove') as mock_remove:
            mock_remove.side_effect = PermissionError('Not allowed')

            resp = self.client.post(url_for('api_1_0.transferlist'),
                                    json={'software_id': str(self.soft.id),
                                          'dest_path': self.dest_path,
                                          'num_chunks': 16,
                                          'force': True}, headers=self.auth.header)
            self.assertEqual(500, resp.status_code)
            file = os.path.join(self.dest_path, self.soft.filename)
            self.assertDictEqual({"error": f"Unable to remove {file}: Not allowed"}, resp.get_json())

    def test_post_create_transfer_error_with_pending_transfer(self):
        t = Transfer(software=self.soft, dest_path=self.dest_path, num_chunks=16, status=TransferStatus.IN_PROGRESS)
        db.session.add(t)
        db.session.commit()

        resp = self.client.post(url_for('api_1_0.transferlist'),
                                json={"software_id": str(self.soft.id), 'dest_path': self.dest_path,
                                      'num_chunks': 16}, headers=self.auth.header)
        self.assertEqual(409, resp.status_code)
        self.assertDictEqual({"error": f"There is already a transfer sending software {self.soft.id}"}, resp.get_json())

    @patch('dimensigon.web.api_1_0.resources.transfer.os.makedirs', autospec=True)
    def test_post_create_software_error_on_create_dest_folder(self, mock_makedirs):
        mock_makedirs.side_effect = PermissionError('Not allowed')
        resp = self.client.post(url_for('api_1_0.transferlist'),
                                json={"software_id": str(self.soft.id),
                                      'dest_path': self.dest_path,
                                      'num_chunks': 16}, headers=self.auth.header)
        self.assertEqual(500, resp.status_code)
        self.assertDictEqual({'error': f"Unable to create dest path {self.dest_path}: Not allowed"}, resp.get_json())


class TestTransferResource(TestCase):

    def setUp(self) -> None:
        self.setUpPyfakefs()
        self.app = create_app('test')
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        self.auth = HTTPBearerAuth(create_access_token('00000000-0000-0000-0000-000000000001'))

        db.create_all()
        set_initial()
        db.session.commit()

        self.source_path = '/software'
        self.filename = 'filename.zip'
        self.content = b'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
        self.size = len(self.content)
        self.checksum = hashlib.md5(self.content).hexdigest()
        self.dest_path = '/dest_repo'

        self.fs.create_dir(self.source_path)
        self.fs.create_dir(self.dest_path)
        self.fs.create_file(os.path.join(self.source_path, self.filename), contents=self.content)

        self.server = Server.get_current()
        self.transfer = Transfer(software=self.filename, size=self.size, checksum=self.checksum,
                                 dest_path=self.dest_path,
                                 num_chunks=16, status=TransferStatus.WAITING_CHUNKS)
        db.session.add(self.transfer)
        db.session.commit()

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()

    def test_get_transfer(self):
        resp = self.client.get(url_for('api_1_0.transferresource', transfer_id=str(self.transfer.id)),
                               headers=self.auth.header)
        self.assertEqual(200, resp.status_code)
        self.assertDictEqual(self.transfer.to_json(), resp.get_json())

        resp = self.client.get(url_for('api_1_0.transferresource', transfer_id='aaaaaaaa-1234-5678-1234-56781234aaa1'),
                               headers=self.auth.header)
        self.assertEqual(404, resp.status_code)

    def test_post_transfer(self):
        self.assertIsNone(self.transfer.started_on)
        resp = self.client.post(url_for('api_1_0.transferresource', transfer_id=str(self.transfer.id)),
                                json={'chunk': 0,
                                      'content': base64.b64encode(b'abcd').decode('ascii')},
                                headers=self.auth.header)

        self.assertEqual(201, resp.status_code)
        db.session.refresh(self.transfer)
        self.assertDictEqual({'message': f"Chunk 0 from transfer {str(self.transfer.id)} generated successfully"},
                             resp.get_json())
        self.assertEqual(TransferStatus.IN_PROGRESS, self.transfer.status)
        self.assertIsNotNone(self.transfer.started_on)
        self.assertTrue(os.path.exists(os.path.join(self.dest_path, f"{self.filename}_chunk.0")))

    def test_post_create_filename_one_chunk(self):
        self.transfer.num_chunks = 1
        db.session.commit()
        resp = self.client.post(url_for('api_1_0.transferresource', transfer_id=str(self.transfer.id)),
                                json={'chunk': 1,
                                      'content': base64.b64encode(self.content).decode('ascii')},
                                headers=self.auth.header)
        self.assertEqual(201, resp.status_code)
        self.assertDictEqual(
            {'message': f"File {self.filename} from transfer {str(self.transfer.id)} generated successfully"},
            resp.get_json())
        self.assertTrue(os.path.exists(os.path.join(self.dest_path, self.filename)))

    def test_put_transfer_file(self):
        self.transfer.status = TransferStatus.IN_PROGRESS
        db.session.commit()
        for chunk_content, chunk_id in zip([self.content[i:i + 4] for i in range(0, len(self.content), 4)],
                                           range(0, 16)):
            self.fs.create_file(os.path.join(self.dest_path, f"{self.filename}_chunk.{chunk_id}"))
            with open(os.path.join(self.dest_path, f"{self.filename}_chunk.{chunk_id}"), 'wb') as fh:
                fh.write(chunk_content)

        resp = self.client.put(url_for('api_1_0.transferresource', transfer_id=str(self.transfer.id)),
                                 headers=self.auth.header)
        self.assertEqual(201, resp.status_code)
        self.assertDictEqual({'message': f"File {os.path.join(self.dest_path, self.filename)} from transfer "
                                         f"{self.transfer.id} recived successfully"}, resp.get_json())
        self.assertTrue(os.path.exists(os.path.join(self.dest_path, self.filename)))
        with open(os.path.join(self.dest_path, self.filename), 'rb') as fh:
            self.assertEqual(self.content, fh.read())

    def test_put_transfer_status_completed(self):
        self.transfer.status = TransferStatus.COMPLETED
        db.session.commit()

        resp = self.client.put(url_for('api_1_0.transferresource', transfer_id=str(self.transfer.id)),
                                 headers=self.auth.header)
        self.assertEqual(410, resp.status_code)
        self.assertDictEqual({'error': 'Transfer has already completed'}, resp.get_json())

    def test_put_transfer_status_waiting_chunks(self):
        resp = self.client.put(url_for('api_1_0.transferresource', transfer_id=str(self.transfer.id)),
                                 headers=self.auth.header)
        self.assertEqual(406, resp.status_code)
        self.assertDictEqual({'error': 'Transfer still waiting for chunks'}, resp.get_json())

    def test_create_file_error_chunks(self):
        self.transfer.status = TransferStatus.IN_PROGRESS
        db.session.commit()
        # Generate put with files
        for chunk_content, chunk_id in zip([self.content[i:i + 4] for i in range(0, len(self.content), 4)],
                                           [0, 1, 2, 3, 4, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]):
            self.fs.create_file(os.path.join(self.dest_path, f"{self.filename}_chunk.{chunk_id}"))
            with open(os.path.join(self.dest_path, f"{self.filename}_chunk.{chunk_id}"), 'wb') as fh:
                fh.write(chunk_content)

        resp = self.client.put(
            url_for('api_1_0.transferresource', transfer_id=str(self.transfer.id), _external=False),
            json={},
            headers=self.auth.header)

        self.assertEqual(404, resp.status_code)
        self.assertDictEqual({"error": f"Not enough chunks to generate the file"}, resp.json)

    def test_create_file_error_no_chunk(self):
        self.transfer.status = TransferStatus.IN_PROGRESS
        db.session.commit()
        resp = self.client.put(
            url_for('api_1_0.transferresource', transfer_id=str(self.transfer.id), _external=False),
            json={},
            headers=self.auth.header)

        self.assertEqual(404, resp.status_code)
        self.assertDictEqual({"error": f"Any chunk found on {self.dest_path}"}, resp.json)

    def test_error_checksum(self):
        self.transfer.status = TransferStatus.IN_PROGRESS
        db.session.commit()
        # Generate put with files
        content = b'abcdefghijklmnopqrstuvwxyzXXXDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
        for chunk_content, chunk_id in zip([content[i:i + 4] for i in range(0, len(self.content), 4)],
                                           range(0, 16)):
            self.fs.create_file(os.path.join(self.dest_path, f"{self.filename}_chunk.{chunk_id}"))
            with open(os.path.join(self.dest_path, f"{self.filename}_chunk.{chunk_id}"), 'wb') as fh:
                fh.write(chunk_content)

        resp = self.client.put(
            url_for('api_1_0.transferresource', transfer_id=str(self.transfer.id), _external=False),
            json={},
            headers=self.auth.header)

        self.assertEqual(404, resp.status_code)
        db.session.refresh(self.transfer)
        self.assertDictEqual(
            {"error": f"Error on transfer '{str(self.transfer.id)}': Checksum error"},
            resp.get_json())
        self.assertEqual(self.transfer.status, TransferStatus.CHECKSUM_ERROR)

    def test_error_size_file(self):
        self.transfer.status = TransferStatus.IN_PROGRESS
        db.session.commit()
        # Generate put with files
        content = b'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ012345678'
        for chunk_content, chunk_id in zip([content[i:i + 4] for i in range(0, len(content), 4)],
                                           range(0, 16)):
            self.fs.create_file(os.path.join(self.dest_path, f"{self.filename}_chunk.{chunk_id}"))
            with open(os.path.join(self.dest_path, f"{self.filename}_chunk.{chunk_id}"), 'wb') as fh:
                fh.write(chunk_content)

        resp = self.client.put(
            url_for('api_1_0.transferresource', transfer_id=str(self.transfer.id), _external=False),
            json={},
            headers=self.auth.header)

        self.assertEqual(404, resp.status_code)
        db.session.refresh(self.transfer)
        self.assertDictEqual(
            {"error": f"Error on transfer '{str(self.transfer.id)}': Final file size does not match expected size"},
            resp.get_json())
        self.assertEqual(self.transfer.status, TransferStatus.SIZE_ERROR)
