import copy
import datetime as dt
import functools
import inspect
import os
import re
import sqlite3
import stat
import sys
import tempfile
import time
import typing as t
from abc import ABC, abstractmethod
from dataclasses import dataclass

import flask
import jinja2
import requests
from flask import json
from flask_jwt_extended import create_access_token, get_jwt_identity

from dimensigon import defaults
from dimensigon.domain.entities import Step, Server, Software, OrchExecution, Orchestration, Scope, Route
from dimensigon.network.auth import HTTPBearerAuth
from dimensigon.use_cases import routing
from dimensigon.use_cases.lock import lock_scope
from dimensigon.utils import subprocess
from dimensigon.utils.helpers import get_now
from dimensigon.utils.typos import Kwargs
from dimensigon.utils.var_context import Context
from dimensigon.web import db, errors
from dimensigon.web import network as ntwrk
from dimensigon.web.helpers import normalize_hosts


@dataclass
class CompletedProcess:
    success: bool = None
    stdout: t.Union[str, bytes] = None
    stderr: t.Union[str, bytes] = None
    rc: int = None
    start_time: dt.datetime = None
    end_time: dt.datetime = None
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
    def _execute(self, params: Kwargs, timeout=None, context: Context = None) -> CompletedProcess:
        """
        StepExecution process
        Parameters
        ----------
        properties:
            properties passed to execute implementation
        env:
            environment variables

        Returns
        -------
        StepExecution:
            dataclass containing all the information from the result execution
        """

    def execute(self, params: Kwargs, timeout=None, context: Context = None) -> CompletedProcess:
        """
        StepExecution wrapper
        Parameters
        ----------
        properties:
            properties passed to execute implementation
        env:
            environment variables

        Returns
        -------
        StepExecution:
            dataclass containing all the information from the result execution
        """
        start = get_now()
        try:
            return self._execute(params, timeout=timeout, context=context)
        except Exception as e:
            return CompletedProcess(success=False, stderr=f"Error creating execution: {str(e)}", start_time=start,
                                    end_time=get_now())

    def rpl_params(self, params: Kwargs, env: Kwargs):
        template = jinja2.Template(self.code)
        return template.render(input=params, env=env)

    def evaluate_result(self, cp: CompletedProcess, context=None):
        if cp.success is None:
            res = []
            if self.expected_stdout is not None:
                if isinstance(cp.stdout, str):
                    match = re.match(self.expected_stdout, cp.stdout)
                    if match:
                        res.append(True)
                        if context:
                            for k, v in match.groupdict().items():
                                context.set(k, v)
                    else:
                        res.append(False)
            if self.expected_stderr is not None:
                if isinstance(cp.stderr, str):
                    match = re.match(self.expected_stderr, cp.stderr)
                    if match:
                        res.append(True)
                        if context:
                            for k, v in match.groupdict().items():
                                context.set(k, v)
                    else:
                        res.append(False)
            if self.expected_rc is not None:
                res.append(True) if self.expected_rc == cp.rc else res.append(False)
            cp.success = all(res)
        return cp


# class AnsibleOperation(IOperationEncapsulation):
# 
#     def execute(self, params: Kwargs, timeout=None, env=None) -> CompletedProcess:
#         code = self.code
#         if re.match(r'^[^<>:;,?"*|/\\]+$', self.code):
#             file = os.path.join('', 'ansible', self.code)
#             if os.path.exists(file):
#                 with open(file, 'r') as fh:
#                     code = fh.read()
# 
#         template = self.rpl_params({'globals': var_context.globals, **dict(var_context)})
# 
#         system_kwargs = self.system_kwargs.copy()
# 
#         tokens = ('ansible-playbook', '-i', '"localhost,"', '-c', 'local') + tuple(template)
# 
#         cp = CompletedProcess()
#         cp.set_start_time()
#         try:
#             r = subprocess.run(tokens, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
#                                **system_kwargs, timeout=timeout)
#             cp.stdout = r.stdout
#             cp.stderr = r.stderr
#             cp.rc = r.returncode
#         except (subprocess.TimeoutExpired, ValueError) as e:
#             cp.stderr = f"{e.__class__.__name__}{e.args}"
#             cp.success = False
#         finally:
#             cp.set_end_time()
# 
#         return self.evaluate_result(cp)


class RequestOperation(IOperationEncapsulation):

    def _execute(self, params: Kwargs, timeout=None, context: Context = None) -> CompletedProcess:
        kwargs = json.loads(self.rpl_params(params, context.env))
        kwargs.update(self.system_kwargs)
        cp = CompletedProcess()
        cp.set_start_time()

        # common parameters
        if kwargs.get('timeout') is not None and timeout is not None:
            kwargs['timeout'] = min(kwargs.get('timeout'), timeout)
        method = kwargs.pop('method').lower()

        resp, exception = None, None

        # process kwargs
        url = kwargs.pop('view_or_url', kwargs.pop('view', kwargs.pop('url', None)))

        # Run request
        try:
            resp = requests.request(method, url, **kwargs)
        except Exception as e:
            exception = e
        else:
            cp.rc = resp.status_code
            cp.stdout = resp.text
        if exception is None:
            self.evaluate_result(cp, context)
        else:
            cp.success = False
            cp.stderr = str(exception) if str(exception) else exception.__class__.__name__
        cp.set_end_time()
        return cp


class NativeOperation(IOperationEncapsulation):

    def _execute(self, params: Kwargs, timeout=None, context: Context = None):
        pass


class NativeSoftwareSendOperation(IOperationEncapsulation):

    def _execute(self, params: Kwargs, timeout=None, context: Context = None) -> CompletedProcess:
        params_dict = dict(params)
        cp = CompletedProcess()
        cp.set_start_time()

        # common parameters
        kwargs = self.system_kwargs
        if kwargs.get('timeout') is not None and timeout is not None:
            kwargs['timeout'] = min(kwargs.get('timeout'), timeout)
        else:
            if timeout is None:
                kwargs['timeout'] = kwargs.get('timeout') or 15 * 60
            else:
                kwargs['timeout'] = timeout

        auth = HTTPBearerAuth(
            create_access_token(get_jwt_identity(), expires_delta=dt.timedelta(seconds=kwargs['timeout'])))
        resp, exception = None, None

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

        # decide best server source
        resp = ntwrk.get(dest_server, 'api_1_0.routes', auth=auth, timeout=10)
        if resp.code == 200:
            ssas = copy.copy(soft.ssas)
            ssas.sort(key=functools.partial(search_cost, route_list=resp.msg['route_list']))
        else:
            ssas = soft.ssas
        server = ssas[0].server

        # Process kwargs
        if 'auth' not in kwargs:
            kwargs['auth'] = auth
        data = {'software_id': soft.id, 'dest_server_id': dest_server.id, "background": False,
                "include_transfer_data": True, "force": True}
        if params.get('dest_path', None):
            data.update(dest_path=params.get('dest_path', None))
        if params.get('chunk_size', None):
            data.update(chunk_size=params.get('chunk_size', None))
        if params.get('max_senders', None):
            data.update(max_senders=params.get('max_senders', None))
        # run request
        resp = ntwrk.post(server, 'api_1_0.send', json=data, **kwargs)
        cp.stdout = flask.json.dumps(resp.msg) if isinstance(resp.msg, dict) else resp.msg
        cp.stderr = str(resp.exception) if str(resp.exception) else resp.exception.__class__.__name__
        cp.rc = resp.code
        if resp.exception is None:
            self.evaluate_result(cp)
        cp.set_end_time()
        return cp


class NativeWaitOperation(IOperationEncapsulation):

    def _execute(self, params: Kwargs, timeout=None, context: Context = None):
        start = time.time()
        found = []
        cp = CompletedProcess()
        cp.set_start_time()
        try:
            min_timeout = min(timeout, params.get('timeout', None))
        except TypeError:
            if timeout is not None:
                min_timeout = timeout
            elif params.get('timeout', None) is not None:
                min_timeout = params.get('timeout')
            else:
                min_timeout = defaults.MAX_TIME_WAITING_SERVERS
        try:
            now = get_now()
            pending_names = set(params.get('server_names', []))
            with lock_scope(Scope.CATALOG, retries=3, delay=4, applicant=context.env.get('orch_execution_id')):
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
                cp.stdout = f"Server{'s' if len(params.get('server_names', [])) > 1 else ''} " \
                            f"{', '.join(sorted(params.get('server_names', [])))} found"
            else:
                cp.success = False
                cp.stderr = f"Server{'s' if len(pending_names) > 1 else ''} {', '.join(sorted(pending_names))} " \
                            f"not created after {min_timeout} seconds"
        cp.set_end_time()
        return cp


class NativeDmRunningOperation(IOperationEncapsulation):

    def _execute(self, params: Kwargs, timeout=None, context: Context = None):
        start = time.time()
        running = []
        cp = CompletedProcess()
        cp.set_start_time()
        try:
            min_timeout = min(timeout, params.get('timeout', None))
        except TypeError:
            if timeout is not None:
                min_timeout = timeout
            elif params.get('timeout', None) is not None:
                min_timeout = params.get('timeout')
            else:
                min_timeout = defaults.MAX_TIME_WAITING_SERVERS

        pending_names = set(params.get('server_names', []))

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
            cp.stdout = f"Server{'s' if len(params.get('server_names', [])) > 1 else ''} " \
                        f"{', '.join(sorted(params.get('server_names', [])))} with dimensigon running"
        else:
            cp.success = False
            cp.stderr = f"Server{'s' if len(pending_names) > 1 else ''} {', '.join(sorted(pending_names))} " \
                        f"with dimensigon not running after {min_timeout} seconds"
        cp.set_end_time()
        return cp


class NativeDeleteOperation(IOperationEncapsulation):

    def _execute(self, params: Kwargs, timeout=None, context: Context = None):
        cp = CompletedProcess()
        cp.set_start_time()
        try:
            with lock_scope(Scope.CATALOG, retries=3, delay=4, applicant=context.env.get('orch_execution_id')):
                to_be_deleted = Server.query.filter(Server.name.in_(params.get('server_names', []))).all()
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
            cp.stderr = f"Unable to delete server{'s' if len(params.get('to_be_deleted', [])) > 1 else ''} " \
                        f"{', '.join([s.name for s in to_be_deleted])}. Exception: {e}"
        else:
            cp.success = True
            cp.stdout = f"Server{'s' if len(to_be_deleted) > 1 else ''} " \
                        f"{', '.join([s._old_name for s in to_be_deleted])} deleted"

        cp.set_end_time()
        return cp


# class PythonOperation(IOperationEncapsulation):
#     def execute(self, params: Kwargs, timeout=None, env=None) -> CompletedProcess:
#         byte_code = compile_restricted(self.code, '<inline>', 'exec')
#         safe_builtins.update(json=json)
#         safe_builtins.update(yaml=yaml)
#         safe_builtins.update(jinja2=jinja2)
#         safe_builtins.update(open=open)
#
#         cp = CompletedProcess()
#         cp.set_start_time()
#         _locals = dict(vc=var_context)
#
#         try:
#             exec(byte_code, {'__builtins__': safe_builtins, '_write_': lambda x: x, '_print_': PrintCollector}, _locals)
#         except Exception as e:
#             cp.stderr = format_exception(e)
#             cp.success = False
#         else:
#             cp.stdout = ''.join(getattr(_locals.get('_print', None), 'txt', []))
#             cp.success = True
#             cp.set_end_time()
#
#         return cp
#
# class PythonOperation(IOperationEncapsulation):
#
#     def _get_env(self, var_context):
#         env = dict(var_context)
#         if 'PATH' in os.environ:
#             env.update(PATH=os.environ.get('PATH'))
#         if 'PYTHONPATH' in os.environ:
#             env.update(PYTHONPATH=os.environ.get('PATH'))
#         if 'VIRTUAL_ENV' in os.environ:
#             env.update(VIRTUAL_ENV=os.environ.get('VIRTUAL_ENV'))
#         return env
#
#     def execute(self, params: Kwargs, timeout=None, env=None) -> CompletedProcess:
#         system_kwargs = self.system_kwargs.copy()
#
#         timeout = system_kwargs.pop('timeout', 300)
#
#         cp = CompletedProcess()
#         cp.set_start_time()
#
#         try:
#             r = subprocess.run(f"{sys.executable} -c {self.code}", shell=True, stdout=subprocess.PIPE,
#                                stderr=subprocess.PIPE,
#                                **system_kwargs, timeout=timeout, env=self._get_env(var_context))
#             cp.stdout = r.stdout.decode() if isinstance(r.stdout, bytes) else r.stdout
#             cp.stderr = r.stderr.decode() if isinstance(r.stderr, bytes) else r.stderr
#             cp.rc = r.returncode
#         except (subprocess.TimeoutExpired, ValueError) as e:
#             cp.stderr = f"{e.__class__.__name__}{e.args}"
#             cp.success = False
#         finally:
#             cp.set_end_time()
#
#         self.evaluate_result(cp)
#
#         return cp


class ShellOperation(IOperationEncapsulation):
    #
    # def _get_env(self, params):
    #     env = {}
    #     for k, v in dict(params).items():
    #         if isinstance(dict, v):
    #             env.update({k: json.dumps(v)})
    #         else:
    #             env.update({k: str(v)})
    #     env.update(**os.environ)
    #     return env

    def _execute(self, params: Kwargs, timeout=None, context: Context = None) -> CompletedProcess:
        tokens = self.rpl_params(params, context.env)

        system_kwargs = self.system_kwargs.copy()

        shebang = system_kwargs.pop('shebang', '/bin/bash')
        user = system_kwargs.pop('run_as', None)
        timeout = system_kwargs.pop('timeout', None)

        cp = CompletedProcess()
        cp.set_start_time()
        tmp = tempfile.NamedTemporaryFile('w', delete=False)
        tmp.write(f"#!{shebang}\n")
        tmp.write(tokens)
        tmp.close()
        os.chmod(tmp.name, stat.S_IEXEC | stat.S_IREAD | stat.S_IWRITE)
        r = None

        if user:
            cmd = f"sudo -niu {user} {tmp.name}"
        else:
            cmd = tmp.name
        try:
            r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
            cp.stdout = r.stdout.decode() if isinstance(r.stdout, bytes) else r.stdout
            cp.stderr = r.stderr.decode() if isinstance(r.stderr, bytes) else r.stderr
            cp.rc = r.returncode
        except subprocess.TimeoutExpired as e:
            cp.stderr = str(e)
            cp.success = False
        finally:
            os.remove(tmp.name)
            cp.set_end_time()

        self.evaluate_result(cp, context)

        return cp


class OrchestrationOperation(IOperationEncapsulation):

    def execute(self, params: Kwargs, timeout=None, context: Context = None) -> CompletedProcess:
        from dimensigon.use_cases.deployment import deploy_orchestration

        cp = CompletedProcess().set_start_time()
        # Validation
        orchestration_id = params.get('orchestration_id', None)
        if orchestration_id is None:
            cp.stderr = "No orchestration_id specified"
            cp.success = False
            cp.set_end_time()
            return cp
        orch = Orchestration.query.get(orchestration_id)
        if orch is None:
            cp.stderr = str(errors.EntityNotFound('Orchestration', orchestration_id))
            cp.success = False
            cp.set_end_time()
            return cp

        hosts = params.get('hosts', None)
        if hosts is None:
            cp.stderr = "No hosts specified"
            cp.success = False
            cp.set_end_time()
            return cp
        hosts = copy.deepcopy(hosts)
        if isinstance(hosts, list):
            hosts = {'all': hosts}
        elif isinstance(hosts, str):
            hosts = {'all': [hosts]}
        not_found = normalize_hosts(hosts)
        if not_found:
            cp.stderr = str(errors.ServerNormalizationError(not_found))
            cp.success = False
            return cp

        exe = OrchExecution(orchestration_id=orchestration_id,
                            target=hosts,
                            params=params,
                            executor_id=context.env['executor_id'],
                            server=Server.get_current(),
                            parent_step_execution_id=context.env['step_execution_id'])
        db.session.add(exe)
        db.session.commit()

        cp.stdout = f"orch_execution_id={exe.id}"

        ctx = Context(params,
                      dict(parent_orch_execution_id=context.env['orch_execution_id'],
                           orch_execution_id=exe.id,
                           executor_id=context.env['executor_id']))
        try:
            deploy_orchestration(orchestration=orchestration_id, hosts=hosts, var_context=ctx, execution=exe)
        except Exception as e:
            cp.stderr = str(e) if str(e) else e.__class__.__name__
            cp.success = False
        else:
            context.merge_ctx(ctx)
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
        if step.action_template.id == '00000000-0000-0000-000a-000000000001':
            kls = NativeSoftwareSendOperation
        elif step.action_template.id == '00000000-0000-0000-000a-000000000002':
            kls = NativeWaitOperation
        elif step.action_template.id == '00000000-0000-0000-000a-000000000004':
            kls = NativeDmRunningOperation
        elif step.action_template.id == '00000000-0000-0000-000a-000000000005':
            kls = NativeDeleteOperation
    return kls(code=step.code, expected_stdout=step.expected_stdout, expected_stderr=step.expected_stderr,
               expected_rc=step.expected_rc,
               system_kwargs=step.system_kwargs)
