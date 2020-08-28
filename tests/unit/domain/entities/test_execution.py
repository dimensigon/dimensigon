import datetime as dt
from unittest import TestCase

from flask_jwt_extended import create_access_token

from dimensigon import defaults
from dimensigon.domain.entities import StepExecution, Server, OrchExecution, User, Orchestration, ActionTemplate, \
    ActionType
from dimensigon.network.auth import HTTPBearerAuth
from dimensigon.web import create_app, db


class TestStepExecution(TestCase):
    def setUp(self):
        """Create and configure a new app instance for each test."""
        # create the app with common test config
        self.app = create_app('test')
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        self.auth = HTTPBearerAuth(create_access_token('00000000-0000-0000-0000-000000000001'))
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
        start = dt.datetime(2019, 4, 1, tzinfo=dt.timezone.utc)
        end = dt.datetime(2019, 4, 2, tzinfo=dt.timezone.utc)
        e = StepExecution(id='aaaaaaaa-1234-5678-1234-56781234aaa1', start_time=start,
                          params={'param': 'data'}, rc=0, success=True, server=self.remote,
                          end_time=end)

        self.assertDictEqual(dict(id='aaaaaaaa-1234-5678-1234-56781234aaa1',
                                  start_time=start.strftime(defaults.DATETIME_FORMAT),
                                  end_time=end.strftime(defaults.DATETIME_FORMAT),
                                  params={'param': 'data'}, step_id=None, stdout=None, stderr=None, rc=0, success=True,
                                  server_id=str(self.remote.id)),
                             e.to_json())

        self.assertDictEqual(dict(id='aaaaaaaa-1234-5678-1234-56781234aaa1',
                                  start_time=start.strftime(defaults.DATETIME_FORMAT),
                                  end_time=end.strftime(defaults.DATETIME_FORMAT),
                                  params={'param': 'data'}, step_id=None, stdout=None, stderr=None, rc=0, success=True,
                                  server=str(self.remote)),
                             e.to_json(human=True))


class TestOrchExecution(TestCase):
    def setUp(self):
        """Create and configure a new app instance for each test."""
        # create the app with common test config
        self.app = create_app('test')
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        self.auth = HTTPBearerAuth(create_access_token('00000000-0000-0000-0000-000000000001'))
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
        start = dt.datetime(2019, 4, 1, tzinfo=dt.timezone.utc)
        end = dt.datetime(2019, 4, 2, tzinfo=dt.timezone.utc)
        u = User('user', id='cccccccc-1234-5678-1234-56781234ccc1')
        db.session.add(u)
        o = Orchestration('run_orch', 1, id='eeeeeeee-1234-5678-1234-56781234eee1')
        s = o.add_step(undo=False,
                       action_template=ActionTemplate('orchestration', 1, ActionType.ORCHESTRATION, code=''),
                       parameters={'orchestration_id': 'eeeeeeee-1234-5678-1234-56781234eee2'})

        co = Orchestration('child', 1, id='eeeeeeee-1234-5678-1234-56781234eee2')
        cs = o.add_step(undo=False, action_template=ActionTemplate('action', 1, ActionType.SHELL, code=''))

        db.session.add_all([o, s, co, cs])

        oe = OrchExecution(id='bbbbbbbb-1234-5678-1234-56781234bbb1', start_time=start,
                           end_time=end,
                           target={'all': [str(self.me.id), str(self.remote.id)], 'backend': self.remote.name},
                           params={'params': 'content'},
                           executor=u,
                           orchestration=o
                           )
        se = StepExecution(id='aaaaaaaa-1234-5678-1234-56781234aaa1', start_time=start, end_time=end, step=s,
                           orch_execution_id=oe.id,
                           params={'orchestration_id': 'eeeeeeee-1234-5678-1234-56781234eee2'}, rc=None, success=True,
                           server=self.remote)

        coe = OrchExecution(id='bbbbbbbb-1234-5678-1234-56781234bbb2', start_time=start,
                            end_time=end,
                            target={'all': [str(self.me.id), str(self.remote.id)], 'backend': self.remote.name},
                            params={'params': 'content'},
                            executor=u,
                            orchestration=o,
                            parent_step_execution_id=se.id
                            )
        cse = StepExecution(id='aaaaaaaa-1234-5678-1234-56781234aaa2', start_time=start, end_time=end, step=s,
                            orch_execution_id=coe.id,
                            params={'param': 'data'}, rc=0, success=True, server=self.remote,
                            )

        se.child_orch_execution_id = coe.id
        db.session.add_all([oe, se, coe, cse])
        db.session.commit()
        self.assertDictEqual(dict(id=str(oe.id),
                                  start_time=start.strftime(defaults.DATETIME_FORMAT),
                                  end_time=end.strftime(defaults.DATETIME_FORMAT),
                                  target={'all': [str(self.me.id), str(self.remote.id)], 'backend': self.remote.name},
                                  params={'params': 'content'}, orchestration_id=str(o.id),
                                  server_id=None,
                                  service_id=None,
                                  success=None, undo_success=None,
                                  executor_id='cccccccc-1234-5678-1234-56781234ccc1',
                                  message=None),
                             oe.to_json())

        self.assertDictEqual(dict(id=str(oe.id),
                                  start_time=start.strftime(defaults.DATETIME_FORMAT),
                                  end_time=end.strftime(defaults.DATETIME_FORMAT),
                                  target={'all': [str(self.me), str(self.remote)], 'backend': self.remote.name},
                                  params={'params': 'content'},
                                  orchestration={'id': 'eeeeeeee-1234-5678-1234-56781234eee1',
                                                 'name': 'run_orch',
                                                 'version': 1},
                                  server=None,
                                  service=None,
                                  success=None, undo_success=None,
                                  executor='user',
                                  message=None),
                             oe.to_json(human=True))

        dumped = oe.to_json(add_step_exec=True)
        self.assertEqual(1, len(dumped['steps']))
        self.assertEqual('aaaaaaaa-1234-5678-1234-56781234aaa1', dumped['steps'][0]['id'])
        self.assertIn('orch_execution', dumped['steps'][0])

        o_e_json = oe.to_json()
        db.session.commit()
        del oe

        # load existent object
        smashed = OrchExecution.from_json(o_e_json)

        self.assertEqual('bbbbbbbb-1234-5678-1234-56781234bbb1', smashed.id)
        self.assertEqual(start, smashed.start_time)
        self.assertEqual(end, smashed.end_time)
        self.assertEqual(o.id, smashed.orchestration.id)
        self.assertDictEqual({'all': [str(self.me.id), str(self.remote.id)], 'backend': self.remote.name},
                             smashed.target)
        self.assertDictEqual({'params': 'content'}, smashed.params)
        self.assertEqual(User.get_by_user('user'), smashed.executor)
        self.assertEqual(None, smashed.service)
        self.assertEqual(None, smashed.success)
        self.assertEqual(None, smashed.undo_success)

        # load new object and insert into database
        new_obj = OrchExecution.from_json(dict(id='bbbbbbbb-1234-5678-1234-56781234bbb3',
                                               start_time=start.strftime(defaults.DATETIME_FORMAT),
                                               end_time=end.strftime(defaults.DATETIME_FORMAT),
                                               target={'all': [str(self.me.id), str(self.remote.id)],
                                                       'backend': self.remote.name},
                                               params={'params': 'content'},
                                               orchestration_id=str(o.id),
                                               service_id=None,
                                               success=None, undo_success=None,
                                               executor_id='cccccccc-1234-5678-1234-56781234ccc1'))
        db.session.add(new_obj)
        db.session.commit()
