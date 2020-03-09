from unittest import TestCase
from unittest.mock import patch

from dm.domain.entities import ActionType, ActionTemplate, Orchestration
from dm.use_cases.interactor import Interactor


class TestInteractor(TestCase):

    def test_create_cmd_from_orchestration(self):
        at = ActionTemplate(id=1, name='create dir', version=1, action_type=ActionType.NATIVE, code='mkdir {dir}',
                            parameters={}, expected_output='',
                            expected_rc=0, system_kwargs={})

        o = Orchestration('Test Orchestration', 1, 'description', id=1)

        s1 = o.add_step(id=1, undo=False, action_template=at, parents=[], children=[], stop_on_error=False)
        s2 = o.add_step(id=2, undo=True, action_template=at, parents=[s1], children=[], stop_on_error=False)
        s3 = o.add_step(id=3, undo=False, action_template=at, parents=[s1], children=[], stop_on_error=False)
        s4 = o.add_step(id=4, undo=True, action_template=at, parents=[s3], children=[], stop_on_error=False)
        s5 = o.add_step(id=5, undo=True, action_template=at, parents=[s4], children=[], stop_on_error=False)
        s6 = o.add_step(id=6, undo=True, action_template=at, parents=[s5], children=[], stop_on_error=False)
        s7 = o.add_step(id=7, undo=False, action_template=at, parents=[s3], children=[], stop_on_error=False)
        s8 = o.add_step(id=8, undo=True, action_template=at, parents=[s7], children=[], stop_on_error=False)

        i = Interactor()

        cc = i._create_cmd_from_orchestration(o, {'dir': 'C:\\test_folder'})

        self.assertEqual(3, len(cc))

        with patch('subprocess.run') as mocked_run:
            mocked_run.return_value = (0, '', '')
            cc.invoke()

            self.assertEqual(3, mocked_run.call_count)

            cc.undo()

            self.assertEqual(8, mocked_run.call_count)
