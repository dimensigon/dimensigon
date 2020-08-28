import base64
import concurrent
import datetime
import json
import logging
import pickle
import re
import threading
import time
import typing as t
import uuid
from abc import ABC, abstractmethod
from collections import ChainMap
from concurrent.futures.process import ProcessPoolExecutor
from contextlib import contextmanager
from functools import partial

from RestrictedPython import compile_restricted, safe_builtins
from flask import current_app, Flask, has_app_context
from flask_jwt_extended import create_access_token
from sqlalchemy.orm import sessionmaker

from dimensigon import defaults
from dimensigon.domain.entities import Server, Orchestration, Step, StepExecution, OrchExecution
from dimensigon.network.auth import HTTPBearerAuth
from dimensigon.use_cases.operations import CompletedProcess, IOperationEncapsulation, create_operation
from dimensigon.utils.dag import DAG
from dimensigon.utils.event_handler import Event
from dimensigon.utils.helpers import get_now
from dimensigon.utils.typos import Id
from dimensigon.utils.var_context import VarContext
from dimensigon.web import db
from dimensigon.web.network import post

# if t.TYPE_CHECKING:


logger = logging.getLogger('dimensigon.deployment')


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
                 var_context: VarContext = None,
                 id_=None,
                 register: 'RegisterStepExecution' = None,
                 pre_process=None,
                 post_process=None,
                 ):
        super().__init__(id_)
        self.implementation = implementation
        self.var_context = var_context or {}
        self.register = register
        self.step_execution_id = None
        self.pre_post_error = None
        self.pre_process = pre_process
        self.post_process = post_process
        self._cp: CompletedProcess = None

    def invoke(self, timeout=None) -> t.Optional[bool]:
        elapsed_times = {}
        if not self._cp:
            params = None
            if self.register:
                self.step_execution_id = self.register.create_step_execution(self)
                self.var_context.globals.update(step_execution_id=self.step_execution_id)

            try:
                elapsed_times['pre_process_time'] = self.pre_processing(local=dict(vc=self.var_context, cp=self._cp))
            except Exception as e:
                self._cp = CompletedProcess(success=False, stderr=f"Pre-Process error: {e}")

            if not self._cp:
                try:
                    params = dict(self.var_context)
                except Exception as e:
                    self._cp = CompletedProcess(success=False, stderr=f"Variable Resolution error: {e}")

            if not self._cp:
                start = time.time()
                try:
                    self._cp = self.implementation.execute(self.var_context, timeout=timeout)
                except Exception as e:
                    self._cp = CompletedProcess(success=False, stderr=f"Execution error: {e}")
                    logger.exception(f"Exception on execution {self.id}")
                else:
                    try:
                        elapsed_times['post_process_time'] = self.post_processing(
                            local=dict(vc=self.var_context, cp=self._cp))
                    except Exception as e:
                        self._cp.success = False
                        self._cp.stderr = f"{self._cp.stderr}\nPost-Process error: {e}"

            if self.register:
                self.register.register_step_execution(self, params=params, **elapsed_times)

        return self.success

    @property
    def result(self) -> t.Dict[Id, CompletedProcess]:
        return {self.id: self._cp}

    @property
    def success(self) -> t.Optional[bool]:
        return getattr(self._cp, 'success', None)

    def pre_processing(self, local: dict = None):
        local = local or dict()
        if self.pre_process:
            start = time.time()

            byte_code = compile_restricted(self.pre_process, '<inline>', 'exec')
            safe_builtins.update(json=json)
            exec(byte_code, {'__builtins__': safe_builtins, '_write_': lambda x: x}, local)

            return time.time() - start
        else:
            return None

    def post_processing(self, local: dict = None):
        local = local or dict()
        if self.post_process:
            start = time.time()

            byte_code = compile_restricted(self.post_process, '<inline>', 'exec')
            safe_builtins.update(json=json, re=re)
            exec(byte_code, {'__builtins__': safe_builtins, '_write_': lambda x: x}, local)

            return time.time() - start
        else:
            return None

class UndoCommand(ImplementationCommand):

    def __init__(self, *args, stop_on_error: bool = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.stop_on_error = stop_on_error

    def undo(self, timeout=None) -> t.Optional[bool]:
        return True

    def __iter__(self):
        return [self]


class Command(ImplementationCommand):

    def __init__(self, *args,
                 undo_command: t.Union['CompositeCommand', UndoCommand] = None,
                 stop_on_error: bool = None, stop_undo_on_error: bool = None, undo_on_error: bool = True, **kwargs
                 ):
        """
        
        Parameters
        ----------
        implementation:
            operation to perform.
        undo_command:
            undo command
        var_context:
            var_context used to execute the implementation
        undo_on_error:
            sets whether to execute "undo" function when "invoke" terminated incorrectly
        """
        super().__init__(*args, **kwargs)
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

    def __init__(self, server: Id, timeout: t.Union[int, float] = 30):
        """
        Parameters
        ----------
        server:
            Server Id to execute the command
        implementation:
            operation to perform.
        undo_implementation:
            undo operation to perform
        var_context:
            var_context to pass to the execution
        undo_on_error:
            if the invoke ended up with an error, the undo process will be executed if undo_on_error is True
        id_:
            command identifier
        timeout:
            timeout when waiting response from remote server when invoke and undo executed
        """
        self.__dict__['_server'] = server
        self.__dict__['_app'] = current_app._get_current_object()
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

    def callback_completion_event(self, event: Event):
        """callback executed on response to the invoke command on remote server
        """
        if 'step_execution' in event.data:
            step_exec_json = event.data.get('step_execution')
            self._command._cp = CompletedProcess(success=step_exec_json.get('success'),
                                                 stdout=step_exec_json.get('stdout'),
                                                 stderr=step_exec_json.get('stderr'),
                                                 rc=step_exec_json.get('rc'),
                                                 start_time=datetime.datetime.strptime(step_exec_json.get('start_time'),
                                                                                       defaults.DATETIME_FORMAT) if step_exec_json.get(
                                                     'start_time') else None,
                                                 end_time=datetime.datetime.strptime(step_exec_json.get('end_time'),
                                                                                     defaults.DATETIME_FORMAT) if step_exec_json.get(
                                                     'end_time') else None)
            var_context = pickle.loads(base64.b64decode(event.data['var_context'].encode()))
            self._command.var_context.update_variables(var_context.extract_variables())
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
        ctx = None
        if not has_app_context():
            ctx = self._app.app_context()
            ctx.push()
        try:
            auth = HTTPBearerAuth(
                create_access_token(self._command.var_context.globals['executor_id'], datetime.timedelta(seconds=15)))
            self.__dict__['_server'] = Server.query.get(self._server)
            timeout = timeout or self.timeout

            if self._cp is None:
                elapsed_times = {}
                params = None
                if self.register:
                    self._command.step_execution_id = self.register.create_step_execution(self)
                    self._command.var_context.globals.update(step_execution_id=self._command.step_execution_id)

                try:
                    elapsed_times['pre_process_time'] = self.pre_processing(
                        local=dict(vc=self.var_context, cp=self._cp))
                except Exception as e:
                    self._cp = CompletedProcess(success=False, stderr=f"Pre-Process error: {e}")

                if not self._cp:
                    try:
                        params = self.var_context.extract_variables()
                    except Exception as e:
                        self._cp = CompletedProcess(success=False, stderr=f"Variable Resolution error: {e}")

                if not self._cp:
                    start = time.time()
                    data = dict(operation=base64.b64encode(pickle.dumps(self._command.implementation)).decode('ascii'),
                                var_context=base64.b64encode(pickle.dumps(self._command.var_context)).decode('ascii'),
                                timeout=timeout,
                                step_id=str(self.id[1]),
                                orch_execution=self._command.register.json_orch_execution,
                                event_id=str(uuid.uuid4()))
                    resp = post(server=self.server, view_or_url='api_1_0.launch_operation', json=data, auth=auth,
                                timeout=timeout)
                    if resp.code == 204:
                        current_app.events.register(data['event_id'], self.callback_completion_event)
                        event = self._completion_event.wait(timeout=timeout - (time.time() - start))
                        if event is not True:
                            self._command._cp = CompletedProcess(success=False, stdout='',
                                                                 stderr=f'Timeout of {timeout} reached waiting '
                                                                        f'server operation completion')

                    elif resp.code == 200:
                        self.callback_completion_event(Event(None, data=resp.msg))
                    elif resp.code:
                        if isinstance(resp.msg, dict):
                            msg = json.dumps(resp.msg)
                        else:
                            msg = str(resp.msg)

                        self._command._cp = CompletedProcess(success=False, stdout='',
                                                             stderr=msg, rc=resp.code)
                    elapsed_times['execution_time'] = time.time() - start
                try:
                    elapsed_times['post_process_time'] = self.post_processing(
                        local=dict(vc=self.var_context, cp=self._cp))
                except Exception as e:
                    self._cp.success = False
                    self._cp.stderr = f"{self._cp.stderr}\nPost-Process error: {e}"

                if self.register:
                    self.register.register_step_execution(self, params=params, **elapsed_times)
        finally:
            if ctx:
                ctx.pop()
        return self.success


class ProxyCommand(ProxyMixin, Command):

    def __init__(self, server_id: Id, *args, timeout: t.Union[int, float] = 300, **kwargs):
        ProxyMixin.__init__(self, server_id, timeout=timeout)
        object.__setattr__(self, "_command", Command(*args, **kwargs))


class ProxyUndoCommand(ProxyMixin, UndoCommand):

    def __init__(self, server_id: Id, *args, timeout: t.Union[int, float] = 300, **kwargs):
        ProxyMixin.__init__(self, server_id, timeout=timeout)
        object.__setattr__(self, "_command", UndoCommand(*args, **kwargs))


def _create_server_undo_command(executor, var_context, current_server, server_id: Id, s: Step, register, d=None,
                                s2cc=None) -> t.Optional[t.Union[UndoCommand, CompositeCommand]]:
    def iterate_tree(_cls, _step: Step, _d, _s2cc):
        if _step in _s2cc:
            _uc = _s2cc[_step]
        else:
            stop_on_error = _step.step_stop_on_error if _step.step_stop_on_error is not None else s.stop_undo_on_error
            _uc = _cls(create_operation(_step),
                       var_context=var_context.create_new_ctx(
                           defaults=ChainMap({**_step.parameters, 'server_id': server_id},
                                             _step.orchestration.parameters)),
                       id_=(str(server_id), str(_step.id)),
                       pre_process=_step.pre_process,
                       post_process=_step.post_process,
                       stop_on_error=stop_on_error, register=register)
            _s2cc[_step] = _uc
        if _uc not in _d:
            _d[_uc] = []
        for child_step in _step.children_undo_steps:
            _d[_uc].append(iterate_tree(_cls, child_step, _d, _s2cc))
        return _uc

    d = d or {}
    s2cc = s2cc or {}
    if str(server_id) == str(current_server.id):
        u_cmd_cls = UndoCommand
    else:
        u_cmd_cls = partial(ProxyUndoCommand, server_id)
    uc = None
    for child_undo_step in s.children_undo_steps:
        uc = iterate_tree(u_cmd_cls, child_undo_step, d, s2cc)
    if len(d) == 1:
        return uc
    elif len(d) > 1:
        return CompositeCommand(dict_tree=d, stop_on_error=s.stop_undo_on_error,
                                stop_undo_on_error=None,
                                id_=('undo', str(s.id)),
                                executor=executor)


def create_cmd_from_orchestration(orchestration: Orchestration, var_context: VarContext,
                                  hosts: t.Dict[str, t.List[Id]],
                                  executor: concurrent.futures.Executor,
                                  register: 'RegisterStepExecution') -> CompositeCommand:
    current_server = Server.get_current()

    def create_do_cmd_from_step(_step: Step, _s2cc):
        d = {}
        if _step in _s2cc:
            cc = _s2cc[_step]
        else:
            for target in _step.target:
                for server_id in hosts[target]:
                    if str(server_id) == str(current_server.id):
                        cls = Command
                    else:
                        cls = partial(ProxyCommand, server_id)

                    c = cls(create_operation(_step),
                            undo_command=_create_server_undo_command(executor, var_context, current_server, server_id,
                                                                     _step, register),
                            var_context=var_context.create_new_ctx(
                                defaults=ChainMap({**_step.parameters, 'server_id': server_id},
                                                  _step.orchestration.parameters)),
                            stop_on_error=_step.stop_on_error,
                            stop_undo_on_error=None,
                            undo_on_error=_step.undo_on_error,
                            pre_process=_step.pre_process,
                            post_process=_step.post_process,
                            register=register,
                            id_=(str(server_id), str(_step.id)))

                    d[c] = []
            if len(d) == 1:
                cc = c
            elif len(d) > 1:
                cc = CompositeCommand(dict_tree=d,
                                      stop_on_error=False,
                                      stop_undo_on_error=False,
                                      id_=str(_step.id), executor=executor)
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
                            id_=str(orchestration.id), executor=executor)


ORCH_EXEC_PATTERN = re.compile(r"^orch_execution_id=([a-zA-Z0-9-]{36})$")


class RegisterStepExecution:
    def __init__(self, orch_execution: OrchExecution, app: Flask = None):
        if app:
            self.app = app
        else:
            self.app = current_app._get_current_object()

        self.data = threading.local()
        self._json_orch_execution = orch_execution.to_json() # orch_execution property is used when running ProxyCommand
        engine = db.get_engine()
        self.Session = sessionmaker(bind=engine)

    @property
    def json_orch_execution(self):
        return self._json_orch_execution

    @property
    def orch_execution(self):
        if not hasattr(self.data, 'orch_execution') or getattr(self.data, 'orch_execution') not in self.data.session:
            self.data.orch_execution = self.data.session.query(OrchExecution).get(self._json_orch_execution['id'])
        return self.data.orch_execution



    @contextmanager
    def session_scope(self):
        """Provide a transactional scope around a series of operations."""
        self.data.session = self.Session()
        try:
            yield self.data.session
            self.data.session.commit()
        except:
            self.data.session.rollback()
            raise
        finally:
            self.data.session.close()

    def update_orch_execution(self, **kwargs):
        with self.session_scope() as s:
            for key, value in kwargs.items():
                setattr(self.orch_execution, key, value)

    def create_step_execution(self, command):
        ctx = None
        if not has_app_context():
            ctx = self.app.app_context()
            ctx.push()

        try:
            with self.session_scope() as s:
                se = StepExecution(id=uuid.uuid4(), step_id=command.id[1],
                                   server_id=command.id[0], orch_execution_id=self.orch_execution.id,
                                   start_time=get_now())
                s.add(se)

                return se.id
        finally:
            if ctx:
                ctx.pop()

    def register_step_execution(self, command: ImplementationCommand, params=None, pre_process_time=None,
                                execution_time=None,
                                post_process_time=None):
        ctx = None
        if not has_app_context():
            ctx = self.app.app_context()
            ctx.push()

        try:
            with self.session_scope() as s:
                se: StepExecution = s.query(StepExecution).get(command.step_execution_id)
                se.load_completed_result(command._cp)
                se.params = params
                se.pre_process_elapsed_time = pre_process_time
                se.execution_elapsed_time = execution_time
                se.post_process_elapsed_time = post_process_time
                se.end_time = get_now()
                if command._cp.stdout and ORCH_EXEC_PATTERN.match(command._cp.stdout):
                    se.child_orch_execution_id = ORCH_EXEC_PATTERN.findall(command._cp.stdout)[0]
        finally:
            if ctx:
                ctx.pop()
