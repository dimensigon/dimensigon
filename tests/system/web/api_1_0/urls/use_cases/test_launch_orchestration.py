import json
import os
from subprocess import CompletedProcess as CP, CompletedProcess
from unittest import mock

import responses
from aioresponses import aioresponses
from flask import url_for
from flask_jwt_extended import create_access_token
from pyfakefs.fake_filesystem_unittest import TestCase as FSTestCase

from dm import defaults
from dm.domain.entities import Server, Route, Dimension, User, ActionTemplate, ActionType, Orchestration, OrchExecution, \
    StepExecution
from dm.domain.entities.bootstrap import set_initial
from dm.network.auth import HTTPBearerAuth
from dm.use_cases.use_cases import upgrade_catalog
from dm.web import create_app, db
from tests.helpers import set_callbacks, generate_dimension_json_data


class TestLaunchOrchestrationNested(FSTestCase):
    def setUp(self):
        """Create and configure a new app instance for each test."""
        # create the app with common test config
        self.app = create_app('test')
        self.app_context = self.app.app_context()
        self.client = self.app.test_client()

        self.app2 = create_app('test')
        self.app2_context = self.app2.app_context()
        self.app_context.push()
        self.client2 = self.app2.test_client()

        self.json_dim = generate_dimension_json_data()

        set_initial(server=False, action_template=True)
        dim = Dimension.from_json(self.json_dim)
        db.session.add(dim)
        self.node1 = Server('node1', port=8000, me=True, id="00000000-1111-0000-0000-000000000000")
        db.session.add_all([self.node1])
        db.session.commit()
        self.auth = HTTPBearerAuth(create_access_token(User.get_by_user('root').id))

        # dump data
        self.json_node1 = self.node1.to_json(add_gates=True)

        with self.app2.app_context():
            set_initial(server=False, action_template=True)
            dim = Dimension.from_json(self.json_dim)
            db.session.add(dim)
            me = Server('node2', port=8000, me=True, granules=['backend'], id="00000000-2222-0000-0000-000000000000")
            db.session.add(me)

            src_server = Server.from_json(self.json_node1)
            Route(src_server, cost=0)
            db.session.add(src_server)

            db.session.commit()

            # dump data
            self.json_node2 = me.to_json(add_gates=True)

        self.node2 = Server.from_json(self.json_node2)
        r = Route(self.node2, cost=0)
        db.session.add_all([self.node2, r])
        db.session.commit()

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

        with self.app2_context:
            db.session.remove()
            db.drop_all()

    def set_initial_data_nested_orchestration(self):
        # create data for orchestration
        at = ActionTemplate(name='mkdir', version=1, action_type=ActionType.SHELL, code='mkdir -f {{folder}}',
                            expected_rc=0)
        self.o = Orchestration(name='Create folder', version=1, description="creates a folder")
        self.s = self.o.add_step(undo=False, action_template=at)

        db.session.add_all([at, self.o, self.s])
        db.session.commit()
        self.o2 = Orchestration(name="launch create folder", version=1)

        self.s21 = self.o2.add_step(undo=False,
                                    action_type=ActionType.SHELL,
                                    code="ls",
                                    post_process="vc.set('hosts', {'all': '00000000-2222-0000-0000-000000000000'})"
                                    )

        self.s22 = self.o2.add_step(undo=False,
                                    action_template=ActionTemplate.query.filter_by(name='orchestration',
                                                                                   version=1).one(),
                                    parameters={'orchestration_id': str(self.o.id)},
                                    parents=[self.s21]
                                    )

        db.session.add_all([self.o2, self.s21, self.s22])

        db.session.commit()

        self.dtos = {'ActionTemplate': [at.to_json()],
                     'Orchestration': [self.o.to_json(), self.o2.to_json()],
                     'Step': [self.s.to_json(), self.s21.to_json(), self.s22.to_json()]}

        with self.app2.app_context():
            upgrade_catalog(self.dtos, check_mismatch=False)

    @mock.patch('dm.use_cases.operations.subprocess.run', autospec=True)
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
        self.assertEqual(self.node1, se21.server)

        oe1: OrchExecution = OrchExecution.query.filter_by(orchestration_id=self.o.id).one()
        self.assertEqual(User.get_by_user('root'), oe1.executor)
        self.assertEqual(True, oe1.success)
        self.assertDictEqual({'folder': '/new_folder',
                              'hosts': {'all': "00000000-2222-0000-0000-000000000000"},
                              'orchestration_id': str(self.o.id),
                              'server_id': "00000000-1111-0000-0000-000000000000"}, oe1.params)
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
            self.assertEqual(self.json_node2['id'], str(se1.server.id))

        se22: StepExecution = StepExecution.query.filter_by(step=self.s22).one()
        self.assertEqual(True, se22.success)
        self.assertIsNone(se22.stdout)

        self.assertEqual('', se21.stderr)
        self.assertEqual(0, se21.rc)
        self.assertEqual(self.node1, se22.server)

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
                    'server_id': "00000000-1111-0000-0000-000000000000",
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
                "parameters": {
                    "software_id": "00000019-0000-0000-0000-000000000001",
                    "dest_path": "{{folder}}"},
                "last_modified_at": defaults.INITIAL_DATEMARK.strftime(defaults.DATEMARK_FORMAT)},
            {
                "id": "00000015-0000-0000-0001-000000000002",
                "orchestration_id": "00000015-0000-0000-0001-000000000000",
                "undo": False,
                "undo_on_error": False,
                "parent_step_ids": ["00000015-0000-0000-0001-000000000001"],
                "code": "echo '{{file}}'",
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

    @mock.patch('dm.use_cases.operations.subprocess.run')
    @responses.activate
    @aioresponses()
    def test_launch_orchestration_install_software_local(self, mock_run, m):
        set_callbacks([(r'(127\.0\.0\.1|node1)', self.client), ('node2', self.client2)], m)
        self.setUpPyfakefs()

        self.set_initial_data_install_software()

        mock_run.return_value = CompletedProcess(args=f"echo '{os.path.join(self.dest_folder, self.filename)}'",
                                                 stdout='output',
                                                 returncode=0)

        resp = self.client.post(
            url_for('api_1_0.launch_orchestration', orchestration_id="00000015-0000-0000-0001-000000000000"),
            json={'hosts': 'node1', 'params': {'folder': self.dest_folder}, 'background': False},
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
            dict(folder=self.dest_folder, dest_path=self.dest_folder,
                 file=os.path.join(self.dest_folder, self.filename), software_id="00000019-0000-0000-0000-000000000001",
                 server_id=self.node1.id),
            exec_step1.get('params'))

        self.assertEqual(0, exec_step2.get('rc'))
        self.assertEqual('output', exec_step2.get('stdout'))
        self.assertEqual(None, exec_step2.get('stderr'))
        self.assertDictEqual(
            dict(file=os.path.join(self.dest_folder, self.filename), folder=self.dest_folder, server_id=self.node1.id),
            exec_step2.get('params'))

        self.assertTupleEqual((f"echo '{os.path.join(self.dest_folder, self.filename)}'",), mock_run.call_args[0])
        self.assertTrue(os.path.exists(os.path.join(self.dest_folder, self.filename)))

    @mock.patch('dm.use_cases.operations.subprocess.run')
    @responses.activate
    @aioresponses()
    def test_launch_orchestration_install_software_remote(self, mock_run, m):
        set_callbacks([(r'(127\.0\.0\.1|node1)', self.client), ('node2', self.client2)], m)
        self.setUpPyfakefs()

        self.set_initial_data_install_software()

        mock_run.return_value = CompletedProcess(args=f"echo '{os.path.join(self.dest_folder, self.filename)}'",
                                                 stdout='output',
                                                 returncode=0)

        resp = self.client.post(
            url_for('api_1_0.launch_orchestration', orchestration_id="00000015-0000-0000-0001-000000000000"),
            json={'hosts': 'node2', 'params': {'folder': self.dest_folder}, 'background': False},
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
            dict(folder=self.dest_folder, dest_path=self.dest_folder,
                 file=os.path.join(self.dest_folder, self.filename), software_id="00000019-0000-0000-0000-000000000001",
                 server_id=self.node2.id),
            exec_step1.get('params'))

        self.assertEqual(0, exec_step2.get('rc'))
        self.assertEqual('output', exec_step2.get('stdout'))
        self.assertEqual(None, exec_step2.get('stderr'))
        self.assertDictEqual(
            dict(file=os.path.join(self.dest_folder, self.filename), folder=self.dest_folder, server_id=self.node2.id),
            exec_step2.get('params'))

        self.assertTupleEqual((f"echo '{os.path.join(self.dest_folder, self.filename)}'",), mock_run.call_args[0])
        self.assertTrue(os.path.exists(os.path.join(self.dest_folder, self.filename)))

    @mock.patch('dm.use_cases.operations.subprocess.run')
    @responses.activate
    @aioresponses()
    def test_launch_orchestration_install_software_dual(self, mock_run, m):
        set_callbacks([(r'(127\.0\.0\.1|node1)', self.client), ('node2', self.client2)], m)
        self.setUpPyfakefs()

        self.set_initial_data_install_software()

        mock_run.return_value = CompletedProcess(args=f"echo '{os.path.join(self.dest_folder, self.filename)}'",
                                                 stdout='output',
                                                 returncode=0)

        resp = self.client.post(
            url_for('api_1_0.launch_orchestration', orchestration_id="00000015-0000-0000-0001-000000000000"),
            json={'hosts': ['node1', 'node2'], 'params': {'folder': self.dest_folder}, 'background': False},
            headers=self.auth.header)

        self.assertEqual(200, resp.status_code)
        data = resp.get_json()
        self.assertTrue(data['success'])