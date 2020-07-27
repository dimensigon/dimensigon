"""
Usage: dshell action list [--id ID|--name NAME|--like LIKE] [--version N] [--last N]
       dshell action create (- | FILE)
       dshell action create NAME ACTION_TYPE [--code CODE] [--parameters DATA] [--expected-stdout OUT]
                            [--expected-stderr ERR] [--expected-rc RC] [--system-kwargs DATA]
                            [--pre-process CODE] [--post-process CODE]

Command to interact with action templates

Arguments:
    ACTION_TYPE     Type of action templates. Available: ANSIBLE, PYTHON, SHELL, ORCHESTRATION, REQUEST
    NAME            Action template name

Options:
    --code CODE             Code to execute
    --expected-rc RC        Expected return code from execution
    --expected-stderr ERR   Expected err output from execution
    --expected-stdout OUT   Expected output from execution
    --id ID                 Action template id to show
    --last N                Shows last N servers
    --like LIKE             List action templates whose names contain LIKE
    --name NAME             Action templates' name to list
    --parameters DATA       Parameters passed to the code
    --post-process POST     Code executed after CODE execution
    --pre-process PRE       Code executed before CODE execution
    --system-kwargs DATA    Special parameters passed to python command call
    --version N             Versions to list
"""
import json
import sys
from pprint import pprint

from docopt import docopt
from schema import Schema, Or, And, Use, SchemaError

import dimensigon.dshell.network as ntwrk
from dimensigon.dshell.commands import action_list
from dimensigon.dshell.utils import clean_none

action_template_schema = Schema(
    {'ACTION_TYPE': Or(None, And(lambda x: x in ['ANSIBLE', 'PYTHON', 'SHELL', 'ORCHESTRATION', 'REQUEST'],
                                 error="Not a valid action type. See 'dshell help action' for more details")),
     'FILE': Or(None, Use(open, error="Unable to open file. File not found")),
     '--expected-rc': Or(None,
                         And(Use(int, error="Not a valid integer"),
                             And(lambda n: 0 <= n <= 255,
                                 error="integer must be between 0 and 255"))),
     '--last': Or(None, And(Use(int, error="Not a valid integer"), And(lambda n: 0 < n,
                                                                       error="integer must be above 0"))),
     str: object}, )


def main(args):
    argv = docopt(__doc__, args)

    try:
        argv = action_template_schema.validate(argv)
    except SchemaError as e:
        exit(str(e))
    if argv['list']:
        action_list(iden=argv['--id'], name=argv['--name'], version=argv['--version'], like=argv['--like'],
                    last=argv['--last'])
    elif argv['create']:
        if argv['-']:
            content = sys.stdin.read()
            part = json.loads(content)
            data = part if isinstance(part, list) else [part]
        elif argv['FILE']:
            data = []
            content = argv['FILE'].read()
            part = json.loads(content)
            data.extend(part) if isinstance(part, list) else data.append(part)
        else:
            data = {'name': argv['NAME'],
                    'version': argv['--version'],
                    'action_type': argv['ACTION_TYPE'],
                    'code': argv['--code'],
                    'parameters': argv['--parameters'],
                    'expected_stdout': argv['--expected-stdout'],
                    'expected_stderr': argv['--expected-stderr'],
                    'expected_rc': argv['--expected-rc'],
                    'system_kwargs': argv['--system-kwargs'],
                    'pre_process': argv['--pre-process'],
                    'post_process': argv['--post-process']
                    }
            data = clean_none(data)
        pprint(data)
        if data:
            resp = ntwrk.post(f'api_1_0.actiontemplatelist', json=data)
            if resp.ok:
                if resp.msg:
                    pprint(resp.msg)
            else:
                pprint(resp.msg if resp.code is not None else str(resp.exception) if str(
                    resp.exception) else resp.exception.__class__.__name__)
        else:
            print("No data found to create action template")
