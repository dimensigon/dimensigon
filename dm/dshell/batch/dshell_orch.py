"""
Usage: dshell orch list [--id ID|--name NAME|--like LIKE] [--version N] [--last N]
       dshell orch create (- | FILE)
       dshell orch run ID [[--parameter PARAM=VALUE]... | [--json-parameters JSON]]
                          ((--target NAME=VALUE)... | --json-target JSON)
                          [--background]

Command to interact with orchestration

Arguments:
    FILE                     File which has the orchestration to create
    ID                       Orchestration ID to launch
    NAME                     Orchestration's name

Options:
    --id ID                  Action template id to show
    --last N                 Shows last N servers
    --like LIKE              List action templates whose names contain LIKE
    --json-parameters JSON   Json parameters. Ex.: '{"folder":"/tmp",
    --json-target JSON       Target in json format. Ex.: '{"all":["node1", "node2"], "backend": "granule-backend"}'
    --name NAME              Action templates' name to list
    --parameter PARAM=VALUE  Parameter passed to run orchestration. Examples: --parameter folder=/tmp
    --target NAME=VALUE      Target to run the orchestrations NAME is the target name and value the granules or hosts
                             select. Example: --target all=node1,node2 --target backend=granule-backend
    --version N              Versions to list
    --background             Runs the orchestration in background
"""
import json
import sys
from pprint import pprint

from docopt import docopt
from schema import Schema, Or, Use, And, SchemaError

import dm.dshell.network as ntwrk
from dm.dshell.commands import orch_list, orch_run

orch_schema = Schema(
    {
        'FILE': Or(None, Use(open, error="Unable to open file. File not found")),
        '--last': Or(None, And(Use(int, error="Not a valid integer"), And(lambda n: 0 < n,
                                                                          error="integer must be above 0"))),
        str: object}, )


def main(args):
    argv = docopt(__doc__, args)

    try:
        argv = orch_schema.validate(argv)
    except SchemaError as e:
        exit(str(e))
    if argv['list']:
        orch_list(iden=argv['--id'], name=argv['--name'], version=argv['--version'], like=argv['--like'],
                    last=argv['--last'])
    elif argv['create']:
        data = None
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
            exit("No file specified")
        if data:
            resp = ntwrk.post(f'api_1_0.orchestrationlist', json=data)
            if resp.ok:
                if resp.msg:
                    pprint(resp.msg)
            else:
                pprint(resp.msg if resp.code is not None else str(resp.exception) if str(
                    resp.exception) else resp.exception.__class__.__name__)
        else:
            print("No data found to create action template")
    elif argv['run']:
        orchestration_id = argv['ID']

        if argv['--json-parameters'] is None:
            parameters = {}
            for param in argv['PARAM=VALUE']:
                key, value = param.split('=', 1)
                if key not in parameters:
                    parameters[key] = value
                else:
                    if isinstance(parameters[key], list):
                        parameters[key].append(value)
                    else:
                        parameters[key] = [parameters[key], value]
        else:
            parameters = json.loads(argv['--json-parameters'])

        if argv['--json-target'] is None:
            target = {}
            for param in argv['NAME=VALUE']:
                key, value = param.split('=', 1)
                if ',' in value:
                    target[key] = value.split(',')
                else:
                    target[key] = value
        else:
            target = json.loads(argv['--json-target'])

        orch_run(orchestration_id, params=parameters, hosts=target, background=argv['--background'] or False)
