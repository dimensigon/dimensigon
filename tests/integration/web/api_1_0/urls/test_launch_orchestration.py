import concurrent
from unittest import mock
from unittest import mock
from unittest.mock import patch

from flask import url_for

from dimensigon.domain.entities import Orchestration, ActionTemplate, ActionType, OrchExecution
from dimensigon.domain.entities.user import ROOT
from dimensigon.use_cases.deployment import deploy_orchestration
from dimensigon.web import db, errors
from tests.base import TestDimensigonBase, ValidateResponseMixin


class TestLaunchOrchestration(TestDimensigonBase, ValidateResponseMixin):

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

        self.st1 = self.o.add_step(undo=False, action_template=self.at1)
        self.st2 = self.o.add_step(undo=True, action_template=self.at2, parents=[self.st1])
        self.st3 = self.o.add_step(undo=False, action_template=self.at3, parents=[self.st1])
        self.st4 = self.o.add_step(undo=True, action_template=self.at4, parents=[self.st3])

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

    @patch('dimensigon.web.api_1_0.urls.use_cases.uuid.uuid4')
    @patch('dimensigon.web.api_1_0.urls.use_cases.Context')
    @patch('dimensigon.web.api_1_0.urls.use_cases.deploy_orchestration')
    def test_launch_orchestration_ok_foreground(self, mock_deploy, mock_var_context, mock_uuid4):
        mock_uuid4.return_value = 'a7083c43-34cc-4b26-91f0-ea0928cf5945'

        data = {'hosts': self.s1.id,
                'params': {'folder': '/home/{{user}}',
                           'home': '{{folder}}',
                           'user': 'dimensigon'},
                'skip_validation': True,
                'background': False}

        oe = OrchExecution(id=mock_uuid4.return_value, orchestration_id=self.o.id)
        db.session.add(oe)
        db.session.commit()

        def deploy_orchestration(*args, **kwargs):
            return mock_uuid4.return_value

        mock_deploy.side_effect = deploy_orchestration
        MockVarContext = mock.Mock(name='MockVarContext')
        mock_var_context.return_value = MockVarContext
        resp = self.client.post(url_for('api_1_0.launch_orchestration', orchestration_id=str(self.o.id)),
                                json=data,
                                headers=self.auth.header)

        self.assertEqual(200, resp.status_code)
        self.assertDictEqual(oe.to_json(add_step_exec=True, split_lines=True), resp.get_json())

        mock_var_context.assert_called_once_with(data['params'],
                                                 dict(execution_id=None, root_orch_execution_id=mock_uuid4.return_value,
                                                      orch_execution_id=mock_uuid4.return_value,
                                                      executor_id=ROOT),
                                                 vault={})

        mock_deploy.assert_called_once_with(orchestration=self.o, var_context=MockVarContext,
                                            hosts={'all': [self.s1.id]}, timeout=None)

    @patch('dimensigon.web.api_1_0.urls.use_cases.uuid.uuid4')
    @patch('dimensigon.web.api_1_0.urls.use_cases.Context')
    @patch('dimensigon.web.api_1_0.urls.use_cases.executor.submit')
    def test_launch_orchestration_ok_background(self, mock_submit, mock_var_context, mock_uuid4):
        with self.subTest("Test background resolved"):
            mock_uuid4.return_value = 'a7083c43-34cc-4b26-91f0-ea0928cf5945'

            data = {'hosts': self.s1.id,
                    'params': {'folder': '/home/{{user}}',
                               'home': '{{folder}}',
                               'user': 'dimensigon'},
                    'skip_validation': True,
                    'background': True}

            oe = OrchExecution(id=mock_uuid4.return_value, orchestration_id=self.o.id)
            db.session.add(oe)
            db.session.commit()

            mock_submit.return_value = mock.Mock()

            MockVarContext = mock.Mock(name='MockVarContext')
            mock_var_context.return_value = MockVarContext

            resp = self.client.post(url_for('api_1_0.launch_orchestration', orchestration_id=str(self.o.id)),
                                    json=data,
                                    headers=self.auth.header)

            mock_var_context.assert_called_once_with(data['params'],
                                                     dict(execution_id=None, root_orch_execution_id=mock_uuid4.return_value,
                                                          orch_execution_id=mock_uuid4.return_value,
                                                          executor_id=ROOT),
                                                     vault={})

            mock_submit.assert_called_once_with(deploy_orchestration, orchestration=self.o.id, var_context=MockVarContext,
                                                hosts={'all': [self.s1.id]}, timeout=None)

            self.assertEqual(200, resp.status_code)
            self.assertDictEqual(oe.to_json(add_step_exec=True, split_lines=True), resp.get_json())

        with self.subTest("Test background taking longer"):
            mock_submit.return_value = mock.Mock()
            mock_submit.return_value.result.side_effect = concurrent.futures.TimeoutError()

            resp = self.client.post(url_for('api_1_0.launch_orchestration', orchestration_id=str(self.o.id)),
                                    json=data,
                                    headers=self.auth.header)

            self.assertEqual(202, resp.status_code)
            self.assertDictEqual({'execution_id': 'a7083c43-34cc-4b26-91f0-ea0928cf5945'},
                                 resp.get_json())
