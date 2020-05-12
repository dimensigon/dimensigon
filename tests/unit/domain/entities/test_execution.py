import uuid
from datetime import datetime
from unittest import TestCase

from flask_jwt_extended import create_access_token

from dm import defaults
from dm.domain.entities import StepExecution, Server, OrchExecution, User, Orchestration, ActionTemplate, ActionType
from dm.web import create_app, db
from dm.web.network import HTTPBearerAuth


class TestStepExecution(TestCase):
    def setUp(self):
        """Create and configure a new app instance for each test."""
        # create the app with common test config
        self.app = create_app('test')
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        self.auth = HTTPBearerAuth(create_access_token('test'))
        db.create_all()
        self.me = Server('me', port=5000, _me=True)
        self.remote = Server('remote', port=5000)
        db.session.add_all([self.remote, self.me])
        self.maxDiff = None

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_to_json(self):
        start = datetime(2019, 4, 1)
        end = datetime(2019, 4, 2)
        e = StepExecution(id=uuid.UUID('aaaaaaaa-1234-5678-1234-56781234aaa1'), start_time=start,
                          params={'param': 'data'}, rc=0, success=True, execution_server=self.remote,
                          source_server=self.me)

        self.assertDictEqual(dict(id='aaaaaaaa-1234-5678-1234-56781234aaa1',
                                  start_time=start.strftime(defaults.DATETIME_FORMAT),
                                  params={'param': 'data'}, step_id=None, stdout=None, stderr=None, rc=0, success=True,
                                  execution_server_id=str(self.remote.id),
                                  fetched_data=None,
                                  source_server_id=str(self.me.id)),
                             e.to_json())


class TestOrchExecution(TestCase):
    def setUp(self):
        """Create and configure a new app instance for each test."""
        # create the app with common test config
        self.app = create_app('test')
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        self.auth = HTTPBearerAuth(create_access_token('test'))
        db.create_all()
        self.me = Server('me', port=5000, _me=True)
        self.remote = Server('remote', port=5000)
        db.session.add_all([self.remote, self.me])
        self.maxDiff = None

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_to_from_json(self):
        start = datetime(2019, 4, 1)
        end = datetime(2019, 4, 2)
        o = Orchestration('orch', 1, id=uuid.UUID('eeeeeeee-1234-5678-1234-56781234eee1'))
        s = o.add_step(undo=True, action_template=ActionTemplate('action', 1, ActionType.NATIVE, code=''))
        oe = OrchExecution(id=uuid.UUID('bbbbbbbb-1234-5678-1234-56781234bbb1'), start_time=start,
                           target={'all': [self.me.id, self.remote.id], 'backend': [self.remote.id]},
                           params={'params': 'content'},
                           executor=User('user', id=uuid.UUID('cccccccc-1234-5678-1234-56781234ccc1')),
                           orchestration=o
                           )

        se = StepExecution(id=uuid.UUID('aaaaaaaa-1234-5678-1234-56781234aaa1'), start_time=start, step=s,
                           orch_execution_id=uuid.UUID('bbbbbbbb-1234-5678-1234-56781234bbb1'),
                           params={'param': 'data'}, rc=0, success=True, execution_server=self.remote,
                           source_server=self.me)
        db.session.add_all([oe, se, o])
        self.assertDictEqual(dict(id='bbbbbbbb-1234-5678-1234-56781234bbb1',
                                  start_time=start.strftime(defaults.DATETIME_FORMAT),
                                  target={'all': [str(self.me.id), str(self.remote.id)],
                                          'backend': [str(self.remote.id)]},
                                  params={'params': 'content'}, orchestration_id='eeeeeeee-1234-5678-1234-56781234eee1',
                                  service_id=None,
                                  success=None, undo_success=None,
                                  executor_id='cccccccc-1234-5678-1234-56781234ccc1'),
                             oe.to_json())

        self.assertDictEqual(dict(id='bbbbbbbb-1234-5678-1234-56781234bbb1',
                                  start_time=start.strftime(defaults.DATETIME_FORMAT),
                                  target={'all': [str(self.me), str(self.remote)], 'backend': [str(self.remote)]},
                                  params={'params': 'content'}, orchestration='orch.1',
                                  service=None,
                                  success=None, undo_success=None,
                                  executor='user'),
                             oe.to_json(human=True))

        self.assertDictEqual(dict(id='bbbbbbbb-1234-5678-1234-56781234bbb1',
                                  start_time=start.strftime(defaults.DATETIME_FORMAT),
                                  target={'all': [str(self.me.id), str(self.remote.id)],
                                          'backend': [str(self.remote.id)]},
                                  params={'params': 'content'}, orchestration_id='eeeeeeee-1234-5678-1234-56781234eee1',
                                  service_id=None,
                                  success=None, undo_success=None,
                                  executor_id='cccccccc-1234-5678-1234-56781234ccc1',
                                  steps=[dict(id='aaaaaaaa-1234-5678-1234-56781234aaa1',
                                              start_time=start.strftime(defaults.DATETIME_FORMAT),
                                              params={'param': 'data'},
                                              step_id=str(s.id),
                                              stdout=None,
                                              stderr=None,
                                              rc=0,
                                              success=True,
                                              execution_server_id=str(self.remote.id),
                                              source_server_id=str(self.me.id),
                                              fetched_data=None
                                              )]),
                             oe.to_json(add_step_exec=True))

        o_e_json = oe.to_json()
        db.session.commit()
        del oe

        smashed = OrchExecution.from_json(o_e_json)

        self.assertEqual(uuid.UUID('bbbbbbbb-1234-5678-1234-56781234bbb1'), smashed.id)
        self.assertEqual(start, smashed.start_time)
        self.assertEqual(uuid.UUID('eeeeeeee-1234-5678-1234-56781234eee1'), smashed.orchestration.id)
        self.assertEqual({'all': [str(self.me.id), str(self.remote.id)],
                          'backend': [str(self.remote.id)]}, smashed.target)
        self.assertEqual({'params': 'content'}, smashed.params)
        self.assertEqual(User.get_by_user('user'), smashed.executor)
        self.assertEqual(None, smashed.service)
        self.assertEqual(None, smashed.success)
        self.assertEqual(None, smashed.undo_success)
