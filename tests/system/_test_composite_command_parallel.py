import datetime
from unittest import TestCase, mock

from dm.utils.async_operator import AsyncOperator

from dm.use_cases.deployment import UndoCommand, StepExecution, Command, CompositeCommand
from dm.utils.helpers import get_now


class PickableMock(mock.Mock):
    def __reduce__(self):
        return mock.Mock, ()


class TestCompositeCommand(TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ao = AsyncOperator()
        cls.ao.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.ao.stop()
        super().tearDownClass()

    def test_force_all(self):
        mocked_imp_succ = mock.Mock()
        mocked_imp_error = mock.Mock()

        mocked_imp_succ.execute.return_value = StepExecution(success=True, stdout='stdout', stderr='stderr', rc=0,
                                                         start_time=get_now(),
                                                         end_time=get_now() + datetime.timedelta(
                                                             5 / (24 * 60 * 60)))

        mocked_imp_error.execute.return_value = StepExecution(success=False, stdout='stdout', stderr='stderr', rc=0,
                                                          start_time=get_now(),
                                                          end_time=get_now() + datetime.timedelta(
                                                              5 / (24 * 60 * 60)))

        uc1 = UndoCommand(implementation=mocked_imp_succ, id_=1)
        uc2 = UndoCommand(implementation=mocked_imp_error, id_=2)
        uc3 = UndoCommand(implementation=mocked_imp_succ, id_=3)

        cc1 = CompositeCommand({uc1: [uc2], uc2: [uc3]}, force_all=True, id_=1, async_operator=self.ao)

        res = cc1.invoke()

        self.assertEqual(2, mocked_imp_succ.execute.call_count)
        self.assertEqual(1, mocked_imp_error.execute.call_count)
        self.assertFalse(res)

    def test_force_all_undo(self):
        mocked_imp_succ = mock.Mock()
        mocked_imp_error = mock.Mock()

        mocked_imp_succ.execute.return_value = StepExecution(success=True, stdout='stdout', stderr='stderr', rc=0,
                                                         start_time=get_now(),
                                                         end_time=get_now() + datetime.timedelta(
                                                             5 / (24 * 60 * 60)))

        mocked_imp_error.execute.return_value = StepExecution(success=False, stdout='stdout', stderr='stderr', rc=0,
                                                          start_time=get_now(),
                                                          end_time=get_now() + datetime.timedelta(
                                                              5 / (24 * 60 * 60)))

        uc1 = UndoCommand(implementation=mocked_imp_succ, id_=1)
        uc2 = UndoCommand(implementation=mocked_imp_error, id_=2)
        uc3 = UndoCommand(implementation=mocked_imp_succ, id_=3)

        c1 = Command(implementation=mocked_imp_succ, undo_implementation=uc1, id_=1)
        c2 = Command(implementation=mocked_imp_succ, undo_implementation=uc2, id_=2)
        c3 = Command(implementation=mocked_imp_error, undo_implementation=uc3, id_=3)

        cc1 = CompositeCommand({c1: [c2], c2: [c3]}, force_all=True, id_=1, async_operator=self.ao)

        res = cc1.invoke()

        self.assertFalse(res)

        res = cc1.undo()

        self.assertEqual(2, mocked_imp_succ.execute.call_count)
        self.assertEqual(2, mocked_imp_error.execute.call_count)
        self.assertFalse(res)

    def test_undo_on_error(self):
        mocked_imp_succ = mock.Mock()
        mocked_imp_error = mock.Mock()

        mocked_imp_succ.execute.return_value = StepExecution(success=True, stdout='stdout', stderr='stderr', rc=0,
                                                         start_time=get_now(),
                                                         end_time=get_now() + datetime.timedelta(
                                                             5 / (24 * 60 * 60)))

        mocked_imp_error.execute.return_value = StepExecution(success=False, stdout='stdout', stderr='stderr', rc=0,
                                                          start_time=get_now(),
                                                          end_time=get_now() + datetime.timedelta(
                                                              5 / (24 * 60 * 60)))

        uc1 = UndoCommand(implementation=mocked_imp_succ, id_=1)
        uc2 = UndoCommand(implementation=mocked_imp_error, id_=2)
        uc3 = UndoCommand(implementation=mocked_imp_succ, id_=3)

        c1 = Command(implementation=mocked_imp_succ, undo_implementation=uc1, id_=1)
        c2 = Command(implementation=mocked_imp_succ, undo_implementation=uc2, id_=2)
        c3 = Command(implementation=mocked_imp_error, undo_implementation=uc3, undo_on_error=True, id_=3)

        cc1 = CompositeCommand({c1: [c2], c2: [c3]}, force_all=True, id_=1, async_operator=self.ao)

        res = cc1.invoke()

        self.assertFalse(res)

        res = cc1.undo()

        self.assertEqual(3, mocked_imp_succ.execute.call_count)
        self.assertEqual(2, mocked_imp_error.execute.call_count)
        self.assertFalse(res)

    def test_composite_command_error(self):
        mocked_imp_succ = mock.Mock()
        mocked_imp_error = mock.Mock()

        start_time = get_now()
        end_time = get_now() + datetime.timedelta(5 / (24 * 60 * 60))

        mocked_imp_succ.execute.return_value = StepExecution(success=True, stdout='stdout', stderr='stderr', rc=0,
                                                         start_time=start_time,
                                                         end_time=end_time)
        mocked_imp_error.execute.return_value = StepExecution(success=False, stdout='stdout', stderr='stderr', rc=0,
                                                          start_time=start_time,
                                                          end_time=end_time)

        uc1 = UndoCommand(implementation=mocked_imp_succ, id_=1)
        uc2 = UndoCommand(implementation=mocked_imp_succ, id_=2)
        uc3 = UndoCommand(implementation=mocked_imp_succ, id_=3)
        uc4 = UndoCommand(implementation=mocked_imp_succ, id_=4)

        ccu1 = CompositeCommand({uc1: []}, async_operator=self.ao)
        ccu2 = CompositeCommand({uc2: [uc3], uc3: [uc4]}, async_operator=self.ao)

        c1 = Command(implementation=mocked_imp_succ, undo_implementation=ccu1, id_=5)
        c2 = Command(implementation=mocked_imp_error, undo_implementation=ccu2, id_=6)

        cc = CompositeCommand({c1: [c2], c2: []}, async_operator=self.ao)

        res = cc.invoke()

        self.assertDictEqual({5: StepExecution(success=True, stdout='stdout', stderr='stderr', rc=0,
                                           start_time=start_time,
                                           end_time=end_time),
                              6: StepExecution(success=False, stdout='stdout', stderr='stderr', rc=0,
                                           start_time=start_time,
                                           end_time=end_time)}
                             , cc.execution)

        self.assertEqual(False, res)
        self.assertEqual(1, mocked_imp_succ.execute.call_count)
        self.assertEqual(1, mocked_imp_error.execute.call_count)

        res = cc.undo()

        self.assertDictEqual({5: StepExecution(success=True, stdout='stdout', stderr='stderr', rc=0,
                                           start_time=start_time,
                                           end_time=end_time),
                              6: StepExecution(success=False, stdout='stdout', stderr='stderr', rc=0,
                                           start_time=start_time,
                                           end_time=end_time),
                              1: StepExecution(success=True, stdout='stdout', stderr='stderr', rc=0,
                                           start_time=start_time,
                                           end_time=end_time)}
                             , cc.execution)

        self.assertEqual(True, res)
        self.assertEqual(2, mocked_imp_succ.execute.call_count)
        self.assertEqual(1, mocked_imp_error.execute.call_count)

    def test_composite_command_error2(self):
        mocked_imp_succ = mock.Mock()
        mocked_imp_error = mock.Mock()

        start_time = get_now()
        end_time = get_now() + datetime.timedelta(5 / (24 * 60 * 60))

        mocked_imp_succ.execute.return_value = StepExecution(success=True, stdout='stdout', stderr='stderr', rc=0,
                                                         start_time=start_time,
                                                         end_time=end_time)
        mocked_imp_error.execute.return_value = StepExecution(success=False, stdout='stdout', stderr='stderr', rc=0,
                                                          start_time=start_time,
                                                          end_time=end_time)

        uc1 = UndoCommand(implementation=mocked_imp_succ, id_=1)
        uc2 = UndoCommand(implementation=mocked_imp_succ, id_=2)
        uc3 = UndoCommand(implementation=mocked_imp_succ, id_=3)
        uc4 = UndoCommand(implementation=mocked_imp_succ, id_=4)
        uc5 = UndoCommand(implementation=mocked_imp_succ, id_=5)

        ccu1 = CompositeCommand({uc1: []}, async_operator=self.ao)
        ccu2 = CompositeCommand({uc2: [uc3], uc3: [uc4]}, async_operator=self.ao)

        c1 = Command(implementation=mocked_imp_succ, undo_implementation=ccu1, id_=6)
        c2 = Command(implementation=mocked_imp_error, undo_implementation=ccu2, id_=7)
        c3 = Command(implementation=mocked_imp_succ, undo_implementation=uc5, id_=8)

        cc = CompositeCommand({c1: [c2], c2: [c3]}, async_operator=self.ao)

        res = cc.invoke()

        self.assertEqual(False, res)
        self.assertEqual(1, mocked_imp_succ.execute.call_count)
        self.assertEqual(1, mocked_imp_error.execute.call_count)

        res = cc.undo()

        self.assertEqual(True, res)
        self.assertEqual(2, mocked_imp_succ.execute.call_count)
        self.assertEqual(1, mocked_imp_error.execute.call_count)

    def test_composite_command_error3(self):
        mocked_imp_succ = PickableMock()
        mocked_imp_error = PickableMock()

        start_time = get_now()
        end_time = get_now() + datetime.timedelta(5 / (24 * 60 * 60))

        mocked_imp_succ.execute.return_value = StepExecution(success=True, stdout='stdout', stderr='stderr', rc=0,
                                                         start_time=start_time,
                                                         end_time=end_time)
        mocked_imp_error.execute.return_value = StepExecution(success=False, stdout='stdout', stderr='stderr', rc=0,
                                                          start_time=start_time,
                                                          end_time=end_time)

        uc1 = UndoCommand(implementation=mocked_imp_succ, id_=1)
        uc2 = UndoCommand(implementation=mocked_imp_succ, id_=2)
        uc3 = UndoCommand(implementation=mocked_imp_error, id_=3)
        uc4 = UndoCommand(implementation=mocked_imp_succ, id_=4)
        uc5 = UndoCommand(implementation=mocked_imp_succ, id_=5)

        ccu1 = CompositeCommand({uc1: []}, async_operator=self.ao)
        ccu2 = CompositeCommand({uc2: [uc3, uc4]}, async_operator=self.ao)

        c1 = Command(implementation=mocked_imp_succ, undo_implementation=ccu1, id_=6)
        c2 = Command(implementation=mocked_imp_succ, undo_implementation=ccu2, id_=7)
        c3 = Command(implementation=mocked_imp_succ, undo_implementation=uc5, id_=8)

        cc = CompositeCommand({c1: [c2], c2: [c3]}, async_operator=self.ao)

        res = cc.invoke()

        self.assertTrue(res)
        self.assertEqual(3, mocked_imp_succ.execute.call_count)
        self.assertEqual(0, mocked_imp_error.execute.call_count)

        res = cc.undo()

        self.assertFalse(res)
        self.assertEqual(6, mocked_imp_succ.execute.call_count)
        self.assertEqual(1, mocked_imp_error.execute.call_count)

        self.assertDictEqual({2: StepExecution(success=True, stdout='stdout', stderr='stderr', rc=0,
                                           start_time=start_time,
                                           end_time=end_time),
                              3: StepExecution(success=False, stdout='stdout', stderr='stderr', rc=0,
                                           start_time=start_time,
                                           end_time=end_time),
                              4: StepExecution(success=True, stdout='stdout', stderr='stderr', rc=0,
                                           start_time=start_time,
                                           end_time=end_time),
                              5: StepExecution(success=True, stdout='stdout', stderr='stderr', rc=0,
                                           start_time=start_time,
                                           end_time=end_time),
                              6: StepExecution(success=True, stdout='stdout', stderr='stderr', rc=0,
                                           start_time=start_time,
                                           end_time=end_time),
                              7: StepExecution(success=True, stdout='stdout', stderr='stderr', rc=0,
                                           start_time=start_time,
                                           end_time=end_time),
                              8: StepExecution(success=True, stdout='stdout', stderr='stderr', rc=0,
                                           start_time=start_time,
                                           end_time=end_time)
                              }
                             , cc.execution)

    def test_composite_command_success(self):
        mocked_imp_succ = mock.Mock()
        mocked_imp_error = mock.Mock()

        start_time = get_now()
        end_time = get_now() + datetime.timedelta(5 / (24 * 60 * 60))

        mocked_imp_succ.execute.return_value = StepExecution(success=True, stdout='stdout', stderr='stderr', rc=0,
                                                         start_time=start_time,
                                                         end_time=end_time)
        mocked_imp_error.execute.return_value = StepExecution(success=False, stdout='stdout', stderr='stderr', rc=0,
                                                          start_time=start_time,
                                                          end_time=end_time)

        uc1 = UndoCommand(implementation=mocked_imp_succ, id_=1)
        uc2 = UndoCommand(implementation=mocked_imp_succ, id_=2)
        uc3 = UndoCommand(implementation=mocked_imp_succ, id_=3)
        uc4 = UndoCommand(implementation=mocked_imp_succ, id_=4)

        c1 = Command(implementation=mocked_imp_succ, undo_implementation=uc1, id_=5)
        c2 = Command(implementation=mocked_imp_succ, undo_implementation=uc2, id_=6)
        c3 = Command(implementation=mocked_imp_succ, undo_implementation=uc3, id_=7)
        c4 = Command(implementation=mocked_imp_succ, undo_implementation=uc4, id_=8)

        cc = CompositeCommand({c1: [c2, c3, c4]}, async_operator=self.ao)

        res = cc.invoke()

        self.assertDictEqual({5: StepExecution(success=True, stdout='stdout', stderr='stderr', rc=0,
                                           start_time=start_time,
                                           end_time=end_time),
                              6: StepExecution(success=True, stdout='stdout', stderr='stderr', rc=0,
                                           start_time=start_time,
                                           end_time=end_time),
                              7: StepExecution(success=True, stdout='stdout', stderr='stderr', rc=0,
                                           start_time=start_time,
                                           end_time=end_time),
                              8: StepExecution(success=True, stdout='stdout', stderr='stderr', rc=0,
                                           start_time=start_time,
                                           end_time=end_time),
                              }
                             , cc.execution)
        self.assertEqual(True, res)
        self.assertEqual(4, mocked_imp_succ.execute.call_count)
        self.assertEqual(0, mocked_imp_error.execute.call_count)

    def test_composite_command_success(self):
        mocked_imp_succ = mock.Mock()
        mocked_imp_error = mock.Mock()

        start_time = get_now()
        end_time = get_now() + datetime.timedelta(5 / (24 * 60 * 60))

        mocked_imp_succ.execute.return_value = StepExecution(success=True, stdout='stdout', stderr='stderr', rc=0,
                                                         start_time=start_time,
                                                         end_time=end_time)
        mocked_imp_error.execute.return_value = StepExecution(success=False, stdout='stdout', stderr='stderr', rc=0,
                                                          start_time=start_time,
                                                          end_time=end_time)

        uc1 = UndoCommand(implementation=mocked_imp_succ, id_=1)
        uc2 = UndoCommand(implementation=mocked_imp_succ, id_=2)
        uc3 = UndoCommand(implementation=mocked_imp_succ, id_=3)
        uc4 = UndoCommand(implementation=mocked_imp_succ, id_=4)

        c1 = Command(implementation=mocked_imp_succ, undo_implementation=uc1, id_=5)
        c2 = Command(implementation=mocked_imp_succ, undo_implementation=uc2, id_=6)
        c3 = Command(implementation=mocked_imp_error, undo_implementation=uc3, id_=7)
        c4 = Command(implementation=mocked_imp_succ, undo_implementation=uc4, id_=8)

        cc = CompositeCommand({c1: [c2, c3, c4]}, async_operator=self.ao)

        res = cc.invoke()

        self.assertDictEqual({5: StepExecution(success=True, stdout='stdout', stderr='stderr', rc=0,
                                           start_time=start_time,
                                           end_time=end_time),
                              6: StepExecution(success=True, stdout='stdout', stderr='stderr', rc=0,
                                           start_time=start_time,
                                           end_time=end_time),
                              7: StepExecution(success=False, stdout='stdout', stderr='stderr', rc=0,
                                           start_time=start_time,
                                           end_time=end_time),
                              8: StepExecution(success=True, stdout='stdout', stderr='stderr', rc=0,
                                           start_time=start_time,
                                           end_time=end_time),
                              }
                             , cc.execution)
        self.assertEqual(False, res)
        self.assertEqual(3, mocked_imp_succ.execute.call_count)
        self.assertEqual(1, mocked_imp_error.execute.call_count)
