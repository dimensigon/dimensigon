import json
import sqlite3
from unittest import TestCase, mock
from unittest.case import TestCase
from unittest.mock import Mock

import flask
import responses
from flask_jwt_extended import create_access_token

import dimensigon.use_cases
from dimensigon.domain.entities import User, ActionTemplate, Server, Software, SoftwareServerAssociation, Scope
from dimensigon.domain.entities.bootstrap import set_initial
from dimensigon.network.auth import HTTPBearerAuth
from dimensigon.use_cases.operations import RequestOperation, NativeWaitOperation, NativeSoftwareSendOperation
from dimensigon.web import create_app, db, errors
from dimensigon.web.network import Response
from tests.base import FlaskAppMixin


class TestNativeSoftwareSendOperation(TestCase):
    def setUp(self):
        """Create and configure a new app instance for each test."""
        # create the app with common test config
        self.app = create_app('test')
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        db.create_all()
        set_initial(user=True, action_template=True)
        self.server = Server.get_current()
        self.auth = HTTPBearerAuth(create_access_token(User.get_by_name('root').id))

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    @mock.patch('dimensigon.use_cases.operations.ntwrk.get')
    @mock.patch('dimensigon.use_cases.operations.ntwrk.post')
    def test_execute_send_software(self, mock_post, mock_get):
        at = ActionTemplate.query.get('00000000-0000-0000-000a-000000000001')
        soft = Software(name='test', version=1, filename='test.zip')
        node1 = Server('node1', port=5000)
        node2 = Server('node2', port=5000)
        ssa1 = SoftwareServerAssociation(software=soft, server=node1, path='/')
        ssa2 = SoftwareServerAssociation(software=soft, server=node2, path='/')
        ssa3 = SoftwareServerAssociation(software=soft, server=self.server, path='/')
        db.session.add_all([soft, node1, node2, ssa1, ssa2, ssa3])

        mock_post.return_value = Response(msg={'transfer_id': 1}, code=at.expected_rc)
        mock_get.return_value = Response(msg={
            "route_list": [
                {
                    "cost": 0,
                    "destination_id": f"{node1.id}",
                },
                {
                    "cost": 1,
                    "destination_id": f"{self.server.id}",
                }
            ],
        }, code=200, server=node2)

        ro = NativeSoftwareSendOperation(code,
                                         expected_stdout=at.expected_stdout,
                                         expected_stderr=at.expected_stderr,
                                         expected_rc=at.expected_rc)

        cp = ro._execute(
            dict(input=dict(software=soft.id, server=node2.id, dest_path='dest', chunk_size=20, max_senders=2)),
            timeout=None)

        mock_post.assert_called_once_with(node1, 'api_1_0.send',
                                          json=dict(software_id=str(soft.id), dest_server_id=str(node2.id),
                                                    background=False, include_transfer_data=True, force=True,
                                                    dest_path='dest', chunk_size=20, max_senders=2),
                                          timeout=None)
        self.assertTrue(cp.success)
        self.assertEqual(flask.json.dumps(mock_post.return_value.msg), cp.stdout)

    def test_execute_send_software_no_software(self):
        at = ActionTemplate.query.get('00000000-0000-0000-000a-000000000001')

        ro = NativeSoftwareSendOperation(code,
                                         expected_stdout=at.expected_stdout,
                                         expected_stderr=at.expected_stderr,
                                         expected_rc=at.expected_rc)

        with self.subTest("pass an invalid id"):
            soft_id = '00000000-0000-0000-0000-000000000001'
            cp = ro._execute(dict(input=dict(software=soft_id, server=self.server.id)),
                             timeout=None)

            self.assertFalse(cp.success)
            self.assertEqual(f"software id '{soft_id}' not found", cp.stderr)

        with self.subTest("pass an invalid name"):
            cp = ro._execute(dict(input=dict(software='software', server=self.server.id)),
                             timeout=None)

            self.assertFalse(cp.success)
            self.assertEqual(f"No software found for 'software'", cp.stderr)

        soft = Software(name='test', version="1", filename='test.zip')
        db.session.add(soft)

        with self.subTest("pass an invalid version"):
            cp = ro._execute(dict(input=dict(software='test', version="2.1", server=self.server.id)),
                             timeout=None)

            self.assertFalse(cp.success)
            self.assertEqual(f"No software found for 'test' and version '2.1'", cp.stderr)

    def test_execute_send_software_no_destination_server(self):
        at = ActionTemplate.query.get('00000000-0000-0000-000a-000000000001')
        soft = Software(name='test', version='1', filename='test.zip')
        soft2 = Software(name='test', version='2', filename='test.zip')
        node1 = Server('node1', port=5000)
        ssa1 = SoftwareServerAssociation(software=soft2, server=node1, path='/')
        db.session.add_all([soft, soft2, node1, ssa1])

        ro = NativeSoftwareSendOperation(code,
                                         expected_stdout=at.expected_stdout,
                                         expected_stderr=at.expected_stderr,
                                         expected_rc=at.expected_rc)

        cp = ro._execute(dict(input=dict(software='test', server='a')))

        self.assertFalse(cp.success)
        self.assertEqual(f"destination server 'a' not found", cp.stderr)

    @mock.patch('dimensigon.use_cases.operations.ntwrk.get')
    def test_execute_send_software_no_ssa(self, mock_get):
        at = ActionTemplate.query.get('00000000-0000-0000-000a-000000000001')
        soft = Software(name='test', version=1, filename='test.zip')
        node1 = Server('node1', port=5000)
        db.session.add_all([soft, node1])

        mock_get.return_value = Response(code=400)

        ro = NativeSoftwareSendOperation(code,
                                         expected_stdout=at.expected_stdout,
                                         expected_stderr=at.expected_stderr,
                                         expected_rc=at.expected_rc)

        cp = ro._execute(dict(input=dict(software=soft.id, server=self.server.id)))

        self.assertFalse(cp.success)
        self.assertEqual(f'{soft.id} has no server association', cp.stderr)

    @mock.patch('dimensigon.use_cases.operations.ntwrk.get')
    @mock.patch('dimensigon.use_cases.operations.ntwrk.post')
    def test_execute_send_software_error(self, mock_post, mock_get):
        at = ActionTemplate.query.get('00000000-0000-0000-000a-000000000001')
        soft = Software(name='test', version=1, filename='test.zip')
        node1 = Server('node1', port=5000)
        ssa1 = SoftwareServerAssociation(software=soft, server=node1, path='/')
        db.session.add_all([soft, node1, ssa1])

        mock_post.return_value = Response(msg={'error': 'message'}, code=400)
        mock_get.return_value = Response(code=400)

        ro = NativeSoftwareSendOperation(code,
                                         expected_stdout=at.expected_stdout,
                                         expected_stderr=at.expected_stderr,
                                         expected_rc=at.expected_rc)

        cp = ro._execute(dict(input=dict(software=str(soft.id), server=str(node1.id))), timeout=10)

        mock_post.assert_called_once_with(node1, 'api_1_0.send',
                                          json=dict(software_id=str(soft.id), dest_server_id=str(node1.id),
                                                    background=False, include_transfer_data=True, force=True),
                                          timeout=10)
        self.assertFalse(cp.success)
        self.assertEqual(flask.json.dumps(mock_post.return_value.msg), cp.stdout)


class TestNativeWaitOperation(FlaskAppMixin, TestCase):
    def setUp(self):
        super().setUp()
        set_initial(action_template=True)
        self.at = ActionTemplate.query.get('00000000-0000-0000-000a-000000000002')
        self.nwo = NativeWaitOperation(code=code, system_kwargs=dict(sleep_time=0))
        self.patcher_lock_scope = mock.patch('dimensigon.use_cases.operations.lock_scope', autospec=True)
        self.patcher_db = mock.patch('dimensigon.use_cases.operations.db')

        self.mock_db = self.patcher_db.start()
        self.mock_lock_scope = self.patcher_lock_scope.start()

        m = self.mock_db.session.query.return_value = Mock()
        mm = m.filter.return_value = Mock()
        self.mmm = mm.filter.return_value = Mock()

    def tearDown(self) -> None:
        super().tearDown()
        self.patcher_lock_scope.stop()
        self.patcher_db.stop()

    def test_server_found(self):
        self.mmm.all.side_effect = [[], [('node1',)]]

        cp = self.nwo._execute(dict(input=dict(server_names=['node1'])), context=Mock())

        self.assertEqual(f"Server node1 found", cp.stdout)
        self.assertTrue(cp.success)

    def test_server_notfound(self):
        self.mmm.all.reset_mock()
        self.mmm.all.return_value = []
        self.mmm.all.side_effect = None
        cp = self.nwo._execute(dict(input=dict(server_names='node1', timeout=0.01)), context=Mock())
        self.assertEqual(f"Server node1 not created after 0.01 seconds", cp.stderr)
        self.assertFalse(cp.success)

    def test_wait_multiple_servers(self):
        self.mmm.all.reset_mock()
        self.mmm.all.return_value = None
        self.mmm.all.side_effect = [[('node1',)], sqlite3.OperationalError('database is locked'), []]
        with mock.patch('dimensigon.use_cases.operations.time.time') as mock_time:
            mock_time.side_effect = [0, 1, 2, 3]
            cp = self.nwo._execute(dict(input=dict(server_names=['node1', 'node2', 'node3'], timeout=3)),
                                   context=Mock())
            self.assertEqual(f"Servers node2, node3 not created after 3 seconds", cp.stderr)
            self.assertFalse(cp.success)

    def test_no_server_provided(self):
        cp = self.nwo._execute(dict(input=dict(server_names=[])), context=Mock())
        self.assertEqual(f"No server to wait", cp.stderr)
        self.assertFalse(cp.success)

    def test_sqlite_error(self):
        self.mmm.all.reset_mock()
        self.mmm.all.return_value = None
        self.mmm.all.side_effect = [sqlite3.OperationalError(), sqlite3]
        with mock.patch('dimensigon.use_cases.operations.time.time') as mock_time:
            mock_time.side_effect = [0, 1, 2]

            with self.assertRaises(sqlite3.OperationalError):
                cp = self.nwo._execute(dict(input=dict(server_names=['node1', 'node2', 'node3'])),
                                       context=Mock())

    def test_lock_error(self):
        self.mmm.all.reset_mock()
        self.mmm.all.return_value = None

        e = errors.LockError(Scope.CATALOG, action='lock', responses=[])
        self.mock_lock_scope.side_effect = [e]

        cp = self.nwo._execute(dict(input=dict(server_names='node1')), context=Mock())
        self.assertEqual(str(e), cp.stderr)
        self.assertFalse(cp.success)


# class TestRequestOperation(TestCase):
#     def setUp(self):
#         """Create and configure a new app instance for each test."""
#         # create the app with common test config
#         self.app = create_app('test')
#         self.app_context = self.app.app_context()
#         self.app_context.push()
#         self.client = self.app.test_client()
#         db.create_all()
#         set_initial(user=True, action_template=True)
#         self.server = Server.get_current()
#         self.auth = HTTPBearerAuth(create_access_token(User.get_by_name('root').id))
#
#     @responses.activate
#     def test_execute_request(self):
#         url = 'http://new.url/'
#         content = {"content": "this is a message"}
#         responses.add(method='GET', url=url, body=json.dumps(content), status=200,
#                       content_type='application/json')
#
#         ro = RequestOperation('{"method":"get", "url":"{{view_or_url}}"}',
#                               expected_stdout='{}',
#                               expected_stderr='',
#                               expected_rc=200,
#                               post_code="params.update(response.json())")
#
#         params = {"view_or_url": url}
#         cp = ro.execute(context=params, timeout=None)
#
#         self.assertTrue(cp.success)
#         self.assertDictEqual({**params, **content}, params)
#
#     @responses.activate
#     def test_execute_request_timeout(self):
#         url = 'http://new.url/'
#         content = {"content": "this is a message"}
#         responses.add(method='GET', url=url, body=TimeoutError())
#
#         ro = RequestOperation('{"method":"get", "url":"{{url}}"}',
#                               expected_stdout='{}',
#                               expected_stderr='',
#                               expected_rc=200
#                               )
#
#         params = {"url": url}
#         cp = ro.execute(params, timeout=None)
#
#         self.assertFalse(cp.success)
#         self.assertEqual(cp.stderr, "TimeoutError")
#
#     @responses.activate
#     def test_execute_request(self):
#         url = 'http://new.url/'
#         content = "response"
#         responses.add(method='GET', url=url, body=content, status=200)
#
#         ro = RequestOperation('{"method":"get", "url":"{{view_or_url}}"}',
#                               expected_rc=200)
#
#         params = {"view_or_url": url}
#         cp = ro.execute(context=params, timeout=None)
#
#         self.assertTrue(cp.success)
#         self.assertEqual(content, cp.stdout)
code = """
import signal
import time

print("START")
signal.signal(signal.SIGTERM, lambda x, y: print("SIGTERM called"))
signal.signal(signal.SIGINT, lambda x, y: print("SIGINT called"))

time.sleep(100)
print("END")
"""


class TestShellOperation(TestCase):
    def test_execute(self):
        mock_context = mock.Mock()
        mock_context.env = {}
        nc = dimensigon.use_cases.operations.ShellOperation('echo -n "{{input.message}}"', expected_stdout=None,
                                                            expected_rc=None,
                                                            system_kwargs={})
        cp = nc._execute(dict(input={'message': 'this is a test message'}), context=mock_context)
        self.assertTrue(cp.success)
        self.assertEqual('this is a test message', cp.stdout)
        self.assertIsNone(cp.stderr)
        self.assertEqual(0, cp.rc)

        nc = dimensigon.use_cases.operations.ShellOperation('sleep 10', expected_stdout=None,
                                                            expected_rc=None,
                                                            system_kwargs={})
        cp = nc._execute(dict(input={}), context=mock_context, timeout=0.01)
        self.assertFalse(cp.success)
        self.assertEqual('', cp.stdout)
        self.assertEqual('Timeout of 0.01 seconds while executing shell', cp.stderr)