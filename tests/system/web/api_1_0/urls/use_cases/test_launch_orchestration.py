import json
import os
from subprocess import CompletedProcess as CP, CompletedProcess
from unittest import mock

import responses
from aioresponses import aioresponses
from flask import url_for, current_app
from pyfakefs.fake_filesystem_unittest import TestCase as FSTestCase

from dimensigon import defaults
from dimensigon.domain.entities import User, ActionTemplate, ActionType, Orchestration, \
    OrchExecution, \
    StepExecution
from dimensigon.use_cases.catalog import upgrade_catalog
from dimensigon.web import db
from tests.base import TwoNodeMixin
from tests.helpers import set_callbacks, request_scope

now = defaults.INITIAL_DATEMARK


class TestLaunchOrchestrationNested(TwoNodeMixin, FSTestCase):

    def set_scoped_session(self, func=None):
        super().set_scoped_session(request_scope)

    def set_initial_data_nested_orchestration(self):
        # create data for orchestration
        at = ActionTemplate(name='mkdir', version=1, action_type=ActionType.SHELL, code='mkdir -f {{input.folder}}',
                            schema={'input': {'folder': {'type': 'string'}},
                                    'required': ['folder']},
                            expected_rc=0)
        self.o = Orchestration(name='Create folder', version=1, description="creates a folder")
        self.s = self.o.add_step(undo=False, action_template=at)

        db.session.add_all([at, self.o, self.s])
        db.session.commit()
        self.o2 = Orchestration(name="launch create folder", version=1)

        self.s21 = self.o2.add_step(undo=False,
                                    action_type=ActionType.SHELL,
                                    code="ls",
                                    post_process="vc.set('hosts', {'all': '" + self.s2.id + "'})",
                                    schema={'output': ['hosts']},
                                    )

        self.s22 = self.o2.add_step(undo=False,
                                    action_template=ActionTemplate.query.filter_by(name='orchestration',
                                                                                   version=1).one(),
                                    schema={'mapping': {'orchestration_id': str(self.o.id)}},
                                    parents=[self.s21]
                                    )

        db.session.add_all([self.o2, self.s21, self.s22])

        db.session.commit()

        self.dtos = {'ActionTemplate': [at.to_json()],
                     'Orchestration': [self.o.to_json(), self.o2.to_json()],
                     'Step': [self.s.to_json(), self.s21.to_json(), self.s22.to_json()]}

        with self.app2.app_context():
            upgrade_catalog(self.dtos, check_mismatch=False)

    @mock.patch('dimensigon.use_cases.operations.subprocess.run', autospec=True)
    @responses.activate
    @aioresponses()
    def test_launch_orchestration_nested_orchestration(self, mock_run, m):
        set_callbacks([(r'(127\.0\.0\.1|node1)', self.client), ('node2', self.client2)], m)

        mock_run.side_effect = [CP((), returncode=0, stdout='ls output', stderr=''),
                                CP((), returncode=0, stdout='folder output', stderr='')]

        ###### INITIAL DATA #####
        self.set_initial_data_nested_orchestration()

        resp = self.client.post(url_for('api_1_0.launch_orchestration', orchestration_id=self.o2.id),
                                json={'hosts': 'node1', 'params': {'folder': '/new_folder'}, 'background': False},
                                headers=self.auth.header)

        self.assertIn(resp.status_code, (200, 202))
        self.assertEqual(2, mock_run.call_count)
        self.assertTupleEqual(('ls',), mock_run.call_args_list[0][0])
        self.assertTupleEqual(('mkdir -f /new_folder',), mock_run.call_args_list[1][0])

        oe2: OrchExecution = OrchExecution.query.filter_by(orchestration_id=self.o2.id).one()
        self.assertEqual(User.get_by_user('root'), oe2.executor)
        self.assertEqual(True, oe2.success)
        self.assertDictEqual({'folder': '/new_folder'}, oe2.params)
        self.assertEqual(2, len(oe2.step_executions))
        se21: StepExecution = StepExecution.query.filter_by(step=self.s21).one()
        self.assertEqual(True, se21.success)
        self.assertEqual('ls output', se21.stdout)
        self.assertEqual('', se21.stderr)
        self.assertEqual(0, se21.rc)
        self.assertEqual(self.s1.id, se21.server.id)

        oe1: OrchExecution = OrchExecution.query.filter_by(orchestration_id=self.o.id).one()
        self.assertEqual(User.get_by_user('root'), oe1.executor)
        self.assertEqual(True, oe1.success)
        self.assertDictEqual({'folder': '/new_folder',
                              'hosts': {'all': self.s2.id},
                              'orchestration_id': str(self.o.id)}, oe1.params)
        self.assertEqual(1, len(oe1.step_executions))

        o_id = self.o.id
        with self.app2.app_context():
            oe1: OrchExecution = OrchExecution.query.filter_by(orchestration_id=o_id).one()
            self.assertEqual(1, len(oe1.step_executions))
            se1: StepExecution = oe1.step_executions[0]
            self.assertEqual(True, se1.success)
            self.assertEqual('folder output', se1.stdout)
            self.assertEqual('', se1.stderr)
            self.assertEqual(0, se1.rc)
            self.assertEqual(self.s2.id, se1.server.id)

        se22: StepExecution = StepExecution.query.filter_by(step=self.s22).one()
        self.assertEqual(True, se22.success)
        self.assertEqual(f"orch_execution_id={oe1.id}", se22.stdout)

        self.assertEqual('', se21.stderr)
        self.assertEqual(0, se21.rc)
        self.assertEqual(self.s1.id, se22.server.id)

    def set_initial_data_install_software(self):
        self.source_folder = '/source'
        self.dest_folder = '/dest'
        self.filename = 'Python-3.8.3.tgz'
        self.content = '1234'
        self.size = 4
        self.checksum = "4"
        os.makedirs(self.source_folder)
        os.makedirs(self.dest_folder)
        with open(os.path.join(self.source_folder, self.filename), 'w') as fh:
            fh.write(self.content)

        soft_dto = [{"name": "python",
                     "version": "3.8.3",
                     "family": "programming",
                     "filename": self.filename,
                     "size": self.size,
                     "checksum": self.checksum,
                     "id": "00000019-0000-0000-0000-000000000001",
                     "last_modified_at": defaults.INITIAL_DATEMARK.strftime(defaults.DATEMARK_FORMAT)}]

        ssa_dto = [{'software_id': "00000019-0000-0000-0000-000000000001",
                    'server_id': self.s1.id,
                    'path': self.source_folder,
                    "last_modified_at": defaults.INITIAL_DATEMARK.strftime(defaults.DATEMARK_FORMAT)}]

        orch_dto = [{"name": "install python 3.8.3",
                     "version": 1,
                     "description": "installs python 3.8.3",
                     "id": "00000015-0000-0000-0001-000000000000",
                     "last_modified_at": defaults.INITIAL_DATEMARK.strftime(defaults.DATEMARK_FORMAT)
                     }]

        step_dtos = [
            {
                "id": "00000015-0000-0000-0001-000000000001",
                "orchestration_id": "00000015-0000-0000-0001-000000000000",
                "action_template_id": "00000000-0000-0000-000a-000000000001",
                "undo": False,
                "undo_on_error": False,
                "schema": {"mapping": {"software_id": "00000019-0000-0000-0000-000000000001",
                                       "server_id": {"from": "env.server_id"}}},
                "last_modified_at": defaults.INITIAL_DATEMARK.strftime(defaults.DATEMARK_FORMAT)},
            {
                "id": "00000015-0000-0000-0001-000000000002",
                "orchestration_id": "00000015-0000-0000-0001-000000000000",
                "undo": False,
                "undo_on_error": False,
                "parent_step_ids": ["00000015-0000-0000-0001-000000000001"],
                "code": "echo '{{input.file}}'",
                "action_type": "SHELL",
                "expected_rc": 0,
                "last_modified_at": defaults.INITIAL_DATEMARK.strftime(defaults.DATEMARK_FORMAT)}]

        self.dtos = {'Software': soft_dto,
                     'SoftwareServerAssociation': ssa_dto,
                     'Orchestration': orch_dto,
                     'Step': step_dtos}
        upgrade_catalog(self.dtos, check_mismatch=False)

        with self.app2.app_context():
            upgrade_catalog(self.dtos, check_mismatch=False)

    @mock.patch('dimensigon.use_cases.operations.subprocess.run')  # due to pyfakefs does not mock C library access
    @mock.patch('dimensigon.web.api_1_0.resources.transfer.current_app')
    @responses.activate
    @aioresponses()
    def test_launch_orchestration_install_software_local(self, mock_current_app, mock_run, m):
        set_callbacks([(r'(127\.0\.0\.1|node1)', self.client), ('node2', self.client2)], m)
        self.setUpPyfakefs()

        self.set_initial_data_install_software()

        mock_run.return_value = CompletedProcess(args=f"echo '{os.path.join(self.dest_folder, self.filename)}'",
                                                 stdout='output',
                                                 returncode=0)

        resp = self.client.post(
            url_for('api_1_0.launch_orchestration', orchestration_id="00000015-0000-0000-0001-000000000000"),
            json={'hosts': 'node1', 'params': {'dest_path': self.dest_folder},
                  'background': False},
            headers=self.auth.header)

        self.assertEqual(200, resp.status_code)
        data = resp.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(2, len(data['steps']))
        exec_step1 = data['steps'][0]
        exec_step2 = data['steps'][1]
        self.assertEqual(201, exec_step1.get('rc'))
        step_out = json.loads(exec_step1.get('stdout'))
        self.assertEqual(os.path.join(self.dest_folder, self.filename), step_out.get('file'))
        self.assertIn('id', step_out)
        self.assertDictEqual(
            dict(dest_path=self.dest_folder, software_id="00000019-0000-0000-0000-000000000001", server_id=self.s1.id),
            exec_step1.get('params'))

        self.assertEqual(0, exec_step2.get('rc'))
        self.assertEqual('output', exec_step2.get('stdout'))
        self.assertEqual(None, exec_step2.get('stderr'))
        self.assertDictEqual(
            dict(file=os.path.join(self.dest_folder, self.filename), dest_path=self.dest_folder),
            exec_step2.get('params'))

        self.assertTupleEqual((f"echo '{os.path.join(self.dest_folder, self.filename)}'",), mock_run.call_args[0])
        self.assertTrue(os.path.exists(os.path.join(self.dest_folder, self.filename)))

    @mock.patch('dimensigon.use_cases.operations.subprocess.run')
    @mock.patch('dimensigon.web.api_1_0.resources.transfer.current_app')
    @responses.activate
    @aioresponses()
    def test_launch_orchestration_install_software_remote(self, mock_current_app, mock_run, m):
        set_callbacks([(r'(127\.0\.0\.1|node1)', self.client), ('node2', self.client2)], m)
        self.setUpPyfakefs()

        self.set_initial_data_install_software()

        mock_run.return_value = CompletedProcess(args=f"echo '{os.path.join(self.dest_folder, self.filename)}'",
                                                 stdout='output',
                                                 returncode=0)

        resp = self.client.post(
            url_for('api_1_0.launch_orchestration', orchestration_id="00000015-0000-0000-0001-000000000000"),
            json={'hosts': 'node2', 'params': {'dest_path': self.dest_folder},
                  'background': False},
            headers=self.auth.header)

        self.assertEqual(200, resp.status_code)
        data = resp.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(2, len(data['steps']))
        exec_step1 = data['steps'][0]
        exec_step2 = data['steps'][1]
        self.assertEqual(201, exec_step1.get('rc'))
        step_out = json.loads(exec_step1.get('stdout'))
        self.assertEqual(os.path.join(self.dest_folder, self.filename), step_out.get('file'))
        self.assertIn('id', step_out)
        self.assertDictEqual(
            dict(dest_path=self.dest_folder, software_id="00000019-0000-0000-0000-000000000001", server_id=self.s2.id),
            exec_step1.get('params'))

        self.assertEqual(0, exec_step2.get('rc'))
        self.assertEqual('output', exec_step2.get('stdout'))
        self.assertEqual(None, exec_step2.get('stderr'))
        self.assertDictEqual(
            dict(file=os.path.join(self.dest_folder, self.filename), dest_path=self.dest_folder),
            exec_step2.get('params'))

        self.assertTupleEqual((f"echo '{os.path.join(self.dest_folder, self.filename)}'",), mock_run.call_args[0])
        self.assertTrue(os.path.exists(os.path.join(self.dest_folder, self.filename)))

    @mock.patch('dimensigon.use_cases.operations.subprocess.run')
    @mock.patch('dimensigon.web.api_1_0.resources.transfer.current_app')
    @responses.activate
    @aioresponses()
    def test_launch_orchestration_install_software_dual(self, mock_current_app, mock_run, m):
        set_callbacks([(r'(127\.0\.0\.1|node1)', self.client), ('node2', self.client2)], m)
        self.setUpPyfakefs()

        self.set_initial_data_install_software()

        mock_run.return_value = CompletedProcess(args=f"echo '{os.path.join(self.dest_folder, self.filename)}'",
                                                 stdout='output',
                                                 returncode=0)

        def path(soft_path):
            if current_app == self.app:
                return os.path.join('/node1', soft_path)
            else:
                return os.path.join('/node2', soft_path)

        mock_current_app.dm.config.path.side_effect = path
        resp = self.client.post(
            url_for('api_1_0.launch_orchestration', orchestration_id="00000015-0000-0000-0001-000000000000"),
            json={'hosts': ['node1', 'node2'], 'background': False},
            headers=self.auth.header)

        self.assertEqual(200, resp.status_code)
        data = resp.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(4, len(data['steps']))

        exec_step1_s1 = [s for s in data['steps'] if
                         s['step_id'] == '00000015-0000-0000-0001-000000000001' and s['server_id'] == self.s1.id][0]
        exec_step2_s1 = [s for s in data['steps'] if
                         s['step_id'] == '00000015-0000-0000-0001-000000000002' and s['server_id'] == self.s1.id][0]
        exec_step1_s2 = [s for s in data['steps'] if
                         s['step_id'] == '00000015-0000-0000-0001-000000000001' and s['server_id'] == self.s2.id][0]
        exec_step2_s2 = [s for s in data['steps'] if
                         s['step_id'] == '00000015-0000-0000-0001-000000000002' and s['server_id'] == self.s2.id][0]
        self.assertEqual(201, exec_step1_s1.get('rc'))
        step_out = json.loads(exec_step1_s1.get('stdout'))
        self.assertEqual(os.path.join('/node1', defaults.SOFTWARE_REPO, self.filename), step_out.get('file'))
        self.assertIn('id', step_out)
        self.assertDictEqual(
            dict(software_id="00000019-0000-0000-0000-000000000001", server_id=self.s1.id),
            exec_step1_s1.get('params'))

        self.assertEqual(201, exec_step1_s2.get('rc'))
        step_out = json.loads(exec_step1_s2.get('stdout'))
        self.assertEqual(os.path.join('/node2', defaults.SOFTWARE_REPO, self.filename), step_out.get('file'))
        self.assertIn('id', step_out)
        self.assertDictEqual(
            dict(software_id="00000019-0000-0000-0000-000000000001", server_id=self.s2.id),
            exec_step1_s2.get('params'))

        self.assertEqual(0, exec_step2_s1.get('rc'))
        self.assertEqual('output', exec_step2_s1.get('stdout'))
        self.assertEqual(None, exec_step2_s1.get('stderr'))
        self.assertDictEqual(
            dict(file='/node1/software/Python-3.8.3.tgz'),
            exec_step2_s1.get('params'))

        self.assertEqual(0, exec_step2_s2.get('rc'))
        self.assertEqual('output', exec_step2_s2.get('stdout'))
        self.assertEqual(None, exec_step2_s2.get('stderr'))
        self.assertDictEqual(
            dict(file='/node2/software/Python-3.8.3.tgz'),
            exec_step2_s2.get('params'))

        if mock_run.call_args_list[0][0][0].startswith("echo '/node1"):
            self.assertTupleEqual((f"echo '{os.path.join('/node1', defaults.SOFTWARE_REPO, self.filename)}'",),
                                  mock_run.call_args_list[0][0])
            self.assertTupleEqual((f"echo '{os.path.join('/node2', defaults.SOFTWARE_REPO, self.filename)}'",),
                                  mock_run.call_args_list[1][0])
        else:
            self.assertTupleEqual((f"echo '{os.path.join('/node2', defaults.SOFTWARE_REPO, self.filename)}'",),
                                  mock_run.call_args_list[0][0])
            self.assertTupleEqual((f"echo '{os.path.join('/node1', defaults.SOFTWARE_REPO, self.filename)}'",),
                                  mock_run.call_args_list[1][0])
        self.assertTrue(os.path.exists(os.path.join('/node1', defaults.SOFTWARE_REPO, self.filename)))
        self.assertTrue(os.path.exists(os.path.join('/node2', defaults.SOFTWARE_REPO, self.filename)))
