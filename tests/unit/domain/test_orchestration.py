from itertools import count
from unittest import TestCase
from unittest.mock import PropertyMock

from asynctest import mock

import dm.domain.entities as e
from dm.domain.exceptions import CycleError
from dm.framework.domain import Entity, Id


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

    def setUp(self) -> None:
        self.o = e.Orchestration(name='Test Orchestration', version=1, description='description')

    def tearDown(self) -> None:
        del self.o

    def test_constructor(self):
        seq = count(1)

        class Step(Entity):
            __id__ = Id(factory=lambda: next(seq))

            def __init__(self, num, **kwargs):
                super().__init__(**kwargs)
                self.num = num

        s1 = Step(5)
        s2 = Step(6)
        s3 = Step(7)

        o = e.Orchestration('test', 1, description='description test', steps=[s1, s2, s3],
                            dependencies={s1.id: [s2.id], s2.id: [s3.id], s3.id: []})

        self.assertDictEqual(o.dependencies, {1: [2], 2: [3], 3: []})

        self.assertListEqual(o.steps, [s1, s2, s3])

        with self.assertRaises(ValueError):
            o2 = e.Orchestration('test', 1, description='description test', steps=[s1, s2, s3],
                                 dependencies={s1.id: [s2.id], s2.id: [s3.id], s3.id: [4]})

    def test_orchestration(self):
        e.Step.__id__.factory = mock.Mock(side_effect=[n for n in range(1, 100)])
        s1 = self.o.add_step(undo=False, action_template=self.at, parents=[], children=[], stop_on_error=False)
        s2 = self.o.add_step(undo=True, action_template=self.at, parents=[s1], children=[], stop_on_error=False)

        with self.assertRaises(ValueError):
            self.o.add_step(undo=False, action_template=self.at, parents=[s2], children=[], stop_on_error=False)

        o2 = e.Orchestration('dto', 2)
        s21 = o2.add_step(undo=False, action_template=self.at, parents=[], children=[], stop_on_error=False)

        with self.assertRaises(ValueError):
            self.o.add_parents(s21, [s1])

        self.o.delete_step(s2)

        self.assertListEqual(self.o.steps, [s1])
        self.assertListEqual(self.o.children[s1], [])

        s2 = self.o.add_step(undo=False, action_template=self.at, parents=[s1], children=[], stop_on_error=False)
        s3 = self.o.add_step(undo=False, action_template=self.at, parents=[s2], children=[], stop_on_error=False)
        s4 = self.o.add_step(undo=False, action_template=self.at, parents=[s2], children=[], stop_on_error=False)
        s5 = self.o.add_step(undo=False, action_template=self.at, parents=[s4], children=[], stop_on_error=False)
        s6 = self.o.add_step(undo=False, action_template=self.at, parents=[s4], children=[], stop_on_error=False)
        s7 = self.o.add_step(undo=False, action_template=self.at, parents=[s1], children=[s2], stop_on_error=False)

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

        self.o.set_children(s4, [s5, s6]).set_children(s3, [])
        self.assertListEqual(self.o.parents[s6], [s4])

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
        e.Step.__id__.factory = mock.Mock(side_effect=[n for n in range(1, 100)])
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

        self.assertFalse(o1.eq_imp(o2))
