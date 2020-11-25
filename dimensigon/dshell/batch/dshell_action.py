"""
Usage: dshell action list [--version N] [--id ID|--name NAME|--like LIKE]  [--last N]
       dshell action create (- | FILE)
       dshell action create NAME ACTION_TYPE [--code CODE] [--expected-stdout OUT] [--schema DATA|FILE]
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
    --schema DATA|FILE      Schema defined. Can be JSON data or a yaml file containing schema information
    --post-process POST     Code executed after CODE execution
    --pre-process PRE       Code executed before CODE execution
    --system-kwargs DATA    Special parameters passed to python command call
    --version N             Versions to list
"""
import json
import os
import sys

import yaml
from docopt import docopt
from schema import Schema, Or, And, Use, SchemaError

import dimensigon.dshell.network as ntwrk
from dimensigon.dshell.commands import action_list
from dimensigon.dshell.output import dprint
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
        action_list(ident=argv['--id'], name=argv['--name'], version=argv['--version'], like=argv['--like'],
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
            if argv['--schema']:
                if os.path.isfile(argv['--schema']):
                    try:
                        content = open(argv['--schema'], 'r').read()
                        schema = yaml.load(content, Loader=yaml.SafeLoader)
                    except Exception as e:
                        exit(f"Error while trying to load yaml file. Exception {e}")
                else:
                    schema = argv['--schema']
            data = {'name': argv['NAME'],
                    'version': argv['--version'],
                    'action_type': argv['ACTION_TYPE'],
                    'code': argv['--code'],
                    'schema': schema,
                    'expected_stdout': argv['--expected-stdout'],
                    'expected_stderr': argv['--expected-stderr'],
                    'expected_rc': argv['--expected-rc'],
                    'system_kwargs': argv['--system-kwargs'],
                    'pre_process': argv['--pre-process'],
                    'post_process': argv['--post-process']
                    }
            data = clean_none(data)
        dprint(data)
        if data:
            resp = ntwrk.post(f'api_1_0.actiontemplatelist', json=data)
            dprint(resp)
        else:
            exit("No data found to create action template")
