from unittest import TestCase

from flask_jwt_extended import create_access_token

from dimensigon import defaults
from dimensigon.domain.entities import ActionType, Step, ActionTemplate, Orchestration
from dimensigon.utils.helpers import get_now
from dimensigon.web import create_app, db, errors


class TestStep(TestCase):

    def setUp(self):
        """Create and configure a new app instance for each test."""
        # create the app with common test config
        self.app = create_app('test')
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        self.headers = {"Authorization": f"Bearer {create_access_token('00000000-0000-0000-0000-000000000001')}"}

        db.create_all()

        self.at1 = ActionTemplate(id='11111111-2222-3333-4444-555555550001', name='action1', version=1,
                                  action_type=ActionType.SHELL, code='code to run',
                                  expected_stdout='expected output', expected_stderr='stderr', expected_rc=0,
                                  system_kwargs={})

        self.at2 = ActionTemplate(id='11111111-2222-3333-4444-555555550002', name='action2', version=1,
                                  action_type=ActionType.SHELL, code='code to run',
                                  expected_stdout='expected output', expected_stderr='stderr', expected_rc=0,
                                  system_kwargs={})

        self.o = Orchestration(id='11111111-2222-3333-4444-666666660001', name='orchestration_name',
                               version=1, description='desc')
        # db.session.add_all([self.at1, self.at2, self.o])

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_equality(self):
        created = get_now()
        s1 = Step(orchestration=self.o, undo=True, stop_on_error=False, action_template=self.at1,
                  expected_stdout='expected', expected_stderr='stderr',
                  expected_rc=0, system_kwargs={'timeout': 30}, created_on=created)
        s2 = Step(orchestration=self.o, undo=True, stop_on_error=False, action_template=self.at2,
                  expected_stdout='expected', expected_stderr='stderr',
                  expected_rc=0, system_kwargs={'timeout': 30}, created_on=created)

        self.assertTrue(s1.eq_imp(s2))

        s2.post_process = 'post_process'
        self.assertFalse(s1.eq_imp(s2))


    def test_target(self):
        s = Step(None, True, self.at1)
        self.assertEqual(None, s.target)

        with self.assertRaises(errors.BaseError):
            s = Step(None, True, self.at1, target='one')

        s = Step(None, False, self.at1, target='one')
        self.assertEqual(['one'], s.target)

        s = Step(None, False, self.at1)
        self.assertEqual(['all'], s.target)

        s = Step(None, False, self.at1, target=[])
        self.assertEqual(['all'], s.target)

        s = Step(None, False, self.at1, target=['one', 'two'])
        self.assertEqual(['one', 'two'], s.target)

    def test_to_from_json(self):
        created = get_now()
        s2 = Step(orchestration=self.o, undo=True,
                  stop_on_error=False,
                  action_template=self.at2,
                  expected_stdout='expected',
                  expected_stderr='stderr',
                  id='11111111-2222-3333-4444-111111110002',
                  created_on=created)
        s1 = Step(orchestration=self.o, undo=True,
                  stop_on_error=False,
                  action_template=self.at1,
                  expected_stdout='expected',
                  expected_stderr='stderr',
                  expected_rc=0,
                  system_kwargs={'timeout': 180},
                  children_steps=[s2],
                  id='11111111-2222-3333-4444-111111110001',
                  created_on=created)

        s1_json = s1.to_json()
        s2_json = s2.to_json()
        self.assertDictEqual(
            dict(id='11111111-2222-3333-4444-111111110001',
                 orchestration_id='11111111-2222-3333-4444-666666660001',
                 undo=True,
                 stop_on_error=False,
                 action_template_id=str(self.at1.id),
                 expected_stdout='expected',
                 expected_stderr='stderr',
                 parent_step_ids=[],
                 expected_rc=0,
                 system_kwargs={'timeout': 180},
                 created_on=created.strftime(defaults.DATETIME_FORMAT)), s1_json)
        self.assertDictEqual(
            dict(id='11111111-2222-3333-4444-111111110002',
                 orchestration_id='11111111-2222-3333-4444-666666660001',
                 undo=True,
                 stop_on_error=False,
                 action_template_id=str(self.at2.id),
                 expected_stdout='expected',
                 expected_stderr='stderr',
                 parent_step_ids=['11111111-2222-3333-4444-111111110001'],
                 system_kwargs={},
                 created_on=created.strftime(defaults.DATETIME_FORMAT)), s2_json)

        with self.assertRaises(errors.EntityNotFound):
            Step.from_json(s1_json)

        db.session.add(s1)

        smashed_s1 = Step.from_json(s1_json)
        self.assertEqual(s1, smashed_s1)

        s1_json['parent_step_ids'].append('11111111-2222-3333-4444-111111110003')
        with self.assertRaises(errors.EntityNotFound):
            smashed_s1 = Step.from_json(s1_json)
