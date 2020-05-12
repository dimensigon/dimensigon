from datetime import datetime
from unittest import TestCase, mock

from dm.use_cases.deployment import UndoCommand, Command
from dm.use_cases.operations import CompletedProcess


class TestCommand(TestCase):

    def setUp(self) -> None:
        self.mock_implementation = mock.Mock()
        self.mock_undo_command = mock.Mock()

    def test_invoke(self):
        with mock.patch('dm.use_cases.deployment.Command.success', new_callable=mock.PropertyMock) as mock_success:
            mock_success.return_value = True

            c = Command(implementation=self.mock_implementation, undo_command=self.mock_undo_command,
                        params={'param': 'a'},
                        undo_on_error=False, id_=1)
            r = c.invoke()
            # call a second time to see if only one time is called
            r = c.invoke()
            self.mock_implementation.execute.assert_called_once_with({'param': 'a'}, timeout=None)
            self.assertTrue(r)

    def test_undo_command_succeed(self):
        with mock.patch('dm.use_cases.deployment.Command.success', new_callable=mock.PropertyMock) as mock_success:
            mock_success.return_value = True
            type(self.mock_undo_command).success = mock.PropertyMock(return_value=None)
            self.mock_undo_command.invoke.return_value = True

            c = Command(implementation=self.mock_implementation, undo_command=self.mock_undo_command,
                        params={'param': 'a'},
                        undo_on_error=False, id_=1)
            r = c.undo()
            self.mock_undo_command.invoke.assert_called_once()
            self.assertTrue(r)

    def test_undo_command_not_succeed(self):
        with mock.patch('dm.use_cases.deployment.Command.success', new_callable=mock.PropertyMock) as mock_success:
            mock_success.return_value = False
            type(self.mock_undo_command).success = mock.PropertyMock(return_value=None)
            self.mock_undo_command.invoke.return_value = True

            c = Command(implementation=self.mock_implementation, undo_command=self.mock_undo_command,
                        params={'param': 'a'},
                        undo_on_error=False, id_=1)
            r = c.undo()
            self.mock_undo_command.invoke.assert_not_called()
            self.assertIsNone(r)
            c.undo_on_error = True
            r = c.undo()
            self.mock_undo_command.invoke.assert_called_once()
            self.assertTrue(r)

    def test_undo_command_invoke_not_executed(self):
        with mock.patch('dm.use_cases.deployment.Command.success', new_callable=mock.PropertyMock) as mock_success:
            mock_success.return_value = None
            type(self.mock_undo_command).success = mock.PropertyMock(return_value=None)
            self.mock_undo_command.invoke.return_value = True

            c = Command(implementation=self.mock_implementation, undo_command=self.mock_undo_command,
                        params={'param': 'a'},
                        undo_on_error=False, id_=1)
            r = c.undo()
            self.mock_undo_command.invoke.assert_not_called()
            self.assertIsNone(r)

    def test_result(self):
        type(self.mock_undo_command).success = mock.PropertyMock(return_value=True)
        self.mock_undo_command.invoke.return_value = True
        self.mock_undo_command._id.return_value = 2
        type(self.mock_undo_command).result = mock.PropertyMock(return_value={2: {'a': 2}})

        c = Command(implementation=self.mock_implementation, undo_command=self.mock_undo_command,
                    params={'param': 'a'},
                    undo_on_error=False, id_=1)
        c._cp = {'success': True}
        self.assertDictEqual({1: {'success': True}, 2: {'a': 2}}, c.result)

    def test_fetch_result(self):
        self.mock_implementation.execute.return_value = CompletedProcess(success=True, stdout='output: var',
                                                                         stderr='',
                                                                         rc=0, start_time=datetime(2019, 4, 1))
        c = Command(implementation=self.mock_implementation, undo_command=self.mock_undo_command,
                    params={'param': 'a'},
                    undo_on_error=False, regexp_fetch=r'output: (?P<output>\w+)', error_on_fetch=True, id_=1)
        r = c.invoke()
        self.assertTrue(r)
        self.assertDictEqual({'output': 'var'}, c.data_fetched)
        self.assertDictEqual({'param': 'a', 'output': 'var'}, c.params)

        c = Command(implementation=self.mock_implementation, undo_command=self.mock_undo_command,
                    params={'param': 'a'},
                    undo_on_error=False, regexp_fetch=r'output2: (?P<output>\w+)', error_on_fetch=False, id_=1)
        r = c.invoke()
        self.assertTrue(r)

    def test_command_no_undo(self):
        cp = CompletedProcess(success=True, stdout='output: var',
                              stderr='',
                              rc=0, start_time=datetime(2019, 4, 1))
        self.mock_implementation.execute.return_value = cp
        c = Command(implementation=self.mock_implementation, params={'param': 'a'},
                    undo_on_error=False, regexp_fetch=r'output: (?P<output>\w+)', error_on_fetch=True, id_=1)

        r = c.invoke()
        self.assertTrue(r)
        r = c.undo()
        self.assertTrue(r)
        self.assertDictEqual({1: cp}, c.result)


class TestUndoCommand(TestCase):

    def setUp(self) -> None:
        self.mock_implementation = mock.Mock()

    def test_invoke(self):
        completed_process = mock.Mock()
        type(completed_process).success = mock.PropertyMock(return_value=True)
        self.mock_implementation.execute.return_value = completed_process
        uc = UndoCommand(implementation=self.mock_implementation, params={'param': 'a'}, id_=1)

        uc.invoke(timeout=10)
        r = uc.invoke()
        self.mock_implementation.execute.assert_called_once_with({'param': 'a'}, timeout=10)
        self.assertTrue(r)

    def test_undo(self):
        uc = UndoCommand(implementation=self.mock_implementation, params={'param': 'a'}, id_=1)

        r = uc.undo()
        self.assertTrue(r)

    def test_execution(self):
        uc = UndoCommand(implementation=self.mock_implementation, params={'param': 'a'}, id_=1)
        uc._cp = {'success': True}
        self.assertDictEqual({1: {'success': True}}, uc.result)
