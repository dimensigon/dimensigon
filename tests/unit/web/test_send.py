import hashlib
import os
from unittest import mock, TestCase

from flask import url_for
from flask_jwt_extended import create_access_token

from dm.domain.entities import Server, Software, SoftwareServerAssociation
from dm.domain.entities import User
from dm.domain.entities.bootstrap import set_initial
from dm.network.auth import HTTPBearerAuth
from dm.web import create_app, db, errors
from dm.web.network import Response
from tests.helpers import ValidateResponseMixin


class Test(TestCase, ValidateResponseMixin):
    def setUp(self):
        """Create and configure a new app instance for each test."""
        # create the app with common test config
        self.app = create_app('test')
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        db.create_all()
        set_initial()
        self.auth = HTTPBearerAuth(create_access_token(User.get_by_user('root').id))

        self.source_path = '/software'
        self.filename = 'filename.zip'
        self.content = b'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
        self.size = len(self.content)
        self.checksum = hashlib.md5(self.content).hexdigest()
        self.dest_path = '/dest_repo'

        self.soft = Software(name='test_software', version=1, filename=self.filename, size=self.size,
                             checksum=self.checksum)
        self.ssa = SoftwareServerAssociation(software=self.soft, server=Server.get_current(), path=self.source_path)
        self.node2 = Server('node2', port=5000)
        db.session.add_all([self.soft, self.ssa, self.node2])
        db.session.commit()

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    @mock.patch('dm.web.api_1_0.urls.use_cases.os.path.exists', autospec=True)
    @mock.patch('dm.web.api_1_0.urls.use_cases.async_send_file', autospec=True)
    @mock.patch('dm.web.api_1_0.urls.use_cases.post', autospec=True)
    def test_send_software(self, mock_post, mock_send_file, mock_exists):
        mock_post.return_value = Response(msg={'transfer_id': '1'}, code=200)
        mock_exists.return_value = True

        resp = self.client.post(url_for('api_1_0.send'),
                                json=dict(software_id=str(self.soft.id), dest_server_id=str(self.node2.id),
                                          dest_path=self.dest_path),
                                headers=self.auth.header)

        mock_post.assert_called_once()
        server, view = mock_post.call_args[0]
        kwargs = mock_post.call_args[1]
        self.assertEqual(self.node2, db.session.merge(server))
        self.assertDictEqual({'software_id': str(self.soft.id), 'num_chunks': 1,
                              'dest_path': self.dest_path}, kwargs['json'])
        self.assertEqual(202, resp.status_code)
        self.assertDictEqual({'transfer_id': '1'}, resp.get_json())

    @mock.patch('dm.web.api_1_0.urls.use_cases.os.path.exists', autospec=True)
    @mock.patch('dm.web.api_1_0.urls.use_cases.async_send_file', autospec=True)
    @mock.patch('dm.web.api_1_0.urls.use_cases.post', autospec=True)
    def test_send_foreground(self, mock_post, mock_send_file, mock_exists):
        mock_post.return_value = Response(msg={'transfer_id': '1'}, code=200)
        mock_exists.return_value = True

        resp = self.client.post(url_for('api_1_0.send'),
                                json=dict(software_id=str(self.soft.id), dest_server_id=str(self.node2.id),
                                          dest_path=self.dest_path, background=False),
                                headers=self.auth.header)

        mock_post.assert_called_once()
        server, view = mock_post.call_args[0]
        kwargs = mock_post.call_args[1]
        self.assertEqual(self.node2, db.session.merge(server))
        self.assertDictEqual({'software_id': str(self.soft.id), 'num_chunks': 1,
                              'dest_path': self.dest_path}, kwargs['json'])
        self.assertEqual(201, resp.status_code)
        self.assertDictEqual({'transfer_id': '1'}, resp.get_json())

    @mock.patch('dm.web.api_1_0.urls.use_cases.md5', autospec=True)
    @mock.patch('dm.web.api_1_0.urls.use_cases.os.path.getsize', autospec=True)
    @mock.patch('dm.web.api_1_0.urls.use_cases.os.path.exists', autospec=True)
    @mock.patch('dm.web.api_1_0.urls.use_cases.async_send_file', autospec=True)
    @mock.patch('dm.web.api_1_0.urls.use_cases.post', autospec=True)
    def test_send_file(self, mock_post, mock_send_file, mock_exists, mock_getsize, mock_md5):
        mock_post.return_value = Response(msg={'transfer_id': '1'}, code=200)
        mock_exists.return_value = True
        mock_getsize.return_value = self.size
        mock_md5.return_value = self.checksum

        resp = self.client.post(url_for('api_1_0.send'),
                                json=dict(file=os.path.join(self.source_path, self.filename),
                                          dest_server_id=str(self.node2.id),
                                          dest_path=self.dest_path),
                                headers=self.auth.header)

        mock_post.assert_called_once()
        server, view = mock_post.call_args[0]
        kwargs = mock_post.call_args[1]
        self.assertEqual(self.node2, db.session.merge(server))
        self.assertDictEqual({'filename': self.filename, 'num_chunks': 1, 'dest_path': self.dest_path,
                              'checksum': self.checksum, 'size': self.size},
                             kwargs['json'])
        self.assertEqual(202, resp.status_code)
        self.assertDictEqual({'transfer_id': '1'}, resp.get_json())

    @mock.patch('dm.web.api_1_0.urls.use_cases.os.path.exists', autospec=True)
    @mock.patch('dm.web.api_1_0.urls.use_cases.async_send_file', autospec=True)
    @mock.patch('dm.web.api_1_0.urls.use_cases.post', autospec=True)
    def test_send_SoftwareServerNotFound(self, mock_post, mock_send_file, mock_exists):
        mock_post.return_value = Response(msg={'transfer_id': '1'}, code=200)
        mock_exists.return_value = True
        db.session.delete(self.ssa)
        db.session.commit()

        resp = self.client.post(url_for('api_1_0.send'),
                                json=dict(software_id=str(self.soft.id), dest_server_id=str(self.node2.id),
                                          dest_path=self.dest_path),
                                headers=self.auth.header)

        self.validate_error_response(resp, errors.SoftwareServerNotFound(str(self.soft.id), str(self.node2.id)))

    @mock.patch('dm.web.api_1_0.urls.use_cases.os.path.exists', autospec=True)
    @mock.patch('dm.web.api_1_0.urls.use_cases.async_send_file', autospec=True)
    @mock.patch('dm.web.api_1_0.urls.use_cases.post', autospec=True)
    def test_send_software_FileNotFound(self, mock_post, mock_send_file, mock_exists):
        mock_post.return_value = Response(msg={'transfer_id': '1'}, code=200)
        mock_exists.return_value = False

        resp = self.client.post(url_for('api_1_0.send'),
                                json=dict(software_id=str(self.soft.id), dest_server_id=str(self.node2.id),
                                          dest_path=self.dest_path),
                                headers=self.auth.header)

        self.validate_error_response(resp, errors.FileNotFound(os.path.join(self.source_path, self.filename)))

    @mock.patch('dm.web.api_1_0.urls.use_cases.md5', autospec=True)
    @mock.patch('dm.web.api_1_0.urls.use_cases.os.path.getsize', autospec=True)
    @mock.patch('dm.web.api_1_0.urls.use_cases.os.path.exists', autospec=True)
    @mock.patch('dm.web.api_1_0.urls.use_cases.async_send_file', autospec=True)
    @mock.patch('dm.web.api_1_0.urls.use_cases.post', autospec=True)
    def test_send_file_FileNotFound(self, mock_post, mock_send_file, mock_exists, mock_getsize, mock_md5):
        mock_post.return_value = Response(msg={'transfer_id': '1'}, code=200)
        mock_exists.return_value = False
        mock_getsize.return_value = self.size
        mock_md5.return_value = self.checksum

        resp = self.client.post(url_for('api_1_0.send'),
                                json=dict(file=os.path.join(self.source_path, self.filename),
                                          dest_server_id=str(self.node2.id),
                                          dest_path=self.dest_path),
                                headers=self.auth.header)

        self.validate_error_response(resp, errors.FileNotFound(os.path.join(self.source_path, self.filename)))

    @mock.patch('dm.web.api_1_0.urls.use_cases.get', autospec=True)
    @mock.patch('dm.web.api_1_0.urls.use_cases.os.path.exists', autospec=True)
    @mock.patch('dm.web.api_1_0.urls.use_cases.async_send_file', autospec=True)
    @mock.patch('dm.web.api_1_0.urls.use_cases.post', autospec=True)
    def test_send_software_get_transfer_data(self, mock_post, mock_send_file, mock_exists, mock_get):
        mock_post.return_value = Response(msg={'transfer_id': '1'}, code=200)
        mock_exists.return_value = True
        mock_get.return_value = Response(msg={'transfer_id': '1', 'status': 'COMPLETED'}, code=200)

        resp = self.client.post(url_for('api_1_0.send'),
                                json=dict(software_id=str(self.soft.id), dest_server_id=str(self.node2.id),
                                          dest_path=self.dest_path, include_transfer_data=True),
                                headers=self.auth.header)

        mock_get.assert_called_once()
        server, view = mock_get.call_args[0]
        kwargs = mock_get.call_args[1]
        self.assertEqual(self.node2, db.session.merge(server))
        self.assertEqual('api_1_0.transferresource', view)
        self.assertDictEqual({'transfer_id': '1'}, kwargs['view_data'])

        self.assertEqual(202, resp.status_code)
        self.assertDictEqual({'transfer_id': '1', 'status': 'COMPLETED'}, resp.get_json())

        mock_get.return_value = Response(msg={'error': {'message': 'some error content'}}, code=404)

        resp = self.client.post(url_for('api_1_0.send'),
                                json=dict(software_id=str(self.soft.id), dest_server_id=str(self.node2.id),
                                          dest_path=self.dest_path, include_transfer_data=True),
                                headers=self.auth.header)

        self.validate_error_response(resp, errors.HTTPError(mock_get.return_value))