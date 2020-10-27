from datetime import datetime
from unittest import TestCase, mock

from dimensigon.use_cases.deployment import UndoCommand, Command
from dimensigon.use_cases.operations import CompletedProcess


class TestCommand(TestCase):

    def setUp(self) -> None:
        self.mock_implementation = mock.Mock()
        self.mock_undo_command = mock.Mock()
        self.mock_parameters = mock.Mock()

    def test_invoke(self):
        with mock.patch('dimensigon.use_cases.deployment.Command.success', new_callable=mock.PropertyMock) as mock_success:
            mock_success.return_value = True

            c = Command(implementation=self.mock_implementation, undo_command=self.mock_undo_command,
                        var_context=self.mock_parameters,
                        undo_on_error=False, id_=1)
            r = c.invoke()
            # call a second time to see if only one time is called
            r = c.invoke()
            self.mock_implementation.execute.assert_called_once_with(self.mock_parameters, timeout=None)
            self.assertTrue(r)

    def test_undo_command_succeed(self):
        with mock.patch('dimensigon.use_cases.deployment.Command.success', new_callable=mock.PropertyMock) as mock_success:
            mock_success.return_value = True
            type(self.mock_undo_command).success = mock.PropertyMock(return_value=None)
            self.mock_undo_command.invoke.return_value = True

            c = Command(implementation=self.mock_implementation, undo_command=self.mock_undo_command,
                        var_context=self.mock_parameters,
                        undo_on_error=False, id_=1)
            r = c.undo()
            self.mock_undo_command.invoke.assert_called_once()
            self.assertTrue(r)

    def test_undo_command_not_succeed(self):
        with mock.patch('dimensigon.use_cases.deployment.Command.success', new_callable=mock.PropertyMock) as mock_success:
            mock_success.return_value = False
            type(self.mock_undo_command).success = mock.PropertyMock(return_value=None)
            self.mock_undo_command.invoke.return_value = True

            c = Command(implementation=self.mock_implementation, undo_command=self.mock_undo_command,
                        var_context=self.mock_parameters,
                        undo_on_error=False, id_=1)
            r = c.undo()
            self.mock_undo_command.invoke.assert_not_called()
            self.assertIsNone(r)
            c.undo_on_error = True
            r = c.undo()
            self.mock_undo_command.invoke.assert_called_once()
            self.assertTrue(r)

    def test_undo_command_invoke_not_executed(self):
        with mock.patch('dimensigon.use_cases.deployment.Command.success', new_callable=mock.PropertyMock) as mock_success:
            mock_success.return_value = None
            type(self.mock_undo_command).success = mock.PropertyMock(return_value=None)
            self.mock_undo_command.invoke.return_value = True

            c = Command(implementation=self.mock_implementation, undo_command=self.mock_undo_command,
                        var_context=self.mock_parameters,
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
                    var_context=self.mock_parameters,
                    undo_on_error=False, id_=1)
        c._cp = {'success': True}
        self.assertDictEqual({1: {'success': True}, 2: {'a': 2}}, c.result)

    def test_fetch_result(self):
        self.mock_implementation.execute.return_value = CompletedProcess(success=True, stdout='output: var',
                                                                         stderr='',
                                                                         rc=0, start_time=datetime(2019, 4, 1))
        c = Command(implementation=self.mock_implementation, undo_command=self.mock_undo_command,
                    var_context=self.mock_parameters,
                    undo_on_error=False, post_process=r'output: (?P<output>\w+)', id_=1)
        r = c.invoke()
        self.assertTrue(r)
        self.mock_parameters.set.assert_called_once_with('output', 'var')

        self.mock_parameters.reset_mock()
        c = Command(implementation=self.mock_implementation, undo_command=self.mock_undo_command,
                    var_context=self.mock_parameters,
                    undo_on_error=False, post_process=r'output2: (?P<output>\w+)', id_=1)
        r = c.invoke()
        self.assertTrue(r)
        self.mock_parameters.set.assert_not_called()

        self.mock_implementation.execute.return_value = CompletedProcess(success=True, stdout='',
                                                                         stderr='output: var',
                                                                         rc=0, start_time=datetime(2019, 4, 1))
        self.mock_parameters.reset_mock()
        c = Command(implementation=self.mock_implementation, undo_command=self.mock_undo_command,
                    var_context=self.mock_parameters,
                    undo_on_error=False, post_process=r'output: (?P<output>\w+)', id_=1)
        r = c.invoke()
        self.assertTrue(r)
        self.mock_parameters.set.assert_called_with('output', 'var')

    def test_command_no_undo(self):
        cp = CompletedProcess(success=True, stdout='output: var',
                              stderr='',
                              rc=0, start_time=datetime(2019, 4, 1))
        self.mock_implementation.execute.return_value = cp
        c = Command(implementation=self.mock_implementation, var_context={'param': 'a'},
                    undo_on_error=False, id_=1)

        r = c.invoke()
        self.assertTrue(r)
        r = c.undo()
        self.assertTrue(r)
        self.assertDictEqual({1: cp}, c.result)

    def test_command_post_process(self):
        cp = CompletedProcess(success=True, stdout='{"output": "this is a message"}',
                              stderr='',
                              rc=0, start_time=datetime(2019, 4, 1))
        self.mock_implementation.execute.return_value = cp
        c = Command(implementation=self.mock_implementation, var_context=self.mock_parameters,
                    undo_on_error=False, post_process="vc.set('response', json.loads(cp.stdout))", id_=1)

        c.invoke()
        self.mock_parameters.set.assert_called_once_with('response', {"output": "this is a message"})

        c = Command(implementation=self.mock_implementation, var_context=self.mock_parameters,
                    undo_on_error=False, post_process="raise RuntimeError()", id_=1)

        c.invoke()
        self.assertIsInstance(cp.pre_post_error, RuntimeError)
        self.assertFalse(cp.success)

    def test_command_register(self):
        cp = CompletedProcess(success=True, stdout='{"output": "this is a message"}',
                              stderr='',
                              rc=0, start_time=datetime(2019, 4, 1))
        self.mock_implementation.execute.return_value = cp
        mock_register = mock.Mock()
        c = Command(implementation=self.mock_implementation, var_context=self.mock_parameters, register=mock_register,
                    undo_on_error=False, post_process="", id_=1)

        c.invoke()

        mock_register.register_step_execution.assert_called_once_with(c)


class TestUndoCommand(TestCase):

    def setUp(self) -> None:
        self.mock_implementation = mock.Mock()

    def test_invoke(self):
        completed_process = mock.Mock()
        type(completed_process).success = mock.PropertyMock(return_value=True)
        self.mock_implementation.execute.return_value = completed_process
        uc = UndoCommand(implementation=self.mock_implementation, var_context={'param': 'a'}, id_=1)

        uc.invoke(timeout=10)
        r = uc.invoke()
        self.mock_implementation.execute.assert_called_once_with({'param': 'a'}, timeout=10)
        self.assertTrue(r)

    def test_undo(self):
        uc = UndoCommand(implementation=self.mock_implementation, var_context={'param': 'a'}, id_=1)

        r = uc.undo()
        self.assertTrue(r)

    def test_execution(self):
        uc = UndoCommand(implementation=self.mock_implementation, var_context={'param': 'a'}, id_=1)
        uc._cp = {'success': True}
        self.assertDictEqual({1: {'success': True}}, uc.result)


