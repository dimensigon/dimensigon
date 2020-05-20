import re
import traceback
import uuid
from functools import partial
from subprocess import CompletedProcess
from unittest import TestCase, mock

import responses
from flask_jwt_extended import create_access_token

from dm.domain.entities import Server, ActionTemplate, ActionType, Orchestration, StepExecution, Step, User, \
    OrchExecution
from dm.domain.entities.route import Route
from dm.web import create_app, db
from dm.web.async_functions import deploy_orchestration
from dm.web.network import HTTPBearerAuth


class TestLaunchOrchestration(TestCase):

    def setUp(self) -> None:
        self.maxDiff = None
        self.app = create_app('test')
        self.app2 = create_app('test')

        self.client = self.app.test_client()
        with self.app.app_context():
            self.access_token = create_access_token(identity='test')
            self.auth = HTTPBearerAuth(self.access_token)
            self.headers = self.auth.header
        for app in [self.app, self.app2]:
            with app.app_context():
                db.create_all()
                u = User('root', id='eeeeeeee-1234-5678-1234-eeeeeeee0001')
                at1 = ActionTemplate(id=uuid.UUID('aaaaaaaa-1234-5678-1234-aaaaaaaa0001'), name='create dir', version=1,
                                     action_type=ActionType.SHELL, code='useradd {{user}}; mkdir {{dir}}',
                                     parameters={}, expected_stdout='',
                                     expected_rc=0, system_kwargs={})
                at2 = ActionTemplate(id=uuid.UUID('aaaaaaaa-1234-5678-1234-aaaaaaaa0002'), name='rm dir', version=1,
                                     action_type=ActionType.SHELL, code='rmuser {{user}}',
                                     parameters={}, expected_stdout='',
                                     expected_rc=0, system_kwargs={})
                at3 = ActionTemplate(id=uuid.UUID('aaaaaaaa-1234-5678-1234-aaaaaaaa0003'), name='untar', version=1,
                                     action_type=ActionType.SHELL, code='tar -xf {{dir}}',
                                     parameters={}, expected_stdout='',
                                     expected_rc=0, system_kwargs={})
                at4 = ActionTemplate(id=uuid.UUID('aaaaaaaa-1234-5678-1234-aaaaaaaa0004'), name='install tibero',
                                     version=1,
                                     action_type=ActionType.SHELL, code='{{home}}/install_tibero.sh',
                                     parameters={}, expected_stdout='',
                                     expected_rc=0, system_kwargs={})

                o = Orchestration('Test Orchestration', 1, 'description',
                                  id=uuid.UUID('bbbbbbbb-1234-5678-1234-bbbbbbbb0001'))

                me = Server('me', port=5000, me=app == self.app, id=uuid.UUID('cccccccc-1234-5678-1234-cccccccc0001'))
                remote = Server('remote', port=5000, me=app == self.app2,
                                id=uuid.UUID('cccccccc-1234-5678-1234-cccccccc0002'))
                if app == self.app:
                    r = Route(remote, cost=0)
                else:
                    r = Route(me, cost=0)
                db.session.add_all([me, remote, o, r, u])

                # Orch diagram
                # f   f
                # 1-->3-->u4-->u5-->u6
                #  \/  \    \_____/
                #  /\   \
                # 9-->u2 7-->u8
                # b

                s1 = o.add_step(id=uuid.UUID('dddddddd-1234-5678-1234-dddddddd0001'), undo=False, action_template=at1,
                                parents=[], target=['frontend'])
                s2 = o.add_step(id=uuid.UUID('dddddddd-1234-5678-1234-dddddddd0002'), undo=True, action_template=at2,
                                parents=[s1], target=[])
                s3 = o.add_step(id=uuid.UUID('dddddddd-1234-5678-1234-dddddddd0003'), undo=False, action_template=at3,
                                parents=[s1], target=['frontend'])
                s4 = o.add_step(id=uuid.UUID('dddddddd-1234-5678-1234-dddddddd0004'), undo=True, action_template=at2,
                                parents=[s3], target=[])
                s5 = o.add_step(id=uuid.UUID('dddddddd-1234-5678-1234-dddddddd0005'), undo=True, action_template=at2,
                                parents=[s4], target=[])
                s6 = o.add_step(id=uuid.UUID('dddddddd-1234-5678-1234-dddddddd0006'), undo=True, action_template=at2,
                                parents=[s4, s5], target=[])
                s7 = o.add_step(id=uuid.UUID('dddddddd-1234-5678-1234-dddddddd0007'), undo=False, action_template=at4,
                                parents=[s3], target=[])
                s8 = o.add_step(id=uuid.UUID('dddddddd-1234-5678-1234-dddddddd0008'), undo=True, action_template=at2,
                                parents=[s7], target=[])
                s9 = o.add_step(id=uuid.UUID('dddddddd-1234-5678-1234-dddddddd0009'), undo=False, action_template=at1,
                                children=[s2, s3], target=['backend'])
                db.session.commit()

    def tearDown(self) -> None:
        for app in [self.app, self.app2]:
            with app.app_context():
                db.session.remove()
                db.drop_all()

    @mock.patch('dm.web.async_functions.get_jwt_identity', autospec=True)
    @mock.patch('dm.web.async_functions.lock', autospec=True)
    @mock.patch('dm.web.async_functions.unlock', autospec=True)
    @mock.patch('dm.use_cases.operations.subprocess.run')
    @responses.activate
    def test_deploy_orchestration(self, mock_run, mock_lock, mock_unlock, mock_identity):
        mock_run.side_effect = [CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr='')]

        def requests_callback_client(client, request):
            method_func = getattr(client, request.method.lower())
            try:
                resp = method_func(request.path_url, data=request.body, headers=dict(request.headers))
            except Exception as e:
                return 500, {}, traceback.format_exc()

            return resp.status_code, resp.headers, resp.data

        responses.add_callback(responses.POST, re.compile('https?://me:.*'),
                               callback=partial(requests_callback_client, self.app.test_client()))
        responses.add_callback(responses.POST, re.compile('https?://remote:.*'),
                               callback=partial(requests_callback_client, self.app2.test_client()))

        with self.app.app_context():
            mock_identity.return_value = User.get_by_user('root').id
            me = Server.query.get('cccccccc-1234-5678-1234-cccccccc0001')
            remote = Server.query.get('cccccccc-1234-5678-1234-cccccccc0002')
            o = Orchestration.query.get('bbbbbbbb-1234-5678-1234-bbbbbbbb0001')

            deploy_orchestration(o.id, params={'user': 'joan', 'dir': '/opt/dimensigon', 'home': '{{dir}}'},
                                 hosts={'all': [me.id, remote.id], 'frontend': [me.id], 'backend': [remote.id]},
                                 max_parallel_tasks=4, auth=self.auth)

            self.assertEqual(1, OrchExecution.query.count())
            oe = OrchExecution.query.one()
            orch_execution_id = oe.id
            self.assertTrue(oe.success)
            self.assertEqual(o, oe.orchestration)
            self.assertDictEqual(
                {'all': [str(me.id), str(remote.id)], 'frontend': [str(me.id)], 'backend': [str(remote.id)]}, oe.target)
            self.assertDictEqual({'user': 'joan', 'dir': '/opt/dimensigon', 'home': '{{dir}}'}, oe.params)
            self.assertEqual(User.get_by_user('root'), oe.executor)
            self.assertIsNone(oe.service)
            self.assertTrue(oe.success)
            self.assertIsNone(oe.undo_success)

            self.assertEqual(3, StepExecution.query.count())

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0001').one()
            self.assertTrue(e.success)

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0003').one()
            self.assertTrue(e.success)

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0007').one()
            self.assertTrue(e.success)

        with self.app2.app_context():
            self.assertEqual(1, OrchExecution.query.count())
            oe = OrchExecution.query.one()
            self.assertEqual(orch_execution_id, oe.id)
            self.assertEqual(o.id, oe.orchestration.id)
            self.assertDictEqual(
                {'all': [str(me.id), str(remote.id)], 'frontend': [str(me.id)], 'backend': [str(remote.id)]}, oe.target)
            self.assertDictEqual({'user': 'joan', 'dir': '/opt/dimensigon', 'home': '{{dir}}'}, oe.params)
            self.assertEqual(User.get_by_user('root'), oe.executor)
            self.assertIsNone(oe.service)
            # self.assertTrue(oe.success)
            # self.assertIsNone(oe.undo_success)

            self.assertEqual(2, StepExecution.query.count())

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0009').one()
            self.assertTrue(e.success)

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0007').one()
            self.assertTrue(e.success)

    @mock.patch('dm.web.async_functions.get_jwt_identity', autospec=True)
    @mock.patch('dm.web.async_functions.lock', autospec=True)
    @mock.patch('dm.web.async_functions.unlock', autospec=True)
    @mock.patch('dm.use_cases.operations.subprocess.run')
    @responses.activate
    def test_deploy_orchestration_stop_on_error(self, mock_run, mock_lock, mock_unlock, mock_identity):
        mock_run.side_effect = [CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=1, stdout='err', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr='')]

        

        def requests_callback_client(client, request):
            method_func = getattr(client, request.method.lower())
            try:
                resp = method_func(request.path_url, data=request.body, headers=dict(request.headers))
            except Exception as e:
                return 500, {}, traceback.format_exc()

            return resp.status_code, resp.headers, resp.data

        responses.add_callback(responses.POST, re.compile('https?://me:.*'),
                               callback=partial(requests_callback_client, self.app.test_client()))
        responses.add_callback(responses.POST, re.compile('https?://remote:.*'),
                               callback=partial(requests_callback_client, self.app2.test_client()))

        with self.app.app_context():
            me = Server.query.get('cccccccc-1234-5678-1234-cccccccc0001')
            remote = Server.query.get('cccccccc-1234-5678-1234-cccccccc0002')
            o = Orchestration.query.get('bbbbbbbb-1234-5678-1234-bbbbbbbb0001')
            mock_identity.return_value = User.get_by_user('root').id

            deploy_orchestration(o, params={'user': 'joan', 'dir': '/opt/dimensigon', 'home': '{{dir}}'},
                                 hosts={'all': [me.id, remote.id], 'frontend': [me.id], 'backend': [remote.id]},
                                 max_parallel_tasks=4, auth=self.auth)

            self.assertEqual(1, OrchExecution.query.count())
            oe = OrchExecution.query.one()
            self.assertFalse(oe.success)
            self.assertTrue(oe.undo_success)


            self.assertEqual(6, StepExecution.query.count())

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

            ue = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0002').one()
            self.assertTrue(ue.success)


        with self.app2.app_context():
            self.assertEqual(2, StepExecution.query.count())

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0009').one()
            self.assertTrue(e.success)

            ue = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0002').one()
            self.assertTrue(ue.success)

    @mock.patch('dm.web.async_functions.get_jwt_identity', autospec=True)
    @mock.patch('dm.web.async_functions.lock', autospec=True)
    @mock.patch('dm.web.async_functions.unlock', autospec=True)
    @mock.patch('dm.use_cases.operations.subprocess.run')
    @responses.activate
    def test_deploy_orchestration_stop_on_error_false(self, mock_run, mock_lock, mock_unlock, mock_identity):
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

        

        def requests_callback_client(client, request):
            method_func = getattr(client, request.method.lower())
            try:
                resp = method_func(request.path_url, data=request.body, headers=dict(request.headers))
            except Exception as e:
                return 500, {}, traceback.format_exc()

            return resp.status_code, resp.headers, resp.data

        responses.add_callback(responses.POST, re.compile('https?://me:.*'),
                               callback=partial(requests_callback_client, self.app.test_client()))
        responses.add_callback(responses.POST, re.compile('https?://remote:.*'),
                               callback=partial(requests_callback_client, self.app2.test_client()))

        with self.app.app_context():
            mock_identity.return_value = User.get_by_user('root').id
            me = Server.query.get('cccccccc-1234-5678-1234-cccccccc0001')
            remote = Server.query.get('cccccccc-1234-5678-1234-cccccccc0002')
            o = Orchestration.query.get('bbbbbbbb-1234-5678-1234-bbbbbbbb0001')
            o.stop_on_error = False
            deploy_orchestration(o, params={'user': 'joan', 'dir': '/opt/dimensigon', 'home': '{{dir}}'},
                                 hosts={'all': [me.id, remote.id], 'frontend': [me.id], 'backend': [remote.id]},
                                 max_parallel_tasks=4, auth=self.auth)

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

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0007').one()
            self.assertTrue(e.success)

            ue21 = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0002').one()
            self.assertTrue(ue21.success)

            ue71 = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0007').one()
            self.assertTrue(ue71.success)

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

    @mock.patch('dm.web.async_functions.get_jwt_identity', autospec=True)
    @mock.patch('dm.web.async_functions.lock', autospec=True)
    @mock.patch('dm.web.async_functions.unlock', autospec=True)
    @mock.patch('dm.use_cases.operations.subprocess.run')
    @responses.activate
    def test_deploy_orchestration_step_stop_on_error_false(self, mock_run, mock_lock, mock_unlock, mock_identity):
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
        

        def requests_callback_client(client, request):
            method_func = getattr(client, request.method.lower())
            try:
                resp = method_func(request.path_url, data=request.body, headers=dict(request.headers))
            except Exception as e:
                return 500, {}, traceback.format_exc()

            return resp.status_code, resp.headers, resp.data

        responses.add_callback(responses.POST, re.compile('https?://me:.*'),
                               callback=partial(requests_callback_client, self.app.test_client()))
        responses.add_callback(responses.POST, re.compile('https?://remote:.*'),
                               callback=partial(requests_callback_client, self.app2.test_client()))

        with self.app.app_context():
            mock_identity.return_value = User.get_by_user('root').id
            s = Step.query.get('dddddddd-1234-5678-1234-dddddddd0001')
            s.step_stop_on_error = False
            me = Server.query.get('cccccccc-1234-5678-1234-cccccccc0001')
            remote = Server.query.get('cccccccc-1234-5678-1234-cccccccc0002')
            o = Orchestration.query.get('bbbbbbbb-1234-5678-1234-bbbbbbbb0001')
            deploy_orchestration(o, params={'user': 'joan', 'dir': '/opt/dimensigon', 'home': '{{dir}}'},
                                 hosts={'all': [me.id, remote.id], 'frontend': [me.id], 'backend': [remote.id]},
                                 max_parallel_tasks=4, auth=self.auth)

            self.assertEqual(8, StepExecution.query.count())

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0001').one()
            self.assertFalse(e.success)

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0003').one()
            self.assertTrue(e.success)

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0007').one()
            self.assertTrue(e.success)

            ue81 = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0008').one()
            self.assertTrue(ue81.success)

            ue4 = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0004').one()
            self.assertTrue(ue4.success)

            ue5 = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0005').one()
            self.assertTrue(ue5.success)
            self.assertGreater(ue5.start_time, ue4.start_time)

            ue6 = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0006').one()
            self.assertTrue(ue6.success)
            self.assertGreater(ue6.start_time, ue5.start_time)

            ue21 = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0002').one()
            self.assertTrue(ue21.success)

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

    @mock.patch('dm.web.async_functions.get_jwt_identity', autospec=True)
    @mock.patch('dm.web.async_functions.lock', autospec=True)
    @mock.patch('dm.web.async_functions.unlock', autospec=True)
    @mock.patch('dm.use_cases.operations.subprocess.run')
    @responses.activate
    def test_deploy_orchestration_step_stop_on_error_true(self, mock_run, mock_lock, mock_unlock, mock_identity):
        mock_run.side_effect = [CompletedProcess(args=(), returncode=1, stdout='err', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr='')
                                ]

        def requests_callback_client(client, request):
            method_func = getattr(client, request.method.lower())
            try:
                resp = method_func(request.path_url, data=request.body, headers=dict(request.headers))
            except Exception as e:
                return 500, {}, traceback.format_exc()

            return resp.status_code, resp.headers, resp.data

        responses.add_callback(responses.POST, re.compile('https?://me:.*'),
                               callback=partial(requests_callback_client, self.app.test_client()))
        responses.add_callback(responses.POST, re.compile('https?://remote:.*'),
                               callback=partial(requests_callback_client, self.app2.test_client()))

        with self.app.app_context():
            mock_identity.return_value = User.get_by_user('root').id
            s = Step.query.get('dddddddd-1234-5678-1234-dddddddd0001')
            s.step_stop_on_error = True
            me = Server.query.get('cccccccc-1234-5678-1234-cccccccc0001')
            remote = Server.query.get('cccccccc-1234-5678-1234-cccccccc0002')
            o = Orchestration.query.get('bbbbbbbb-1234-5678-1234-bbbbbbbb0001')
            o.stop_on_error = False
            deploy_orchestration(o, params={'user': 'joan', 'dir': '/opt/dimensigon', 'home': '{{dir}}'},
                                 hosts={'all': [me.id, remote.id], 'frontend': [me.id], 'backend': [remote.id]},
                                 max_parallel_tasks=4, auth=self.auth)

            self.assertEqual(2, StepExecution.query.count())

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0001').one()
            self.assertFalse(e.success)

            ue = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0002').one()
            self.assertTrue(ue.success)

        with self.app2.app_context():
            self.assertEqual(2, StepExecution.query.count())

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0009').one()
            self.assertTrue(e.success)

            ue = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0002').one()
            self.assertTrue(ue.success)

    @mock.patch('dm.web.async_functions.get_jwt_identity', autospec=True)
    @mock.patch('dm.web.async_functions.lock', autospec=True)
    @mock.patch('dm.web.async_functions.unlock', autospec=True)
    @mock.patch('dm.use_cases.operations.subprocess.run')
    @responses.activate
    def test_deploy_orchestration_undo_on_error_false(self, mock_run, mock_lock, mock_unlock, mock_identity):
        mock_run.side_effect = [CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=1, stdout='err', stderr='')]

        

        def requests_callback_client(client, request):
            method_func = getattr(client, request.method.lower())
            try:
                resp = method_func(request.path_url, data=request.body, headers=dict(request.headers))
            except Exception as e:
                return 500, {}, traceback.format_exc()

            return resp.status_code, resp.headers, resp.data

        responses.add_callback(responses.POST, re.compile('https?://me:.*'),
                               callback=partial(requests_callback_client, self.app.test_client()))
        responses.add_callback(responses.POST, re.compile('https?://remote:.*'),
                               callback=partial(requests_callback_client, self.app2.test_client()))

        with self.app.app_context():
            mock_identity.return_value = User.get_by_user('root').id
            me = Server.query.get('cccccccc-1234-5678-1234-cccccccc0001')
            remote = Server.query.get('cccccccc-1234-5678-1234-cccccccc0002')
            o = Orchestration.query.get('bbbbbbbb-1234-5678-1234-bbbbbbbb0001')
            o.undo_on_error = False
            deploy_orchestration(o, params={'user': 'joan', 'dir': '/opt/dimensigon', 'home': '{{dir}}'},
                                 hosts={'all': [me.id, remote.id], 'frontend': [me.id], 'backend': [remote.id]},
                                 max_parallel_tasks=4, auth=self.auth)

            self.assertEqual(3, StepExecution.query.count())

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0001').one()
            self.assertTrue(e.success)

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0003').one()
            self.assertTrue(e.success)

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0007').one()
            self.assertTrue(e.success)

        with self.app2.app_context():
            self.assertEqual(2, StepExecution.query.count())

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0009').one()
            self.assertTrue(e.success)

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0007').one()
            self.assertFalse(e.success)

    @mock.patch('dm.web.async_functions.get_jwt_identity', autospec=True)
    @mock.patch('dm.web.async_functions.lock', autospec=True)
    @mock.patch('dm.web.async_functions.unlock', autospec=True)
    @mock.patch('dm.use_cases.operations.subprocess.run')
    @responses.activate
    def test_deploy_orchestration_step_undo_on_error_false(self, mock_run, mock_lock, mock_unlock, mock_identity):
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

        

        def requests_callback_client(client, request):
            method_func = getattr(client, request.method.lower())
            try:
                resp = method_func(request.path_url, data=request.body, headers=dict(request.headers))
            except Exception as e:
                return 500, {}, traceback.format_exc()

            return resp.status_code, resp.headers, resp.data

        responses.add_callback(responses.POST, re.compile('https?://me:.*'),
                               callback=partial(requests_callback_client, self.app.test_client()))
        responses.add_callback(responses.POST, re.compile('https?://remote:.*'),
                               callback=partial(requests_callback_client, self.app2.test_client()))

        with self.app.app_context():
            mock_identity.return_value = User.get_by_user('root').id
            s = Step.query.get('dddddddd-1234-5678-1234-dddddddd0007')
            s.step_undo_on_error = False
            me = Server.query.get('cccccccc-1234-5678-1234-cccccccc0001')
            remote = Server.query.get('cccccccc-1234-5678-1234-cccccccc0002')
            o = Orchestration.query.get('bbbbbbbb-1234-5678-1234-bbbbbbbb0001')
            deploy_orchestration(o, params={'user': 'joan', 'dir': '/opt/dimensigon', 'home': '{{dir}}'},
                                 hosts={'all': [me.id, remote.id], 'frontend': [me.id], 'backend': [remote.id]},
                                 max_parallel_tasks=4, auth=self.auth)

            self.assertEqual(8, StepExecution.query.count())

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0001').one()
            self.assertTrue(e.success)

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0003').one()
            self.assertTrue(e.success)

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0007').one()
            self.assertTrue(e.success)

            ue = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0008').one()
            self.assertTrue(ue.success)

            ue4 = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0004').one()
            self.assertTrue(ue4.success)

            ue5 = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0005').one()
            self.assertTrue(ue5.success)
            self.assertGreater(ue5.start_time, ue4.start_time)

            ue6 = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0006').one()
            self.assertTrue(ue6.success)
            self.assertGreater(ue6.start_time, ue5.start_time)

            ue = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0002').one()
            self.assertTrue(ue.success)

        with self.app2.app_context():
            self.assertEqual(3, StepExecution.query.count())

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0009').one()
            self.assertTrue(e.success)

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0007').one()
            self.assertFalse(e.success)

            ue = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0002').one()
            self.assertTrue(ue.success)

    @mock.patch('dm.web.async_functions.get_jwt_identity', autospec=True)
    @mock.patch('dm.web.async_functions.lock', autospec=True)
    @mock.patch('dm.web.async_functions.unlock', autospec=True)
    @mock.patch('dm.use_cases.operations.subprocess.run')
    @responses.activate
    def test_deploy_orchestration_stop_undo_on_error_true(self, mock_run, mock_lock, mock_unlock, mock_identity):
        mock_run.side_effect = [CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=1, stdout='err', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=1, stdout='err', stderr='')]

        

        def requests_callback_client(client, request):
            method_func = getattr(client, request.method.lower())
            try:
                resp = method_func(request.path_url, data=request.body, headers=dict(request.headers))
            except Exception as e:
                return 500, {}, traceback.format_exc()

            return resp.status_code, resp.headers, resp.data

        responses.add_callback(responses.POST, re.compile('https?://me:.*'),
                               callback=partial(requests_callback_client, self.app.test_client()))
        responses.add_callback(responses.POST, re.compile('https?://remote:.*'),
                               callback=partial(requests_callback_client, self.app2.test_client()))

        with self.app.app_context():
            mock_identity.return_value = User.get_by_user('root').id
            me = Server.query.get('cccccccc-1234-5678-1234-cccccccc0001')
            remote = Server.query.get('cccccccc-1234-5678-1234-cccccccc0002')
            o = Orchestration.query.get('bbbbbbbb-1234-5678-1234-bbbbbbbb0001')
            o.stop_undo_on_error = True
            deploy_orchestration(o, params={'user': 'joan', 'dir': '/opt/dimensigon', 'home': '{{dir}}'},
                                 hosts={'all': [me.id, remote.id], 'frontend': [me.id], 'backend': [remote.id]},
                                 max_parallel_tasks=4, auth=self.auth)

            self.assertEqual(4, StepExecution.query.count())

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0001').one()
            self.assertTrue(e.success)

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0003').one()
            self.assertFalse(e.success)

            ue = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0004').one()
            self.assertTrue(ue.success)

            ue = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0005').one()
            self.assertFalse(ue.success)

        with self.app2.app_context():
            self.assertEqual(1, StepExecution.query.count())

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0009').one()
            self.assertTrue(e.success)

    @mock.patch('dm.web.async_functions.get_jwt_identity', autospec=True)
    @mock.patch('dm.web.async_functions.lock', autospec=True)
    @mock.patch('dm.web.async_functions.unlock', autospec=True)
    @mock.patch('dm.use_cases.operations.subprocess.run')
    @responses.activate
    def test_deploy_orchestration_step_stop_undo_on_error_true(self, mock_run, mock_lock, mock_unlock, mock_identity):
        mock_run.side_effect = [CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=1, stdout='err', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=1, stdout='err', stderr='')]

        

        def requests_callback_client(client, request):
            method_func = getattr(client, request.method.lower())
            try:
                resp = method_func(request.path_url, data=request.body, headers=dict(request.headers))
            except Exception as e:
                return 500, {}, traceback.format_exc()

            return resp.status_code, resp.headers, resp.data

        responses.add_callback(responses.POST, re.compile('https?://me:.*'),
                               callback=partial(requests_callback_client, self.app.test_client()))
        responses.add_callback(responses.POST, re.compile('https?://remote:.*'),
                               callback=partial(requests_callback_client, self.app2.test_client()))

        with self.app.app_context():
            mock_identity.return_value = User.get_by_user('root').id
            s = Step.query.get('dddddddd-1234-5678-1234-dddddddd0003')
            s.step_stop_undo_on_error = True
            me = Server.query.get('cccccccc-1234-5678-1234-cccccccc0001')
            remote = Server.query.get('cccccccc-1234-5678-1234-cccccccc0002')
            o = Orchestration.query.get('bbbbbbbb-1234-5678-1234-bbbbbbbb0001')
            deploy_orchestration(o, params={'user': 'joan', 'dir': '/opt/dimensigon', 'home': '{{dir}}'},
                                 hosts={'all': [me.id, remote.id], 'frontend': [me.id], 'backend': [remote.id]},
                                 max_parallel_tasks=4, auth=self.auth)

            self.assertEqual(4, StepExecution.query.count())

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0001').one()
            self.assertTrue(e.success)

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0003').one()
            self.assertFalse(e.success)

            ue = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0004').one()
            self.assertTrue(ue.success)

            ue = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0005').one()
            self.assertFalse(ue.success)

        with self.app2.app_context():
            self.assertEqual(1, StepExecution.query.count())

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0009').one()
            self.assertTrue(e.success)

    @mock.patch('dm.web.async_functions.get_jwt_identity', autospec=True)
    @mock.patch('dm.web.async_functions.lock', autospec=True)
    @mock.patch('dm.web.async_functions.unlock', autospec=True)
    @mock.patch('dm.use_cases.operations.subprocess.run')
    @responses.activate
    def test_deploy_orchestration_undo_step_stop_on_error_false(self, mock_run, mock_lock, mock_unlock, mock_identity):
        mock_run.side_effect = [CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=1, stdout='err', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr=''),
                                CompletedProcess(args=(), returncode=1, stdout='err', stderr=''),
                                CompletedProcess(args=(), returncode=0, stdout='', stderr='')]

        

        def requests_callback_client(client, request):
            method_func = getattr(client, request.method.lower())
            try:
                resp = method_func(request.path_url, data=request.body, headers=dict(request.headers))
            except Exception as e:
                return 500, {}, traceback.format_exc()

            return resp.status_code, resp.headers, resp.data

        responses.add_callback(responses.POST, re.compile('https?://me:.*'),
                               callback=partial(requests_callback_client, self.app.test_client()))
        responses.add_callback(responses.POST, re.compile('https?://remote:.*'),
                               callback=partial(requests_callback_client, self.app2.test_client()))

        with self.app.app_context():
            mock_identity.return_value = User.get_by_user('root').id
            s = Step.query.get('dddddddd-1234-5678-1234-dddddddd0005')
            s.step_stop_on_error = False
            me = Server.query.get('cccccccc-1234-5678-1234-cccccccc0001')
            remote = Server.query.get('cccccccc-1234-5678-1234-cccccccc0002')
            o = Orchestration.query.get('bbbbbbbb-1234-5678-1234-bbbbbbbb0001')
            o.stop_undo_on_error = True
            deploy_orchestration(o, params={'user': 'joan', 'dir': '/opt/dimensigon', 'home': '{{dir}}'},
                                 hosts={'all': [me.id, remote.id], 'frontend': [me.id], 'backend': [remote.id]},
                                 max_parallel_tasks=4, auth=self.auth)

            self.assertEqual(5, StepExecution.query.count())

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


        with self.app2.app_context():
            self.assertEqual(1, StepExecution.query.count())

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0009').one()
            self.assertTrue(e.success)

    @mock.patch('dm.web.async_functions.get_jwt_identity', autospec=True)
    @mock.patch('dm.web.async_functions.lock', autospec=True)
    @mock.patch('dm.web.async_functions.unlock', autospec=True)
    @mock.patch('dm.use_cases.operations.subprocess.run')
    @responses.activate
    def test_deploy_orchestration_stop_undo_on_error_false(self, mock_run, mock_lock, mock_unlock, mock_identity):
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

        

        def requests_callback_client(client, request):
            method_func = getattr(client, request.method.lower())
            try:
                resp = method_func(request.path_url, data=request.body, headers=dict(request.headers))
            except Exception as e:
                return 500, {}, traceback.format_exc()

            return resp.status_code, resp.headers, resp.data

        responses.add_callback(responses.POST, re.compile('https?://me:.*'),
                               callback=partial(requests_callback_client, self.app.test_client()))
        responses.add_callback(responses.POST, re.compile('https?://remote:.*'),
                               callback=partial(requests_callback_client, self.app2.test_client()))

        with self.app.app_context():
            mock_identity.return_value = User.get_by_user('root').id
            me = Server.query.get('cccccccc-1234-5678-1234-cccccccc0001')
            remote = Server.query.get('cccccccc-1234-5678-1234-cccccccc0002')
            o = Orchestration.query.get('bbbbbbbb-1234-5678-1234-bbbbbbbb0001')
            o.stop_undo_on_error = False
            deploy_orchestration(o, params={'user': 'joan', 'dir': '/opt/dimensigon', 'home': '{{dir}}'},
                                 hosts={'all': [me.id, remote.id], 'frontend': [me.id], 'backend': [remote.id]},
                                 max_parallel_tasks=4, auth=self.auth)

            self.assertEqual(8, StepExecution.query.count())

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0001').one()
            self.assertTrue(e.success)

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0003').one()
            self.assertTrue(e.success)

            e = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0007').one()
            self.assertFalse(e.success)

            ue = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0008').one()
            self.assertTrue(ue.success)

            ue = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0004').one()
            self.assertTrue(ue.success)

            ue = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0005').one()
            self.assertFalse(ue.success)

            ue = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0006').one()
            self.assertTrue(ue.success)

            ue = StepExecution.query.filter_by(step_id='dddddddd-1234-5678-1234-dddddddd0002').one()
            self.assertTrue(ue.success)

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