"""
usage: dshell [--version] [--username USER] [--password PASSWORD|--token TOKEN] [--server SERVER] [--port PORT]
              [--config-file CONFIG_FILE] [--debug] [COMMAND [ARGS...]]

options:
   -u, --username USER              Login user
   --password PASSWORD              Password used to login
   -t, --token TOKEN                Refresh token used to authenticate
   -s, --server SERVER              Server to communicate with
   -p, --port PORT                  Port to communicate with [default: 5000]
   -c, --config-file CONFIG_FILE    configuration file [default: ~/.dshell]
   --debug                          Sets trace for debugging

The available dshell commands are:
   status    Status of a node
   ping      Ping a node
   server    Server Resource
   orch      Orchestration Resource, run Orchestrations
   action    Action Resource
   exec      Execution Resource
   software  Software Resource, send software
   logfed    LogFed Resource
   manager   Commands to manage internal conditions

When no dshell command specified dshell starts in interactive mode

See 'dshell <command> --help' for more information on a specific command.

"""
import importlib
import logging
import os
import sys
from argparse import ArgumentParser

from docopt import docopt

import dimensigon.dshell.environ as env
from dimensigon.dshell.argparse_raise import create_parser
from dimensigon.dshell.bootstrap import bootstrap_environ
from dimensigon.dshell.commands import nested_dict
from dimensigon.dshell.interactive import interactive, call_func_with_signature

basename = os.path.dirname(os.path.abspath(__file__))

commands = 'cmd exec ping logfed manager server software status transfer refresh'.split()
batch_commands = 'action orch command'.split()  # commands that interact differently from interactive mode


def main():
    ch = logging.StreamHandler()
    logger = logging.getLogger('dshell')
    logger.addHandler(ch)

    # parse args
    args = docopt(__doc__,
                  version='dshell version 1.0',
                  options_first=True)

    bootstrap_environ(args)

    # process args
    argv = [args['COMMAND']] + args['ARGS']

    if not ('-h' or '--help') in argv:
        if args['COMMAND'] is None:
            import dimensigon.dshell
            dimensigon.dshell.INTERACTIVE = True
            interactive()
        else:
            if env._refresh_token is None:
                exit('No token specified. Unable to run command')
            if not env.get('SERVER', None):
                exit('No server specified. Unable to run command')
            if args['COMMAND'] in commands:
                parser = create_parser({args['COMMAND']: nested_dict[args['COMMAND']]},
                                       parser=ArgumentParser(prog="dshell"))
                namespace = parser.parse_args(argv)
                if hasattr(namespace, 'func'):
                    call_func_with_signature(vars(namespace))
            elif args['COMMAND'] in batch_commands:
                module = importlib.import_module('.dshell_%s' % args['COMMAND'], 'dimensigon.dshell.batch')
                module.main(argv)
            else:
                exit("%r is not a dshell command. See 'dshell --help'." % args['COMMAND'])
    else:
        parser = create_parser({args['COMMAND']: nested_dict[args['COMMAND']]},
                               parser=ArgumentParser(prog="dshell"))
        parser.parse_args(argv)


if __name__ == '__main__':
    sys.exit(main())
