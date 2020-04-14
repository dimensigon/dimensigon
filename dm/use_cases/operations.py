import re
import subprocess
from abc import ABC, abstractmethod
from datetime import datetime

from dataclasses import dataclass

from dm.utils.helpers import convert
from dm.utils.typos import Kwargs


@dataclass
class CompletedProcess:
    success: bool = None
    stdout: str = None
    stderr: str = None
    rc: int = None
    start_time: datetime = None
    end_time: datetime = None


L_DELIMITER_VAR = '{'
R_DELIMITER_VAR = '}'


class IOperationEncapsulation(ABC):

    def __init__(self, code: str, expected_output: str = None, expected_rc: int = None, system_kwargs: Kwargs = None):
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
    def execute(self, params: Kwargs, timeout=None) -> CompletedProcess:
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


class AnsibleOperation(IOperationEncapsulation):
    def execute(self, params: Kwargs, timeout=None) -> CompletedProcess:
        _params = convert(params)
        tokens = self.code.split()
        cp = CompletedProcess()

        for i in range(len(tokens)):
            if tokens[i][0:len(L_DELIMITER_VAR)] == L_DELIMITER_VAR and tokens[i][
                                                                        -len(R_DELIMITER_VAR):] == R_DELIMITER_VAR:
                try:
                    tokens[i] = eval('_params.' + str(tokens[i][len(L_DELIMITER_VAR):-len(R_DELIMITER_VAR)]))
                except KeyError:
                    raise LookupError(
                        f"Unable to find variable '{str(tokens[i][len(L_DELIMITER_VAR):-len(R_DELIMITER_VAR)])}'")

        cp.start_time = datetime.now()
        system_kwargs = self.system_kwargs.copy()

        tokens = ('ansible-playbook', '-i', '"localhost,"', '-c', 'local') + tuple(tokens)
        try:
            cp.rc, cp.stdout, cp.stderr = subprocess.run(tokens, shell=True, capture_output=True,
                                                         **system_kwargs, timeout=timeout)
        except (subprocess.TimeoutExpired, ValueError) as e:
            cp.stderr = f"{e.__class__.__name__}{e.args}"
            cp.success = False
        finally:
            cp.end_time = datetime.now()

        if cp.success is None:
            if self.expected_output is not None and self.expected_rc is not None:
                if re.search(self.expected_output, cp.stdout) \
                        and cp.rc == self.expected_rc:
                    cp.success = True
            elif self.expected_output is not None:
                if re.search(self.expected_output, cp.stdout):
                    cp.success = True
            elif self.expected_rc is not None:
                if cp.rc == self.expected_rc:
                    cp.success = True
            else:
                cp.success = True

        return cp


class PythonOperation(IOperationEncapsulation):
    def execute(self, params: Kwargs, timeout=None) -> CompletedProcess:
        pass


class NativeOperation(IOperationEncapsulation):

    def execute(self, params: Kwargs, timeout=None) -> CompletedProcess:
        _params = convert(params)
        tokens = self.code.split()
        cp = CompletedProcess()

        for i in range(len(tokens)):
            if tokens[i][0:len(L_DELIMITER_VAR)] == L_DELIMITER_VAR and tokens[i][
                                                                        -len(R_DELIMITER_VAR):] == R_DELIMITER_VAR:
                try:
                    tokens[i] = eval('_params.' + str(tokens[i][len(L_DELIMITER_VAR):-len(R_DELIMITER_VAR)]))
                except KeyError:
                    raise LookupError(
                        f"Unable to find variable '{str(tokens[i][len(L_DELIMITER_VAR):-len(R_DELIMITER_VAR)])}'")

        cp.start_time = datetime.now()
        system_kwargs = self.system_kwargs.copy()

        timeout = system_kwargs.pop('timeout', 300)

        try:
            cp.rc, cp.stdout, cp.stderr = subprocess.run(tokens, shell=True, capture_output=True,
                                                         **system_kwargs, timeout=timeout)
        except (subprocess.TimeoutExpired, ValueError) as e:
            cp.stderr = f"{e.__class__.__name__}{e.args}"
            cp.success = False
        finally:
            cp.end_time = datetime.now()

        if cp.success is None:
            if self.expected_output is not None and self.expected_rc is not None:
                if re.search(self.expected_output, cp.stdout) \
                        and cp.rc == self.expected_rc:
                    cp.success = True
            elif self.expected_output is not None:
                if re.search(self.expected_output, cp.stdout):
                    cp.success = True
            elif self.expected_rc is not None:
                if cp.rc == self.expected_rc:
                    cp.success = True
            else:
                cp.success = True

        return cp


class OrchestrationOperation(IOperationEncapsulation):

    def execute(self, params: Kwargs, timeout=None) -> CompletedProcess:
        pass
