import json
from unittest import TestCase, mock
from unittest.mock import Mock

import flask
import responses
from flask_jwt_extended import create_access_token

from dm.domain.entities import User, ActionTemplate, Server, Software, SoftwareServerAssociation
from dm.domain.entities.bootstrap import set_initial
from dm.use_cases.operations import RequestOperation, NativeWaitOperation
from dm.web import create_app, db
from dm.web.network import HTTPBearerAuth, Response


class TestRequestOperation(TestCase):
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
        self.auth = HTTPBearerAuth(create_access_token(User.get_by_user('root').id))

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    @mock.patch('dm.use_cases.operations.get')
    @mock.patch('dm.use_cases.operations.create_access_token')
    @mock.patch('dm.use_cases.operations.request')
    def test_execute_send_software(self, mock_request, mock_token, mock_get):
        at = ActionTemplate.query.get('00000000-0000-0000-000a-000000000001')
        soft = Software(name='test', version=1, filename='test.zip')
        node1 = Server('node1', port=5000)
        node2 = Server('node2', port=5000)
        ssa1 = SoftwareServerAssociation(software=soft, server=node1, path='/')
        ssa2 = SoftwareServerAssociation(software=soft, server=node2, path='/')
        ssa3 = SoftwareServerAssociation(software=soft, server=self.server, path='/')
        db.session.add_all([soft, node1, node2, ssa1, ssa2, ssa3])

        mock_request.return_value = Response(msg={'transfer_id': 1}, code=at.expected_rc)
        mock_token.return_value = 1
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

        ro = RequestOperation(at.code,
                              expected_stdout=at.expected_stdout,
                              expected_stderr=at.expected_stderr,
                              expected_rc=at.expected_rc)

        cp = ro.execute(var_context=dict(software_id=str(soft.id), server_id=str(node2.id)), timeout=None)

        mock_request.assert_called_once_with('post', node1, 'api_1_0.send',
                                             json=dict(software_id=str(soft.id), dest_server_id=str(node2.id),
                                                       background=False, include_transfer_data=True, force=True),
                                             auth=HTTPBearerAuth(1))
        self.assertTrue(cp.success)
        self.assertEqual(flask.json.dumps(mock_request.return_value.msg), cp.stdout)

    def test_execute_send_software_no_software(self):
        at = ActionTemplate.query.get('00000000-0000-0000-000a-000000000001')

        ro = RequestOperation(at.code,
                              expected_stdout=at.expected_stdout,
                              expected_stderr=at.expected_stderr,
                              expected_rc=at.expected_rc)

        cp = ro.execute(var_context=dict(software_id=1, server_id=str(self.server.id)), timeout=None)

        self.assertFalse(cp.success)
        self.assertEqual(f"software id '1' not found", cp.stderr)

    def test_execute_send_software_no_destination_server(self):
        at = ActionTemplate.query.get('00000000-0000-0000-000a-000000000001')
        soft = Software(name='test', version=1, filename='test.zip')
        node1 = Server('node1', port=5000)
        ssa1 = SoftwareServerAssociation(software=soft, server=node1, path='/')
        db.session.add_all([soft, node1, ssa1])

        ro = RequestOperation(at.code,
                              expected_stdout=at.expected_stdout,
                              expected_stderr=at.expected_stderr,
                              expected_rc=at.expected_rc)

        cp = ro.execute(var_context=dict(software_id=soft.id, server_id=str('a')), timeout=None)

        self.assertFalse(cp.success)
        self.assertEqual(f"destination server id 'a' not found", cp.stderr)

    @mock.patch('dm.use_cases.operations.get')
    def test_execute_send_software_no_ssa(self, mock_get):
        at = ActionTemplate.query.get('00000000-0000-0000-000a-000000000001')
        soft = Software(name='test', version=1, filename='test.zip')
        node1 = Server('node1', port=5000)
        db.session.add_all([soft, node1])

        mock_get.return_value = Response(code=400)

        ro = RequestOperation(at.code,
                              expected_stdout=at.expected_stdout,
                              expected_stderr=at.expected_stderr,
                              expected_rc=at.expected_rc)

        cp = ro.execute(var_context=dict(software_id=str(soft.id), server_id=str(self.server.id), timeout=None))

        self.assertFalse(cp.success)
        self.assertEqual(f'{soft.id} has no server association', cp.stderr)

    @mock.patch('dm.use_cases.operations.get')
    @mock.patch('dm.use_cases.operations.create_access_token')
    @mock.patch('dm.use_cases.operations.request')
    def test_execute_send_software_error(self, mock_request, mock_token, mock_get):
        at = ActionTemplate.query.get('00000000-0000-0000-000a-000000000001')
        soft = Software(name='test', version=1, filename='test.zip')
        node1 = Server('node1', port=5000)
        ssa1 = SoftwareServerAssociation(software=soft, server=node1, path='/')
        db.session.add_all([soft, node1, ssa1])

        mock_request.return_value = Response(msg={'error': 'message'}, code=400)
        mock_token.return_value = 1
        mock_get.return_value = Response(code=400)

        ro = RequestOperation(at.code,
                              expected_stdout=at.expected_stdout,
                              expected_stderr=at.expected_stderr,
                              expected_rc=at.expected_rc)

        cp = ro.execute(var_context=dict(software_id=str(soft.id), server_id=str(node1.id)), timeout=None)

        mock_request.assert_called_once_with('post', node1, 'api_1_0.send',
                                             json=dict(software_id=str(soft.id), dest_server_id=str(node1.id),
                                                       background=False,  include_transfer_data=True, force=True),
                                             auth=HTTPBearerAuth(1))
        self.assertFalse(cp.success)
        self.assertEqual(flask.json.dumps(mock_request.return_value.msg), cp.stdout)

    @responses.activate
    def test_execute_request(self):
        url = 'http://new.url/'
        content = {"content": "this is a message"}
        responses.add(method='GET', url=url, body=json.dumps(content), status=200,
                      content_type='application/json')

        ro = RequestOperation('{"method":"get", "url":"{{view_or_url}}"}',
                              expected_stdout='{}',
                              expected_stderr='',
                              expected_rc=200,
                              post_code="params.update(response.json())")

        params = {"view_or_url": url}
        cp = ro.execute(var_context=params, timeout=None)

        self.assertTrue(cp.success)
        self.assertDictEqual({**params, **content}, params)

    @responses.activate
    def test_execute_request_timeout(self):
        url = 'http://new.url/'
        content = {"content": "this is a message"}
        responses.add(method='GET', url=url, body=TimeoutError())

        ro = RequestOperation('{"method":"get", "url":"{{url}}"}',
                              expected_stdout='{}',
                              expected_stderr='',
                              expected_rc=200
                              )

        params = {"url": url}
        cp = ro.execute(var_context=params, timeout=None)

        self.assertFalse(cp.success)
        self.assertEqual(cp.stderr, "TimeoutError")

    @responses.activate
    def test_execute_request(self):
        url = 'http://new.url/'
        content = "response"
        responses.add(method='GET', url=url, body=content, status=200)

        ro = RequestOperation('{"method":"get", "url":"{{view_or_url}}"}',
                              expected_rc=200)

        params = {"view_or_url": url}
        cp = ro.execute(var_context=params, timeout=None)

        self.assertTrue(cp.success)
        self.assertEqual(content, cp.stdout)


class TestNativeWaitOperation(TestCase):
    def setUp(self):
        """Create and configure a new app instance for each test."""
        # create the app with common test config
        self.app = create_app('test')
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        db.create_all()
        set_initial(action_template=True)
        self.server = Server.get_current()
        self.auth = HTTPBearerAuth(create_access_token(User.get_by_user('root').id))

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    @mock.patch('dm.use_cases.operations.db')
    def test_execute(self, mock_db):

        at = ActionTemplate.query.get('00000000-0000-0000-000a-000000000002')

        nwo = NativeWaitOperation(code=at.code, system_kwargs=dict(sleep_time=0.01))

        mock_db.session.query.return_value = Mock()
        mock_db.session.query.return_value.filter_by.return_value = Mock()
        mock_db.session.query.return_value.filter_by.return_value.count.return_value = 0

        cp = nwo.execute(var_context=dict(list_server_names=['node1']), timeout=0.1)

        self.assertEqual(f"Servers node1 not created after 0.1 seconds", cp.stderr)
        self.assertFalse(cp.success)

        cp = nwo.execute(var_context=dict(list_server_names=['node1'], timeout=0.1))
        self.assertEqual(f"Servers node1 not created after 0.1 seconds", cp.stderr)
        self.assertFalse(cp.success)

        cp = nwo.execute(var_context=dict(list_server_names=['node1'], timeout=0.1), timeout=2)
        self.assertEqual(f"Servers node1 not created after 0.1 seconds", cp.stderr)
        self.assertFalse(cp.success)

        mock_db.session.query.return_value.filter_by.return_value.count.side_effect = [0, 0, 1]
        cp = nwo.execute(var_context=dict(list_server_names=['node1']))

        self.assertEqual("Servers node1 found", cp.stdout)
        self.assertIsNone(cp.stderr)
        self.assertTrue(cp.success)

        def func(name):
            if name == 'node1':
                m = Mock()
                m.count.return_value = 1
                return m
            else:
                m = Mock()
                m.count.return_value = 0
                return m

        mock_db.session.query.return_value.filter_by.side_effect = func
        cp = nwo.execute(var_context=dict(list_server_names=['node1', 'node2']), timeout=0.1)
        self.assertEqual(f"Servers node2 not created after 0.1 seconds", cp.stderr)
        self.assertFalse(cp.success)
