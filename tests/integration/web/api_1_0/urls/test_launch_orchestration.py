import time
import uuid
from unittest import TestCase
from unittest.mock import patch

from flask import url_for
from flask_jwt_extended import create_access_token

from dm.domain.entities import Orchestration, ActionTemplate, ActionType, Server
from dm.domain.entities.bootstrap import set_initial
from dm.web import create_app, db
from dm.web.network import HTTPBearerAuth


class TestLaunchOrchestration(TestCase):
    def setUp(self):
        """Create and configure a new app instance for each test."""
        # create the app with common test config
        self.app = create_app('test')
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        self.auth = HTTPBearerAuth(create_access_token('test'))
        db.create_all()
        set_initial()
        self.o = Orchestration('create user', version=1)
        self.at1 = ActionTemplate(action_type=ActionType.NATIVE, name="create folder", version=1,
                                  code="sudo mkdir -p {{folder}}")
        self.at2 = ActionTemplate(action_type=ActionType.NATIVE, name="delete folder", version=1,
                                  code="sudo rm -fr {{folder}}")
        self.at3 = ActionTemplate(action_type=ActionType.NATIVE, name="create user", version=1,
                                  code="sudo useradd -d {{home}} {{user}}")
        self.at4 = ActionTemplate(action_type=ActionType.NATIVE, name="delete user", version=1,
                                  code="sudo userdel {{user}}")

        self.s1 = self.o.add_step(undo=False, action_template=self.at1)
        self.s2 = self.o.add_step(undo=True, action_template=self.at2, parents=[self.s1])
        self.s3 = self.o.add_step(undo=False, action_template=self.at3, parents=[self.s1])
        self.s4 = self.o.add_step(undo=True, action_template=self.at4, parents=[self.s3])
        db.session.add(self.o)

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_launch_orchestration_error_on_server(self):
        resp = self.client.post(url_for('api_1_0.launch_orchestration', orchestration_id=str(self.o.id)),
                                json={'hosts': 'aaaaaaaa-1234-5678-1234-56781234aaa1'},
                                headers=self.auth.header)

        self.assertEqual(404, resp.status_code)
        self.assertDictEqual(
            {"error": "Following granules or ids did not match to any server: aaaaaaaa-1234-5678-1234-56781234aaa1"},
            resp.get_json())

        resp = self.client.post(url_for('api_1_0.launch_orchestration', orchestration_id=str(self.o.id)),
                                json={'hosts': ['aaaaaaaa-1234-5678-1234-56781234aaa1']},
                                headers=self.auth.header)

        self.assertEqual(404, resp.status_code)
        self.assertDictEqual(
            {"error": "Following granules or ids did not match to any server: aaaaaaaa-1234-5678-1234-56781234aaa1"},
            resp.get_json())

        resp = self.client.post(url_for('api_1_0.launch_orchestration', orchestration_id=str(self.o.id)),
                                json={'hosts': {'all': ['aaaaaaaa-1234-5678-1234-56781234aaa1', 'granule']}},
                                headers=self.auth.header)

        self.assertEqual(404, resp.status_code)
        self.assertDictEqual({"error": "Following granules or ids did not match to any server: "
                                       "aaaaaaaa-1234-5678-1234-56781234aaa1, granule"},
                             resp.get_json())

    def test_launch_orchestration_error_on_target(self):
        resp = self.client.post(url_for('api_1_0.launch_orchestration', orchestration_id=str(self.o.id)),
                                json={'hosts': {'all': ['aaaaaaaa-1234-5678-1234-56781234aaa1'],
                                                'other': 'granule'}},
                                headers=self.auth.header)

        self.assertEqual(400, resp.status_code)
        self.assertDictEqual({"error": "Target(s) not in orchestration: "
                                       "other"},
                             resp.get_json())

        self.s3.target = ['remote']
        resp = self.client.post(url_for('api_1_0.launch_orchestration', orchestration_id=str(self.o.id)),
                                json={'hosts': {'all': ['aaaaaaaa-1234-5678-1234-56781234aaa1']}},
                                headers=self.auth.header)

        self.assertEqual(404, resp.status_code)
        self.assertDictEqual({"error": "Target(s) not specified: "
                                       "remote"},
                             resp.get_json())

    def test_launch_orchestration_error_on_parameters(self):
        resp = self.client.post(url_for('api_1_0.launch_orchestration', orchestration_id=str(self.o.id)),
                                json={'hosts': str(Server.get_current().id)},
                                headers=self.auth.header)

        self.assertEqual(404, resp.status_code)
        self.assertDictEqual({"error": "Parameter(s) not specified: "
                                       "folder, home, user"},
                             resp.get_json())

    @patch('dm.web.api_1_0.urls.use_cases.uuid.uuid4', return_value=uuid.UUID('a7083c43-34cc-4b26-91f0-ea0928cf5945'))
    @patch('dm.web.api_1_0.urls.use_cases.deploy_orchestration')
    @patch('dm.web.api_1_0.urls.use_cases.HTTPBearerAuth', return_value='token')
    def test_launch_orchestration_ok(self, mock_create, mock_deploy, mock_uuid4):
        mock_create.return_value = 'token'
        data = {'hosts': str(Server.get_current().id),
                'params': {'folder': '/home/{{user}}',
                           'home': '{{folder}}',
                           'user': 'dimensigon'}}

        def deploy_orchestration(*args, **kwargs):
            return {'result': 'ok'}

        def deploy_orchestration_delayed(*args, **kwargs):
            time.sleep(1.1)
            return dict(**kwargs)

        mock_deploy.side_effect = deploy_orchestration
        resp = self.client.post(url_for('api_1_0.launch_orchestration', orchestration_id=str(self.o.id)),
                                json=data,
                                headers=self.auth.header)

        self.assertEqual(200, resp.status_code)
        self.assertDictEqual({'result': 'ok'}, resp.get_json())
        mock_deploy.assert_called_once_with(auth='token',
                                                 execution=uuid.UUID('a7083c43-34cc-4b26-91f0-ea0928cf5945'),
                                                 hosts={'all': [Server.get_current().id]},
                                                 orchestration=self.o.id,
                                                 params={'folder': '/home/{{user}}', 'home': '{{folder}}',
                                                         'user': 'dimensigon'})

        mock_deploy.side_effect = deploy_orchestration_delayed
        resp = self.client.post(url_for('api_1_0.launch_orchestration', orchestration_id=str(self.o.id)),
                                json=data,
                                headers=self.auth.header)

        self.assertEqual(202, resp.status_code)
        self.assertDictEqual({'execution_id': 'a7083c43-34cc-4b26-91f0-ea0928cf5945'},
                             resp.get_json())