import base64
import concurrent
import inspect
import logging
import pickle
import sys
import threading
import time
import typing as t
from abc import ABC, abstractmethod
from collections import ChainMap
from concurrent.futures.process import ProcessPoolExecutor

from flask import current_app

from dm.domain.entities import ActionType
from dm.domain.entities.orchestration import Step, Orchestration
from dm.use_cases.event_handler import Event
from dm.use_cases.operations import CompletedProcess, IOperationEncapsulation
from dm.utils.dag import DAG
from dm.utils.typos import Kwargs, Id
from dm.web.network import post

if t.TYPE_CHECKING:
    from dm.domain.entities import Server

logger = logging.getLogger('dm.deployment')


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
    def id(self) -> Id:
        """
        Property that returns the ID of the command
        Returns
        -------

        """
        return self._id

    @property
    @abstractmethod
    def execution(self) -> t.List[CompletedProcess]:
        """
        Property to get all the executions

        Returns
        -------
        dict with all the executions
        """

    @abstractmethod
    def invoke(self, timeout=None) -> bool:
        """
        Implement the do process. If the process ends as expected it must set _success to true.

        Returns
        -------
        bool:
            True if the do process ends as expected. False otherwise
        """

    @abstractmethod
    def undo(self, timeout=None) -> t.Optional[bool]:
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
    def __init__(self, implementation: IOperationEncapsulation, params: Kwargs = None, id_=None):
        super().__init__(id_)
        self.params = params or {}
        self.implementation = implementation
        self._cp: CompletedProcess = None

    def invoke(self, timeout=None) -> bool:
        """
        Executes the code once

        Returns
        -------
        None
        """
        if not self._cp:
            self._cp = self.implementation.execute(self.params, timeout=timeout)
        return self.success

    @property
    def execution(self) -> t.Dict[Id, CompletedProcess]:
        return {self.id: self._cp}

    @property
    def success(self) -> t.Optional[bool]:
        return getattr(self._cp, 'success', None)

    def undo(self, timeout=None) -> t.Optional[bool]:
        return True

    def __iter__(self):
        return [self]


class Command(ICommand):

    def __init__(self, implementation: IOperationEncapsulation,
                 undo_command: t.Union['CompositeCommand', UndoCommand],
                 params: Kwargs = None, undo_on_error: bool = False, id_=None):
        """
        
        Parameters
        ----------
        implementation:
            operation to perform.
        undo_command:
            undo command
        params:
            params used to execute the implementation
        undo_on_error:
            sets whether to execute "undo" function when "invoke" terminated incorrectly
        """
        super().__init__(id_)
        self.implementation = implementation
        self.params = params or {}
        self.undo_command = undo_command
        self.undo_on_error = undo_on_error
        self._cp: t.Optional[CompletedProcess] = None

    @property
    def success(self) -> t.Optional[bool]:
        return getattr(self._cp, 'success', None)

    @property
    def execution(self) -> t.Dict[Id, CompletedProcess]:
        e = {}
        e.update({self.id: self._cp})
        if self.undo_command.success is not None:
            e.update(self.undo_command.execution)
        return e

    def invoke(self, timeout=None) -> t.Optional[bool]:
        if not self._cp:
            self._cp = self.implementation.execute(self.params, timeout=timeout)
        return self.success

    def undo(self, timeout=None) -> t.Optional[bool]:
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
                self.success is False and self.undo_on_error)) and self.undo_command.success is None:
            return self.undo_command.invoke(timeout=timeout)
        else:
            return self.undo_command.success

    def __iter__(self):
        return [self]


class CompositeCommand(ICommand):

    def __init__(self, dict_tree: t.Dict[ICommand, t.List[ICommand]], undo_on_error: bool = False, force_all=False,
                 id_=None, executor: concurrent.futures.Executor = None, timeout: t.Union[int, float] = None):
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
        executor:
            async call executor. defaults to concurrent.futures.process.ProcessPoolExecutor
        """
        super().__init__(id_)
        self._dag = DAG().from_dict_of_lists(dict_tree)
        self.undo_on_error = undo_on_error
        self.force_all = force_all
        self.executor = executor or ProcessPoolExecutor(max_workers=4)
        self.timeout = timeout

    @property
    def success(self) -> t.Optional[bool]:
        success_list = [n.success for n in self._dag]
        if success_list == [None] * len(success_list):
            return None
        elif success_list == [True] * len(success_list):
            return True
        else:
            return False

    def invoke(self, timeout=None) -> bool:
        res = []
        level = 1
        timeout = timeout or self.timeout
        start = time.time()
        while level <= self._dag.depth and (all(res) is True or self.force_all is True):
            commands = self._dag.get_nodes_at_level(level)
            duration = time.time() - start
            left = max(timeout - duration, 0) if timeout else None
            if len(commands) == 1:
                res.append(commands[0].invoke(timeout=left))
                if res[-1] is False and self.force_all is False:
                    break
            else:
                futures = {}

                for command in commands:
                    futures.update(
                        {command.id: self.executor.submit(command.invoke, timeout=left)})

                while len(futures) > 0 and (left is None or (time.time() - start) < left):
                    for cmd_id, future in dict(futures).items():
                        try:
                            r = future.result(timeout=0.5)
                        except concurrent.futures.TimeoutError:
                            pass
                        except Exception as e:
                            logger.exception(f"Error while executing step {cmd_id}")
                            del futures[cmd_id]
                            res.append(False)
                        else:
                            del futures[cmd_id]
                            res.append(r)
                    duration = time.time() - start
                    left = max(timeout - duration, 0) if timeout else None

                if all(res) is not True and self.force_all is False or (time.time() - start) > self.timeout:
                    break
            level += 1
        return all(res)

    def undo(self, timeout=None) -> t.Optional[bool]:
        """
        Executes undo operation

        Returns
        -------
        bool:
            True if all undo commands that run ended up succesfully
            False if any undo command ended up badly
            None if undo operation not executed
        """
        res = []
        level = self._dag.depth
        start = time.time()
        duration = time.time() - start
        left = max(timeout - duration, 0) if timeout else None
        while level > 0 and res is not False and (left is None or (time.time() - start) < left):
            commands = self._dag.get_nodes_at_level(level)
            duration = time.time() - start
            left = max(timeout - duration, 0) if timeout else None
            if len(commands) == 1:
                res.append(commands[0].undo(timeout=left))
                # if undo not executed set as True to continue with the rest
                if res[-1] is None:
                    res[-1] = True
                if res[-1] is False and self.force_all is False:
                    break
            else:
                futures = {}

                for command in commands:
                    futures.update(
                        {command.id: self.executor.submit(command.undo, timeout=left)})

                while len(futures) > 0 and (left is None or (time.time() - start) < left):
                    for cmd_id, future in dict(futures).items():
                        try:
                            r = future.result(timeout=0.5)
                        except concurrent.futures.TimeoutError:
                            pass
                        except Exception as e:
                            logger.exception(f"Error while executing step {cmd_id}")
                            del futures[cmd_id]
                            res.append(False)
                        else:
                            del futures[cmd_id]
                            res.append(r)
                    duration = time.time() - start
                    left = max(timeout - duration, 0) if timeout else None

                if all(res) is not True and self.force_all is False or (time.time() - start) > self.timeout:
                    break
            level -= 1
        return all(res)

    @property
    def execution(self) -> t.Dict[Id, CompletedProcess]:
        e = {}
        for n in self._dag.nodes:
            if n.success is not None:
                e.update(n.execution)
        return e

    def __len__(self):
        return len(self._dag)

    def __iter__(self):
        return self._dag


class ProxyMixin(object):

    def __init__(self, server: 'Server', timeout: t.Union[int, float] = 300):
        """
        Parameters
        ----------
        server:
            server to execute the command
        implementation:
            operation to perform.
        undo_implementation:
            undo operation to perform
        params:
            params to pass to the execution
        undo_on_error:
            if the invoke ended up with an error, the undo process will be executed if undo_on_error is True
        id_:
            command identifier
        timeout:
            timeout when waiting response from remote server when invoke and undo executed
        """
        self._server = server
        self._completion_event = threading.Event()
        self.timeout = timeout
        self._command = None

    @property
    def server(self) -> 'Server':
        return self._server

    def __getattr__(self, item):
        return self._command.__dict__.get(item)

    def __setattr__(self, key, value):
        if key in self.__dict__:
            self.__dict__[key] = value
        else:
            self._command.__setattr__(key, value)

    def _completion_event(self, event: Event):
        """callback executed on response to the invoke command on remote server
        """
        self._command._execution = event.data
        self._completion_event.set()

    def invoke(self, timeout=None) -> bool:
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
            data = dict(command=base64.b64encode(pickle.dumps(self._command)).decode('ascii'))
            resp, code = post(server=self.server, view_or_url='api_1_0.launch_command', json=data)
            if code == 202:
                current_app.events.register(resp.get('execution_id'), self._completion_invoke)
                event = self._completion_invoke_event.wait(timeout=self.timeout)
                if event is not True:
                    raise TimeoutError(f'Timeout reached while waiting invoke response of command {self.command}')
            else:
                current_app.logger.error(
                    f"Error while trying to run command {self.id} on {self.server}: {code}, {resp}")

        return self.success


class ProxyCommand(ProxyMixin, Command):

    def __init__(self, server: 'Server', *args, timeout: t.Union[int, float] = 300, **kwargs):
        super().__init__(server, timeout=timeout)
        self._command = Command(*args, **kwargs)


class ProxyUndoCommand(ProxyMixin, UndoCommand):

    def __init__(self, server: 'Server', *args, timeout: t.Union[int, float] = 300, **kwargs):
        super().__init__(server, timeout=timeout)
        self._command = UndoCommand(*args, **kwargs)


_operation_classes = {}
for name, cls in inspect.getmembers(sys.modules['dm.use_cases.operations'],
                                    lambda x: (inspect.isclass(x) and issubclass(x, IOperationEncapsulation))):
    _operation_classes.update({name: cls})

_factories: t.Dict[ActionType, t.Type[IOperationEncapsulation]] = {}

for at in ActionType:
    try:
        _factories.update({at: _operation_classes[at.name.capitalize() + 'Operation']})
    except KeyError:
        NotImplementedError(f"{at.name.capitalize() + 'Operation'} not implemented")


def create_operation(step: Step) -> IOperationEncapsulation:
    cls = _factories[step.type]

    return cls(code=step.code, expected_output=step.expected_output, expected_rc=step.expected_rc,
               system_kwargs=step.system_kwargs)


def create_cmd_from_orchestration(orchestration: Orchestration, params: Kwargs) -> CompositeCommand:
    def convert2cmd(d, mapping):
        nd = {}
        for k, v in d.items():
            nd.update({mapping[k]: [mapping[s] for s in v]})
        return nd

    undo_step_cmd_map = {s: UndoCommand(implementation=create_operation(s), params=ChainMap(params, s.parameters),
                                        id_=s.id)
                         for s in orchestration.steps if s.undo}
    step_cmd_map = {}
    tree_step = {}

    for s in (s for s in orchestration.steps if not s.undo):
        tree_step.update({s: [s for s in orchestration.children[s] if not s.undo]})

        # create Undo CompositeCommand for every command
        cc_tree = convert2cmd(orchestration.subtree([s for s in orchestration.children[s] if s.undo]),
                              undo_step_cmd_map)

        c = Command(create_operation(s), undo_implementation=CompositeCommand(cc_tree),
                    params=ChainMap(params, s.parameters), id_=s.id)

        step_cmd_map.update({s: c})

    return CompositeCommand(convert2cmd(tree_step, step_cmd_map))


def deploy_orchestration(orchestration: Orchestration, params: Kwargs) -> \
        t.Tuple[bool, bool, t.Dict[Id, CompletedProcess]]:
    """
    Parameters
    ----------
    orchestration
        orchestration to deploy
    params
        parameters to pass to the steps

    Returns
    -------
    t.Tuple[bool, bool, t.Dict[int, dpl.CompletedProcess]]:
        tuple with 3 values. (boolean indicating if invoke process ended up successfully,
        boolean indicating if undo process ended up successfully,
        dict with all the executions). If undo process not executed, boolean set to None
    """
    cc = create_cmd_from_orchestration(orchestration, params)

    res_do, res_undo = None, None
    res_do = cc.invoke()
    if not res_do:
        res_undo = cc.undo()

    return res_do, res_undo, cc.execution
