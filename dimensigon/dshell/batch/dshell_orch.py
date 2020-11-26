"""
Usage: dshell orch list [--id ID|--name NAME|--like LIKE] [--version N] [--detail]
       dshell orch create (- | FILE)
       dshell orch run ID [[--param PARAM=VALUE]... | [--json-parameters JSON]]
                          ((--target NAME=VALUE)... | --json-target JSON)
                          [--no-wait]

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
    -p, --param PARAM=VALUE  Parameter passed to run orchestration. Examples: --parameter folder=/tmp
    -t, --target NAME=VALUE  Target to run the orchestrations NAME is the target name and value the granules or hosts
                             select. Example: --target all=node1,node2 --target backend=granule-backend
    --version N              Versions to list
    --no-wait                Does not wait the orchestration to finish
"""
import ast
import json
import re
import sys

from docopt import docopt

import dimensigon.dshell.network as ntwrk
from dimensigon.dshell.commands import orch_list, orch_run, dprint


def main(args):
    argv = docopt(__doc__, args)

    if argv['list']:
        orch_list(ident=argv['--id'], name=argv['--name'], version=argv['--version'], like=argv['--like'],
                  detail=argv['--detail'])
    elif argv['create']:
        data = None
        if argv['-']:
            content = sys.stdin.read()
            part = json.loads(content)
            data = part if isinstance(part, list) else [part]
        elif argv['FILE']:
            try:
                content = open(argv['FILE'], 'r').read()
            except Exception as e:
                exit(str(e))
            try:
                data = json.loads(content)
            except Exception as e:
                exit(f"Json format error: {e}")
        else:
            exit("No file specified")
        if data:
            resp = ntwrk.post(f'api_1_0.orchestrations_full', json=data)
            dprint(resp)
        else:
            exit("No data found to create action template")
    elif argv['run']:
        orchestration_id = argv['ID']

        if argv['--json-parameters'] is None:
            container = {}
            for param in argv['--param']:
                match = re.search(r"^([\"']?)([\w\-_]+):(.*?)\1$", param, re.MULTILINE | re.DOTALL)
                if not match:
                    exit(
                        f"Not a valid parameter '{param}'. Must contain a KEY:VALUE. Ex. string-key:'string-value' or "
                        f"integer-key:12345 or list-key:[1,2]")
                else:
                    mark, key, value = match.groups()
                    try:
                        value = ast.literal_eval(value)
                    except Exception:
                        value = value.encode().decode('unicode-escape')
                if isinstance(value, str) and value.startswith('@'):
                    file = value.strip('@')
                    value = open(file, 'r').read()

                container.update({key: value})
            parameters = container
        else:
            parameters = json.loads(argv['--json-parameters'])

        if argv['--json-target'] is None:
            container = {}
            for value in argv['--target']:
                if '=' in value:
                    target, host = value.split('=')
                    if ',' in host:
                        host = host.split(',')
                    else:
                        host = [host]
                    if target in container:
                        container[target].extend(host)
                    else:
                        container.update({target: host})
                else:
                    if 'all' not in container:
                        container.update({'all': [value]})
                    else:
                        container['all'].append(value)
            target = container
        else:
            target = json.loads(argv['--json-target'])

        orch_run(orchestration_id, params=parameters, hosts=target, background=argv['--no-wait'] or False)
