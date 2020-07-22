import copy
import functools
import inspect
import os
import re
import sys
import time
import typing as t
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

import flask
import jinja2
import requests
from flask import json
from flask_jwt_extended import create_access_token, get_jwt_identity

from dm import defaults
from dm.domain.entities import Step, Server, Software, OrchExecution
from dm.network.auth import HTTPBearerAuth
from dm.utils import subprocess
from dm.utils.helpers import get_now
from dm.utils.typos import Kwargs
from dm.utils.var_context import VarContext
from dm.web import db, errors
from dm.web.helpers import normalize_hosts
from dm.web.network import request, get


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

    def execute(self, var_context: VarContext, timeout=None) -> CompletedProcess:
        code = self.code
        if re.match(r'^[^<>:;,?"*|/\\]+$', self.code):
            file = os.path.join('', 'ansible', self.code)
            if os.path.exists(file):
                with open(file, 'r') as fh:
                    code = fh.read()

        template = self.rpl_params(dict(var_context))

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

    def execute(self, var_context: VarContext, timeout=None) -> CompletedProcess:
        params_dict = dict(var_context)
        kwargs = json.loads(self.rpl_params(params_dict))
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

    def execute(self, var_context: VarContext, timeout=None):
        pass


class NativeWaitOperation(IOperationEncapsulation):

    def execute(self, var_context: VarContext, timeout=None):
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
        for sn in var_context.get('list_server_names', []):
            count = db.session.query(Server).filter_by(name=sn).count()
            if count == 1:
                found.append(sn)
                continue
            while (time.time() - start) < min_timeout:
                count = db.session.query(Server).filter_by(name=sn).count()
                if count == 0:
                    time.sleep(self.system_kwargs.get('sleep_time', 2))
                else:
                    found.append(sn)
                    break

        if var_context.get('list_server_names', []) == found:
            cp.success = True
            cp.stdout = f"Servers {', '.join(var_context.get('list_server_names', []))} found"
        else:
            cp.success = False
            not_found = set(var_context['list_server_names']) - set(found)
            cp.stderr = f"Servers {', '.join(not_found)} not created after {min_timeout} seconds"
        cp.set_end_time()
        return cp


class PythonOperation(IOperationEncapsulation):
    def execute(self, var_context: VarContext, timeout=None) -> CompletedProcess:
        pass


class ShellOperation(IOperationEncapsulation):

    def execute(self, var_context: VarContext, timeout=None) -> CompletedProcess:
        tokens = self.rpl_params(dict(var_context))

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
        from dm.web.async_functions import deploy_orchestration

        exe = OrchExecution(orchestration_id=var_context.get('orchestration_id'),
                            target=var_context.get('hosts'),
                            params=dict(var_context),
                            parent_orch_execution_id=var_context.globals.get('execution_id'),
                            executor_id=var_context.globals.get('executor_id'),
                            server=Server.get_current())
        db.session.add(exe)
        db.session.commit()
        cp = CompletedProcess().set_start_time()
        hosts = copy.deepcopy(var_context.get('hosts'))
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

        return cp.set_end_time()


from dm.domain.entities import ActionType

_operation_classes = {}
for name, cls in inspect.getmembers(sys.modules['dm.use_cases.operations'],
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
        if step.action_template.name == 'wait':
            kls = NativeWaitOperation
    return kls(code=step.code, expected_stdout=step.expected_stdout, expected_stderr=step.expected_stderr,
               expected_rc=step.expected_rc,
               system_kwargs=step.system_kwargs)
