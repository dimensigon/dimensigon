import datetime
from concurrent.futures import ThreadPoolExecutor
from unittest import TestCase, mock

from dm.use_cases.deployment import UndoCommand, CompositeCommand, CompletedProcess, Command


class TestCompositeCommand(TestCase):
    maxDiff = None

    def test_force_all(self):
        mocked_imp_succ = mock.Mock()
        mocked_imp_error = mock.Mock()

        mocked_imp_succ.execute.return_value = CompletedProcess(success=True, stdout='stdout', stderr='stderr', rc=0,
                                                                start_time=datetime.datetime.now(),
                                                                end_time=datetime.datetime.now() + datetime.timedelta(
                                                                    5 / (24 * 60 * 60)))

        mocked_imp_error.execute.return_value = CompletedProcess(success=False, stdout='stdout', stderr='stderr', rc=0,
                                                                 start_time=datetime.datetime.now(),
                                                                 end_time=datetime.datetime.now() + datetime.timedelta(
                                                                     5 / (24 * 60 * 60)))

        uc1 = UndoCommand(implementation=mocked_imp_succ, id_=1)
        uc2 = UndoCommand(implementation=mocked_imp_error, id_=2)
        uc3 = UndoCommand(implementation=mocked_imp_succ, id_=3)

        cc1 = CompositeCommand({uc1: [uc2], uc2: [uc3]}, force_all=True, id_=1)

        res = cc1.invoke()

        self.assertEqual(2, mocked_imp_succ.execute.call_count)
        self.assertEqual(1, mocked_imp_error.execute.call_count)
        self.assertFalse(res)

    def test_force_all_undo(self):
        mocked_imp_succ = mock.Mock()
        mocked_imp_error = mock.Mock()

        mocked_imp_succ.execute.return_value = CompletedProcess(success=True, stdout='stdout', stderr='stderr', rc=0,
                                                                start_time=datetime.datetime.now(),
                                                                end_time=datetime.datetime.now() + datetime.timedelta(
                                                                    5 / (24 * 60 * 60)))

        mocked_imp_error.execute.return_value = CompletedProcess(success=False, stdout='stdout', stderr='stderr', rc=0,
                                                                 start_time=datetime.datetime.now(),
                                                                 end_time=datetime.datetime.now() + datetime.timedelta(
                                                                     5 / (24 * 60 * 60)))

        uc1 = UndoCommand(implementation=mocked_imp_succ, id_=1)
        uc2 = UndoCommand(implementation=mocked_imp_error, id_=2)
        uc3 = UndoCommand(implementation=mocked_imp_succ, id_=3)

        c1 = Command(implementation=mocked_imp_succ, undo_command=uc1, id_=1)
        c2 = Command(implementation=mocked_imp_succ, undo_command=uc2, id_=2)
        c3 = Command(implementation=mocked_imp_error, undo_command=uc3, id_=3)

        cc1 = CompositeCommand({c1: [c2], c2: [c3]}, force_all=True, id_=1, executor=ThreadPoolExecutor)

        res = cc1.invoke()

        self.assertEqual(2, mocked_imp_succ.execute.call_count)
        self.assertEqual(1, mocked_imp_error.execute.call_count)
        self.assertFalse(res)

        res = cc1.undo()

        self.assertEqual(3, mocked_imp_succ.execute.call_count)
        self.assertEqual(2, mocked_imp_error.execute.call_count)
        self.assertFalse(res)

    def test_undo_on_error(self):
        mocked_imp_succ = mock.Mock()
        mocked_imp_error = mock.Mock()

        mocked_imp_succ.execute.return_value = CompletedProcess(success=True, stdout='stdout', stderr='stderr', rc=0,
                                                                start_time=datetime.datetime.now(),
                                                                end_time=datetime.datetime.now() + datetime.timedelta(
                                                                    5 / (24 * 60 * 60)))

        mocked_imp_error.execute.return_value = CompletedProcess(success=False, stdout='stdout', stderr='stderr', rc=0,
                                                                 start_time=datetime.datetime.now(),
                                                                 end_time=datetime.datetime.now() + datetime.timedelta(
                                                                     5 / (24 * 60 * 60)))

        uc1 = UndoCommand(implementation=mocked_imp_succ, id_=1)
        uc2 = UndoCommand(implementation=mocked_imp_error, id_=2)
        uc3 = UndoCommand(implementation=mocked_imp_succ, id_=3)

        c1 = Command(implementation=mocked_imp_succ, undo_command=uc1, id_=1)
        c2 = Command(implementation=mocked_imp_succ, undo_command=uc2, id_=2)
        c3 = Command(implementation=mocked_imp_error, undo_command=uc3, undo_on_error=True, id_=3)

        cc1 = CompositeCommand({c1: [c2], c2: [c3]}, force_all=True, id_=1)

        res = cc1.invoke()
        self.assertEqual(2, mocked_imp_succ.execute.call_count)
        self.assertEqual(1, mocked_imp_error.execute.call_count)
        self.assertFalse(res)

        res = cc1.undo()

        self.assertEqual(4, mocked_imp_succ.execute.call_count)
        self.assertEqual(2, mocked_imp_error.execute.call_count)
        self.assertFalse(res)

    def test_composite_command_success(self):
        mocked_imp_succ = mock.Mock()
        mocked_imp_error = mock.Mock()

        start_time = datetime.datetime.now()
        end_time = datetime.datetime.now() + datetime.timedelta(5 / (24 * 60 * 60))

        mocked_imp_succ.execute.return_value = CompletedProcess(success=True, stdout='stdout', stderr='stderr', rc=0,
                                                                start_time=start_time,
                                                                end_time=end_time)
        mocked_imp_error.execute.return_value = CompletedProcess(success=False, stdout='stdout', stderr='stderr', rc=0,
                                                                 start_time=start_time,
                                                                 end_time=end_time)

        uc1 = UndoCommand(implementation=mocked_imp_succ, id_=1)
        uc2 = UndoCommand(implementation=mocked_imp_succ, id_=2)
        uc3 = UndoCommand(implementation=mocked_imp_succ, id_=3)
        uc4 = UndoCommand(implementation=mocked_imp_succ, id_=4)

        ccu1 = CompositeCommand({uc1: []})
        ccu2 = CompositeCommand({uc2: [uc3], uc3: [uc4]})

        c1 = Command(implementation=mocked_imp_succ, undo_command=ccu1, id_=5)
        c2 = Command(implementation=mocked_imp_succ, undo_command=ccu2, id_=6)

        cc = CompositeCommand({c1: [c2], c2: []})

        res = cc.invoke()

        self.assertDictEqual({5: CompletedProcess(success=True, stdout='stdout', stderr='stderr', rc=0,
                                                  start_time=start_time,
                                                  end_time=end_time),
                              6: CompletedProcess(success=True, stdout='stdout', stderr='stderr', rc=0,
                                                  start_time=start_time,
                                                  end_time=end_time)}
                             , cc.execution)
        self.assertEqual(True, res)
        self.assertEqual(2, mocked_imp_succ.execute.call_count)
        self.assertEqual(0, mocked_imp_error.execute.call_count)

    def test_composite_command_error(self):
        mocked_imp_succ = mock.Mock()
        mocked_imp_error = mock.Mock()

        start_time = datetime.datetime.now()
        end_time = datetime.datetime.now() + datetime.timedelta(5 / (24 * 60 * 60))

        mocked_imp_succ.execute.return_value = CompletedProcess(success=True, stdout='stdout', stderr='stderr', rc=0,
                                                                start_time=start_time,
                                                                end_time=end_time)
        mocked_imp_error.execute.return_value = CompletedProcess(success=False, stdout='stdout', stderr='stderr', rc=0,
                                                                 start_time=start_time,
                                                                 end_time=end_time)

        uc1 = UndoCommand(implementation=mocked_imp_succ, id_=1)
        uc2 = UndoCommand(implementation=mocked_imp_succ, id_=2)
        uc3 = UndoCommand(implementation=mocked_imp_succ, id_=3)
        uc4 = UndoCommand(implementation=mocked_imp_succ, id_=4)

        ccu1 = CompositeCommand({uc1: []})
        ccu2 = CompositeCommand({uc2: [uc3], uc3: [uc4]})

        c1 = Command(implementation=mocked_imp_succ, undo_command=ccu1, id_=5)
        c2 = Command(implementation=mocked_imp_error, undo_command=ccu2, id_=6)

        cc = CompositeCommand({c1: [c2], c2: []})

        res = cc.invoke()

        self.assertDictEqual({5: CompletedProcess(success=True, stdout='stdout', stderr='stderr', rc=0,
                                                  start_time=start_time,
                                                  end_time=end_time),
                              6: CompletedProcess(success=False, stdout='stdout', stderr='stderr', rc=0,
                                                  start_time=start_time,
                                                  end_time=end_time)}
                             , cc.execution)

        self.assertEqual(1, mocked_imp_succ.execute.call_count)
        self.assertEqual(1, mocked_imp_error.execute.call_count)
        self.assertEqual(False, res)

        res = cc.undo()

        self.assertDictEqual({5: CompletedProcess(success=True, stdout='stdout', stderr='stderr', rc=0,
                                                  start_time=start_time,
                                                  end_time=end_time),
                              6: CompletedProcess(success=False, stdout='stdout', stderr='stderr', rc=0,
                                                  start_time=start_time,
                                                  end_time=end_time),
                              1: CompletedProcess(success=True, stdout='stdout', stderr='stderr', rc=0,
                                                  start_time=start_time,
                                                  end_time=end_time)}
                             , cc.execution)

        self.assertEqual(True, res)
        self.assertEqual(2, mocked_imp_succ.execute.call_count)
        self.assertEqual(1, mocked_imp_error.execute.call_count)

    def test_composite_command_error2(self):
        mocked_imp_succ = mock.Mock()
        mocked_imp_error = mock.Mock()

        start_time = datetime.datetime.now()
        end_time = datetime.datetime.now() + datetime.timedelta(5 / (24 * 60 * 60))

        mocked_imp_succ.execute.return_value = CompletedProcess(success=True, stdout='stdout', stderr='stderr', rc=0,
                                                                start_time=start_time,
                                                                end_time=end_time)
        mocked_imp_error.execute.return_value = CompletedProcess(success=False, stdout='stdout', stderr='stderr', rc=0,
                                                                 start_time=start_time,
                                                                 end_time=end_time)

        uc1 = UndoCommand(implementation=mocked_imp_succ, id_=1)
        uc2 = UndoCommand(implementation=mocked_imp_succ, id_=2)
        uc3 = UndoCommand(implementation=mocked_imp_succ, id_=3)
        uc4 = UndoCommand(implementation=mocked_imp_succ, id_=4)
        uc5 = UndoCommand(implementation=mocked_imp_succ, id_=5)

        ccu1 = CompositeCommand({uc1: []})
        ccu2 = CompositeCommand({uc2: [uc3], uc3: [uc4]})

        c1 = Command(implementation=mocked_imp_succ, undo_command=ccu1, id_=6)
        c2 = Command(implementation=mocked_imp_error, undo_command=ccu2, id_=7)
        c3 = Command(implementation=mocked_imp_succ, undo_command=uc5, id_=8)

        cc = CompositeCommand({c1: [c2], c2: [c3]})

        res = cc.invoke()

        self.assertEqual(False, res)
        self.assertEqual(1, mocked_imp_succ.execute.call_count)
        self.assertEqual(1, mocked_imp_error.execute.call_count)

        res = cc.undo()

        self.assertEqual(True, res)
        self.assertEqual(2, mocked_imp_succ.execute.call_count)
        self.assertEqual(1, mocked_imp_error.execute.call_count)

    def test_composite_command_error3(self):
        mocked_imp_succ = mock.Mock()
        mocked_imp_error = mock.Mock()

        start_time = datetime.datetime.now()
        end_time = datetime.datetime.now() + datetime.timedelta(5 / (24 * 60 * 60))

        mocked_imp_succ.execute.return_value = CompletedProcess(success=True, stdout='stdout', stderr='stderr', rc=0,
                                                                start_time=start_time,
                                                                end_time=end_time)
        mocked_imp_error.execute.return_value = CompletedProcess(success=False, stdout='stdout', stderr='stderr', rc=0,
                                                                 start_time=start_time,
                                                                 end_time=end_time)

        uc1 = UndoCommand(implementation=mocked_imp_succ, id_=1)
        uc2 = UndoCommand(implementation=mocked_imp_succ, id_=2)
        uc3 = UndoCommand(implementation=mocked_imp_error, id_=3)
        uc4 = UndoCommand(implementation=mocked_imp_succ, id_=4)
        uc5 = UndoCommand(implementation=mocked_imp_succ, id_=5)

        executor = ThreadPoolExecutor()
        ccu1 = CompositeCommand({uc1: []})
        ccu2 = CompositeCommand({uc2: [uc3, uc4]}, executor=executor)

        c1 = Command(implementation=mocked_imp_succ, undo_command=ccu1, id_=6)
        c2 = Command(implementation=mocked_imp_succ, undo_command=ccu2, id_=7)
        c3 = Command(implementation=mocked_imp_succ, undo_command=uc5, id_=8)

        cc = CompositeCommand({c1: [c2], c2: [c3]}, executor=executor)

        res = cc.invoke()

        self.assertTrue(res)
        self.assertEqual(3, mocked_imp_succ.execute.call_count)
        self.assertEqual(0, mocked_imp_error.execute.call_count)

        res = cc.undo()

        self.assertFalse(res)
        self.assertEqual(6, mocked_imp_succ.execute.call_count)
        self.assertEqual(1, mocked_imp_error.execute.call_count)

        self.assertDictEqual({2: CompletedProcess(success=True, stdout='stdout', stderr='stderr', rc=0,
                                                  start_time=start_time,
                                                  end_time=end_time),
                              3: CompletedProcess(success=False, stdout='stdout', stderr='stderr', rc=0,
                                                  start_time=start_time,
                                                  end_time=end_time),
                              4: CompletedProcess(success=True, stdout='stdout', stderr='stderr', rc=0,
                                                  start_time=start_time,
                                                  end_time=end_time),
                              5: CompletedProcess(success=True, stdout='stdout', stderr='stderr', rc=0,
                                                  start_time=start_time,
                                                  end_time=end_time),
                              6: CompletedProcess(success=True, stdout='stdout', stderr='stderr', rc=0,
                                                  start_time=start_time,
                                                  end_time=end_time),
                              7: CompletedProcess(success=True, stdout='stdout', stderr='stderr', rc=0,
                                                  start_time=start_time,
                                                  end_time=end_time),
                              8: CompletedProcess(success=True, stdout='stdout', stderr='stderr', rc=0,
                                                  start_time=start_time,
                                                  end_time=end_time)
                              }
                             , cc.execution)
