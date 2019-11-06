from unittest import TestCase

from dm.domain.entities import ActionTemplate, ActionType
from dm.domain.entities.orchestration import Step


class TestStep(TestCase):

    def test_equality(self):
        at1 = ActionTemplate(name='action', version=1, action_type=ActionType.NATIVE, code='code to run',
                             parameters={'param1': 'test'}, expected_output='expected output',
                             expected_rc=0, system_kwargs={})
        at2 = ActionTemplate(name='action', version=1, action_type=ActionType.NATIVE, code='code to run',
                             parameters={'param1': 'test'}, expected_output='expected output',
                             expected_rc=0, system_kwargs={})

        s1 = Step(num=1, undo=True, stop_on_error=False, action_template=at1, step_expected_output='expected',
                  step_expected_rc=0, step_system_kwargs={'timeout': 180}, step_parameters={'param2': 2})
        s2 = Step(num=1, undo=True, stop_on_error=False, action_template=at2, step_expected_output='expected',
                  step_expected_rc=0, step_system_kwargs={'timeout': 180}, step_parameters={'param2': 2})

        self.assertTrue(s1.eq_imp(s2))

        s2.parameters.update({'param2': 3})
        self.assertFalse(s1.eq_imp(s2))

        at2.parameters['param1'] = 'test2'
        s2.parameters.update({'param2': 2, 'param1': 'test'})
        self.assertTrue(s1.eq_imp(s2))
