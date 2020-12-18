import base64
import concurrent
import copy
import datetime
import functools
import json
import logging
import pickle
import re
import threading
import time
import typing as t
import uuid
from abc import ABC, abstractmethod
from collections import OrderedDict
from concurrent.futures.process import ProcessPoolExecutor
from concurrent.futures.thread import ThreadPoolExecutor
from contextlib import contextmanager
from functools import partial

import jsonschema
from flask import current_app, has_app_context, g
from flask_jwt_extended import create_access_token
from sqlalchemy.orm import sessionmaker

from dimensigon import defaults
from dimensigon.domain.entities import Server, Orchestration, Step, StepExecution, OrchExecution, User, Scope
from dimensigon.network.auth import HTTPBearerAuth
from dimensigon.use_cases import lock as lock
from dimensigon.use_cases.operations import CompletedProcess, IOperationEncapsulation, create_operation
from dimensigon.utils.dag import DAG
from dimensigon.utils.event_handler import Event
from dimensigon.utils.helpers import get_now, format_exception
from dimensigon.utils.typos import Id
from dimensigon.utils.var_context import Context
from dimensigon.web import db, errors, executor, DimensigonFlask
from dimensigon.web.network import post

# if t.TYPE_CHECKING:


logger = logging.getLogger('dm.deployment')


def exec_safe(code, locals=None):
    # TODO: redefine builtin scope
    # byte_code = compile_restricted(code, '<string>', 'exec')
    # safe_builtins.update(json=json)
    # safe_builtins.update(yaml=yaml)
    # safe_builtins.update(re=re)
    # exec(byte_code, {'__builtins__': safe_builtins,
    #                  '_write_': full_write_guard,
    #                  '_getiter_': default_guarded_getiter},
    #      locals)
    exec(code, {}, locals)


class ICommand(ABC):
    _id: Id

    @property
    @abstractmethod
    def success(self) -> bool:
        """
        Property that returns True if the command executed successfully
        Returns
        -------

        """

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

    @property
    def id(self) -> Id:
        """
        Property that returns the ID of the command
        Returns
        -------

        """
        return self._id

    def __repr__(self):
        return f"{self.__class__.__name__} {self.id}"


def elapsed_times(tag):
    def decorator(f):
        @functools.wraps(f)
        def wrapper(self, *args, **kwargs):
            if not hasattr(self, '_elapsed_times'):
                self._elapsed_times = {}
            start = time.time()
            ret = f(self, *args, **kwargs)
            self._elapsed_times[tag] = time.time() - start
            return ret

        return wrapper

    return decorator


def extract_container_var(var):
    if var.startswith('input.'):
        source = var.split('.', 1)[1]
        container_name = 'input'
    elif '.' not in var:
        source = var
        container_name = 'input'
    else:
        container_name, source = var.split('.', 1)
    return container_name, source


def normalize_container_var(var):
    return '.'.join(extract_container_var(var))



reserved_words = ['mapping', 'required', 'output']


class ImplementationCommand(ICommand):

    def __init__(self, implementation: IOperationEncapsulation,
                 var_context: Context = None,
                 id_=None,
                 register: 'RegisterStepExecution' = None,
                 pre_process=None,
                 post_process=None,
                 signature=None
                 ):
        self._id = id_ or id(self)
        self.implementation = implementation
        self.var_context = var_context
        self.params = DictDict()
        self.register = register
        self.step_execution_id = None
        self.pre_process_code = pre_process
        self.post_process_code = post_process
        self.signature = signature or {}
        self._elapsed_times = {}
        self._cp: CompletedProcess = None

    def create_step_execution(self):
        if self.register:
            step_execution_id = self.register.create_step_execution(self)
            self.var_context.env.update(step_execution_id=step_execution_id)
            self.step_execution_id = step_execution_id

    def register_execution(self):
        if self.register:
            self.register.save_step_execution(self, params=self.params, **self._elapsed_times)

    @elapsed_times('pre_process_time')
    def pre_process(self):
        if self.pre_process_code:
            try:
                local = dict(vc=self.var_context, cp=self._cp)
                exec_safe(self.pre_process_code, local)
            except Exception as e:
                self._cp = CompletedProcess(success=False, stderr=f"Pre-Process error: {format_exception(e)}")

    def extract_params(self):
        """
        Turns over only params from var context to params
        :return:
        """
        if not self._cp:
            try:
                if self.signature:
                    # get required variables
                    required = DictSet()
                    for r in self.signature.get('required', []):
                        container_name, var = extract_container_var(r)
                        required[container_name].add(var)
                        # del container_name
                    # containers in signature
                    container_names = [k for k in self.signature.keys() if k not in reserved_words]
                    # add containers to turn over params from required
                    container_names = set(container_names) | set(required.keys())
                    container_names -= {'env'}  # remove env container cause is going to be passed explicitly

                    # resolve mapping values
                    for dest, value in self.signature.get('mapping', {}).items():
                        if isinstance(value, dict) and len(value) == 1 and 'from' in value:
                            action, source = tuple(value.items())[0]
                            container_name, var = extract_container_var(source)
                            try:
                                self.params['input'].update({dest: getattr(self.var_context, container_name, {})[var]})
                            except KeyError:
                                if dest in required.get('input', []):
                                    se = StepExecution.query.get(self.step_execution_id)
                                    raise errors.MissingParameters([source],
                                                                   se.step, se.server)
                        else:
                            self.params['input'][dest] = value

                    schema2validate = {'type': 'object', 'properties': {}}
                    for container_name in container_names:
                        schema2validate['properties'].update(
                            {container_name: dict(type="object", properties=self.signature.get(container_name, {}),
                                                  required=list(required[container_name]))})
                        for var, value in self.signature.get(container_name, {}).items():
                            if var not in self.params[container_name]:
                                try:
                                    self.params[container_name].update(
                                        {var: getattr(self.var_context, container_name, {})[var]})
                                except KeyError:
                                    if 'default' in value:
                                        self.params[container_name][var] = value['default']
                                    elif var in required.get(container_name, []):
                                        if has_app_context():
                                            raise errors.MissingParameters([f"{container_name}.{var}"],
                                                                           Step.query.get(self.id[1]),
                                                                           Server.query.get(self.id[0]))
                                        else:
                                            raise errors.MissingParameters([f"{container_name}.{var}"])
                        # add variables specified in required
                        for var in required.get(container_name, []):
                            if var not in self.params[container_name]:
                                try:
                                    self.params[container_name].update(
                                        {var: getattr(self.var_context, container_name, {})[var]})
                                except KeyError:
                                    raise errors.MissingParameters([f"{container_name}.{var}"],
                                                                   Step.query.get(self.id[1]),
                                                                   Server.query.get(self.id[0]))

                    if schema2validate:
                        jsonschema.validate(self.params, schema2validate)
                else:
                    self.params = self.var_context.dict()
            except KeyError as e:
                self._cp = CompletedProcess(success=False, stderr=f"Variable {e} not found")
            except jsonschema.ValidationError as e:
                self._cp = CompletedProcess(success=False, stderr=f"Param validation error: {e}")
            except errors.MissingParameters as e:
                self._cp = CompletedProcess(success=False, stderr=f"{e}")
            except Exception as e:
                self._cp = CompletedProcess(success=False, stderr=f"{format_exception(e)}")

    def _invoke(self, timeout):
        if not self._cp:
            try:
                self._cp = self.implementation.execute(self.params, timeout=timeout, context=self.var_context)
            except Exception as e:
                self._cp = CompletedProcess(success=False, stderr=f"Execution error: {e}")
                logger.exception(f"Exception on execution {self.id}")

    @elapsed_times('post_process_time')
    def post_process(self):
        if self.post_process_code:
            try:
                local = dict(vc=self.var_context, cp=self._cp)
                exec_safe(self.post_process_code, local)
            except Exception as e:
                self._cp.success = False
                if self._cp.stderr:
                    self._cp.stderr = f"{self._cp.stderr}\nPost-Process error: {format_exception(e)}"
                else:
                    self._cp.stderr = f"Post-Process error: {format_exception(e)}"

    def check_output_variables(self):
        if self._cp.success and self.signature.get('output', []):
            output = set(self.signature.get('output', []))
            missing = output - set(self.var_context.keys())
            if missing:
                self._cp.success = False
                if self._cp.stderr:
                    self._cp.stderr = f"{self._cp.stderr}\nMissing output values: {', '.join(missing)}"
                else:
                    self._cp.stderr = f"Missing output values: {', '.join(sorted(missing))}"

    def invoke(self, timeout=None) -> t.Optional[bool]:
        if not self._cp:
            self.create_step_execution()

            self.pre_process()

            self.extract_params()

            self._invoke(timeout)

            self.post_process()

            self.check_output_variables()

            self.register_execution()

        return self.success

    @property
    def result(self) -> t.Dict[Id, CompletedProcess]:
        return {self.id: self._cp}

    @property
    def success(self) -> t.Optional[bool]:
        return getattr(self._cp, 'success', None)


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
                 id_=None, executor: concurrent.futures.Executor = None,
                 register: 'RegisterStepExecution' = None, var_context: Context = None):
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
        self._id = id_
        self._dag = DAG().from_dict_of_lists(dict_tree)
        self.stop_on_error = stop_on_error
        self.stop_undo_on_error = stop_undo_on_error
        self.executor = executor or ThreadPoolExecutor(max_workers=4)
        self.register = register
        self.var_context = var_context

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
        # logging.basicConfig(format='%(threadName)s %(levelname)-8s %(message)s')
        # logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
        res = []
        stop = False
        level = 1
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
                # if self.var_context:
                #     self.var_context.merge_common_variables()
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


class ProxyImplementation:
    _command: ImplementationCommand

    def __init__(self, server: Id):
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
        self.__dict__['_auth'] = None
        self.__dict__['_completion_event'] = threading.Event()
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
        else:
            self._command._cp = CompletedProcess(success=False, stdout=str(event.data),
                                                 stderr=f'Unknown message got on completion event.')

        self._completion_event.set()

    def _invoke(self, timeout) -> bool:
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
            self.__dict__['_server'] = Server.query.get(self._server)

            # set a timeout if none to avoid infinite wait in event
            if timeout is None:
                timeout = defaults.TIMEOUT_REMOTE_COMMAND
            if not self._command._cp:
                auth = HTTPBearerAuth(
                    create_access_token(self._command.var_context.env['executor_id'], datetime.timedelta(seconds=15)))
                start = time.time()
                data = dict(operation=base64.b64encode(pickle.dumps(self._command.implementation)).decode('ascii'),
                            var_context=base64.b64encode(pickle.dumps(self._command.var_context)).decode('ascii'),
                            params=base64.b64encode(pickle.dumps(self._command.params)).decode('ascii'),
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

        finally:
            if ctx:
                ctx.pop()
        return self.success


class ProxyCommand(ProxyImplementation, Command):

    def __init__(self, server_id: Id, *args, **kwargs):
        super().__init__(server_id)
        self.__dict__['_command'] = Command(*args, **kwargs)


class ProxyUndoCommand(ProxyImplementation, UndoCommand):

    def __init__(self, server_id: Id, *args, **kwargs):
        super().__init__(server_id)
        self.__dict__['_command'] = UndoCommand(*args, **kwargs)


def _create_server_undo_command(executor, current_server, server_id: Id, s: Step, var_context: Context, register,
                                d=None, s2cc=None) -> t.Optional[t.Union[UndoCommand, CompositeCommand]]:
    def iterate_tree(_cls, _step: Step, _d, _s2cc):
        if _step in _s2cc:
            _uc = _s2cc[_step]
        else:
            stop_on_error = _step.step_stop_on_error if _step.step_stop_on_error is not None else s.stop_undo_on_error
            _uc = _cls(create_operation(_step),
                       id_=(str(server_id), str(_step.id)),
                       var_context=var_context.local_ctx({'server_id': server_id}, key_server_ctx=server_id),
                       pre_process=_step.pre_process,
                       post_process=_step.post_process,
                       stop_on_error=stop_on_error,
                       register=register,
                       signature=_step.schema)
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


def create_cmd_from_orchestration(orchestration: Orchestration, var_context: Context,
                                  hosts: t.Dict[str, t.List[Id]],
                                  executor: concurrent.futures.Executor,
                                  register: 'RegisterStepExecution') -> CompositeCommand:
    current_server = Server.get_current()

    def create_do_cmd_from_step(_step: Step, _s2cc):
        d = {}
        if _step in _s2cc:
            cc = _s2cc[_step]
        else:
            activate_server_ctx = len([server_id for target in _step.target for server_id in hosts[target]]) > 1
            for target in _step.target:
                for server_id in hosts[target]:
                    if str(server_id) == str(current_server.id):
                        cls = Command
                    else:
                        cls = partial(ProxyCommand, server_id)

                    var_kwargs = dict()
                    if activate_server_ctx:
                        var_kwargs.update(key_server_ctx=server_id)
                    c = cls(create_operation(_step),
                            undo_command=_create_server_undo_command(executor, current_server, server_id,
                                                                     _step, var_context, register),
                            var_context=var_context.local_ctx({'server_id': server_id}, **var_kwargs),
                            stop_on_error=_step.stop_on_error,
                            stop_undo_on_error=None,
                            undo_on_error=_step.undo_on_error,
                            pre_process=_step.pre_process,
                            post_process=_step.post_process,
                            register=register,
                            id_=(str(server_id), str(_step.id)),
                            signature=_step.schema)

                    d[c] = []
            if len(d) == 1:
                cc = c
            elif len(d) > 1:
                cc = CompositeCommand(dict_tree=d,
                                      stop_on_error=False,
                                      stop_undo_on_error=False,
                                      id_=str(_step.id), executor=executor, register=register, var_context=var_context)
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
                            id_=str(orchestration.id), executor=executor, register=register)


ORCH_EXEC_PATTERN = re.compile(r"^orch_execution_id=([a-zA-Z0-9-]{36})$")


class RegisterStepExecution:
    def __init__(self, orch_execution: OrchExecution, app: DimensigonFlask = None):
        if app:
            self.app = app
        else:
            self.app = current_app._get_current_object()

        self.json_orch_execution = orch_execution.to_json()  # json_orch_execution property is used when running ProxyCommand
        self._store: t.Dict[Id, StepExecution] = OrderedDict()
        if hasattr(app, 'dm') and getattr(app.dm, 'engine'):
            engine = app.dm.engine
        else:
            engine = db.get_engine()
        self.Session = sessionmaker(bind=engine, autoflush=False)

        # def receive_after_transaction_create(session: Session, transaction:SessionTransaction):
        #     print(f"Created transaction {transaction}{transaction._state}({transaction.parent}) on session {session}()")
        #
        # def receive_after_transaction_end(session, transaction):
        #     print(f"Ended transaction {transaction}{transaction._state}({transaction.parent}) on session {session}")
        #
        # from sqlalchemy import event
        # event.listen(self.Session, 'after_transaction_create', receive_after_transaction_create)
        # event.listen(self.Session, 'after_transaction_end', receive_after_transaction_end)

    @property
    def id(self):
        return self.json_orch_execution.get('id')

    @contextmanager
    def session_scope(self):
        """Provide a transactional scope around a series of operations."""
        session = self.Session()
        try:
            yield session
            session.flush()
            session.commit()
        except:
            session.rollback()
            logger.exception("Unable to commit")
        finally:
            session.close()

    def update_orch_execution(self, **kwargs):
        with self.session_scope() as s:
            orch_execution = s.query(OrchExecution).get(self.json_orch_execution.get('id'))
            for key, value in kwargs.items():
                setattr(orch_execution, key, value)
            self.json_orch_execution = orch_execution.to_json()

    def create_step_execution(self, command):
        ident = str(uuid.uuid4())
        with self.session_scope() as s:
            se = StepExecution(id=ident, step_id=command.id[1],
                               server_id=command.id[0], orch_execution_id=self.json_orch_execution.get('id'),
                               start_time=get_now())
            s.add(se)
        self._store[ident] = se
        return ident

    def save_step_execution(self, command: ImplementationCommand, params=None, pre_process_time=None,
                            execution_time=None,
                            post_process_time=None):
        with self.session_scope() as s:
            se = s.merge(self._store[command.step_execution_id])
            se.load_completed_result(command._cp)
            se.params = params
            se.pre_process_elapsed_time = pre_process_time
            se.execution_elapsed_time = execution_time
            se.post_process_elapsed_time = post_process_time
            se.end_time = get_now()
            if command._cp.stdout and ORCH_EXEC_PATTERN.match(command._cp.stdout):
                se.child_orch_execution_id = ORCH_EXEC_PATTERN.match(command._cp.stdout)[1]

    def commit_data(self):
        pass
        # if self._store:
        #     with self.session_scope() as s:
        #         for step in self._store.values():
        #             s.add(step)
        #         try:
        #             s.commit()
        #         except:
        #             s.rollback()
        #             logger.exception("Unable to commit data")
        #         else:
        #             self._store.clear()


class DictSet(dict):

    def __getitem__(self, item):
        if item not in self:
            super().__setitem__(item, set())
        return super().__getitem__(item)

    def __sub__(self, other):
        missing = []
        for c, v in self.items():
            m = v - other[c]
            missing.extend([f"{c}.{vv}" for vv in m])
        return missing


class DictDict(dict):

    def __getitem__(self, item):
        if item not in self:
            super().__setitem__(item, {})
        return super().__getitem__(item)

    def __sub__(self, other):
        missing = []
        for c, v in self.items():
            m = v - other[c]
            missing.extend([f"{c}.{vv}" for vv in m])
        return missing


def validate_input_chain(validatable: t.Union[Orchestration, Step], params: t.Dict[str, set]) -> \
        t.Dict[Step, t.Set[str]]:
    """validates against the validatable that params have all needed parameters

    Parameters
    ----------
    validatable: object that carries the schema
    params:      dict with variables grouped by container

    Returns
    -------
    returns a dict like object with all missed parameters per step
    """

    def split_container(_var):
        if '.' in var:
            c_name, v_name = var.split('.', 1)
        else:
            c_name, v_name = 'input', var
        return c_name, v_name

    iterable = validatable.root if isinstance(validatable, Orchestration) else validatable.children
    not_found = {}
    if not isinstance(params, DictSet):
        params = DictSet(params)
    current_params = DictSet(copy.deepcopy(params))
    for step in iterable:
        p = set(step.schema.get('required', []))
        required_params = DictSet()
        for var in p:
            if '.' in var:
                container_name, var_name = var.split('.', 1)
            else:
                container_name, var_name = 'input', var
            required_params[container_name].add(var_name)

        m = step.schema.get('mapping', {})
        if m:
            for dest, value in m.items():
                if isinstance(value, dict) and len(value) == 1 and 'from' in value:
                    action, source = tuple(value.items())[0]
                    if dest in required_params['input']:
                        current_params['input'].add(dest)
                        # add source as required
                        container_name, var_name = split_container(source)
                        required_params[container_name].add(var_name)
                else:
                    current_params['input'].add(dest)

        # add default values into current_params
        for k, v in step.schema.get('input', {}).items():
            if 'default' in v:
                current_params['input'].add(k)

        missing = required_params - current_params
        if missing:
            raise errors.MissingParameters(list(missing), step)

        out_params = set(step.schema.get('output', []))
        params['input'].update(out_params)

        r_not_found = validate_input_chain(step, params=params)
        not_found.update(r_not_found)
    return not_found


def deploy_orchestration(orchestration: t.Union[Id, Orchestration],
                         hosts: t.Dict[str, t.Union[t.List[Id]]],
                         var_context: 'Context' = None,
                         execution: t.Union[Id, OrchExecution] = None,
                         executor: t.Union[Id, User] = None,
                         execution_server: t.Union[Id, Server] = None,
                         lock_retries=2,
                         lock_delay=3, timeout=None) -> Id:
    """deploy the orchestration

    Args:
        orchestration: id or orchestration to execute
        hosts: Mapping to all distributions
        var_context: Context configuration
        execution: id or execution to associate with the orchestration. If none, a new one is created
        executor: id or User who executes the orchestration
        execution_server: id or User who executes the orchestration
        lock_retries: tries to lock for orchestration N times
        lock_delay: delay between retries
    Returns:
        OrchExecution ID

    Raises:
        Exception: if anything goes wrong
    """
    execution = execution or var_context.env.get('orch_execution_id')
    executor = executor or var_context.env.get('executor_id')
    hosts = hosts or var_context.get('hosts')
    if not isinstance(orchestration, Orchestration):
        orchestration = db.session.query(Orchestration).get(orchestration)
    if not isinstance(execution, OrchExecution):
        exe = None
        if execution is not None:
            exe = db.session.query(OrchExecution).get(execution)
        if exe is None:
            if not isinstance(executor, User):
                executor = db.session.query(User).get(executor)
            if executor is None:
                raise ValueError('executor must be set')
            if not isinstance(execution_server, Server):
                if execution_server is None:
                    try:
                        execution_server = g.server
                    except AttributeError:
                        execution_server = Server.get_current()
                    if execution_server is None:
                        raise ValueError('execution server not found')
                else:
                    execution_server = db.session.query(Server).get(execution_server)
            exe = OrchExecution(id=execution, orchestration_id=orchestration.id, target=hosts,
                                params=dict(var_context),
                                executor_id=executor.id, server_id=execution_server.id)
            db.session.add(exe)
            db.session.commit()

    else:
        exe = execution
    current_app.logger.debug(
        f"Execution {exe.id}: Launching orchestration {orchestration} on {hosts} with {var_context}")

    return _deploy_orchestration(orchestration, var_context, hosts, exe, lock_retries, lock_delay, timeout)


def _deploy_orchestration(orchestration: Orchestration,
                          var_context: 'Context',
                          hosts: t.Dict[str, t.List[Id]],
                          execution: OrchExecution,
                          lock_retries,
                          lock_delay,
                          timeout
                          ) -> Id:
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
    rse = RegisterStepExecution(execution)
    kwargs = dict()
    kwargs['start_time'] = execution.start_time or get_now()
    cc = create_cmd_from_orchestration(orchestration, var_context, hosts=hosts, register=rse, executor=executor)

    # convert UUID into str as in_ filter does not handle UUID type
    all = [str(s) for s in hosts['all']]
    servers = Server.query.filter(Server.id.in_(all)).all()
    try:
        applicant = lock.lock(Scope.ORCHESTRATION, servers, applicant=var_context.env.get('root_orch_execution_id'),
                              retries=lock_retries, delay=lock_delay)
    except errors.LockError as e:
        kwargs.update(success=False, message=str(e))
        rse.update_orch_execution(**kwargs)
        raise
    try:
        kwargs['success'] = cc.invoke(timeout=timeout)
        if not kwargs['success'] and orchestration.undo_on_error:
            kwargs['undo_success'] = cc.undo()
        kwargs['end_time'] = get_now()
        rse.update_orch_execution(**kwargs)
    except Exception as e:
        current_app.logger.exception("Exception while executing invocation command")
        kwargs.update(success=False, message=str(e))
        rse.update_orch_execution(**kwargs)
        try:
            db.session.rollback()
        except:
            pass

    finally:
        lock.unlock(Scope.ORCHESTRATION, applicant=applicant, servers=servers)

    return execution.id
