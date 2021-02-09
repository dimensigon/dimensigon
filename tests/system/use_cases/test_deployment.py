import os
import tempfile
from unittest import mock, TestCase

import responses
from flask import g

from dimensigon.domain.entities import ActionTemplate, ActionType, Orchestration, StepExecution, Step, User, \
    OrchExecution
from dimensigon.use_cases.deployment import deploy_orchestration
from dimensigon.utils.var_context import Context
from dimensigon.web import db
from tests.base import LockBypassMixin, TestBase, TwoNodeMixin
from tests.helpers import set_callbacks


class TestDeployOrchestration(TwoNodeMixin, LockBypassMixin, TestBase, TestCase):
    db_uris = ['sqlite:///' + os.path.join(tempfile.gettempdir(), 'node1.db'),
               'sqlite:///' + os.path.join(tempfile.gettempdir(), 'node2.db')]

    def fill_database(self):
        at1 = ActionTemplate(id='aaaaaaaa-1234-5678-1234-aaaaaaaa0001', name='create dir', version=1,
                             action_type=ActionType.SHELL, code='useradd {{input.user}}; mkdir {{input.dir}}',
                             expected_stdout='',
                             expected_rc=0, system_kwargs={})
        at2 = ActionTemplate(id='aaaaaaaa-1234-5678-1234-aaaaaaaa0002', name='rm dir', version=1,
                             action_type=ActionType.SHELL, code='rmuser {{input.user}}',
                             expected_stdout='',
                             expected_rc=0, system_kwargs={})
        at3 = ActionTemplate(id='aaaaaaaa-1234-5678-1234-aaaaaaaa0003', name='untar', version=1,
                             action_type=ActionType.SHELL, code='tar -xf {{input.dir}}',
                             expected_stdout='',
                             expected_rc=0, system_kwargs={})
        at4 = ActionTemplate(id='aaaaaaaa-1234-5678-1234-aaaaaaaa0004', name='install tibero',
                             version=1,
                             action_type=ActionType.SHELL, code='{{input.home}}/install_tibero.sh',
                             expected_stdout='',
                             expected_rc=0, system_kwargs={})

        o = Orchestration('Test Orchestration', 1, 'description',
                          id='bbbbbbbb-1234-5678-1234-bbbbbbbb0001')
        db.session.add(o)

        # Orch diagram
        # f   f
        # 1-->3-->u4-->u5-->u6
        #  \/  \    \_____/
        #  /\   \
        # 9-->u2 7-->u8
        # b

        s1 = o.add_step(id='dddddddd-1234-5678-1234-dddddddd0001', undo=False, action_template=at1,
                        parents=[], target=['frontend'])
        s2 = o.add_step(id='dddddddd-1234-5678-1234-dddddddd0002', undo=True, action_template=at2,
                        parents=[s1], target=[])
        s3 = o.add_step(id='dddddddd-1234-5678-1234-dddddddd0003', undo=False, action_template=at3,
                        parents=[s1], target=['frontend'])
        s4 = o.add_step(id='dddddddd-1234-5678-1234-dddddddd0004', undo=True, action_template=at2,
                        parents=[s3], target=[])
        s5 = o.add_step(id='dddddddd-1234-5678-1234-dddddddd0005', undo=True, action_template=at2,
                        parents=[s4], target=[])
        s6 = o.add_step(id='dddddddd-1234-5678-1234-dddddddd0006', undo=True, action_template=at2,
                        parents=[s4, s5], target=[])
        s7 = o.add_step(id='dddddddd-1234-5678-1234-dddddddd0007', undo=False, action_template=at4,
                        parents=[s3], target=[])
        s8 = o.add_step(id='dddddddd-1234-5678-1234-dddddddd0008', undo=True, action_template=at2,
                        parents=[s7], target=[])
        s9 = o.add_step(id='dddddddd-1234-5678-1234-dddddddd0009', undo=False, action_template=at1,
                        children=[s2, s3], target=['backend'])

    def setUp(self) -> None:
        def remove_db():
            for db in self.db_uris:
                try:
                    os.remove(db[10:])
                except:
                    pass

        remove_db()
        super().setUp()
        self.vs = Context({'user': 'joan', 'dir': '/opt/dimensigon', 'home': '/home/joan'},
                          dict(executor_id='00000000-0000-0000-0000-000000000001'))
        set_callbacks([('node1', self.app.test_client()), ('node2', self.app2.test_client())])

        # self.addCleanup(remove_db)

    @mock.patch('dimensigon.use_cases.operations.ShellOperation._run')
    @responses.activate
    def test_deploy_orchestration(self, mock_run):
        mock_run.side_effect = [('', '', 0),
                                ('', '', 0),
                                ('', '', 0),
                                ('', '', 0),
                                ('', '', 0)]

        g.server = self.s1
        o = Orchestration.query.get('bbbbbbbb-1234-5678-1234-bbbbbbbb0001')

        deploy_orchestration(o.id, var_context=self.vs,
                             hosts={'all': [self.s1.id, self.s2.id], 'frontend': [self.s1.id], 'backend': [self.s2.id]})

        self.assertEqual(1, OrchExecution.query.count())
        oe = OrchExecution.query.one()
        orch_execution_id = oe.id
        self.assertTrue(oe.success)
        self.assertEqual(o, oe.orchestration)
        self.assertDictEqual(
            {'all': [str(self.s1.id), str(self.s2.id)], 'frontend': [str(self.s1.id)], 'backend': [str(self.s2.id)]},
            oe.target)
        self.assertDictEqual(dict(self.vs), oe.params)
        self.assertEqual(User.get_by_name('root'), oe.executor)
        self.assertIsNone(oe.service)
        self.assertTrue(oe.success)
        self.assertIsNone(oe.undo_success)

        self.assertEqual(5, StepExecution.query.count())

        e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0001').filter_by(
            server_id=self.s1.id).one()
        self.assertTrue(e.success)

        e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0003').filter_by(
            server_id=self.s1.id).one()
        self.assertTrue(e.success)

        e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0007').filter_by(
            server_id=self.s1.id).one()
        self.assertTrue(e.success)

        e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0009').filter_by(
            server_id=self.s2.id).one()
        self.assertTrue(e.success)

        e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0007').filter_by(
            server_id=self.s2.id).one()
        self.assertTrue(e.success)

        with self.app2.app_context():
            self.assertEqual(1, OrchExecution.query.count())
            oe = OrchExecution.query.one()
            self.assertEqual(orch_execution_id, oe.id)
            self.assertEqual(o.id, oe.orchestration.id)
            self.assertDictEqual(
                {'all': [str(self.s1.id), str(self.s2.id)], 'frontend': [str(self.s1.id)],
                 'backend': [str(self.s2.id)]}, oe.target)
            self.assertDictEqual(dict(self.vs), oe.params)
            self.assertEqual(User.get_by_name('root'), oe.executor)
            self.assertIsNone(oe.service)
            # self.assertTrue(oe.success)
            # self.assertIsNone(oe.undo_success)

            self.assertEqual(2, StepExecution.query.count())

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0009').one()
            self.assertTrue(e.success)

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0007').one()
            self.assertTrue(e.success)

    @mock.patch('dimensigon.use_cases.operations.ShellOperation._run')
    @responses.activate
    def test_deploy_orchestration_stop_on_error(self, mock_run):
        mock_run.side_effect = [('', '', 0),
                                ('', '', 0),
                                ('err', '', 1),
                                ('', '', 0),
                                ('', '', 0),
                                ('', '', 0),
                                ('', '', 0),
                                ('', '', 0),
                                ('', '', 0)]

        o = Orchestration.query.get('bbbbbbbb-1234-5678-1234-bbbbbbbb0001')

        deploy_orchestration(o, var_context=self.vs,
                             hosts={'all': [self.s1.id, self.s2.id], 'frontend': [self.s1.id], 'backend': [self.s2.id]})

        self.assertEqual(1, OrchExecution.query.count())
        oe = OrchExecution.query.one()
        self.assertFalse(oe.success)
        self.assertTrue(oe.undo_success)

        self.assertEqual(8, StepExecution.query.count())

        e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0001').one()
        self.assertTrue(e.success)

        e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0003').one()
        self.assertFalse(e.success)

        ue4 = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0004').one()
        self.assertTrue(ue4.success)

        ue5 = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0005').one()
        self.assertTrue(ue5.success)
        self.assertGreater(ue5.start_time, ue4.start_time)

        ue6 = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0006').one()
        self.assertTrue(ue6.success)
        self.assertGreater(ue6.start_time, ue5.start_time)

        ue = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0002').filter_by(
            server_id=self.s1.id).one()
        self.assertTrue(ue.success)

        e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0009').one()
        self.assertTrue(e.success)

        ue = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0002').filter_by(
            server_id=self.s2.id).one()
        self.assertTrue(ue.success)

        with self.app2.app_context():
            self.assertEqual(2, StepExecution.query.count())

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0009').one()
            self.assertTrue(e.success)

            ue = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0002').one()
            self.assertTrue(ue.success)

    @mock.patch('dimensigon.use_cases.operations.ShellOperation._run')
    @responses.activate
    def test_deploy_orchestration_stop_on_error_false(self, mock_run):
        mock_run.side_effect = [('', '', 0),
                                ('', '', 0),
                                ('err', '', 1),
                                ('', '', 0),
                                ('', '', 0),
                                ('', '', 0),
                                ('', '', 0),
                                ('', '', 0),
                                ('', '', 0),
                                ('', '', 0),
                                ('', '', 0),
                                ('', '', 0),
                                ('', '', 0)
                                ]

        o = Orchestration.query.get('bbbbbbbb-1234-5678-1234-bbbbbbbb0001')
        o.stop_on_error = False
        deploy_orchestration(o, var_context=self.vs,
                             hosts={'all': [self.s1.id, self.s2.id], 'frontend': [self.s1.id], 'backend': [self.s2.id]})

        self.assertEqual(12, StepExecution.query.count())

        e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0001').one()
        self.assertTrue(e.success)

        e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0003').one()
        self.assertFalse(e.success)

        ue4 = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0004').one()
        self.assertTrue(ue4.success)

        ue5 = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0005').one()
        self.assertTrue(ue5.success)
        self.assertGreater(ue5.start_time, ue4.start_time)

        ue6 = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0006').one()
        self.assertTrue(ue6.success)
        self.assertGreater(ue6.start_time, ue5.start_time)

        e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0007').filter_by(
            server_id=self.s1.id).one()
        self.assertTrue(e.success)

        e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0008').filter_by(
            server_id=self.s1.id).one()
        self.assertTrue(e.success)

        e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0009').filter_by(
            server_id=self.s2.id).one()
        self.assertTrue(e.success)

        e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0007').filter_by(
            server_id=self.s2.id).one()
        self.assertTrue(e.success)

        ue = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0002').filter_by(
            server_id=self.s2.id).one()
        self.assertTrue(ue.success)

        ue = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0008').filter_by(
            server_id=self.s2.id).one()
        self.assertTrue(ue.success)

        with self.app2.app_context():
            self.assertEqual(4, StepExecution.query.count())

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0009').one()
            self.assertTrue(e.success)

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0007').one()
            self.assertTrue(e.success)

            ue = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0002').one()
            self.assertTrue(ue.success)

            ue = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0008').one()
            self.assertTrue(ue.success)

    @mock.patch('dimensigon.use_cases.operations.ShellOperation._run')
    @responses.activate
    def test_deploy_orchestration_step_stop_on_error_false(self, mock_run):
        mock_run.side_effect = [('err', '', 1),
                                ('', '', 0),
                                ('', '', 0),
                                ('', '', 0),
                                ('', '', 0),
                                ('', '', 0),
                                ('', '', 0),
                                ('', '', 0),
                                ('', '', 0),
                                ('', '', 0),
                                ('', '', 0),
                                ('', '', 0)
                                ]

        s = Step.query.get('dddddddd-1234-5678-1234-dddddddd0001')
        s.step_stop_on_error = False
        o = Orchestration.query.get('bbbbbbbb-1234-5678-1234-bbbbbbbb0001')
        deploy_orchestration(o, var_context=self.vs,
                             hosts={'all': [self.s1.id, self.s2.id], 'frontend': [self.s1.id], 'backend': [self.s2.id]})

        self.assertEqual(12, StepExecution.query.count())

        e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0001').one()
        self.assertFalse(e.success)

        e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0003').one()
        self.assertTrue(e.success)

        e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0007').filter_by(
            server_id=self.s1.id).one()
        self.assertTrue(e.success)

        ue81 = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0008').filter_by(
            server_id=self.s1.id).one()
        self.assertTrue(ue81.success)

        ue4 = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0004').one()
        self.assertTrue(ue4.success)

        ue5 = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0005').one()
        self.assertTrue(ue5.success)
        self.assertGreater(ue5.start_time, ue4.start_time)

        ue6 = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0006').one()
        self.assertTrue(ue6.success)
        self.assertGreater(ue6.start_time, ue5.start_time)

        ue21 = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0002').filter_by(
            server_id=self.s1.id).one()
        self.assertTrue(ue21.success)

        e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0009').filter_by(
            server_id=self.s2.id).one()
        self.assertTrue(e.success)

        e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0007').filter_by(
            server_id=self.s2.id).one()
        self.assertTrue(e.success)

        ue = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0002').filter_by(
            server_id=self.s2.id).one()
        self.assertTrue(ue.success)

        ue = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0008').filter_by(
            server_id=self.s2.id).one()
        self.assertTrue(ue.success)

        with self.app2.app_context():
            self.assertEqual(4, StepExecution.query.count())

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0009').one()
            self.assertTrue(e.success)

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0007').one()
            self.assertTrue(e.success)

            ue = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0002').one()
            self.assertTrue(ue.success)

            ue = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0008').one()
            self.assertTrue(ue.success)

    @mock.patch('dimensigon.use_cases.operations.ShellOperation._run')
    @responses.activate
    def test_deploy_orchestration_step_stop_on_error_true(self, mock_run):
        mock_run.side_effect = [('err', '', 1),
                                ('', '', 0),
                                ('', '', 0),
                                ('', '', 0)
                                ]

        s = Step.query.get('dddddddd-1234-5678-1234-dddddddd0001')
        s.step_stop_on_error = True
        o = Orchestration.query.get('bbbbbbbb-1234-5678-1234-bbbbbbbb0001')
        o.stop_on_error = False
        deploy_orchestration(o, var_context=self.vs,
                             hosts={'all': [self.s1.id, self.s2.id], 'frontend': [self.s1.id], 'backend': [self.s2.id]})

        self.assertEqual(4, StepExecution.query.count())

        e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0001').one()
        self.assertFalse(e.success)

        ue = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0002').filter_by(
            server_id=self.s1.id).one()
        self.assertTrue(ue.success)

        e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0009').filter_by(
            server_id=self.s2.id).one()
        self.assertTrue(e.success)

        ue = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0002').filter_by(
            server_id=self.s2.id).one()
        self.assertTrue(ue.success)

        with self.app2.app_context():
            self.assertEqual(2, StepExecution.query.count())

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0009').one()
            self.assertTrue(e.success)

            ue = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0002').one()
            self.assertTrue(ue.success)

    @mock.patch('dimensigon.use_cases.operations.ShellOperation._run')
    @responses.activate
    def test_deploy_orchestration_undo_on_error_false(self, mock_run):
        mock_run.side_effect = [('', '', 0),
                                ('', '', 0),
                                ('', '', 0),
                                ('', '', 0),
                                ('err', '', 1)]

        o = Orchestration.query.get('bbbbbbbb-1234-5678-1234-bbbbbbbb0001')
        o.undo_on_error = False
        deploy_orchestration(o, var_context=self.vs,
                             hosts={'all': [self.s1.id, self.s2.id], 'frontend': [self.s1.id], 'backend': [self.s2.id]})

        self.assertEqual(5, StepExecution.query.count())

        e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0001').one()
        self.assertTrue(e.success)

        e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0003').one()
        self.assertTrue(e.success)

        e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0007').filter_by(
            server_id=self.s1.id).one()
        self.assertTrue(e.success)

        e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0009').filter_by(
            server_id=self.s2.id).one()
        self.assertTrue(e.success)

        e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0007').filter_by(
            server_id=self.s2.id).one()
        self.assertFalse(e.success)

        with self.app2.app_context():
            self.assertEqual(2, StepExecution.query.count())

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0009').one()
            self.assertTrue(e.success)

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0007').one()
            self.assertFalse(e.success)

    @mock.patch('dimensigon.use_cases.operations.ShellOperation._run')
    @responses.activate
    def test_deploy_orchestration_step_undo_on_error_false(self, mock_run):
        mock_run.side_effect = [('', '', 0),
                                ('', '', 0),
                                ('', '', 0),
                                ('', '', 0),
                                ('err', '', 1),
                                ('', '', 0),
                                ('', '', 0),
                                ('', '', 0),
                                ('', '', 0),
                                ('', '', 0),
                                ('', '', 0), ]

        s = Step.query.get('dddddddd-1234-5678-1234-dddddddd0007')
        s.step_undo_on_error = False
        o = Orchestration.query.get('bbbbbbbb-1234-5678-1234-bbbbbbbb0001')
        deploy_orchestration(o, var_context=self.vs,
                             hosts={'all': [self.s1.id, self.s2.id], 'frontend': [self.s1.id], 'backend': [self.s2.id]},
                             )

        self.assertEqual(11, StepExecution.query.count())

        e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0001').one()
        self.assertTrue(e.success)

        e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0003').one()
        self.assertTrue(e.success)

        e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0007').filter_by(
            server_id=self.s1.id).one()
        self.assertTrue(e.success)

        ue = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0008').filter_by(
            server_id=self.s1.id).one()
        self.assertTrue(ue.success)

        ue4 = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0004').one()
        self.assertTrue(ue4.success)

        ue5 = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0005').one()
        self.assertTrue(ue5.success)
        self.assertGreater(ue5.start_time, ue4.start_time)

        ue6 = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0006').one()
        self.assertTrue(ue6.success)
        self.assertGreater(ue6.start_time, ue5.start_time)

        ue = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0002').filter_by(
            server_id=self.s1.id).one()
        self.assertTrue(ue.success)

        e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0009').filter_by(
            server_id=self.s2.id).one()
        self.assertTrue(e.success)

        e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0007').filter_by(
            server_id=self.s2.id).one()
        self.assertFalse(e.success)

        ue = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0002').filter_by(
            server_id=self.s2.id).one()
        self.assertTrue(ue.success)

        with self.app2.app_context():
            self.assertEqual(3, StepExecution.query.count())

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0009').one()
            self.assertTrue(e.success)

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0007').one()
            self.assertFalse(e.success)

            ue = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0002').one()
            self.assertTrue(ue.success)

    @mock.patch('dimensigon.use_cases.operations.ShellOperation._run')
    @responses.activate
    def test_deploy_orchestration_stop_undo_on_error_true(self, mock_run):
        mock_run.side_effect = [('', '', 0),
                                ('', '', 0),
                                ('err', '', 1),
                                ('', '', 0),
                                ('err', '', 1)]

        o = Orchestration.query.get('bbbbbbbb-1234-5678-1234-bbbbbbbb0001')
        o.stop_undo_on_error = True
        deploy_orchestration(o, var_context=self.vs,
                             hosts={'all': [self.s1.id, self.s2.id], 'frontend': [self.s1.id], 'backend': [self.s2.id]},
                             )

        self.assertEqual(5, StepExecution.query.count())

        e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0001').one()
        self.assertTrue(e.success)

        e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0003').one()
        self.assertFalse(e.success)

        ue = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0004').one()
        self.assertTrue(ue.success)

        ue = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0005').one()
        self.assertFalse(ue.success)

        e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0009').filter_by(
            server_id=self.s2.id).one()
        self.assertTrue(e.success)

        with self.app2.app_context():
            self.assertEqual(1, StepExecution.query.count())

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0009').one()
            self.assertTrue(e.success)

    @mock.patch('dimensigon.use_cases.operations.ShellOperation._run')
    @responses.activate
    def test_deploy_orchestration_step_stop_undo_on_error_true(self, mock_run):
        mock_run.side_effect = [('', '', 0),
                                ('', '', 0),
                                ('err', '', 1),
                                ('', '', 0),
                                ('err', '', 1)]

        s = Step.query.get('dddddddd-1234-5678-1234-dddddddd0003')
        s.step_stop_undo_on_error = True
        o = Orchestration.query.get('bbbbbbbb-1234-5678-1234-bbbbbbbb0001')
        deploy_orchestration(o, var_context=self.vs,
                             hosts={'all': [self.s1.id, self.s2.id], 'frontend': [self.s1.id], 'backend': [self.s2.id]},
                             )

        self.assertEqual(5, StepExecution.query.count())

        e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0001').one()
        self.assertTrue(e.success)

        e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0003').one()
        self.assertFalse(e.success)

        ue = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0004').one()
        self.assertTrue(ue.success)

        ue = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0005').one()
        self.assertFalse(ue.success)

        e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0009').filter_by(
            server_id=self.s2.id).one()
        self.assertTrue(e.success)

        with self.app2.app_context():
            self.assertEqual(1, StepExecution.query.count())

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0009').one()
            self.assertTrue(e.success)

    @mock.patch('dimensigon.use_cases.operations.ShellOperation._run')
    @responses.activate
    def test_deploy_orchestration_undo_step_stop_on_error_false(self, mock_run):
        mock_run.side_effect = [('', '', 0),
                                ('', '', 0),
                                ('err', '', 1),
                                ('', '', 0),
                                ('err', '', 1),
                                ('', '', 0)]

        s = Step.query.get('dddddddd-1234-5678-1234-dddddddd0005')
        s.step_stop_on_error = False
        o = Orchestration.query.get('bbbbbbbb-1234-5678-1234-bbbbbbbb0001')
        o.stop_undo_on_error = True
        deploy_orchestration(o, var_context=self.vs,
                             hosts={'all': [self.s1.id, self.s2.id], 'frontend': [self.s1.id], 'backend': [self.s2.id]},
                             )

        self.assertEqual(6, StepExecution.query.count())

        e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0001').one()
        self.assertTrue(e.success)

        e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0003').one()
        self.assertFalse(e.success)

        ue4 = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0004').one()
        self.assertTrue(ue4.success)

        ue5 = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0005').one()
        self.assertFalse(ue5.success)
        self.assertGreater(ue5.start_time, ue4.start_time)

        ue6 = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0006').one()
        self.assertTrue(ue6.success)
        self.assertGreater(ue6.start_time, ue5.start_time)

        e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0009').filter_by(
            server_id=self.s2.id).one()
        self.assertTrue(e.success)

        with self.app2.app_context():
            self.assertEqual(1, StepExecution.query.count())

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0009').one()
            self.assertTrue(e.success)

    @mock.patch('dimensigon.use_cases.operations.ShellOperation._run')
    @responses.activate
    def test_deploy_orchestration_stop_undo_on_error_false(self, mock_run):
        mock_run.side_effect = [('', '', 0),
                                ('', '', 0),
                                ('', '', 0),
                                ('err', '', 1),
                                ('', '', 0),
                                ('', '', 0),
                                ('err', '', 1),
                                ('', '', 0),
                                ('err', '', 1),
                                ('', '', 0),
                                ('', '', 0),
                                ('', '', 0)
                                ]

        o = Orchestration.query.get('bbbbbbbb-1234-5678-1234-bbbbbbbb0001')
        o.stop_undo_on_error = False
        deploy_orchestration(o, var_context=self.vs,
                             hosts={'all': [self.s1.id, self.s2.id], 'frontend': [self.s1.id], 'backend': [self.s2.id]},
                             )

        self.assertEqual(12, StepExecution.query.count())

        e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0001').one()
        self.assertTrue(e.success)

        e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0003').one()
        self.assertTrue(e.success)

        e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0007').filter_by(
            server_id=self.s1.id).one()
        self.assertFalse(e.success)

        ue = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0008').filter_by(
            server_id=self.s1.id).one()
        self.assertTrue(ue.success)

        ue = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0004').one()
        self.assertTrue(ue.success)

        ue = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0005').one()
        self.assertFalse(ue.success)

        ue = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0006').one()
        self.assertTrue(ue.success)

        ue = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0002').filter_by(
            server_id=self.s1.id).one()
        self.assertTrue(ue.success)

        e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0009').filter_by(
            server_id=self.s2.id).one()
        self.assertTrue(e.success)

        e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0007').filter_by(
            server_id=self.s2.id).one()
        self.assertTrue(e.success)

        ue = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0002').filter_by(
            server_id=self.s2.id).one()
        self.assertTrue(ue.success)

        ue = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0008').filter_by(
            server_id=self.s2.id).one()
        self.assertFalse(ue.success)

        with self.app2.app_context():
            self.assertEqual(4, StepExecution.query.count())

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0009').one()
            self.assertTrue(e.success)

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0007').one()
            self.assertTrue(e.success)

            ue = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0008').one()
            self.assertFalse(ue.success)

            ue = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0002').one()
            self.assertTrue(ue.success)
