import datetime
from unittest import TestCase, mock

from dm.use_cases.deployment import UndoCommand, Execution, NativeOperation, Command


class TestCommands(TestCase):

    def test_undo_command(self):
        with mock.patch.object(NativeOperation, 'execute') as mocked_imp:
            mocked_imp.execute.return_value = Execution(success=True, stdout='stdout', stderr='stderr', rc=0,
                                                        start_time=datetime.datetime.now(),
                                                        end_time=datetime.datetime.now() + datetime.timedelta(
                                                            5 / (24 * 60 * 60)))
            uc = UndoCommand(implementation=mocked_imp)
            uc.invoke()
            uc.invoke()
            self.assertTrue(uc.success)
            mocked_imp.execute.assert_called_once_with({})

            uc = UndoCommand(implementation=mocked_imp, params={})

            mocked_imp.execute.return_value = Execution(success=False, stdout='stdout', stderr='stderr',
                                                        rc=0,
                                                        start_time=datetime.datetime.now(),
                                                        end_time=datetime.datetime.now() + datetime.timedelta(
                                                            5 / (24 * 60 * 60)))
            self.assertFalse(uc.invoke())
            self.assertTrue(uc.undo())

    def test_do_command_success(self):
        mocked_undo_imp = mock.Mock()
        mocked_imp = mock.Mock()
        command = Command(implementation=mocked_imp, params={'timeout': 60}, undo_implementation=mocked_undo_imp)

        mocked_imp.execute.return_value = Execution(success=True, stdout='stdout', stderr='stderr', rc=0,
                                                    start_time=datetime.datetime.now(),
                                                    end_time=datetime.datetime.now() + datetime.timedelta(
                                                        5 / (24 * 60 * 60)))

        self.assertIsNone(command.success)
        m = command.invoke()
        self.assertIs(m, True)
        mocked_imp.execute.assert_called_once_with({'timeout': 60})

        p = mock.PropertyMock(side_effect=[None, True])
        type(mocked_undo_imp).success = p
        mocked_undo_imp.invoke.return_value = True

        m = command.undo()
        self.assertIs(True, m)

    def test_do_command_no_success(self):
        mocked_undo_imp = mock.Mock()
        mocked_imp = mock.Mock()
        command = Command(implementation=mocked_imp, undo_implementation=mocked_undo_imp)

        mocked_imp.execute.return_value = Execution(success=False, stdout='stdout', stderr='stderr', rc=0,
                                                    start_time=datetime.datetime.now(),
                                                    end_time=datetime.datetime.now() + datetime.timedelta(
                                                        5 / (24 * 60 * 60)))

        self.assertIsNone(command.success)
        m = command.invoke()
        self.assertIs(m, False)
        mocked_imp.execute.assert_called_once_with({})

        p = mock.PropertyMock(return_value=None)
        type(mocked_undo_imp).success = p

        m = command.undo()
        mocked_undo_imp.invoke.assert_not_called()
        self.assertIsNone(m)

    def test_do_command_success_with_error_undo(self):
        mocked_undo_imp = mock.Mock()
        mocked_imp = mock.Mock()
        command = Command(implementation=mocked_imp, params={'timeout': 60}, undo_implementation=mocked_undo_imp)

        mocked_imp.execute.return_value = Execution(success=True, stdout='stdout', stderr='stderr', rc=0,
                                                    start_time=datetime.datetime.now(),
                                                    end_time=datetime.datetime.now() + datetime.timedelta(
                                                        5 / (24 * 60 * 60)))

        self.assertIsNone(command.success)
        m = command.invoke()
        self.assertIs(m, True)
        mocked_imp.execute.assert_called_once_with({'timeout': 60})

        p = mock.PropertyMock(side_effect=[None, False])
        type(mocked_undo_imp).success = p
        mocked_undo_imp.invoke.return_value = False

        m = command.undo()
        self.assertIs(False, m)