import base64
import concurrent
import logging
import pickle
import re
import threading
import time
import typing as t
from abc import ABC, abstractmethod
from collections import ChainMap
from concurrent.futures.process import ProcessPoolExecutor
from datetime import datetime
from functools import partial

from flask import current_app

from dm import defaults
from dm.domain.entities import Server, Orchestration, Step, StepExecution, OrchExecution
from dm.use_cases.operations import CompletedProcess, IOperationEncapsulation, create_operation
from dm.utils.dag import DAG
from dm.utils.event_handler import Event
from dm.utils.typos import Kwargs, Id
from dm.web import db
from dm.web.network import post

# if t.TYPE_CHECKING:


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
    def result(self) -> t.Dict[Id, CompletedProcess]:
        """
        Property to get all the results

        Returns
        -------
        dict with all the results
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
        return f"{self.__class__.__name__} {self.id}"


class ImplementationCommand(ICommand):

    def __init__(self, implementation: IOperationEncapsulation,
                 params: Kwargs = None,
                 id_=None,
                 register: 'RegisterStepExecution' = None,
                 regexp_fetch=None,
                 error_on_fetch=None):
        super().__init__(id_)
        self.implementation = implementation
        self.params = params or {}
        self.regexp_fetch = regexp_fetch
        self.register = register
        self._fetched_data = None
        self.fetch_result = None
        self.error_on_fetch: bool = error_on_fetch
        self._cp: CompletedProcess = None

    def invoke(self, timeout=None) -> t.Optional[bool]:
        if not self._cp:
            self._cp = self.implementation.execute(self.params, timeout=timeout)
            self.params.update(self.fetched_data)
            if self.regexp_fetch is not None:
                self.fetch_result = len(self.fetched_data) == len(self.fetch_parameters)
            if self.register:
                self.register.register_step_execution(self)
        return self.success

    @property
    def result(self) -> t.Dict[Id, CompletedProcess]:
        return {self.id: self._cp}

    @property
    def success(self) -> t.Optional[bool]:
        r = getattr(self._cp, 'success', None)
        if r is True and self.error_on_fetch and self.fetch_result is not None:
            r = self.fetch_result
        return r

    @property
    def fetched_data(self):
        if self._fetched_data is not None:
            return self._fetched_data
        else:
            fetched = {}
            if self.success is True:
                if self.regexp_fetch is not None:
                    match = re.search(self.regexp_fetch, self._cp.stdout)
                    if not match:
                        match = re.search(self.regexp_fetch, self._cp.stderr)
                        if match:
                            fetched.update(match.groupdict())
                    else:
                        fetched.update(match.groupdict())
                self._fetched_data = fetched
            return fetched

    @property
    def fetch_parameters(self):
        return set(re.findall(r'\(\?P<(\w+)>', self.regexp_fetch, flags=re.MULTILINE))


class UndoCommand(ImplementationCommand):

    def __init__(self, implementation: IOperationEncapsulation, params: Kwargs = None, id_=None,
                 stop_on_error: bool = None,
                 register: 'RegisterStepExecution' = None,
                 regexp_fetch: str = None,
                 error_on_fetch: bool = None
                 ):
        super().__init__(implementation, params, id_, register, regexp_fetch, error_on_fetch)
        self.stop_on_error = stop_on_error

    def undo(self, timeout=None) -> t.Optional[bool]:
        return True

    def __iter__(self):
        return [self]


class Command(ImplementationCommand):

    def __init__(self, implementation: IOperationEncapsulation,
                 undo_command: t.Union['CompositeCommand', UndoCommand] = None,
                 stop_on_error: bool = None, stop_undo_on_error: bool = None, undo_on_error: bool = True,
                 params: Kwargs = None, id_=None, register: 'RegisterStepExecution' = None,
                 regexp_fetch: str = None, error_on_fetch: bool = None):
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
        super().__init__(implementation, params, id_, register, regexp_fetch, error_on_fetch)
        self.undo_command = undo_command
        self.stop_on_error = stop_on_error
        self.stop_undo_on_error = stop_undo_on_error
        self.undo_on_error = undo_on_error
        self._cp: t.Optional[CompletedProcess] = None


    @property
    def result(self) -> t.Dict[Id, CompletedProcess]:
        e = {}
        e.update({self.id: self._cp})
        if self.undo_command and self.undo_command.success is not None:
            e.update(self.undo_command.result)
        return e

    def undo(self, timeout=None) -> t.Optional[bool]:
        """
        Executes undo operation

        Returns
        -------
        bool:
            True if all undo commands that run ended up successfully
            False if any undo command ended up badly
            None if undo operation not executed
        """
        if self.undo_command:
            if (self.success is True or (
                    self.success is False and self.undo_on_error)) and self.undo_command.success is None:
                return self.undo_command.invoke(timeout=timeout)
            else:
                return self.undo_command.success
        else:
            return True

    def __iter__(self):
        return [self]


class CompositeCommand(ICommand):

    def __init__(self, dict_tree: t.Dict[ICommand, t.List[ICommand]],
                 stop_on_error: bool, stop_undo_on_error: bool = None,
                 id_=None, executor: concurrent.futures.Executor = None, timeout: t.Union[int, float] = None):
        """

        Parameters
        ----------
        dict_tree:
            dict tree containing command nodes as keys and it's neighbours as a list of commands. See examples for more
            information
        undo_on_error:
            executes the undo process even if the command ended up with error
        stop_on_error:
            executes all the commands regardless if a command succeed or fail
        stop_undo_on_error:
            executes all the undo commands regardless if an undo command succeed or fail
        id_:
            command identifier
        executor:
            async call executor. defaults to concurrent.futures.process.ProcessPoolExecutor
        """
        super().__init__(id_)
        self._dag = DAG().from_dict_of_lists(dict_tree)
        self.stop_on_error = stop_on_error
        self.stop_undo_on_error = stop_undo_on_error
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
        stop = False
        level = 1
        timeout = timeout or self.timeout
        start = time.time()
        while level <= self._dag.depth:
            commands = self._dag.get_nodes_at_level(level)
            duration = time.time() - start
            left = max(timeout - duration, 0) if timeout else None
            if len(commands) == 1:
                r = commands[0].invoke(timeout=left)
                res.append(r)
                stop_on_error = commands[0].stop_on_error if commands[0].stop_on_error is not None \
                    else self.stop_on_error
                if r is False and stop_on_error is True:
                    break
            else:
                futures = {}

                for command in commands:
                    futures.update(
                        {command.id: self.executor.submit(command.invoke, timeout=left)})

                stop = None
                while len(futures) > 0 and (left is None or (time.time() - start) < left) and stop is not True:
                    for cmd_id, future in dict(futures).items():
                        r = None
                        try:
                            r = future.result(timeout=0.5)
                        except concurrent.futures.TimeoutError:
                            pass
                        except Exception as e:
                            logger.exception(f"Error while executing step {cmd_id}")
                            del futures[cmd_id]
                            r = False
                        else:
                            del futures[cmd_id]
                        if r is not None:
                            res.append(r)
                            cmd = list(filter(lambda c: c.id == cmd_id, commands))[0]
                            stop_on_error = cmd.stop_on_error if cmd.stop_on_error is not None else self.stop_on_error
                            if r is False and stop_on_error is True:
                                stop = True

                    duration = time.time() - start
                    left = max(timeout - duration, 0) if timeout else None

                if stop is True or (timeout is not None and (time.time() - start) > timeout):
                    break
            level += 1
        return all(res) if len(res) > 0 else None

    def undo(self, timeout=None) -> t.Optional[bool]:
        """
        Executes undo operation

        Returns
        -------
        bool:
            True if all undo commands that run ended up successfully
            False if any undo command ended up badly
            None if undo operation not executed
        """
        if self.stop_undo_on_error is None:
            raise RuntimeError(f'stop_undo_on_error not set for command {self.id}')
        res = []
        level = self._dag.depth
        start = time.time()
        duration = time.time() - start
        left = max(timeout - duration, 0) if timeout else None
        while level > 0 and (left is None or (time.time() - start) < left):
            commands = self._dag.get_nodes_at_level(level)
            duration = time.time() - start
            left = max(timeout - duration, 0) if timeout else None
            if len(commands) == 1:
                r = commands[0].undo(timeout=left)
                if r is not None:
                    res.append(r)
                stop_undo_on_error = commands[0].stop_undo_on_error if commands[0].stop_undo_on_error is not None \
                    else self.stop_undo_on_error
                if r is False and stop_undo_on_error is True:
                    break
            else:
                futures = {}

                for command in commands:
                    futures.update(
                        {command.id: self.executor.submit(command.undo, timeout=left)})

                stop = None
                while len(futures) > 0 and (left is None or (time.time() - start) < left):
                    for cmd_id, future in dict(futures).items():
                        r = None
                        try:
                            r = future.result(timeout=0.5)
                        except concurrent.futures.TimeoutError:
                            pass
                        except Exception as e:
                            logger.exception(f"Error while executing step {cmd_id}")
                            del futures[cmd_id]
                            r = False
                        else:
                            del futures[cmd_id]
                        if r is not None:
                            res.append(r)
                            cmd = list(filter(lambda c: c.id == cmd_id, commands))[0]
                            stop_undo_on_error = cmd.stop_undo_on_error if cmd.stop_undo_on_error is not None \
                                else self.stop_undo_on_error
                            if r is False and cmd.stop_undo_on_error is True:
                                stop = True
                    duration = time.time() - start
                    left = max(timeout - duration, 0) if timeout else None

                if stop is True or (timeout is not None and (time.time() - start) > timeout):
                    break
            level -= 1
        return all(res) if len(res) > 0 else None

    @property
    def result(self) -> t.Dict[Id, CompletedProcess]:
        e = {}
        for n in self._dag.nodes:
            if n.success is not None:
                e.update(n.result)
        return e

    def __len__(self):
        return len(self._dag)

    def __iter__(self):
        return self._dag


class ProxyMixin(object):

    def __init__(self, server: Id, auth, timeout: t.Union[int, float] = 300):
        """
        Parameters
        ----------
        server:
            Server Id to execute the command
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
        self.__dict__['_server'] = server
        self.__dict__['_auth'] = auth
        self.__dict__['_completion_event'] = threading.Event()
        self.__dict__['timeout'] = timeout
        self.__dict__['_command'] = None

    #
    # proxying (special cases)
    #

    def __getattr__(self, item):
        return getattr(object.__getattribute__(self, "_command"), item)

    def __delattr__(self, name):
        delattr(object.__getattribute__(self, "_command"), name)

    def __setattr__(self, name, value):
        setattr(object.__getattribute__(self, "_command"), name, value)

    def __nonzero__(self):
        return bool(object.__getattribute__(self, "_command"))

    def __str__(self):
        return str(object.__getattribute__(self, "_command"))

    def __repr__(self):
        return repr(object.__getattribute__(self, "_command"))

    def __hash__(self):
        return hash(object.__getattribute__(self, "_command"))

    @property
    def server(self) -> 'Server':
        return self._server

    @property
    def auth(self):
        return self._auth

    # def __setattr__(self, key, value):
    #     if key in self.__dict__:
    #         self.__dict__[key] = value
    #     else:
    #         self._command.__setattr__(key, value)

    def callback_completion_event(self, event: Event):
        """callback executed on response to the invoke command on remote server
        """
        if 'success' in event.data:
            self._command._cp = CompletedProcess(success=event.data.get('success'),
                                                 stdout=event.data.get('stdout'),
                                                 stderr=event.data.get('stderr'),
                                                 rc=event.data.get('rc'),
                                                 start_time=datetime.strptime(event.data.get('start_time'),
                                                                              defaults.DATETIME_FORMAT),
                                                 end_time=datetime.strptime(event.data.get('end_time'),
                                                                            defaults.DATETIME_FORMAT))
        else:
            self._command._cp = CompletedProcess(success=False, stdout=str(event.data),
                                                 stderr=f'Unknown message got on completion event.')

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
        self.__dict__['_server'] = Server.query.get(self._server)
        timeout = timeout or self.timeout
        if self._command.success is None:
            data = dict(operation=base64.b64encode(
                pickle.dumps((self._command.implementation, self._command.params))).decode('ascii'),
                        timeout=timeout,
                        step_id=str(self.id[1]),
                        execution=self._command.register.execution.to_json())
            resp, code = post(server=self.server, view_or_url='api_1_0.launch_operation', json=data, auth=self.auth)
            if code == 202:
                current_app.events.register(resp.get('execution_id'), self.callback_completion_event)
                event = self._completion_event.wait(timeout=timeout)
                if event is not True:
                    raise TimeoutError(f'Timeout reached while waiting invoke response of command {self.command}')
                if self.register:
                    self.register.register_step_execution(self)
                self.params.update(self.fetched_data)
            elif code == 200:
                self.callback_completion_event(Event(None, data=resp))
            else:
                current_app.logger.error(
                    f"Error while trying to run command {self.id} on server {self.server}: {code}, {resp}")

        return self.success


class ProxyCommand(ProxyMixin, Command):

    def __init__(self, server: Id, auth, *args, timeout: t.Union[int, float] = 300, **kwargs):
        ProxyMixin.__init__(self, server, auth, timeout=timeout)
        object.__setattr__(self, "_command", Command(*args, **kwargs))


class ProxyUndoCommand(ProxyMixin, UndoCommand):

    def __init__(self, server: Id, auth, *args, timeout: t.Union[int, float] = 300, **kwargs):
        ProxyMixin.__init__(self, server, auth, timeout=timeout)
        object.__setattr__(self, "_command", UndoCommand(*args, **kwargs))


def _create_cmd_from_orchestration(orchestration: Orchestration, params: Kwargs) -> CompositeCommand:
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

        c = Command(create_operation(s), undo_command=CompositeCommand(cc_tree),
                    params=ChainMap(params, s.parameters), id_=s.id)

        step_cmd_map.update({s: c})

    return CompositeCommand(convert2cmd(tree_step, step_cmd_map))


# def _create_do_cc_from_step_server(orchestration, executor, params, hosts, s: Step, current_server):
#     d = {}
#     c = None
#     for t in s.target:
#         for server in hosts[t]:
#             if server == current_server:
#                 c = UndoCommand(create_operation(s), params=params, id_=s.id)
#                 d[c] = []
#             else:
#                 c = ProxyUndoCommand(server=server, implementation=create_operation(s), params=params,
#                                      id_=s.id)
#                 d[c] = []
#     if len(d) <= 1:
#         return c
#     else:
#         return CompositeCommand(dict_tree=d, executor=executor,
#                                 undo_on_error=orchestration.undo_on_error if s.undo_on_error is None else s.undo_on_error,
#                                 stop_on_error=orchestration.stop_on_error if s.stop_on_error is None else s.stop_on_error,
#                                 id_=s)


def _create_server_undo_command(executor, params, current_server, server: Id, s: Step, register, d=None,
                                s2cc=None, auth=None) -> t.Optional[t.Union[UndoCommand, CompositeCommand]]:
    def iterate_tree(_cls, _step: Step, _d, _s2cc):
        if _step in _s2cc:
            _uc = _s2cc[_step]
        else:
            stop_on_error = _step.step_stop_on_error if _step.step_stop_on_error is not None else s.stop_undo_on_error
            _uc = _cls(create_operation(_step), params=params, id_=(server, _step.id),
                       stop_on_error=stop_on_error, register=register)
            _s2cc[_step] = _uc
        if _uc not in _d:
            _d[_uc] = []
        for child_step in _step.children_undo_steps:
            _d[_uc].append(iterate_tree(_cls, child_step, _d, _s2cc))
        return _uc

    d = d or {}
    s2cc = s2cc or {}
    if server == current_server.id:
        u_cmd_cls = UndoCommand
    else:
        u_cmd_cls = partial(ProxyUndoCommand, server, auth)
    uc = None
    for child_undo_step in s.children_undo_steps:
        uc = iterate_tree(u_cmd_cls, child_undo_step, d, s2cc)
    if len(d) == 1:
        return uc
    elif len(d) > 1:
        return CompositeCommand(dict_tree=d, stop_on_error=s.stop_undo_on_error,
                                stop_undo_on_error=None,
                                id_=('undo', s.id),
                                executor=executor)


def create_cmd_from_orchestration2(orchestration: Orchestration, params: Kwargs,
                                   hosts: t.Dict[str, t.List[Id]],
                                   executor, register, auth=None) -> CompositeCommand:
    current_server = Server.get_current()

    def create_do_cmd_from_step(_step: Step, _s2cc):
        d = {}
        if _step in _s2cc:
            cc = _s2cc[_step]
        else:
            for target in _step.target:
                for server in hosts[target]:
                    if server == current_server.id:
                        cls = Command
                    else:
                        if auth is None:
                            RuntimeError('auth must be specified when executing orchestration to a remote server')
                        cls = partial(ProxyCommand, server, auth)

                    c = cls(create_operation(_step),
                            undo_command=_create_server_undo_command(executor, params, current_server, server, _step,
                                                                     register, auth=auth),
                            params=params,
                            stop_on_error=_step.stop_on_error,
                            stop_undo_on_error=None,
                            undo_on_error=_step.undo_on_error,
                            register=register,
                            id_=(server, _step.id))

                    d[c] = []
            if len(d) == 1:
                cc = c
            elif len(d) > 1:
                cc = CompositeCommand(dict_tree=d,
                                      stop_on_error=False,
                                      stop_undo_on_error=False,
                                      id_=_step.id, executor=executor)
            else:
                cc = None
        return cc

    def iterate_tree(_step: Step, _d, _s2cc):
        if _step in s2cc_map:
            _c = _s2cc[_step]
        else:
            _c = create_do_cmd_from_step(_step, _s2cc)
            _s2cc[_step] = _c
            if _c not in _d:
                _d[_c] = []
            for child_step in _step.children_do_steps:
                _d[_c].append(iterate_tree(child_step, _d, _s2cc))
        return _c

    root_steps = orchestration.root
    tree = {}
    s2cc_map = {}
    for step in root_steps:
        iterate_tree(step, tree, s2cc_map)

    return CompositeCommand(dict_tree=tree,
                            stop_undo_on_error=orchestration.stop_undo_on_error,
                            stop_on_error=orchestration.stop_on_error,
                            id_=orchestration.id, executor=executor)


class RegisterStepExecution:
    def __init__(self, execution: OrchExecution):
        self.execution = execution

    def register_step_execution(self, command: ImplementationCommand):
        e = StepExecution(orch_execution_id=self.execution.id)
        e.load_completed_result(command._cp)
        e.step_id = command.id[1]
        e.execution_server_id = command.id[0]
        e.source_server_id = command.id[0]
        db.session.add(e)
        db.session.commit()
