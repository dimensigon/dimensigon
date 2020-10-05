import copy
import functools
import inspect
import os
import re
import sqlite3
import sys
import time
import typing as t
from abc import ABC, abstractmethod
from datetime import datetime

import flask
import jinja2
import requests
import yaml
from RestrictedPython import compile_restricted, safe_builtins
from dataclasses import dataclass
from flask import json
from flask_jwt_extended import create_access_token, get_jwt_identity

from dimensigon import defaults
from dimensigon.domain.entities import Step, Server, Software, OrchExecution, Orchestration, Scope, Route
from dimensigon.network.auth import HTTPBearerAuth
from dimensigon.use_cases import routing
from dimensigon.use_cases.lock import lock_scope
from dimensigon.utils import subprocess
from dimensigon.utils.helpers import get_now, format_exception
from dimensigon.utils.typos import Kwargs
from dimensigon.utils.var_context import VarContext
from dimensigon.web import db, errors
from dimensigon.web.helpers import normalize_hosts
from dimensigon.web.network import request, get


@dataclass
class CompletedProcess:
    success: bool = None
    stdout: t.Union[str, bytes] = None
    stderr: t.Union[str, bytes] = None
    rc: int = None
    start_time: datetime = None
    end_time: datetime = None
    pre_post_error: Exception = None

    def set_start_time(self) -> 'CompletedProcess':
        self.start_time = get_now()
        return self

    def set_end_time(self) -> 'CompletedProcess':
        self.end_time = get_now()
        return self

    def to_json(self):
        return self.__dict__


class IOperationEncapsulation(ABC):

    def __init__(self, code: str, expected_stdout: str = None, expected_stderr: str = None, expected_rc: int = None,
                 system_kwargs: Kwargs = None):
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
        self.expected_stdout = expected_stdout
        self.expected_stderr = expected_stderr
        self.expected_rc = expected_rc
        self.system_kwargs = system_kwargs or {}

    def load_code(self):
        return

    @abstractmethod
    def execute(self, var_context: VarContext, timeout=None) -> CompletedProcess:
        """
        StepExecution process
        Parameters
        ----------
        var_context:
            var_context to be passed through the execution

        Returns
        -------
        StepExecution:
            dataclass containing all the information from the result execution
        """

    def rpl_params(self, params: Kwargs):
        template = jinja2.Template(self.code)
        return template.render(params)

    def evaluate_result(self, cp: CompletedProcess):
        if cp.success is None:
            res = []
            if self.expected_stdout is not None:
                if isinstance(cp.stdout, str):
                    res.append(True) if re.search(self.expected_stdout, cp.stdout) else res.append(False)
            if self.expected_stderr is not None:
                if isinstance(cp.stderr, str):
                    res.append(True) if re.search(self.expected_stderr, cp.stderr) else res.append(False)
            if self.expected_rc is not None:
                res.append(True) if self.expected_rc == cp.rc else res.append(False)
            cp.success = all(res)
        return cp


class AnsibleOperation(IOperationEncapsulation):

    def execute(self, var_context: VarContext, timeout=None, command=None) -> CompletedProcess:
        code = self.code
        if re.match(r'^[^<>:;,?"*|/\\]+$', self.code):
            file = os.path.join('', 'ansible', self.code)
            if os.path.exists(file):
                with open(file, 'r') as fh:
                    code = fh.read()

        template = self.rpl_params({'globals': var_context.globals, **dict(var_context)})

        system_kwargs = self.system_kwargs.copy()

        tokens = ('ansible-playbook', '-i', '"localhost,"', '-c', 'local') + tuple(template)

        cp = CompletedProcess()
        cp.set_start_time()
        try:
            r = subprocess.run(tokens, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               **system_kwargs, timeout=timeout)
            cp.stdout = r.stdout
            cp.stderr = r.stderr
            cp.rc = r.returncode
        except (subprocess.TimeoutExpired, ValueError) as e:
            cp.stderr = f"{e.__class__.__name__}{e.args}"
            cp.success = False
        finally:
            cp.set_end_time()

        return self.evaluate_result(cp)


class RequestOperation(IOperationEncapsulation):

    def execute(self, var_context: VarContext, timeout=None, command=None) -> CompletedProcess:
        params_dict = dict(var_context)
        kwargs = json.loads(self.rpl_params({'globals': var_context.globals, **dict(var_context)}))
        kwargs.update(self.system_kwargs)
        cp = CompletedProcess()
        cp.set_start_time()

        # common parameters
        if kwargs.get('timeout') is not None and timeout is not None:
            kwargs['timeout'] = min(kwargs.get('timeout'), timeout)
        method = kwargs.pop('method').lower()

        resp, exception = None, None

        if 'software_id' in var_context:
            def search_cost(ssa, route_list):
                cost = [route['cost'] for route in route_list if str(ssa.server.id) == route['destination_id']]
                if cost:
                    if cost[0] is None:
                        cost = 999999
                    else:
                        cost = cost[0]
                else:
                    cost = 999999
                return cost

            soft = Software.query.get(params_dict.get('software_id', None))
            if not soft:
                cp.stderr = f"software id '{params_dict.get('software_id', None)}' not found"
                cp.success = False
                cp.set_end_time()
                return cp
            if not soft.ssas:
                cp.stderr = f"{soft.id} has no server association"
                cp.success = False
                cp.set_end_time()
                return cp
            dest_server = Server.query.get(params_dict.get('server_id', None))
            if not dest_server:
                cp.stderr = f"destination server id '{params_dict.get('server_id', None)}' not found"
                cp.success = False
                cp.set_end_time()
                return cp

            auth = HTTPBearerAuth(create_access_token(get_jwt_identity()))
            # decide best server source
            resp = get(dest_server, 'api_1_0.routes', auth=auth, timeout=5)
            if resp.code == 200:
                ssas = copy.copy(soft.ssas)
                ssas.sort(key=functools.partial(search_cost, route_list=resp.msg['route_list']))
            else:
                ssas = soft.ssas
            server = ssas[0].server

            # Process kwargs
            if 'auth' not in kwargs:
                kwargs['auth'] = auth

            view_or_url = kwargs.pop('view_or_url', kwargs.pop('view', kwargs.pop('url', None)))

            # run request
            resp = request(method, server, view_or_url, **kwargs)
            cp.stdout = flask.json.dumps(resp.msg) if isinstance(resp.msg, dict) else resp.msg
            cp.stderr = str(resp.exception) if str(resp.exception) else resp.exception.__class__.__name__
            cp.rc = resp.code
            if resp.exception is None:
                self.evaluate_result(cp)
        else:
            # process kwargs
            url = kwargs.pop('view_or_url', kwargs.pop('url', None))

            # Run request
            try:
                resp = requests.request(method, url, **kwargs)
            except Exception as e:
                exception = e
            else:
                cp.rc = resp.status_code
                cp.stdout = resp.text
            if exception is None:
                self.evaluate_result(cp)
            else:
                cp.success = False
                cp.stderr = str(exception) if str(exception) else exception.__class__.__name__
        cp.set_end_time()
        return cp

class NativeOperation(IOperationEncapsulation):

    def execute(self, var_context: VarContext, timeout=None, command=None):
        pass


class NativeWaitOperation(IOperationEncapsulation):

    def execute(self, var_context: VarContext, timeout=None, command=None):
        start = time.time()
        found = []
        cp = CompletedProcess()
        cp.set_start_time()
        try:
            min_timeout = min(timeout, var_context.get('timeout', None))
        except TypeError:
            if timeout is not None:
                min_timeout = timeout
            elif var_context.get('timeout', None) is not None:
                min_timeout = var_context.get('timeout')
            else:
                min_timeout = defaults.MAX_TIME_WAITING_SERVERS
        try:
            now = get_now()
            pending_names = set(var_context.get('list_server_names', []))
            with lock_scope(Scope.CATALOG, retries=3, delay=4, applicant=var_context.globals.get('orch_execution_id')):
                while len(pending_names) > 0:
                    try:
                        found_names = db.session.query(Server.name).filter(Server.name.in_(pending_names)).filter(
                            Server.created_on >= now).all()
                    except sqlite3.OperationalError as e:
                        if str(e) == 'database is locked':
                            found_names = []
                    found_names = set([t[0] for t in found_names])
                    pending_names = pending_names - found_names
                    if pending_names and (time.time() - start) < min_timeout:
                        time.sleep(self.system_kwargs.get('sleep_time', 15))
                    else:
                        break
        except errors.LockError as e:
            cp.success = False
            cp.stderr = str(e)

        else:
            if not pending_names:
                cp.success = True
                cp.stdout = f"Server{'s' if len(var_context.get('list_server_names', [])) > 1 else ''} " \
                            f"{', '.join(sorted(var_context.get('list_server_names', [])))} found"
            else:
                cp.success = False
                cp.stderr = f"Server{'s' if len(pending_names) > 1 else ''} {', '.join(sorted(pending_names))} " \
                            f"not created after {min_timeout} seconds"
        cp.set_end_time()
        return cp


class NativeDmRunningOperation(IOperationEncapsulation):

    def execute(self, var_context: VarContext, timeout=None, command=None):
        start = time.time()
        running = []
        cp = CompletedProcess()
        cp.set_start_time()
        try:
            min_timeout = min(timeout, var_context.get('timeout', None))
        except TypeError:
            if timeout is not None:
                min_timeout = timeout
            elif var_context.get('timeout', None) is not None:
                min_timeout = var_context.get('timeout')
            else:
                min_timeout = defaults.MAX_TIME_WAITING_SERVERS

        pending_names = set(var_context.get('list_server_names', []))

        while len(pending_names) > 0:
            try:
                found_names = db.session.query(Server.name).join(Route, Route.destination_id == Server.id).filter(
                    Server.name.in_(pending_names)).filter(Route.cost.isnot(None)).order_by(Server.name).all()
            except sqlite3.OperationalError as e:
                if str(e) == 'database is locked':
                    found_names = []
            found_names = set([t[0] for t in found_names])
            pending_names = pending_names - found_names
            if pending_names and (time.time() - start) < min_timeout:
                time.sleep(self.system_kwargs.get('sleep_time', 15))
            else:
                break


        if not pending_names:
            cp.success = True
            cp.stdout = f"Server{'s' if len(var_context.get('list_server_names', [])) > 1 else ''} " \
                        f"{', '.join(sorted(var_context.get('list_server_names', [])))} with dimensigon running"
        else:
            cp.success = False
            cp.stderr = f"Server{'s' if len(pending_names) > 1 else ''} {', '.join(sorted(pending_names))} " \
                        f"with dimensigon not running after {min_timeout} seconds"
        cp.set_end_time()
        return cp


class NativeDeleteOperation(IOperationEncapsulation):

    def execute(self, var_context: VarContext, timeout=None, command=None):
        cp = CompletedProcess()
        cp.set_start_time()
        try:
            with lock_scope(Scope.CATALOG, retries=3, delay=4, applicant=var_context.globals.get('orch_execution_id')):
                to_be_deleted = Server.query.filter(Server.name.in_(var_context.get('list_server_names', []))).all()
                acquired = routing._lock.acquire(timeout=15)
                if acquired:
                    routing.logger.debug(
                        f"Routing Lock acquired for deletion of servers {[s.name for s in to_be_deleted]}")
                else:
                    routing.logger.debug(
                        f"Unable to lock Routing Lock. Force deletion of servers {[s.name for s in to_be_deleted]}")
                try:
                    for s in to_be_deleted:
                        # remove associated routes
                        db.session.delete(s.route)
                        s.delete()
                        db.session.commit()
                finally:
                    if acquired:
                        routing._lock.release()
        except errors.LockError as e:
            cp.success = False
            cp.stderr = str(e)
        except Exception as e:
            cp.success = False
            cp.stderr = f"Unable to delete server{'s' if len(var_context.get('to_be_deleted', [])) > 1 else ''} " \
                        f"{', '.join([s.name for s in to_be_deleted])}. Exception: {e}"
        else:
            cp.success = True
            cp.stdout = f"Server{'s' if len(to_be_deleted) > 1 else ''} " \
                        f"{', '.join([s._old_name for s in to_be_deleted])} deleted"

        cp.set_end_time()
        return cp


class PythonOperation(IOperationEncapsulation):
    def execute(self, var_context: VarContext, timeout=None, command=None) -> CompletedProcess:
        byte_code = compile_restricted(self.code, '<inline>', 'exec')
        safe_builtins.update(json=json)
        safe_builtins.update(json=yaml)

        cp = CompletedProcess()
        cp.set_start_time()
        _locals = dict(vc=var_context)

        try:
            exec(byte_code, {'__builtins__': safe_builtins, '_write_': lambda x: x}, _locals)
        except Exception as e:
            cp.stderr = format_exception(e)
            cp.success = False
        else:
            cp.stdout = ''.join(getattr(_locals.get('_print', None), 'txt', []))
            cp.success = True
            cp.set_end_time()

        return cp


class ShellOperation(IOperationEncapsulation):

    def execute(self, var_context: VarContext, timeout=None, command=None) -> CompletedProcess:
        tokens = self.rpl_params({'globals': var_context.globals, **dict(var_context)})

        system_kwargs = self.system_kwargs.copy()

        timeout = system_kwargs.pop('timeout', 300)

        cp = CompletedProcess()
        cp.set_start_time()
        r = None
        try:
            r = subprocess.run(tokens, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               **system_kwargs, timeout=timeout)
            cp.stdout = r.stdout.decode() if isinstance(r.stdout, bytes) else r.stdout
            cp.stderr = r.stderr.decode() if isinstance(r.stderr, bytes) else r.stderr
            cp.rc = r.returncode
        except (subprocess.TimeoutExpired, ValueError) as e:
            cp.stderr = f"{e.__class__.__name__}{e.args}"
            cp.success = False
        finally:
            cp.set_end_time()

        self.evaluate_result(cp)

        return cp


class OrchestrationOperation(IOperationEncapsulation):

    def execute(self, var_context: VarContext, timeout=None) -> CompletedProcess:
        from dimensigon.web.async_functions import deploy_orchestration

        cp = CompletedProcess().set_start_time()
        #validate data
        orchestration_id = var_context.get('orchestration_id')


        orch = Orchestration.query.get(orchestration_id)
        if orch is None:
            cp.stderr = str(errors.EntityNotFound('Orchestration', orchestration_id))
            cp.success = False
            cp.set_end_time()
            return cp

        exe = OrchExecution(orchestration_id=orchestration_id,
                            target=var_context.get('hosts'),
                            params=dict(var_context),
                            executor_id=var_context.globals.get('executor_id'),
                            server=Server.get_current(),
                            parent_step_execution_id=var_context.globals.get('step_execution_id'))
        db.session.add(exe)
        db.session.commit()

        cp.stdout = f"orch_execution_id={exe.id}"
        hosts = copy.deepcopy(var_context.get('hosts'))
        if isinstance(hosts, list):
            hosts = {'all': hosts}
        elif isinstance(hosts, str):
            hosts = {'all': [hosts]}
        not_found = normalize_hosts(hosts)
        if not_found:
            cp.stderr = str(errors.ServerNormalizationError(not_found))
            cp.success = False
        else:
            try:
                deploy_orchestration(orchestration=var_context.get('orchestration_id'), hosts=hosts,
                                     var_context=var_context.create_new_ctx({}, initials=dict(var_context)),
                                     execution=exe)
            except Exception as e:
                cp.stderr = str(e) if str(e) else e.__class__.__name__
                cp.success = False
            else:
                db.session.refresh(exe)
                cp.success = exe.success
        cp.set_end_time()

        return cp


from dimensigon.domain.entities import ActionType

_operation_classes = {}
for name, cls in inspect.getmembers(sys.modules['dimensigon.use_cases.operations'],
                                    lambda x: (inspect.isclass(x) and issubclass(x, IOperationEncapsulation))):
    _operation_classes.update({name: cls})

_factories: t.Dict['ActionType', t.Type[IOperationEncapsulation]] = {}

for at in ActionType:
    try:
        _factories.update({at: _operation_classes[at.name.capitalize() + 'Operation']})
    except KeyError:
        NotImplementedError(f"{at.name.capitalize() + 'Operation'} not implemented")


def create_operation(step: 'Step') -> IOperationEncapsulation:
    kls = _factories[step.action_type]

    if kls == NativeOperation:
        if step.action_template.id == '00000000-0000-0000-000a-000000000002':
            kls = NativeWaitOperation
        elif step.action_template.id == '00000000-0000-0000-000a-000000000004':
            kls = NativeDmRunningOperation
        elif step.action_template.id == '00000000-0000-0000-000a-000000000005':
            kls = NativeDeleteOperation
    return kls(code=step.code, expected_stdout=step.expected_stdout, expected_stderr=step.expected_stderr,
               expected_rc=step.expected_rc,
               system_kwargs=step.system_kwargs)
