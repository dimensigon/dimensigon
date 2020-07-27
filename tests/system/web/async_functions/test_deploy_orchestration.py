from subprocess import CompletedProcess
from unittest import mock

import responses
from flask import g

from dimensigon.domain.entities import Server, ActionTemplate, ActionType, Orchestration, StepExecution, Step, User, \
    OrchExecution
from dimensigon.domain.entities.route import Route
from dimensigon.utils.var_context import VarContext
from dimensigon.web import create_app, db
from dimensigon.web.async_functions import deploy_orchestration
from tests.helpers import TestCaseLockBypass, set_callbacks


class TestDeployOrchestration(TestCaseLockBypass):

    def setUp(self) -> None:
        self.maxDiff = None
        self.app = create_app('test')
        self.app2 = create_app('test')

        self.client = self.app.test_client()
        for app in [self.app, self.app2]:
            with app.app_context():
                db.create_all()
                User.set_initial()
                at1 = ActionTemplate(id='aaaaaaaa-1234-5678-1234-aaaaaaaa0001', name='create dir', version=1,
                                     action_type=ActionType.SHELL, code='useradd {{user}}; mkdir {{dir}}',
                                     parameters={}, expected_stdout='',
                                     expected_rc=0, system_kwargs={})
                at2 = ActionTemplate(id='aaaaaaaa-1234-5678-1234-aaaaaaaa0002', name='rm dir', version=1,
                                     action_type=ActionType.SHELL, code='rmuser {{user}}',
                                     parameters={}, expected_stdout='',
                                     expected_rc=0, system_kwargs={})
                at3 = ActionTemplate(id='aaaaaaaa-1234-5678-1234-aaaaaaaa0003', name='untar', version=1,
                                     action_type=ActionType.SHELL, code='tar -xf {{dir}}',
                                     parameters={}, expected_stdout='',
                                     expected_rc=0, system_kwargs={})
                at4 = ActionTemplate(id='aaaaaaaa-1234-5678-1234-aaaaaaaa0004', name='install tibero',
                                     version=1,
                                     action_type=ActionType.SHELL, code='{{home}}/install_tibero.sh',
                                     parameters={}, expected_stdout='',
                                     expected_rc=0, system_kwargs={})

                o = Orchestration('Test Orchestration', 1, 'description',
                                  id='bbbbbbbb-1234-5678-1234-bbbbbbbb0001')

                me = Server('me', port=5000, me=app == self.app, id='cccccccc-1234-5678-1234-cccccccc0001')
                remote = Server('remote', port=5000, me=app == self.app2,
                                id='cccccccc-1234-5678-1234-cccccccc0002')
                if app == self.app:
                    r = Route(remote, cost=0)
                else:
                    r = Route(me, cost=0)
                db.session.add_all([me, remote, o, r])

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
                db.session.commit()
        self.vs = VarContext(globals=dict(executor_id='00000000-0000-0000-0000-000000000001'),
                             defaults={'user': 'joan', 'dir': '/opt/dimensigon',
                                       'home': '{{dir}}'}, )
        set_callbacks([('me', self.app.test_client()), ('remote', self.app2.test_client())])

    def tearDown(self) -> None:
        for app in [self.app, self.app2]:
            with app.app_context():
                db.session.remove()
                db.drop_all()

    @mock.patch('dimensigon.use_cases.operations.subprocess.run')
    @responses.activate
    def test_deploy_orchestration(self, mock_run):
        mock_run.side_effect = [CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr='')]

        with self.app.app_context():
            me = Server.query.get('cccccccc-1234-5678-1234-cccccccc0001')
            g.server = me
            remote = Server.query.get('cccccccc-1234-5678-1234-cccccccc0002')
            o = Orchestration.query.get('bbbbbbbb-1234-5678-1234-bbbbbbbb0001')

            deploy_orchestration(o.id, var_context=self.vs,
                                 hosts={'all': [me.id, remote.id], 'frontend': [me.id], 'backend': [remote.id]})

            self.assertEqual(1, OrchExecution.query.count())
            oe = OrchExecution.query.one()
            orch_execution_id = oe.id
            self.assertTrue(oe.success)
            self.assertEqual(o, oe.orchestration)
            self.assertDictEqual(
                {'all': [str(me.id), str(remote.id)], 'frontend': [str(me.id)], 'backend': [str(remote.id)]}, oe.target)
            self.assertDictEqual(dict(self.vs), oe.params)
            self.assertEqual(User.get_by_user('root'), oe.executor)
            self.assertIsNone(oe.service)
            self.assertTrue(oe.success)
            self.assertIsNone(oe.undo_success)

            self.assertEqual(5, StepExecution.query.count())

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0001').filter_by(
                server_id='cccccccc-1234-5678-1234-cccccccc0001').one()
            self.assertTrue(e.success)

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0003').filter_by(
                server_id='cccccccc-1234-5678-1234-cccccccc0001').one()
            self.assertTrue(e.success)

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0007').filter_by(
                server_id='cccccccc-1234-5678-1234-cccccccc0001').one()
            self.assertTrue(e.success)

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0009').filter_by(
                server_id='cccccccc-1234-5678-1234-cccccccc0002').one()
            self.assertTrue(e.success)

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0007').filter_by(
                server_id='cccccccc-1234-5678-1234-cccccccc0002').one()
            self.assertTrue(e.success)

        with self.app2.app_context():
            self.assertEqual(1, OrchExecution.query.count())
            oe = OrchExecution.query.one()
            self.assertEqual(orch_execution_id, oe.id)
            self.assertEqual(o.id, oe.orchestration.id)
            self.assertDictEqual(
                {'all': [str(me.id), str(remote.id)], 'frontend': [str(me.id)], 'backend': [str(remote.id)]}, oe.target)
            self.assertDictEqual(dict(self.vs), oe.params)
            self.assertEqual(User.get_by_user('root'), oe.executor)
            self.assertIsNone(oe.service)
            # self.assertTrue(oe.success)
            # self.assertIsNone(oe.undo_success)

            self.assertEqual(2, StepExecution.query.count())

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0009').one()
            self.assertTrue(e.success)

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0007').one()
            self.assertTrue(e.success)

    @mock.patch('dimensigon.use_cases.operations.subprocess.run')
    @responses.activate
    def test_deploy_orchestration_stop_on_error(self, mock_run):
        mock_run.side_effect = [CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=1, stdout='err', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr='')]

        with self.app.app_context():
            me = Server.query.get('cccccccc-1234-5678-1234-cccccccc0001')
            remote = Server.query.get('cccccccc-1234-5678-1234-cccccccc0002')
            o = Orchestration.query.get('bbbbbbbb-1234-5678-1234-bbbbbbbb0001')

            deploy_orchestration(o, var_context=self.vs,
                                 hosts={'all': [me.id, remote.id], 'frontend': [me.id], 'backend': [remote.id]})

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
                server_id='cccccccc-1234-5678-1234-cccccccc0001').one()
            self.assertTrue(ue.success)

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0009').one()
            self.assertTrue(e.success)

            ue = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0002').filter_by(
                server_id='cccccccc-1234-5678-1234-cccccccc0002').one()
            self.assertTrue(ue.success)

        with self.app2.app_context():
            self.assertEqual(2, StepExecution.query.count())

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0009').one()
            self.assertTrue(e.success)

            ue = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0002').one()
            self.assertTrue(ue.success)

    @mock.patch('dimensigon.use_cases.operations.subprocess.run')
    @responses.activate
    def test_deploy_orchestration_stop_on_error_false(self, mock_run):
        mock_run.side_effect = [CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=1, stdout='err', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr='')
                                ]

        with self.app.app_context():
            me = Server.query.get('cccccccc-1234-5678-1234-cccccccc0001')
            remote = Server.query.get('cccccccc-1234-5678-1234-cccccccc0002')
            o = Orchestration.query.get('bbbbbbbb-1234-5678-1234-bbbbbbbb0001')
            o.stop_on_error = False
            deploy_orchestration(o, var_context=self.vs,
                                 hosts={'all': [me.id, remote.id], 'frontend': [me.id], 'backend': [remote.id]})

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
                server_id='cccccccc-1234-5678-1234-cccccccc0001').one()
            self.assertTrue(e.success)

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0008').filter_by(
                server_id='cccccccc-1234-5678-1234-cccccccc0001').one()
            self.assertTrue(e.success)

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0009').filter_by(
                server_id='cccccccc-1234-5678-1234-cccccccc0002').one()
            self.assertTrue(e.success)

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0007').filter_by(
                server_id='cccccccc-1234-5678-1234-cccccccc0002').one()
            self.assertTrue(e.success)

            ue = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0002').filter_by(
                server_id='cccccccc-1234-5678-1234-cccccccc0002').one()
            self.assertTrue(ue.success)

            ue = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0008').filter_by(
                server_id='cccccccc-1234-5678-1234-cccccccc0002').one()
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

    @mock.patch('dimensigon.use_cases.operations.subprocess.run')
    @responses.activate
    def test_deploy_orchestration_step_stop_on_error_false(self, mock_run):
        mock_run.side_effect = [CompletedProcess(args=(), returncode=1, stdout='err', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr='')
                                ]

        with self.app.app_context():
            s = Step.query.get('dddddddd-1234-5678-1234-dddddddd0001')
            s.step_stop_on_error = False
            me = Server.query.get('cccccccc-1234-5678-1234-cccccccc0001')
            remote = Server.query.get('cccccccc-1234-5678-1234-cccccccc0002')
            o = Orchestration.query.get('bbbbbbbb-1234-5678-1234-bbbbbbbb0001')
            deploy_orchestration(o, var_context=self.vs,
                                 hosts={'all': [me.id, remote.id], 'frontend': [me.id], 'backend': [remote.id]})

            self.assertEqual(12, StepExecution.query.count())

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0001').one()
            self.assertFalse(e.success)

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0003').one()
            self.assertTrue(e.success)

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0007').filter_by(
                server_id='cccccccc-1234-5678-1234-cccccccc0001').one()
            self.assertTrue(e.success)

            ue81 = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0008').filter_by(
                server_id='cccccccc-1234-5678-1234-cccccccc0001').one()
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
                server_id='cccccccc-1234-5678-1234-cccccccc0001').one()
            self.assertTrue(ue21.success)

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0009').filter_by(
                server_id='cccccccc-1234-5678-1234-cccccccc0002').one()
            self.assertTrue(e.success)

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0007').filter_by(
                server_id='cccccccc-1234-5678-1234-cccccccc0002').one()
            self.assertTrue(e.success)

            ue = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0002').filter_by(
                server_id='cccccccc-1234-5678-1234-cccccccc0002').one()
            self.assertTrue(ue.success)

            ue = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0008').filter_by(
                server_id='cccccccc-1234-5678-1234-cccccccc0002').one()
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

    @mock.patch('dimensigon.use_cases.operations.subprocess.run')
    @responses.activate
    def test_deploy_orchestration_step_stop_on_error_true(self, mock_run):
        mock_run.side_effect = [CompletedProcess(args=(), returncode=1, stdout='err', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr='')
                                ]

        with self.app.app_context():
            s = Step.query.get('dddddddd-1234-5678-1234-dddddddd0001')
            s.step_stop_on_error = True
            me = Server.query.get('cccccccc-1234-5678-1234-cccccccc0001')
            remote = Server.query.get('cccccccc-1234-5678-1234-cccccccc0002')
            o = Orchestration.query.get('bbbbbbbb-1234-5678-1234-bbbbbbbb0001')
            o.stop_on_error = False
            deploy_orchestration(o, var_context=self.vs,
                                 hosts={'all': [me.id, remote.id], 'frontend': [me.id], 'backend': [remote.id]})

            self.assertEqual(4, StepExecution.query.count())

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0001').one()
            self.assertFalse(e.success)

            ue = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0002').filter_by(
                server_id='cccccccc-1234-5678-1234-cccccccc0001').one()
            self.assertTrue(ue.success)

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0009').filter_by(
                server_id='cccccccc-1234-5678-1234-cccccccc0002').one()
            self.assertTrue(e.success)

            ue = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0002').filter_by(
                server_id='cccccccc-1234-5678-1234-cccccccc0002').one()
            self.assertTrue(ue.success)

        with self.app2.app_context():
            self.assertEqual(2, StepExecution.query.count())

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0009').one()
            self.assertTrue(e.success)

            ue = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0002').one()
            self.assertTrue(ue.success)

    @mock.patch('dimensigon.use_cases.operations.subprocess.run')
    @responses.activate
    def test_deploy_orchestration_undo_on_error_false(self, mock_run):
        mock_run.side_effect = [CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=1, stdout='err', stderr='')]

        with self.app.app_context():
            me = Server.query.get('cccccccc-1234-5678-1234-cccccccc0001')
            remote = Server.query.get('cccccccc-1234-5678-1234-cccccccc0002')
            o = Orchestration.query.get('bbbbbbbb-1234-5678-1234-bbbbbbbb0001')
            o.undo_on_error = False
            deploy_orchestration(o, var_context=self.vs,
                                 hosts={'all': [me.id, remote.id], 'frontend': [me.id], 'backend': [remote.id]})

            self.assertEqual(5, StepExecution.query.count())

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0001').one()
            self.assertTrue(e.success)

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0003').one()
            self.assertTrue(e.success)

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0007').filter_by(
                server_id='cccccccc-1234-5678-1234-cccccccc0001').one()
            self.assertTrue(e.success)

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0009').filter_by(
                server_id='cccccccc-1234-5678-1234-cccccccc0002').one()
            self.assertTrue(e.success)

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0007').filter_by(
                server_id='cccccccc-1234-5678-1234-cccccccc0002').one()
            self.assertFalse(e.success)

        with self.app2.app_context():
            self.assertEqual(2, StepExecution.query.count())

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0009').one()
            self.assertTrue(e.success)

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0007').one()
            self.assertFalse(e.success)

    @mock.patch('dimensigon.use_cases.operations.subprocess.run')
    @responses.activate
    def test_deploy_orchestration_step_undo_on_error_false(self, mock_run):
        mock_run.side_effect = [CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=1, stdout='err', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr=''), ]

        with self.app.app_context():
            s = Step.query.get('dddddddd-1234-5678-1234-dddddddd0007')
            s.step_undo_on_error = False
            me = Server.query.get('cccccccc-1234-5678-1234-cccccccc0001')
            remote = Server.query.get('cccccccc-1234-5678-1234-cccccccc0002')
            o = Orchestration.query.get('bbbbbbbb-1234-5678-1234-bbbbbbbb0001')
            deploy_orchestration(o, var_context=self.vs,
                                 hosts={'all': [me.id, remote.id], 'frontend': [me.id], 'backend': [remote.id]},
                                 )

            self.assertEqual(11, StepExecution.query.count())

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0001').one()
            self.assertTrue(e.success)

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0003').one()
            self.assertTrue(e.success)

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0007').filter_by(
                server_id='cccccccc-1234-5678-1234-cccccccc0001').one()
            self.assertTrue(e.success)

            ue = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0008').filter_by(
                server_id='cccccccc-1234-5678-1234-cccccccc0001').one()
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
                server_id='cccccccc-1234-5678-1234-cccccccc0001').one()
            self.assertTrue(ue.success)

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0009').filter_by(
                server_id='cccccccc-1234-5678-1234-cccccccc0002').one()
            self.assertTrue(e.success)

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0007').filter_by(
                server_id='cccccccc-1234-5678-1234-cccccccc0002').one()
            self.assertFalse(e.success)

            ue = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0002').filter_by(
                server_id='cccccccc-1234-5678-1234-cccccccc0002').one()
            self.assertTrue(ue.success)

        with self.app2.app_context():
            self.assertEqual(3, StepExecution.query.count())

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0009').one()
            self.assertTrue(e.success)

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0007').one()
            self.assertFalse(e.success)

            ue = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0002').one()
            self.assertTrue(ue.success)

    @mock.patch('dimensigon.use_cases.operations.subprocess.run')
    @responses.activate
    def test_deploy_orchestration_stop_undo_on_error_true(self, mock_run):
        mock_run.side_effect = [CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=1, stdout='err', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=1, stdout='err', stderr='')]

        with self.app.app_context():
            me = Server.query.get('cccccccc-1234-5678-1234-cccccccc0001')
            remote = Server.query.get('cccccccc-1234-5678-1234-cccccccc0002')
            o = Orchestration.query.get('bbbbbbbb-1234-5678-1234-bbbbbbbb0001')
            o.stop_undo_on_error = True
            deploy_orchestration(o, var_context=self.vs,
                                 hosts={'all': [me.id, remote.id], 'frontend': [me.id], 'backend': [remote.id]},
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
                server_id='cccccccc-1234-5678-1234-cccccccc0002').one()
            self.assertTrue(e.success)

        with self.app2.app_context():
            self.assertEqual(1, StepExecution.query.count())

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0009').one()
            self.assertTrue(e.success)

    @mock.patch('dimensigon.use_cases.operations.subprocess.run')
    @responses.activate
    def test_deploy_orchestration_step_stop_undo_on_error_true(self, mock_run):
        mock_run.side_effect = [CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=1, stdout='err', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=1, stdout='err', stderr='')]

        with self.app.app_context():
            s = Step.query.get('dddddddd-1234-5678-1234-dddddddd0003')
            s.step_stop_undo_on_error = True
            me = Server.query.get('cccccccc-1234-5678-1234-cccccccc0001')
            remote = Server.query.get('cccccccc-1234-5678-1234-cccccccc0002')
            o = Orchestration.query.get('bbbbbbbb-1234-5678-1234-bbbbbbbb0001')
            deploy_orchestration(o, var_context=self.vs,
                                 hosts={'all': [me.id, remote.id], 'frontend': [me.id], 'backend': [remote.id]},
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
                server_id='cccccccc-1234-5678-1234-cccccccc0002').one()
            self.assertTrue(e.success)

        with self.app2.app_context():
            self.assertEqual(1, StepExecution.query.count())

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0009').one()
            self.assertTrue(e.success)

    @mock.patch('dimensigon.use_cases.operations.subprocess.run')
    @responses.activate
    def test_deploy_orchestration_undo_step_stop_on_error_false(self, mock_run):
        mock_run.side_effect = [CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=1, stdout='err', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=1, stdout='err', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr='')]

        with self.app.app_context():
            s = Step.query.get('dddddddd-1234-5678-1234-dddddddd0005')
            s.step_stop_on_error = False
            me = Server.query.get('cccccccc-1234-5678-1234-cccccccc0001')
            remote = Server.query.get('cccccccc-1234-5678-1234-cccccccc0002')
            o = Orchestration.query.get('bbbbbbbb-1234-5678-1234-bbbbbbbb0001')
            o.stop_undo_on_error = True
            deploy_orchestration(o, var_context=self.vs,
                                 hosts={'all': [me.id, remote.id], 'frontend': [me.id], 'backend': [remote.id]},
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
                server_id='cccccccc-1234-5678-1234-cccccccc0002').one()
            self.assertTrue(e.success)


        with self.app2.app_context():
            self.assertEqual(1, StepExecution.query.count())

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0009').one()
            self.assertTrue(e.success)

    @mock.patch('dimensigon.use_cases.operations.subprocess.run')
    @responses.activate
    def test_deploy_orchestration_stop_undo_on_error_false(self, mock_run):
        mock_run.side_effect = [CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=1, stdout='err', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=1, stdout='err', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=1, stdout='err', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr='')
                                ]

        with self.app.app_context():
            me = Server.query.get('cccccccc-1234-5678-1234-cccccccc0001')
            remote = Server.query.get('cccccccc-1234-5678-1234-cccccccc0002')
            o = Orchestration.query.get('bbbbbbbb-1234-5678-1234-bbbbbbbb0001')
            o.stop_undo_on_error = False
            deploy_orchestration(o, var_context=self.vs,
                                 hosts={'all': [me.id, remote.id], 'frontend': [me.id], 'backend': [remote.id]},
                                 )

            self.assertEqual(12, StepExecution.query.count())

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0001').one()
            self.assertTrue(e.success)

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0003').one()
            self.assertTrue(e.success)

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0007').filter_by(
                server_id='cccccccc-1234-5678-1234-cccccccc0001').one()
            self.assertFalse(e.success)

            ue = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0008').filter_by(
                server_id='cccccccc-1234-5678-1234-cccccccc0001').one()
            self.assertTrue(ue.success)

            ue = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0004').one()
            self.assertTrue(ue.success)

            ue = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0005').one()
            self.assertFalse(ue.success)

            ue = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0006').one()
            self.assertTrue(ue.success)

            ue = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0002').filter_by(
                server_id='cccccccc-1234-5678-1234-cccccccc0001').one()
            self.assertTrue(ue.success)

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0009').filter_by(
                server_id='cccccccc-1234-5678-1234-cccccccc0002').one()
            self.assertTrue(e.success)

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0007').filter_by(
                server_id='cccccccc-1234-5678-1234-cccccccc0002').one()
            self.assertTrue(e.success)

            ue = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0002').filter_by(
                server_id='cccccccc-1234-5678-1234-cccccccc0002').one()
            self.assertTrue(ue.success)

            ue = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0008').filter_by(
                server_id='cccccccc-1234-5678-1234-cccccccc0002').one()
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