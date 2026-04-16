"""
AI-Powered Troubleshooting for failed step executions.

Provides rule-based failure analysis with common error pattern matching.
When an AI backend is available, TROUBLESHOOT_PROMPT can be sent to an LLM
for deeper analysis.
"""

import re


# ---------------------------------------------------------------------------
# Prompt template for use with an AI backend (LLM) when one is available
# ---------------------------------------------------------------------------

TROUBLESHOOT_PROMPT = """\
You are an expert DevOps troubleshooter for the Dimensigon orchestration platform.

A step execution has failed with the following details:

Orchestration: {orchestration_name}
Step: {step_name}
Server: {server_name}
Command: {command}
Return code: {rc}
STDOUT:
{stdout}
STDERR:
{stderr}

Analyze the failure and respond in JSON with exactly these fields:
- root_cause: a concise explanation of why the command failed
- suggestion: actionable steps the operator should take to fix it
- confidence: "high", "medium", or "low"
- modified_command: a corrected version of the command that would likely succeed, \
or null if no simple fix is possible
"""


# ---------------------------------------------------------------------------
# Rule-based error patterns
# ---------------------------------------------------------------------------

_ERROR_RULES = [
    {
        'pattern': re.compile(r'permission denied', re.IGNORECASE),
        'root_cause': 'The command failed due to insufficient permissions.',
        'suggestion': (
            'Run the command with elevated privileges (sudo) or adjust '
            'file/directory permissions with chmod/chown.'
        ),
        'confidence': 'high',
        'fix': lambda cmd: f'sudo {cmd}' if not cmd.strip().startswith('sudo') else None,
    },
    {
        'pattern': re.compile(r'command not found', re.IGNORECASE),
        'root_cause': 'The command or binary is not installed or not in PATH.',
        'suggestion': (
            'Install the missing package or specify the full path to the '
            'executable. Verify PATH includes the binary location.'
        ),
        'confidence': 'high',
        'fix': lambda cmd: None,
    },
    {
        'pattern': re.compile(r'no such file or directory', re.IGNORECASE),
        'root_cause': 'A referenced file or directory does not exist.',
        'suggestion': (
            'Verify the file/directory path is correct. Ensure prerequisite '
            'steps have created the expected files before this step runs.'
        ),
        'confidence': 'high',
        'fix': lambda cmd: None,
    },
    {
        'pattern': re.compile(r'connection refused', re.IGNORECASE),
        'root_cause': 'The target service refused the connection.',
        'suggestion': (
            'Check that the target service is running and listening on the '
            'expected port. Verify firewall rules allow the connection.'
        ),
        'confidence': 'high',
        'fix': lambda cmd: None,
    },
    {
        'pattern': re.compile(r'connection timed out|timed?\s*out|timeout', re.IGNORECASE),
        'root_cause': 'The operation timed out waiting for a response.',
        'suggestion': (
            'Increase the timeout value, check network connectivity to the '
            'target host, and verify the remote service is responsive.'
        ),
        'confidence': 'medium',
        'fix': lambda cmd: None,
    },
    {
        'pattern': re.compile(r'disk\s+full|no space left on device', re.IGNORECASE),
        'root_cause': 'The target filesystem has run out of disk space.',
        'suggestion': (
            'Free up disk space on the target server. Check for large log '
            'files, temporary files, or unused packages that can be removed.'
        ),
        'confidence': 'high',
        'fix': lambda cmd: None,
    },
    {
        'pattern': re.compile(r'name or service not known|could not resolve', re.IGNORECASE),
        'root_cause': 'DNS resolution failed for the target hostname.',
        'suggestion': (
            'Verify the hostname is correct and DNS is properly configured. '
            'Check /etc/resolv.conf and try using an IP address instead.'
        ),
        'confidence': 'high',
        'fix': lambda cmd: None,
    },
    {
        'pattern': re.compile(r'authentication fail|login fail|access denied|unauthorized', re.IGNORECASE),
        'root_cause': 'Authentication or authorization failed.',
        'suggestion': (
            'Verify the credentials are correct and the account has not been '
            'locked. Check that the user has the required privileges.'
        ),
        'confidence': 'high',
        'fix': lambda cmd: None,
    },
    {
        'pattern': re.compile(r'syntax error|unexpected token|parse error', re.IGNORECASE),
        'root_cause': 'The command or script contains a syntax error.',
        'suggestion': (
            'Review the command for typos, missing quotes, or incorrect '
            'shell syntax. Test the command manually before re-running.'
        ),
        'confidence': 'medium',
        'fix': lambda cmd: None,
    },
    {
        'pattern': re.compile(r'killed|out of memory|oom|cannot allocate memory', re.IGNORECASE),
        'root_cause': 'The process was killed, likely due to insufficient memory.',
        'suggestion': (
            'Increase available memory on the target server or reduce the '
            'memory footprint of the command. Check system OOM logs.'
        ),
        'confidence': 'medium',
        'fix': lambda cmd: None,
    },
]


def analyze_failure(step_data):
    """Analyze a failed step execution and return troubleshooting advice.

    Parameters
    ----------
    step_data : dict
        Must contain at least some of these keys:
        - command (str): the command that was executed
        - stdout (str): captured standard output
        - stderr (str): captured standard error
        - rc (int): return code
        - server_name (str): name of the server where the step ran
        - step_name (str): human-readable step label
        - orchestration_name (str): name of the parent orchestration

    Returns
    -------
    dict
        {
            'root_cause': str,
            'suggestion': str,
            'confidence': 'high' | 'medium' | 'low',
            'modified_command': str | None,
        }
    """
    command = step_data.get('command') or ''
    stdout = step_data.get('stdout') or ''
    stderr = step_data.get('stderr') or ''
    rc = step_data.get('rc')

    # Combine output for pattern searching
    combined_output = f'{stdout}\n{stderr}'.strip()

    # Walk through rules in priority order
    for rule in _ERROR_RULES:
        if rule['pattern'].search(combined_output):
            modified_command = rule['fix'](command) if command else None
            return {
                'root_cause': rule['root_cause'],
                'suggestion': rule['suggestion'],
                'confidence': rule['confidence'],
                'modified_command': modified_command,
            }

    # Fallback: no known pattern matched
    fallback = {
        'root_cause': f'The command exited with return code {rc}.',
        'suggestion': (
            'Review the command output above for error details. '
            'Try running the command manually on the target server to reproduce '
            'and diagnose the issue.'
        ),
        'confidence': 'low',
        'modified_command': None,
    }

    # If rc is 0 but marked as failed, note the anomaly
    if rc is not None and rc == 0:
        fallback['root_cause'] = (
            'The command returned exit code 0 but was marked as failed. '
            'This may indicate a post-processing validation failure.'
        )
        fallback['suggestion'] = (
            'Check the orchestration step post-process logic. The command '
            'itself succeeded but the output may not match expected patterns.'
        )
        fallback['confidence'] = 'medium'

    return fallback
