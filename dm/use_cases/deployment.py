import re
import subprocess
import threading
import typing as t
from abc import ABC, abstractmethod
from datetime import datetime

from dataclasses import dataclass

from dm.utils.dag import DAG
from dm.utils.helpers import convert
from dm.utils.typos import Params


@dataclass
class Execution:
    success: bool = None
    stdout: str = None
    stderr: str = None
    rc: int = None
    start_time: datetime = None
    end_time: datetime = None


L_DELIMITER_VAR = '{'
R_DELIMITER_VAR = '}'


class IOperationEncapsulation(ABC):

    def __init__(self, code: str, expected_output: str = None, expected_rc: int = None, system_kwargs: Params = None):
        """
        Operation Initializer

        Parameters
        ----------
        code:
            Code to be executed
        expected_output:
            Expected output to compare from execution output. If None it won't be compared
        expected_rc:
            Expected return code to be compared with the execution return code. If None it won't be compared
        system_kwargs:
            system arguments to be passed to the commend execution, not the variables inside the code
        """
        self.code = code
        self.expected_output = expected_output
        self.expected_rc = expected_rc
        self.system_kwargs = system_kwargs or {}

    @abstractmethod
    def execute(self, params: Params) -> Execution:
        """
        Execution process
        Parameters
        ----------
        params:
            params to be passed through the execution

        Returns
        -------
        Execution:
            dataclass containing all the information from the result execution
        """


class TestOperation(IOperationEncapsulation):
    def execute(self, params: Params) -> Execution:
        return Execution(params.get('success', True), stdout=params.get('stdout', 'stdout'),
                         stderr=params.get('stderr', 'stderr'), rc=params.get('rc', 0),
                         start_time=params.get('start_time', datetime.now()),
                         end_time=params.get('end_time', datetime.now()))


class AnsibleOperation(IOperationEncapsulation):
    def execute(self, params: Params) -> Execution:
        _params = convert(params)
        tokens = self.code.split()
        result = Execution()

        for i in range(len(tokens)):
            if tokens[i][0:len(L_DELIMITER_VAR)] == L_DELIMITER_VAR and tokens[i][
                                                                        -len(R_DELIMITER_VAR):] == R_DELIMITER_VAR:
                try:
                    tokens[i] = eval('_params.' + str(tokens[i][len(L_DELIMITER_VAR):-len(R_DELIMITER_VAR)]))
                except KeyError:
                    raise LookupError(
                        f"Unable to find variable '{str(tokens[i][len(L_DELIMITER_VAR):-len(R_DELIMITER_VAR)])}'")

        result.start_time = datetime.now()
        system_kwargs = self.system_kwargs.copy()

        timeout = system_kwargs.pop('timeout', 600)

        tokens = ('ansible-playbook', '-i', '"localhost,"', '-c', 'local') + tuple(tokens)
        try:
            result.rc, result.stdout, result.stderr = subprocess.run(tokens, shell=True, capture_output=True,
                                                                     **system_kwargs, timeout=timeout)
        except (subprocess.TimeoutExpired, ValueError) as e:
            result.stderr = f"{e.__class__.__name__}{e.args}"
            result.success = False
        finally:
            result.end_time = datetime.now()

        if result.success is None:
            if self.expected_output is not None and self.expected_rc is not None:
                if re.search(self.expected_output, result.stdout) \
                        and result.rc == self.expected_rc:
                    result.success = True
            elif self.expected_output is not None:
                if re.search(self.expected_output, result.stdout):
                    result.success = True
            elif self.expected_rc is not None:
                if result.rc == self.expected_rc:
                    result.success = True
            else:
                result.success = True

        return result


class PythonOperation(IOperationEncapsulation):
    def execute(self, params: Params) -> Execution:
        pass


class NativeOperation(IOperationEncapsulation):

    def execute(self, params: Params) -> Execution:
        _params = convert(params)
        tokens = self.code.split()
        result = Execution()

        for i in range(len(tokens)):
            if tokens[i][0:len(L_DELIMITER_VAR)] == L_DELIMITER_VAR and tokens[i][
                                                                        -len(R_DELIMITER_VAR):] == R_DELIMITER_VAR:
                try:
                    tokens[i] = eval('_params.' + str(tokens[i][len(L_DELIMITER_VAR):-len(R_DELIMITER_VAR)]))
                except KeyError:
                    raise LookupError(
                        f"Unable to find variable '{str(tokens[i][len(L_DELIMITER_VAR):-len(R_DELIMITER_VAR)])}'")

        result.start_time = datetime.now()
        system_kwargs = self.system_kwargs.copy()

        timeout = system_kwargs.pop('timeout', 300)

        try:
            result.rc, result.stdout, result.stderr = subprocess.run(tokens, shell=True, capture_output=True,
                                                                     **system_kwargs, timeout=timeout)
        except (subprocess.TimeoutExpired, ValueError) as e:
            result.stderr = f"{e.__class__.__name__}{e.args}"
            result.success = False
        finally:
            result.end_time = datetime.now()

        if result.success is None:
            if self.expected_output is not None and self.expected_rc is not None:
                if re.search(self.expected_output, result.stdout) \
                        and result.rc == self.expected_rc:
                    result.success = True
            elif self.expected_output is not None:
                if re.search(self.expected_output, result.stdout):
                    result.success = True
            elif self.expected_rc is not None:
                if result.rc == self.expected_rc:
                    result.success = True
            else:
                result.success = True

        return result


class OrchestrationOperation(IOperationEncapsulation):

    def execute(self, params: Params) -> Execution:
        pass


class ICommand(ABC):

    def __init__(self, id_):
        self._id = id_ or id(self)

    @property
    @abstractmethod
    def success(self) -> bool:
        """
        Property that returns True if the command executed successfully
        Returns
        -------

        """

    @property
    def id(self) -> int:
        """
        Property that returns the ID of the command
        Returns
        -------

        """
        return self._id

    @property
    @abstractmethod
    def execution(self) -> t.Dict[int, Execution]:
        """
        Property to get all the executions

        Returns
        -------
        dict with all the executions
        """

    @abstractmethod
    def invoke(self) -> bool:
        """
        Implement the do process. If the process ends as expected it must set _success to true.

        Returns
        -------
        bool:
            True if the do process ends as expected. False otherwise
        """

    @abstractmethod
    def undo(self) -> t.Optional[bool]:
        """
        Method to implement the undo process. Executed only if success is true

        Returns
        -------
        bool:
            True if the undo process ends up OK. False otherwise
        """

    def __repr__(self):
        return f"{self.__class__.__name__}{self.id}"


class UndoCommand(ICommand):
    def __init__(self, implementation: IOperationEncapsulation, params: Params = None, id_=None):
        super().__init__(id_)
        self.params = params or {}
        self.implementation = implementation
        self._execution: Execution = None

    def invoke(self) -> bool:
        """
        Executes the code once

        Returns
        -------
        None
        """
        if not self._execution:
            self._execution = self.implementation.execute(self.params)
        return self.success

    @property
    def execution(self) -> t.Dict[int, Execution]:
        return {self.id: self._execution}

    @property
    def success(self) -> t.Optional[bool]:
        return getattr(self._execution, 'success', None)

    def undo(self) -> t.Optional[bool]:
        return True

    def __iter__(self):
        return [self]


class CompositeCommand(ICommand):

    def __init__(self, dict_tree: t.Dict[ICommand, t.List[ICommand]], undo_on_error: bool = False, force_all=False,
                 id_=None, async_operator=None):
        """

        Parameters
        ----------
        dict_tree:
            dict tree containing command nodes as keys and it's neighbours as a list of commands. See examples for more
            information
        undo_on_error:
            executes the undo process if the command ended up with error
        force_all:
            executes all the commands regardless if a command success or fails
        id_:
            command identifier
        async_operator: dm.utils.async_operator.AsyncOperator
            async operator that will execute the invokes in parallel
        """
        super().__init__(id_)
        self._dag = DAG().from_dict_of_lists(dict_tree)
        self.undo_on_error = undo_on_error
        self.force_all = force_all
        self.ao = async_operator

    @property
    def success(self) -> t.Optional[bool]:
        success_list = [n.success for n in self._dag]
        if success_list == [None] * len(success_list):
            return None
        elif success_list == [True] * len(success_list):
            return True
        else:
            return False

    def invoke(self) -> bool:
        res = []
        level = 1
        while level <= self._dag.depth and (all(res) is True or self.force_all is True):
            commands = self._dag.get_nodes_at_level(level)
            if len(commands) == 1:
                res.append(commands[0].invoke())
                if res[-1] is not True and self.force_all is False:
                    break
            else:
                task_ids = []
                for command in commands:
                    if self.ao:
                        t_id = self.ao.register(async_proc=command.invoke,
                                                callback=lambda data: res.append(data.returndata))
                        task_ids.append(t_id)
                    else:
                        res.append(command.invoke())
                        if res[-1] is not True and self.force_all is False:
                            break
                if self.ao and len(commands) > 1:
                    # TODO MEDIUM how to pass timeout and check for running processes health (in case communication with a remote server dies)
                    ended = self.ao.wait_tasks(task_ids)
                    if not ended:
                        # timeout reached
                        raise TimeoutError('Timeout reached while command execution')
                    if all(res) is not True and self.force_all is False:
                        break
            level += 1
        return all(res)

    def undo(self) -> t.Optional[bool]:
        """
        Executes undo operation

        Returns
        -------
        bool:
            True if all undo commands that run ended up succesfully
            False if any undo command ended up badly
            None if undo operation not executed
        """
        res = None
        level = self._dag.depth
        while level > 0 and res is not False:
            for command in self._dag.get_nodes_at_level(level):
                res = command.undo()
                if res is False and self.force_all is False:
                    break
            level -= 1
        return res

    @property
    def execution(self) -> t.Dict[int, Execution]:
        e = {}
        for n in self._dag.nodes:
            if n.success is not None:
                e.update(n.execution)
        return e

    def __len__(self):
        return len(self._dag)

    def __iter__(self):
        return self._dag


class Command(ICommand):

    def __init__(self, implementation: IOperationEncapsulation,
                 undo_implementation: t.Union[CompositeCommand, UndoCommand],
                 params: Params = None, undo_on_error: bool = False, id_=None):
        """
        
        Parameters
        ----------
        implementation:
            operation to perform.
        undo_implementation:
            undo operation to perform
        params
        undo_on_error
        """
        super().__init__(id_)
        self.implementation = implementation
        self.params = params or {}
        self.undo_implementation = undo_implementation
        self.undo_on_error = undo_on_error
        self._execution: t.Optional[Execution] = None

    @property
    def success(self) -> t.Optional[bool]:
        return getattr(self._execution, 'success', None)

    @property
    def execution(self) -> t.Dict[int, Execution]:
        e = {}
        e.update({self.id: self._execution})
        if self.undo_implementation.success is not None:
            e.update(self.undo_implementation.execution)
        return e

    def invoke(self) -> t.Optional[bool]:
        if not self._execution:
            self._execution = self.implementation.execute(self.params)
        return self.success

    def undo(self) -> t.Optional[bool]:
        """
        Executes undo operation

        Returns
        -------
        bool:
            True if all undo commands that run ended up succesfully
            False if any undo command ended up badly
            None if undo operation not executed
        """
        if (self.success is True or (
                self.success is False and self.undo_on_error)) and self.undo_implementation.success is None:
            return self.undo_implementation.invoke()
        else:
            return self.undo_implementation.success

    def __iter__(self):
        return [self]


class ProxyCommand(ICommand):

    def __init__(self, mediator, server, implementation, undo_implementation, params=None, undo_on_error=False,
                 id_=None, timeout=300):
        """
        Parameters
        ----------
        mediator: dm.use_cases.mediator.Mediator
            mediator to send commands
        server: Server
            server to execute the command
        implementation: IOperationEncapsulation
            operation to perform.
        undo_implementation: t.Union[CompositeCommand, UndoCommand]
            undo operation to perform
        params: Params
            params to pass to the execution
        undo_on_error: bool
            if the invoke ended up with an error, the undo process will be executed if undo_on_error is True
        id_: int
            command identifier
        timeout: int
            timeout when waiting response from remote server when invoke and undo executed
        """
        self._command = Command(implementation=implementation, undo_implementation=undo_implementation,
                                params=params, undo_on_error=undo_on_error, id_=id_)
        self._mediator = mediator
        self._server = server
        self._execution = {}
        self._completion_invoke_event = threading.Event()
        self._completion_undo_event = threading.Event()
        self._block = True
        self.timeout = timeout

    @property
    def success(self) -> t.Optional[bool]:
        return getattr(self._execution, 'success', None)

    @property
    def execution(self) -> t.Dict[int, Execution]:
        return self._execution

    def __getattr__(self, item):
        value = self.__dict__.get(item, None)
        if value is None:
            value = self._command.__dict__.get(item, None)
        return value

    def __setattr__(self, key, value):
        if key in self.__dict__:
            self.__dict__[key] = value
        else:
            self._command.__dict__[key] = value

    def _completion_invoke(self, data):
        """callback executed on response to the invoke command on remote server
        """
        self._command._execution = data['execution'][self._command.id]
        self._completion_invoke_event.set()

    def _completion_undo(self, data):
        """callback executed on response to the undo command on remote server
        """
        for uc in self._command.undo_implementation:
            uc._execution = data['execution'].get(uc.id)
        self._completion_undo_event.set()

    def invoke(self) -> bool:
        """
        invokes the command on the remote server

        Returns
        -------
        bool:
            True if command ended up gracefully. False otherwise

        Raises
        ------
        TimeoutError:
            raised when timeout reached while waiting the response back from the remote server
        """
        if self._command.success is None:
            callback = (self._completion_invoke, (), {})
            self._mediator.invoke_remote_cmd(command=self._command, destination=self._server, callback=callback)
            event = self._completion_invoke_event.wait(timeout=self.timeout)
            if event is not True:
                raise TimeoutError(f'Timeout reached while waiting invoke response of command {self.command}')

        return self.success

    def undo(self) -> bool:
        """
        Executes undo operation

        Returns
        -------
        bool:
            True if all undo commands that run ended up succesfully
            False if any undo command ended up badly
            None if undo operation not executed

        Raises
        ------
        TimeoutError:
            raised when timeout reached while waiting the response back from the remote server
        """
        if self._command.success is True or (
                self._command.success is False and self._command.undo_on_error):
            callback = (self._completion_undo, (), {})
            self._mediator.undo_remote_command(command=self._command, callback=callback)

            event = self._completion_undo_event.wait(timeout=self.timeout)
            if event is not True:
                raise TimeoutError(f'Timeout reached while waiting invoke response of command {self.command}')
        return self._command.undo_implementation.success

    def __iter__(self):
        return [self]
