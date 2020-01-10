import uuid
from itertools import count
from unittest import TestCase
from unittest.mock import PropertyMock

from asynctest import mock

import dm.domain.entities as e
from dm.domain.exceptions import CycleError


class TestOrchestration(TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.at = mock.MagicMock()

        type(cls.at).action = PropertyMock(return_value='action')
        type(cls.at).version = PropertyMock(return_value=1)
        type(cls.at).action_type = PropertyMock(return_value=e.ActionType.NATIVE)
        type(cls.at).code = PropertyMock(return_value='code to run')
        type(cls.at).parameters = PropertyMock(return_value={'param1': 'test'})
        type(cls.at).expected_output = PropertyMock(return_value='expected output')
        type(cls.at).expected_rc = PropertyMock(return_value=0)
        type(cls.at).system_kwargs = PropertyMock(return_value={})

    def test_constructor(self):
        from dm.domain.entities.orchestration import Step

        s1 = Step(id=uuid.UUID('11111111-2222-3333-4444-555555550001'))
        s2 = Step(id=uuid.UUID('11111111-2222-3333-4444-555555550002'))
        s3 = Step(id=uuid.UUID('11111111-2222-3333-4444-555555550003'))

        o = e.Orchestration('test', 1, id=uuid.UUID('11111111-2222-3333-4444-555555550004'),
                            description='description test', steps=[s1, s2, s3],
                            dependencies={s1.id: [s2.id], s2.id: [s3.id], s3.id: []})

        self.assertDictEqual(o.dependencies, {s1: [s2], s2: [s3], s3: []})

        self.assertListEqual(o.steps, [s1, s2, s3])

        with self.assertRaises(ValueError):
            o2 = e.Orchestration('test', 1, description='description test', steps=[s1, s2, s3],
                                 dependencies={s1: [s2], s2: [s3], s3: [4]})

    # noinspection PyTypeChecker
    def test_orchestration(self):
        self.o = e.Orchestration(id=1,
                                 name='Test Orchestration',
                                 version=1,
                                 description='description')

        s1 = self.o.add_step(undo=False, action_template=self.at, parents=[], children=[], stop_on_error=False,
                             id=1)
        s2 = self.o.add_step(undo=True, action_template=self.at, parents=[s1], children=[], stop_on_error=False,
                             id=2)

        with self.assertRaises(ValueError):
            self.o.add_step(undo=False, action_template=self.at, parents=[s2], children=[], stop_on_error=False)

        o2 = e.Orchestration('dto', 2, id=2)
        s21 = o2.add_step(undo=False, action_template=self.at, parents=[], children=[], stop_on_error=False,
                          id=21)

        with self.assertRaises(ValueError):
            self.o.add_parents(s21, [s1])

        self.o.delete_step(s2)

        self.assertListEqual(self.o.steps, [s1])
        self.assertListEqual(self.o.children[s1], [])

        s2 = self.o.add_step(undo=False, action_template=self.at, parents=[s1], children=[], stop_on_error=False, id=2)
        s3 = self.o.add_step(undo=False, action_template=self.at, parents=[s2], children=[], stop_on_error=False, id=3)
        s4 = self.o.add_step(undo=False, action_template=self.at, parents=[s2], children=[], stop_on_error=False, id=4)
        s5 = self.o.add_step(undo=False, action_template=self.at, parents=[s4], children=[], stop_on_error=False, id=5)
        s6 = self.o.add_step(undo=False, action_template=self.at, parents=[s4], children=[], stop_on_error=False, id=6)
        s7 = self.o.add_step(undo=False, action_template=self.at, parents=[s1], children=[s2], stop_on_error=False, id=7)

        self.assertListEqual(self.o.steps, [s1, s2, s3, s4, s5, s6, s7])

        self.assertDictEqual(self.o.children,
                             {s1: [s2, s7], s2: [s3, s4], s3: [], s4: [s5, s6], s5: [], s6: [], s7: [s2]})
        self.assertDictEqual(self.o.parents,
                             {s1: [], s2: [s1, s7], s3: [s2], s4: [s2], s5: [s4], s6: [s4], s7: [s1]})

        with self.assertRaises(ValueError):
            self.o.add_step(undo=True, action_template=self.at, parents=[s1], children=[s2], stop_on_error=False)

        with self.assertRaises(CycleError):
            self.o.add_step(undo=False, action_template=self.at, parents=[s6], children=[s1], stop_on_error=False)

        # Check parent functions
        self.o.add_parents(s6, [s2])
        self.assertListEqual(self.o.children[s2], [s3, s4, s6])

        self.o.set_parents(s6, [s3, s4])
        self.assertListEqual(self.o.parents[s6], [s3, s4])

        self.o.delete_parents(s6, [s3, s2])
        self.assertListEqual(self.o.parents[s6], [s4])

        # Check children functions
        self.o.add_children(s3, [s6])
        self.assertListEqual(self.o.parents[s6], [s4, s3])

        self.o.delete_children(s4, [s5, s6])
        self.assertListEqual(self.o.parents[s6], [s3])
        self.assertListEqual(self.o.parents[s5], [])

        self.o.set_children(s4, [s5, s6]).set_children(s3, [])
        self.assertListEqual([s4], self.o.parents[s6])
        self.assertListEqual([s4], self.o.parents[s5])
        self.assertListEqual([], self.o.children[s3])

        # properties and default values
        s = self.o.add_step(undo=False, action_template=self.at)
        self.assertEqual(False, s.stop_on_error)
        self.assertEqual('code to run', s.code)
        self.assertEqual('expected output', s.expected_output)
        s.expected_output = 'changed'
        self.assertEqual('changed', s.expected_output)
        s.expected_output = ''
        self.assertEqual('', s.expected_output)
        s.expected_output = None
        self.assertEqual('expected output', s.expected_output)
        self.assertEqual(0, s.expected_rc)
        s.expected_rc = 2
        self.assertEqual(2, s.expected_rc)
        s.expected_rc = 0
        self.assertEqual(0, s.expected_rc)
        s.expected_rc = None
        self.assertEqual(0, s.expected_rc)

    def test_eq_imp(self):
        o1 = e.Orchestration('dto', 1)

        s11 = o1.add_step(False, self.at, )
        s12 = o1.add_step(False, self.at, parents=[s11])

        o2 = e.Orchestration('dto', 2)
        s21 = o2.add_step(False, self.at, )
        s22 = o2.add_step(False, self.at, parents=[s21])

        self.assertTrue(o1.eq_imp(o2))
        self.assertTrue(o2.eq_imp(o1))

        s23 = o2.add_step(True, self.at, parents=[s22])

        self.assertFalse(o1.eq_imp(o2))
        self.assertFalse(o2.eq_imp(o1))

        s13 = o1.add_step(True, self.at, parents=[s12])

        self.assertTrue(o1.eq_imp(o2))

        s13.parameters['server'] = 'localhost'
        self.assertFalse(s13.eq_imp(s23))
        self.assertFalse(o1.eq_imp(o2))
