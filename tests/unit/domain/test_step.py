import uuid
from unittest import TestCase, mock
from unittest.mock import PropertyMock

from dm.domain.entities import ActionTemplate, ActionType
from dm.domain.entities.orchestration import Step


class TestStep(TestCase):

    def setUp(self) -> None:
        self.at1 = mock.MagicMock()

        type(self.at1).id = PropertyMock(return_value=uuid.UUID('11111111-2222-3333-4444-555555550001'))
        type(self.at1).action = PropertyMock(return_value='action')
        type(self.at1).version = PropertyMock(return_value=1)
        type(self.at1).action_type = PropertyMock(return_value=ActionType.NATIVE)
        type(self.at1).code = PropertyMock(return_value='code to run')
        type(self.at1).parameters = PropertyMock(return_value={'param1': 'test'})
        type(self.at1).expected_output = PropertyMock(return_value='expected output')
        type(self.at1).expected_rc = PropertyMock(return_value=0)
        type(self.at1).system_kwargs = PropertyMock(return_value={})

        self.at2 = mock.MagicMock()

        type(self.at2).id = PropertyMock(return_value=uuid.UUID('11111111-2222-3333-4444-555555550002'))
        type(self.at2).action = PropertyMock(return_value='action')
        type(self.at2).version = PropertyMock(return_value=1)
        type(self.at2).action_type = PropertyMock(return_value=ActionType.NATIVE)
        type(self.at2).code = PropertyMock(return_value='code to run')
        type(self.at2).parameters = PropertyMock(return_value={'param1': 'test'})
        type(self.at2).expected_output = PropertyMock(return_value='expected output')
        type(self.at2).expected_rc = PropertyMock(return_value=0)
        type(self.at2).system_kwargs = PropertyMock(return_value={})

    def test_equality(self):


        s1 = Step(undo=True, stop_on_error=False, action_template=self.at1, step_expected_output='expected',
                  step_expected_rc=0, step_system_kwargs={'timeout': 180}, step_parameters={'param2': 2})
        s2 = Step(undo=True, stop_on_error=False, action_template=self.at2, step_expected_output='expected',
                  step_expected_rc=0, step_system_kwargs={'timeout': 180}, step_parameters={'param2': 2})

        self.assertTrue(s1.eq_imp(s2))

        s2.parameters.update({'param2': 3})
        self.assertFalse(s1.eq_imp(s2))

        self.at2.parameters['param1'] = 'test2'
        s2.parameters.update({'param2': 2, 'param1': 'test'})
        self.assertTrue(s1.eq_imp(s2))
