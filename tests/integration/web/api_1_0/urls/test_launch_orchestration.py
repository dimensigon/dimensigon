import time
from unittest import mock
from unittest.mock import patch

from flask import url_for

from dimensigon.domain.entities import Orchestration, ActionTemplate, ActionType, Server, User
from dimensigon.web import db, errors
from tests import base


class TestLaunchOrchestration(base.TestDimensigonBase, base.ValidateResponseMixin):

    def setUp(self) -> None:
        super().setUp()
        self.fill_database()

    def fill_database(self):
        self.o = Orchestration('create user', version=1)
        self.at1 = ActionTemplate(action_type=ActionType.SHELL, name="create folder", version=1,
                                  code="sudo mkdir -p {{folder}}")
        self.at2 = ActionTemplate(action_type=ActionType.SHELL, name="delete folder", version=1,
                                  code="sudo rm -fr {{folder}}")
        self.at3 = ActionTemplate(action_type=ActionType.SHELL, name="create user", version=1,
                                  code="sudo useradd -d {{home}} {{user}}")
        self.at4 = ActionTemplate(action_type=ActionType.SHELL, name="delete user", version=1,
                                  code="sudo userdel {{user}}")

        self.s1 = self.o.add_step(undo=False, action_template=self.at1)
        self.s2 = self.o.add_step(undo=True, action_template=self.at2, parents=[self.s1])
        self.s3 = self.o.add_step(undo=False, action_template=self.at3, parents=[self.s1])
        self.s4 = self.o.add_step(undo=True, action_template=self.at4, parents=[self.s3])

        db.session.add(self.o)
        db.session.commit()

    def test_launch_orchestration_error_on_server(self):
        resp = self.client.post(url_for('api_1_0.launch_orchestration', orchestration_id=str(self.o.id)),
                                json={'hosts': 'aaaaaaaa-1234-5678-1234-56781234aaa1'},
                                headers=self.auth.header)

        self.assertEqual(404, resp.status_code)
        self.assertDictEqual(
            errors.format_error_content(errors.ServerNormalizationError(['aaaaaaaa-1234-5678-1234-56781234aaa1'])),
            resp.get_json())

    def test_launch_orchestration_error_on_target(self):
        resp = self.client.post(url_for('api_1_0.launch_orchestration', orchestration_id=str(self.o.id)),
                                json={'hosts': {'all': ['aaaaaaaa-1234-5678-1234-56781234aaa1'],
                                                'other': 'granule'}},
                                headers=self.auth.header)

        self.validate_error_response(resp, errors.TargetNotNeeded(['other']))

        s = self.o.steps[0]
        s.target = ['new']
        db.session.commit()

        resp = self.client.post(url_for('api_1_0.launch_orchestration', orchestration_id=str(self.o.id)),
                                json={'hosts': {'all': ['aaaaaaaa-1234-5678-1234-56781234aaa1']}},
                                headers=self.auth.header)

        self.validate_error_response(resp, errors.TargetUnspecified(['new']))

    @patch('dimensigon.web.api_1_0.urls.use_cases.uuid.uuid4', return_value='a7083c43-34cc-4b26-91f0-ea0928cf5945')
    @patch('dimensigon.web.api_1_0.urls.use_cases.Context')
    @patch('dimensigon.web.api_1_0.urls.use_cases.deploy_orchestration')
    @patch('dimensigon.web.api_1_0.urls.use_cases.HTTPBearerAuth', return_value='token')
    def test_launch_orchestration_ok(self, mock_create, mock_deploy, mock_var_context, mock_uuid4):
        mock_uuid4.return_value = 1
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
        MockVarContext = mock.Mock(name='MockVarContext')
        mock_var_context.return_value = MockVarContext
        resp = self.client.post(url_for('api_1_0.launch_orchestration', orchestration_id=str(self.o.id)),
                                json=data,
                                headers=self.auth.header)

        self.assertEqual(200, resp.status_code)
        self.assertDictEqual({'result': 'ok'}, resp.get_json())

        mock_var_context.assert_called_once_with(data['params'],
                                                 dict(execution_id=None, parent_orch_execution_id=None,
                                                      orch_execution_id='1',
                                                      executor_id=str(User.get_by_user('root').id)))
        mock_deploy.assert_called_once_with(execution='1', orchestration=self.o.id, var_context=MockVarContext,
                                            hosts={'all': [str(Server.get_current().id)]})

        mock_deploy.side_effect = deploy_orchestration_delayed
        resp = self.client.post(url_for('api_1_0.launch_orchestration', orchestration_id=str(self.o.id)),
                                json=data,
                                headers=self.auth.header)

        self.assertEqual(202, resp.status_code)
        self.assertDictEqual({'execution_id': '1'},
                             resp.get_json())
