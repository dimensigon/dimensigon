import inspect
import os
import re
import subprocess
import sys
import typing as t
from abc import ABC, abstractmethod
from datetime import datetime

import jinja2
from dataclasses import dataclass

from dm.utils.typos import Kwargs

if t.TYPE_CHECKING:
    from dm.domain.entities import Step


@dataclass
class CompletedProcess:
    success: bool = None
    stdout: t.Union[str, bytes] = None
    stderr: t.Union[str, bytes] = None
    rc: int = None
    start_time: datetime = None
    end_time: datetime = None

    def set_start_time(self):
        self.start_time = datetime.now()

    def set_end_time(self):
        self.end_time = datetime.now()


class IOperationEncapsulation(ABC):

    def __init__(self, code: str, expected_stdout: str = None, expected_stderr: str = None, expected_rc: int = None,
                 system_kwargs: Kwargs = None, path: str = None):
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
        self.path = path or '.'

    def load_code(self):
        return

    @abstractmethod
    def execute(self, params: Kwargs, timeout=None) -> CompletedProcess:
        """
        StepExecution process
        Parameters
        ----------
        params:
            params to be passed through the execution

        Returns
        -------
        StepExecution:
            dataclass containing all the information from the result execution
        """

    def rpl_params(self, params):
        template = jinja2.Template(self.code)
        return template.render(params)

    def evaluate_result(self, cp: CompletedProcess):
        if cp.success is None:
            res = []
            if self.expected_stdout is not None:
                res.append(True) if re.search(self.expected_stdout, cp.stdout) else res.append(False)
            if self.expected_stderr is not None:
                res.append(True) if re.search(self.expected_stderr, cp.stderr) else res.append(False)
            if self.expected_rc is not None:
                res.append(True) if self.expected_rc == cp.rc else res.append(False)
            cp.success = all(res)
        return cp

class AnsibleOperation(IOperationEncapsulation):
    def execute(self, params: Kwargs, timeout=None) -> CompletedProcess:
        code = self.code
        if re.match(r'^[^<>:;,?"*|/\\]+$', self.code):
            file = os.path.join('', 'ansible', self.code)
            if os.path.exists(file):
                with open(file, 'r') as fh:
                    code = fh.read()

        template = self.rpl_params(params)

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




class PythonOperation(IOperationEncapsulation):
    def execute(self, params: Kwargs, timeout=None) -> CompletedProcess:
        pass


class ShellOperation(IOperationEncapsulation):

    def execute(self, params: Kwargs, timeout=None) -> CompletedProcess:
        tokens = self.rpl_params(params)

        system_kwargs = self.system_kwargs.copy()

        timeout = system_kwargs.pop('timeout', 300)

        cp = CompletedProcess()
        cp.set_start_time()
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

        return self.evaluate_result(cp)




class OrchestrationOperation(IOperationEncapsulation):

    def execute(self, params: Kwargs, timeout=None) -> CompletedProcess:
        pass


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
    cls = _factories[step.type]

    return cls(code=step.code, expected_stdout=step.expected_stdout, expected_stderr=step.expected_stderr,
               expected_rc=step.expected_rc,
               system_kwargs=step.system_kwargs)
