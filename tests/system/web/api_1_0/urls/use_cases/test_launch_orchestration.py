import json
import os
import tempfile
from pprint import pprint
from unittest import mock, TestCase

from flask import url_for, current_app
from pyfakefs.fake_filesystem_unittest import TestCase as FSTestCase

from dimensigon import defaults
from dimensigon.domain.entities import User, ActionTemplate, ActionType, Orchestration, \
    OrchExecution, \
    StepExecution, Vault, Software, SoftwareServerAssociation
from dimensigon.domain.entities.user import ROOT
from dimensigon.use_cases.operations import CompletedProcess
from dimensigon.web import db
from tests.base import TwoNodeMixin, OneNodeMixin, VirtualNetworkMixin
from tests.helpers import request_scope

now = defaults.INITIAL_DATEMARK


# function used to mock Operation._execute
def operation_execute(self, params, timeout=None, context=None):
    cp = CompletedProcess()
    cp.set_start_time()
    cp.stdout = self.rpl_params(**params, env=context.env)
    cp.stderr = None
    cp.rc = 0
    cp.success = True
    self.evaluate_result(cp, context)
    return cp


class TestLaunchOrchestrationNested(TwoNodeMixin, VirtualNetworkMixin, TestCase):

    def fill_database(self):
        # create data for orchestration
        at = ActionTemplate(name='mkdir', version=1, action_type=ActionType.SHELL, code='mkdir -f {{input.folder}}',
                            schema={'input': {'folder': {'type': 'string'}},
                                    'required': ['folder']},
                            expected_rc=0)
        o = Orchestration(name='Create folder', version=1, description="creates a folder")
        s = o.add_step(undo=False, action_template=at)

        db.session.add_all([at, o, s])
        o_wrapper = Orchestration(name="launch create folder", version=1)

        s21 = o_wrapper.add_step(undo=False,
                                 action_template=ActionTemplate.query.get(ActionTemplate.ORCHESTRATION),
                                 schema={'mapping': {'orchestration': str(o.id), }},
                                 parents=[]
                                 )

        db.session.add_all([o_wrapper, s21])

    @mock.patch('dimensigon.use_cases.operations.ShellOperation._execute', operation_execute)
    def test_launch_orchestration_nested_orchestration(self):
        self.o = Orchestration.query.filter_by(name='Create folder', version=1).one()
        self.o_wrapper = Orchestration.query.filter_by(name="launch create folder", version=1).one()
        resp = self.client.post(url_for('api_1_0.launch_orchestration', orchestration_id=self.o_wrapper.id),
                                json={'hosts': 'node1', 'params': {'folder': '/new_folder', 'hosts': 'node2'},
                                      'background': False},
                                headers=self.auth.header)

        self.assertIn(resp.status_code, (200, 202))

        o_id = self.o.id
        with self.app2.app_context():
            oe1: OrchExecution = OrchExecution.query.filter_by(orchestration_id=o_id).one()
            self.assertEqual(1, len(oe1.step_executions))
            se1: StepExecution = oe1.step_executions[0]
            self.assertEqual(True, se1.success)
            self.assertEqual('mkdir -f /new_folder', se1.stdout)
            self.assertEqual(None, se1.stderr)
            self.assertEqual(0, se1.rc)
            self.assertEqual(self.s2.id, se1.server.id)

        # check inner orch
        oe1: OrchExecution = OrchExecution.query.filter_by(orchestration_id=self.o.id).one()
        self.assertEqual(User.get_by_name('root'), oe1.executor)
        self.assertEqual(True, oe1.success)
        self.assertDictEqual({'folder': '/new_folder'}, oe1.params)
        self.assertEqual(1, len(oe1.step_executions))

        # check wrapper orch
        oe2: OrchExecution = OrchExecution.query.filter_by(orchestration_id=self.o_wrapper.id).one()
        self.assertEqual(User.get_by_name('root'), oe2.executor)
        self.assertEqual(True, oe2.success)
        self.assertDictEqual({'folder': '/new_folder', 'hosts': 'node2'}, oe2.params)
        self.assertEqual(1, len(oe2.step_executions))
        se21: StepExecution = StepExecution.query.filter_by(step=self.o_wrapper.steps[0]).one()
        self.assertEqual(True, se21.success)
        self.assertEqual(f'orch_execution_id={oe1.id}', se21.stdout)
        self.assertEqual(None, se21.stderr)
        self.assertEqual(None, se21.rc)
        self.assertEqual(self.s1.id, se21.server.id)


class TestLaunchOrchestrationSoftware(TwoNodeMixin, VirtualNetworkMixin, FSTestCase):
    db_uris = ['sqlite:///' + os.path.join(tempfile.gettempdir(), 'node1.db'),
               'sqlite:///' + os.path.join(tempfile.gettempdir(), 'node2.db')]
    scopefunc = request_scope
    SOFTWARE = "00000019-0000-0000-0000-000000000001"
    ORCH = "00000015-0000-0000-0001-000000000000"
    STEP1 = "00000015-0000-0000-0001-000000000001"
    STEP2 = "00000015-0000-0000-0001-000000000002"

    def setUp(self):
        self.source_folder = '/source'
        self.dest_folder = '/dest'
        self.filename = 'Python-3.8.3.tgz'
        self.content = '1234'
        self.size = 4
        self.checksum = "4"
        super().setUp()

    def activate_filesystem(self):
        self.setUpPyfakefs()
        os.makedirs(self.source_folder)
        os.makedirs(self.dest_folder)
        with open(os.path.join(self.source_folder, self.filename), 'w') as fh:
            fh.write(self.content)

    def fill_database(self):
        soft = Software(name="python", version="3.8.3", family="programming", filename=self.filename,
                        size=self.size, checksum=self.checksum, id=self.SOFTWARE,
                        last_modified_at=defaults.INITIAL_DATEMARK.strftime(defaults.DATEMARK_FORMAT))

        ssa = SoftwareServerAssociation(software_id=self.SOFTWARE, server_id=self.SERVER1,
                                        path=self.source_folder,
                                        last_modified_at=defaults.INITIAL_DATEMARK.strftime(
                                            defaults.DATEMARK_FORMAT))

        o = Orchestration(name="install python 3.8.3", version=1, description="installs python 3.8.3",
                          id=self.ORCH,
                          last_modified_at=defaults.INITIAL_DATEMARK.strftime(defaults.DATEMARK_FORMAT))

        s1 = o.add_step(id=self.STEP1, action_template=ActionTemplate.query.get(ActionTemplate.SEND_SOFTWARE),
                        undo=False, undo_on_error=False,
                        schema={"mapping": {"software": self.SOFTWARE,
                                            "server": {"from": "env.server_id"}}},
                        last_modified_at=defaults.INITIAL_DATEMARK.strftime(defaults.DATEMARK_FORMAT))
        o.add_step(id=self.STEP2, undo=False, undo_on_error=False, parents=[s1],
                   code="{{input.file}}", action_type="SHELL", expected_rc=0,
                   last_modified_at=defaults.INITIAL_DATEMARK.strftime(defaults.DATEMARK_FORMAT))
        db.session.add_all([soft, ssa, o])

    @mock.patch('dimensigon.use_cases.operations.ShellOperation._execute', operation_execute)
    @mock.patch('dimensigon.web.api_1_0.resources.transfer.current_app', autospec=True)
    def test_launch_orchestration_install_software_local(self, mock_current_app):
        self.activate_filesystem()
        resp = self.client.post(
            url_for('api_1_0.launch_orchestration', orchestration_id=self.ORCH),
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
            dict(input=dict(dest_path=self.dest_folder, software=self.SOFTWARE, server=self.s1.id)),
            exec_step1.get('params'))

        self.assertEqual(0, exec_step2.get('rc'))
        self.assertEqual(os.path.join(self.dest_folder, self.filename), exec_step2.get('stdout'))
        self.assertEqual(None, exec_step2.get('stderr'))
        self.assertDictEqual(
            dict(input=dict(file=os.path.join(self.dest_folder, self.filename), dest_path=self.dest_folder)),
            exec_step2.get('params'))

        self.assertTrue(os.path.exists(os.path.join(self.dest_folder, self.filename)))

    @mock.patch('dimensigon.use_cases.operations.ShellOperation._execute', operation_execute)
    @mock.patch('dimensigon.web.api_1_0.resources.transfer.current_app')
    def test_launch_orchestration_install_software_remote(self, mock_current_app):
        self.activate_filesystem()
        resp = self.client.post(
            url_for('api_1_0.launch_orchestration', orchestration_id=self.ORCH),
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
        self.assertDictEqual(dict(input=dict(dest_path=self.dest_folder, software=self.SOFTWARE, server=self.s2.id)),
                             exec_step1.get('params'))

        self.assertEqual(0, exec_step2.get('rc'))
        self.assertEqual(os.path.join(self.dest_folder, self.filename), exec_step2.get('stdout'))
        self.assertEqual(None, exec_step2.get('stderr'))
        self.assertDictEqual(
            dict(input=dict(file=os.path.join(self.dest_folder, self.filename), dest_path=self.dest_folder)),
            exec_step2.get('params'))

        self.assertTrue(os.path.exists(os.path.join(self.dest_folder, self.filename)))

    @mock.patch('dimensigon.use_cases.operations.ShellOperation._execute', operation_execute)
    @mock.patch('dimensigon.web.api_1_0.resources.transfer.current_app')
    def test_launch_orchestration_install_software_dual(self, mock_current_app):
        self.activate_filesystem()

        def path(soft_path):
            if current_app == self.app:
                return os.path.join('/node1', soft_path)
            else:
                return os.path.join('/node2', soft_path)

        mock_current_app.dm.config.path.side_effect = path

        resp = self.client.post(
            url_for('api_1_0.launch_orchestration', orchestration_id=self.ORCH),
            json={'hosts': ['node1', 'node2'], 'background': False},
            headers=self.auth.header)

        self.assertEqual(200, resp.status_code)
        data = resp.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(4, len(data['steps']))

        exec_step1_s1 = [s for s in data['steps'] if
                         s['step_id'] == self.STEP1 and s['server_id'] == self.s1.id][0]
        exec_step2_s1 = [s for s in data['steps'] if
                         s['step_id'] == self.STEP2 and s['server_id'] == self.s1.id][0]
        exec_step1_s2 = [s for s in data['steps'] if
                         s['step_id'] == self.STEP1 and s['server_id'] == self.s2.id][0]
        exec_step2_s2 = [s for s in data['steps'] if
                         s['step_id'] == self.STEP2 and s['server_id'] == self.s2.id][0]
        self.assertEqual(201, exec_step1_s1.get('rc'))
        step_out = json.loads(exec_step1_s1.get('stdout'))
        self.assertEqual(os.path.join('/node1', defaults.SOFTWARE_REPO, self.filename), step_out.get('file'))
        self.assertIn('id', step_out)
        self.assertDictEqual(dict(input=dict(software=self.SOFTWARE, server=self.s1.id)),
                             exec_step1_s1.get('params'))

        self.assertEqual(201, exec_step1_s2.get('rc'))
        step_out = json.loads(exec_step1_s2.get('stdout'))
        self.assertEqual(os.path.join('/node2', defaults.SOFTWARE_REPO, self.filename), step_out.get('file'))
        self.assertIn('id', step_out)
        self.assertDictEqual(dict(input=dict(software=self.SOFTWARE, server=self.s2.id)),
                             exec_step1_s2.get('params'))

        self.assertEqual(0, exec_step2_s1.get('rc'))
        self.assertEqual('/node1/software/Python-3.8.3.tgz', exec_step2_s1.get('stdout'))
        self.assertEqual(None, exec_step2_s1.get('stderr'))
        self.assertDictEqual(dict(input=dict(file='/node1/software/Python-3.8.3.tgz')),
                             exec_step2_s1.get('params'))

        self.assertEqual(0, exec_step2_s2.get('rc'))
        self.assertEqual('/node2/software/Python-3.8.3.tgz', exec_step2_s2.get('stdout'))
        self.assertEqual(None, exec_step2_s2.get('stderr'))
        self.assertDictEqual(dict(input=dict(file='/node2/software/Python-3.8.3.tgz')),
                             exec_step2_s2.get('params'))

        self.assertTrue(os.path.exists(os.path.join('/node1', defaults.SOFTWARE_REPO, self.filename)))
        self.assertTrue(os.path.exists(os.path.join('/node2', defaults.SOFTWARE_REPO, self.filename)))


class TestLaunchOrchestrationVault(OneNodeMixin, VirtualNetworkMixin, TestCase):
    ACTION_TEMPLATE1 = "0000000a-0000-0000-0000-000000000001"
    ACTION_TEMPLATE2 = "0000000a-0000-0000-0000-000000000002"
    ORCH = "00000015-0000-0000-0001-000000000000"

    def fill_database(self):
        v1 = Vault(user_id=ROOT, name='home', value='home_content')
        v2 = Vault(user_id=ROOT, name='command', value='command_content')
        v3 = Vault(user_id=ROOT, name='foo', value='foo_content')

        at = ActionTemplate('vault var in mapping', 1, action_type=ActionType.TEST, code='{{input.command}}',
                            schema=dict(input=dict(command=dict(type='string')), required=['command']),
                            id=self.ACTION_TEMPLATE1)
        at2 = ActionTemplate('vault var in action template code', 1, action_type=ActionType.TEST, code='{{vault.foo}}',
                             schema=dict(required=['vault.foo']),
                             id=self.ACTION_TEMPLATE2)
        o = Orchestration('vault', 1, id=self.ORCH)
        s1 = o.add_step(False, name='vault var in step code', action_type=ActionType.TEST, code="{{vault.home}}")
        s2 = o.add_step(False, action_template=at, schema=dict(mapping={'command': {'from': 'vault.command'}}),
                        parents=[s1])
        s3 = o.add_step(False, action_template=at2, parents=[s2])

        db.session.add_all([v1, v2, v3, o])

    @mock.patch('dimensigon.use_cases.operations.ShellOperation._execute', operation_execute)
    def test_launch_orchestration_vault(self):
        resp = self.client.post(
            url_for('api_1_0.launch_orchestration', orchestration_id=self.ORCH),
            json={'hosts': 'node1', 'params': {}, 'background': False},
            headers=self.auth.header)

        if resp.status_code != 200:
            pprint(resp.get_json())
        self.assertEqual(200, resp.status_code)
        data = resp.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(3, len(data['steps']))
        exec_step1 = data['steps'][0]
        exec_step2 = data['steps'][1]
        exec_step3 = data['steps'][2]
        self.assertEqual('home_content', exec_step1['stdout'])
        self.assertEqual('command_content', exec_step2['stdout'])
        self.assertEqual('foo_content', exec_step3['stdout'])
