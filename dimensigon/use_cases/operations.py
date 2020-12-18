import copy
import datetime as dt
import functools
import inspect
import os
import re
import signal
import sqlite3
import sys
import tempfile
import time
import typing as t
from abc import ABC, abstractmethod

import flask
import jinja2
import requests
from dataclasses import dataclass
from flask import json
from packaging.version import parse

from dimensigon import defaults
from dimensigon.domain.entities import Step, Server, Software, OrchExecution, Orchestration, Scope, Route, StepExecution
from dimensigon.use_cases.lock import lock_scope
from dimensigon.utils import subprocess
from dimensigon.utils.helpers import get_now, is_iterable_not_string, format_exception, is_valid_uuid
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
            return CompletedProcess(success=False,
                                    stderr=f"Error creating execution: {format_exception(e)}",
                                    start_time=start,
                                    end_time=get_now())

    def rpl_params(self, **context):
        template = jinja2.Template(self.code)
        return template.render(**context)

    def evaluate_result(self, cp: CompletedProcess, context=None):
        if cp.success is None:
            res = []
            if self.expected_stdout is not None:
                if isinstance(cp.stdout, str):
                    match = re.search(self.expected_stdout, cp.stdout)
                    if match:
                        res.append(True)
                        if context:
                            for k, v in match.groupdict().items():
                                context.set(k, v)
                    else:
                        res.append(False)
            if self.expected_stderr is not None:
                if isinstance(cp.stderr, str):
                    match = re.search(self.expected_stderr, cp.stderr)
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

# TODO: make a test case
class RequestOperation(IOperationEncapsulation):

    def _execute(self, params: Kwargs, timeout=None, context: Context = None) -> CompletedProcess:
        kwargs = json.loads(self.rpl_params(params))
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
        input_params = params['input']
        cp = CompletedProcess()
        cp.set_start_time()

        # common parameters
        kwargs = self.system_kwargs
        kwargs['timeout'] = timeout or kwargs.get('timeout')

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

        software = input_params.get('software', None)
        if is_valid_uuid(software):
            soft = Software.query.get(software)
            if not soft:
                cp.stderr = f"software id '{software}' not found"
                cp.success = False
                cp.set_end_time()
                return cp
        else:
            version = input_params.get('version', None)
            if version:
                parsed_ver = parse(str(version))
                soft_list = [s for s in Software.query.filter_by(name=software).all() if s.parsed_version == parsed_ver]
            else:
                soft_list = sorted(Software.query.filter_by(name=software).all(), key=lambda x: x.parsed_version)
            if soft_list:
                soft = soft_list[-1]
            else:
                cp.stderr = f"No software found for '{software}'" + (f" and version '{version}'" if version else "")
                cp.success = False
                cp.set_end_time()
                return cp

        if not soft.ssas:
            cp.stderr = f"{soft.id} has no server association"
            cp.success = False
            cp.set_end_time()
            return cp

        # Server validation
        server = input_params.get('server', None)
        if is_valid_uuid(server):
            dest_server = Server.query.get(server)
        else:
            dest_server = Server.query.filter_by(name=server).one_or_none()
        if not dest_server:
            cp.stderr = f"destination server {'id ' if is_valid_uuid(server) else ''}'{server}' not found"
            cp.success = False
            cp.set_end_time()
            return cp

        # decide best server source
        resp = ntwrk.get(dest_server, 'api_1_0.routes', timeout=10)
        if resp.code == 200:
            ssas = copy.copy(soft.ssas)
            ssas.sort(key=functools.partial(search_cost, route_list=resp.msg['route_list']))
        else:
            ssas = soft.ssas
        server = ssas[0].server

        # Process kwargs
        data = {'software_id': soft.id, 'dest_server_id': dest_server.id, "background": False,
                "include_transfer_data": True, "force": True}
        if input_params.get('dest_path', None):
            data.update(dest_path=input_params.get('dest_path', None))
        if input_params.get('chunk_size', None):
            data.update(chunk_size=input_params.get('chunk_size', None))
        if input_params.get('max_senders', None):
            data.update(max_senders=input_params.get('max_senders', None))
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
        input_params = params['input']
        start = time.time()
        found = []
        cp = CompletedProcess()
        cp.set_start_time()
        timeout = input_params.get('timeout')
        if timeout is None:
            timeout = self.system_kwargs.get('timeout')
        if timeout is None:
            timeout = defaults.MAX_TIME_WAITING_SERVERS

        try:
            now = get_now()
            server_names = input_params.get('server_names', [])
            if not is_iterable_not_string(server_names):
                server_names = [server_names]

            if not server_names:
                cp.success = False
                cp.stderr = f"No server to wait"
                cp.set_end_time()
                return cp

            pending_names = set(server_names)
            with lock_scope(Scope.CATALOG, retries=3, delay=4, applicant=context.env.get('orch_execution_id')):
                while len(pending_names) > 0:
                    try:
                        found_names = db.session.query(Server.name).filter(Server.name.in_(pending_names)).filter(
                            Server.created_on >= now).all()
                    except sqlite3.OperationalError as e:
                        if str(e) == 'database is locked':
                            found_names = []
                        else:
                            raise
                    found_names = set([t[0] for t in found_names])
                    pending_names = pending_names - found_names
                    if pending_names and (time.time() - start) < timeout:
                        time.sleep(self.system_kwargs.get('sleep_time', 15))
                    else:
                        break
        except errors.LockError as e:
            cp.success = False
            cp.stderr = str(e)

        else:
            if not pending_names:
                cp.success = True
                cp.stdout = f"Server{'s' if len(server_names) > 1 else ''} " \
                            f"{', '.join(sorted(server_names))} found"
            else:
                cp.success = False
                cp.stderr = f"Server{'s' if len(pending_names) > 1 else ''} {', '.join(sorted(pending_names))} " \
                            f"not created after {timeout} seconds"
        cp.set_end_time()
        return cp

# TODO: make a test case
class NativeDmRunningOperation(IOperationEncapsulation):

    def _execute(self, params: Kwargs, timeout=None, context: Context = None):
        input_params = params['input']
        start = time.time()
        running = []
        cp = CompletedProcess()
        cp.set_start_time()
        try:
            min_timeout = min(timeout, input_params.get('timeout', None))
        except TypeError:
            if timeout is not None:
                min_timeout = timeout
            elif input_params.get('timeout', None) is not None:
                min_timeout = input_params.get('timeout')
            else:
                min_timeout = defaults.MAX_TIME_WAITING_SERVERS

        server_names = input_params.get('server_names', [])
        if not is_iterable_not_string(server_names):
            server_names = [server_names]

        if not server_names:
            cp.success = False
            cp.stdout = f"No server to wait for DM running"
            cp.set_end_time()
            return cp
        pending_names = set(server_names)
        found_names = []
        while len(pending_names) > 0:
            try:
                found_names = db.session.query(Server.name).join(Route, Route.destination_id == Server.id).filter(
                    Server.name.in_(pending_names)).filter(Route.cost.isnot(None)).order_by(Server.name).all()
            except sqlite3.OperationalError as e:
                if str(e) == 'database is locked':
                    pass
                else:
                    raise
            found_names = set([t[0] for t in found_names])
            pending_names = pending_names - found_names
            if pending_names and (time.time() - start) < min_timeout:
                time.sleep(self.system_kwargs.get('sleep_time', 15))
            else:
                break

        if not pending_names:
            cp.success = True
            cp.stdout = f"Server{'s' if len(server_names) > 1 else ''} " \
                        f"{', '.join(sorted(server_names))} with dimensigon running"
        else:
            cp.success = False
            cp.stderr = f"Server{'s' if len(pending_names) > 1 else ''} {', '.join(sorted(pending_names))} " \
                        f"with dimensigon not running after {min_timeout} seconds"
        cp.set_end_time()
        return cp

# TODO: make a test case
class NativeDeleteOperation(IOperationEncapsulation):

    def _execute(self, params: Kwargs, timeout=None, context: Context = None):
        input_params = params['input']
        cp = CompletedProcess()
        cp.set_start_time()
        try:
            with lock_scope(Scope.CATALOG, retries=3, delay=4, applicant=context.env.get('orch_execution_id')):
                server_names = input_params.get('server_names', [])
                if not is_iterable_not_string(server_names):
                    server_names = [server_names]
                to_be_deleted = Server.query.filter(Server.name.in_(server_names)).all()

                for s in to_be_deleted:
                    # remove associated routes
                    db.session.delete(s.route)
                    s.delete()
                    db.session.commit()

        except errors.LockError as e:
            cp.success = False
            cp.stderr = str(e)
        except Exception as e:
            cp.success = False
            cp.stderr = f"Unable to delete server{'s' if len(input_params.get('to_be_deleted', [])) > 1 else ''} " \
                        f"{', '.join([s.name for s in to_be_deleted])}. Exception: {e}"
        else:
            cp.success = True
            cp.stdout = f"Server{'s' if len(to_be_deleted) > 1 else ''} " \
                        f"{', '.join([s._old_name for s in to_be_deleted])} deleted"

        cp.set_end_time()
        return cp


class ShellOperation(IOperationEncapsulation):

    def _execute(self, params: Kwargs, timeout=None, context: Context = None) -> CompletedProcess:
        tokens = self.rpl_params(**params, env=context.env)

        system_kwargs = self.system_kwargs.copy()

        shebang = system_kwargs.pop('shebang', '/bin/bash')
        user = system_kwargs.pop('run_as', None)
        timeout = system_kwargs.pop('timeout', timeout)
        if timeout and not isinstance(timeout, float):
            try:
                timeout = float(timeout)
            except:
                timeout = None
        cp = CompletedProcess()
        cp.set_start_time()
        tmp = tempfile.NamedTemporaryFile('w', delete=False, suffix='.' + os.path.basename(shebang))
        tmp.write(f"#!{shebang}\n")
        tmp.write(tokens)
        tmp.close()
        os.chmod(tmp.name, 0o755)
        out_fh = open(tmp.name + '.out', 'w')

        if user:
            cmd = f"sudo -niu {user} {tmp.name}"
        else:
            cmd = tmp.name

        with subprocess.Popen(cmd, stdout=out_fh, stderr=subprocess.STDOUT, encoding='utf-8',
                              shell=True) as p:
            try:
                p.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                subprocess.run(f"sudo -u {user} kill {p.pid}", shell=True) if user else p.terminate()
                try:
                    p.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    subprocess.run(f"sudo -u {user} kill -9 {p.pid}", shell=True) if user else os.kill(p.pid,
                                                                                                       signal.SIGKILL)
                    p.communicate()
                    cp.stderr = f"Timeout of {timeout} seconds while executing shell"
                    cp.success = False
                except Exception as e:
                    subprocess.run(f"sudo -u {user} kill -9 {p.pid}", shell=True) if user else os.kill(p.pid,
                                                                                                       signal.SIGKILL)
                    cp.stderr = f"Error waiting process {p.pid} to terminate\n{format_exception(e)}"
                    cp.success = False
                else:
                    cp.stderr = f"Timeout of {timeout} seconds while executing shell"
                    cp.success = False
            except Exception as e:
                subprocess.run(f"sudo -u {user} kill -9 {p.pid}", shell=True) if user else os.kill(p.pid,
                                                                                                   signal.SIGKILL)
                p.communicate()
                cp.stderr += "\n" + format_exception(e)

            cp.rc = p.poll()
            out_fh.close()
            with open(tmp.name + '.out', 'r') as fh:
                cp.stdout = fh.read()

        try:
            os.remove(tmp.name)
        except:
            pass

        try:

            os.remove(tmp.name + '.out')
        except:
            pass
        cp.set_end_time()

        self.evaluate_result(cp, context)

        return cp

# TODO: make a test case
class OrchestrationOperation(IOperationEncapsulation):

    def _execute(self, params: Kwargs, timeout=None, context: Context = None) -> CompletedProcess:
        from dimensigon.use_cases.deployment import deploy_orchestration
        input_params = params['input']
        cp = CompletedProcess().set_start_time()
        # Validation
        orchestration = Orchestration.get(input_params.pop('orchestration', None), input_params.pop('version', None))
        if not isinstance(orchestration, Orchestration):
            cp.stderr = orchestration
            cp.success = False
            return cp.set_end_time()

        hosts = input_params.pop('hosts', None)
        if hosts is None:
            cp.stderr = "No hosts specified"
            cp.success = False
            return cp.set_end_time()
        hosts = copy.deepcopy(hosts)
        if isinstance(hosts, list):
            hosts = {'all': hosts}
        elif isinstance(hosts, str):
            hosts = {'all': [hosts]}
        not_found = normalize_hosts(hosts)
        if not_found:
            cp.stderr = str(errors.ServerNormalizationError(not_found))
            cp.success = False
            return cp.set_end_time()

        o_exe = OrchExecution(orchestration_id=orchestration.id,
                              target=hosts,
                              params=input_params,
                              executor_id=context.env.get('executor_id'),
                              server_id=context.env.get('server_id'),
                              parent_step_execution_id=context.env.get('step_execution_id'))
        db.session.add(o_exe)
        se = StepExecution.query.get(context.env.get('step_execution_id'))
        if se:
            se.child_orch_execution_id = o_exe.id
        db.session.commit()

        cp.stdout = f"orch_execution_id={o_exe.id}"

        env = dict(context.env)
        env.update(root_orch_execution_id=context.env['root_orch_execution_id'],
                   orch_execution_id=o_exe.id,
                   executor_id=context.env['executor_id'])
        ctx = Context(input_params, env, vault=context.vault)
        try:
            deploy_orchestration(orchestration=orchestration, hosts=hosts, var_context=ctx, execution=o_exe,
                                 timeout=timeout)
        except Exception as e:
            cp.stderr = str(e) if str(e) else e.__class__.__name__
            cp.success = False
        else:
            context.merge_ctx(ctx)
            db.session.refresh(o_exe)
            cp.success = o_exe.success
        return cp.set_end_time()


class TestOperation(IOperationEncapsulation):

    def _execute(self, params: Kwargs, timeout=None, context: Context = None) -> CompletedProcess:
        tokens = self.rpl_params(**params, env=context.env)
        return CompletedProcess(success=True, stdout=tokens, rc=0, start_time=get_now(), end_time=get_now())

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
