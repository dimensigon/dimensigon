from unittest import TestCase

from flask_jwt_extended import create_access_token

from dm.domain.entities import Step, ActionTemplate, ActionType, Orchestration
from dm.network.auth import HTTPBearerAuth
from dm.web import create_app, db, errors


class TestOrchestration(TestCase):
    def setUp(self):
        """Create and configure a new app instance for each test."""
        # create the app with common test config
        self.app = create_app('test')
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        self.auth = HTTPBearerAuth(create_access_token('00000000-0000-0000-0000-000000000001'))
        db.create_all()
        self.at = ActionTemplate(name='action', version=1, action_type=ActionType.SHELL, code='code to run',
                                 parameters={'param1': 'test'}, expected_stdout='expected output', expected_rc=0,
                                 system_kwargs={})

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_orch_creation(self):
        o = Orchestration(id="aaaaaaaa-1234-5678-1234-56781234aaa1",
                          name='Test Orchestration',
                          version=1,
                          description='description',
                          params={'param1': 2})

        db.session.add(o)
        db.session.commit()
        del o
        o = Orchestration.query.get("aaaaaaaa-1234-5678-1234-56781234aaa1")

    def test_parameters(self):
        o = Orchestration(id=1,
                          name='Test Orchestration',
                          version=1,
                          description='description')

        s1 = o.add_step(undo=False, action_template=self.at, parents=[], children=[], stop_on_error=False, id=1)

        at = ActionTemplate(name='action', version=1, action_type=ActionType.SHELL, code='code to run',
                            parameters={}, expected_stdout='expected output', expected_rc=0,
                            system_kwargs={})

        self.assertDictEqual(dict(s1.parameters), {'param1': 'test'})

        s1.action_template = at

        self.assertDictEqual(dict(s1.parameters), {})

    def test_set_dependencies(self):
        s1 = Step(orchestration=None, undo=False, stop_on_error=False, action_template=self.at,
                  id='11111111-2222-3333-4444-555555550001')
        s2 = Step(orchestration=None, undo=False, stop_on_error=False, action_template=self.at,
                  id='11111111-2222-3333-4444-555555550002')
        s3 = Step(orchestration=None, undo=False, stop_on_error=False, action_template=self.at,
                  id='11111111-2222-3333-4444-555555550003')

        o = Orchestration('test', 1, id='11111111-2222-3333-4444-555555550004',
                          description='description test', steps=[s1, s2, s3],
                          dependencies={s1.id: [s2.id], s2.id: [s3.id], s3.id: []})

        self.assertDictEqual(o.dependencies, {s1: [s2], s2: [s3], s3: []})

        self.assertListEqual(o.steps, [s1, s2, s3])

        with self.assertRaises(ValueError):
            o.set_dependencies({s1: [s2], s2: [s3], s3: [4]})

        o = Orchestration('test', 1, id='11111111-2222-3333-4444-555555550004',
                          description='description test', steps=[s1, s2, s3])

        self.assertListEqual([s1, s2, s3], o.steps)
        o.set_dependencies([(s1, s2), (s2, s3)])
        self.assertDictEqual(o.dependencies, {s1: [s2], s2: [s3], s3: []})

    # noinspection PyTypeChecker
    def test_attributes_and_methods(self):
        o = Orchestration(id=1,
                          name='Test Orchestration',
                          version=1,
                          description='description')

        s1 = o.add_step(undo=False, action_template=self.at, parents=[], children=[], stop_on_error=False,
                        id=1)
        s2 = o.add_step(undo=True, action_template=self.at, parents=[s1], children=[], stop_on_error=False,
                        id=2)

        with self.assertRaises(errors.ParentUndoError):
            o.add_step(undo=False, action_template=self.at, parents=[s2], children=[], stop_on_error=False)
        self.assertListEqual(o.steps, [s1, s2])

        o2 = Orchestration('dto', 2, id=2)
        s21 = o2.add_step(undo=False, action_template=self.at, parents=[], children=[], stop_on_error=False,
                          id=21)

        with self.assertRaises(ValueError):
            o.add_parents(s21, [s1])

        o.delete_step(s2)

        self.assertListEqual(o.steps, [s1])
        self.assertListEqual(o.children[s1], [])

        s2 = o.add_step(undo=False, action_template=self.at, parents=[s1], children=[], stop_on_error=False, id=2)
        s3 = o.add_step(undo=False, action_template=self.at, parents=[s2], children=[], stop_on_error=False, id=3)
        s4 = o.add_step(undo=False, action_template=self.at, parents=[s2], children=[], stop_on_error=False, id=4)
        s5 = o.add_step(undo=False, action_template=self.at, parents=[s4], children=[], stop_on_error=False, id=5)
        s6 = o.add_step(undo=False, action_template=self.at, parents=[s4], children=[], stop_on_error=False, id=6)
        s7 = o.add_step(undo=False, action_template=self.at, parents=[s1], children=[s2], stop_on_error=False,
                        id=7)

        self.assertListEqual(o.steps, [s1, s2, s3, s4, s5, s6, s7])

        self.assertDictEqual(o.children,
                             {s1: [s2, s7], s2: [s3, s4], s3: [], s4: [s5, s6], s5: [], s6: [], s7: [s2]})
        self.assertDictEqual(o.parents,
                             {s1: [], s2: [s1, s7], s3: [s2], s4: [s2], s5: [s4], s6: [s4], s7: [s1]})

        with self.assertRaises(errors.ChildDoError):
            o.add_step(undo=True, action_template=self.at, parents=[s1], children=[s2], stop_on_error=False)

        with self.assertRaises(errors.CycleError):
            o.add_step(undo=False, action_template=self.at, parents=[s6], children=[s1], stop_on_error=False)

        # Check parent functions
        o.add_parents(s6, [s2])
        self.assertListEqual(o.children[s2], [s3, s4, s6])

        o.set_parents(s6, [s3, s4])
        self.assertListEqual(o.parents[s6], [s3, s4])

        o.delete_parents(s6, [s3, s2])
        self.assertListEqual(o.parents[s6], [s4])

        # Check children functions
        o.add_children(s3, [s6])
        self.assertListEqual(o.parents[s6], [s4, s3])

        o.delete_children(s4, [s5, s6])
        self.assertListEqual(o.parents[s6], [s3])
        self.assertListEqual(o.parents[s5], [])

        o.set_children(s4, [s5, s6]).set_children(s3, [])
        self.assertListEqual([s4], o.parents[s6])
        self.assertListEqual([s4], o.parents[s5])
        self.assertListEqual([], o.children[s3])

        # properties and default values
        s = o.add_step(undo=False, action_template=self.at)
        self.assertEqual(True, s.stop_on_error)
        self.assertEqual('code to run', s.code)
        self.assertEqual('expected output', s.expected_stdout)
        s.expected_output = 'changed'
        self.assertEqual('changed', s.expected_output)
        s.expected_output = ''
        self.assertEqual('', s.expected_output)
        s.expected_output = None
        self.assertEqual('expected output', s.expected_stdout)
        self.assertEqual(0, s.expected_rc)
        s.expected_rc = 2
        self.assertEqual(2, s.expected_rc)
        s.expected_rc = 0
        self.assertEqual(0, s.expected_rc)
        s.expected_rc = None
        self.assertEqual(0, s.expected_rc)

    def test_eq_imp(self):
        o1 = Orchestration('dto', 1)

        s11 = o1.add_step(False, self.at)
        s12 = o1.add_step(False, self.at, parents=[s11])

        o2 = Orchestration('dto', 2)
        s21 = o2.add_step(False, self.at, )
        s22 = o2.add_step(False, self.at, parents=[s21])

        self.assertTrue(o1.eq_imp(o2))
        self.assertTrue(o2.eq_imp(o1))

        s23 = o2.add_step(True, self.at, parents=[s22])

        self.assertFalse(o1.eq_imp(o2))
        self.assertFalse(o2.eq_imp(o1))

        s13 = o1.add_step(True, self.at, parents=[s12])

        self.assertTrue(o1.eq_imp(o2))

        s13.step_parameters['server'] = 'localhost'
        self.assertFalse(s13.eq_imp(s23))
        self.assertFalse(o1.eq_imp(o2))

    def test_init_on_load(self):
        o = Orchestration(id='aaaaaaaa-1234-5678-1234-aaaaaaaa0001',
                          name='Test Orchestration',
                          version=1,
                          description='description')

        s1 = o.add_step(undo=False, action_template=self.at, parents=[], children=[], stop_on_error=False,
                        id='bbbbbbbb-1234-5678-1234-bbbbbbbb0001')

        db.session.add(o)
        db.session.commit()
        del o

        o = Orchestration.query.get('aaaaaaaa-1234-5678-1234-aaaaaaaa0001')

        self.assertEqual({s1: []}, o._graph.succ)


        s2 = o.add_step(undo=False, action_template=self.at, parents=[], children=[], stop_on_error=False,
                        id='bbbbbbbb-1234-5678-1234-bbbbbbbb0002')
        del o

        o = Orchestration.query.get('aaaaaaaa-1234-5678-1234-aaaaaaaa0001')

        self.assertEqual({s1: [], s2: []}, o._graph.succ)
