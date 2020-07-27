"""
usage: dshell [--version] [--username USER] [--password PASSWORD|--token TOKEN] [--server SERVER] [--port PORT]
              [--config-file CONFIG_FILE] [COMMAND [ARGS...]]

options:
   -u, --username USER              Login user
   --password PASSWORD              Password used to login
   -t, --token TOKEN                Refresh token used to authenticate
   -s, --server SERVER              Server to communicate with
   -p, --port PORT                  Port to communicate with [default: 5000]
   -c, --config-file CONFIG_FILE    configuration file [default: ~/.dshell]

The available dshell commands are:
   status    Status of a node
   ping      Ping a node
   server    Server Resource
   orch      Orchestration Resource, run Orchestrations
   action    Action Resource
   exec      Execution Resource
   software  Software Resource, send software
   logfed    LogFed Resource

When no dshell command specified dshell starts in interactive mode

See 'dshell <command> --help' for more information on a specific command.

"""
import configparser
import importlib
import logging
import os
import sys
from argparse import ArgumentParser
from os.path import expanduser

from docopt import docopt

import dimensigon.dshell.network as ntwrk
from dimensigon.dshell.argparse_raise import create_parser
from dimensigon.dshell.commands import nested_dict
from dimensigon.dshell.environ import set_dict_in_environ
from dimensigon.dshell.interactive import interactive, call_func_with_signature

basename = os.path.dirname(os.path.abspath(__file__))

commands = 'cmd exec ping logfed server software status transfer'.split()
batch_commands = 'action orch'.split()  # commands that interact differently from interactive mode


def load_config_file(file=None):
    data = dict(USERNAME=None, TOKEN=None, SERVER=None, PORT=None)
    config = configparser.ConfigParser()
    if file and os.path.exists(file):
        config.read(file)
        if 'AUTH' in config:
            data['USERNAME'] = config['AUTH'].get('username', None)
            data['TOKEN'] = config['AUTH'].get('token', None)
        if 'REMOTE' in config:
            data['SERVER'] = config['REMOTE'].get('server', None)
            data['PORT'] = config['REMOTE'].get('port', None)

    return data


def main():
    ch = logging.StreamHandler()
    logger = logging.getLogger('dshell')
    logger.addHandler(ch)

    # parse args
    args = docopt(__doc__,
                  version=f'dshell version 1.0',
                  options_first=True)

    # load data from config file
    data = load_config_file(os.path.join(expanduser(args['--config-file'])))

    SERVER = args['--server'] or data['SERVER'] or os.environ.get('DM_SERVER', None)
    PORT = data['PORT'] or os.environ.get('DM_PORT', None)
    if '--port' in sys.argv or PORT is None:
        PORT = args['--port']

    set_dict_in_environ({'SERVER': SERVER, 'PORT': PORT, 'SCHEME': 'https', 'SSL_VERIFY': False,
                         'FILE_HISTORY': '~/.dshell_history'})

    # process args
    argv = [args['COMMAND']] + args['ARGS']
    if args['COMMAND'] in commands:
        ntwrk.bootstrap_auth(args['--username'] or data['USERNAME'], args['--password'],
                             args['--token'] or data['TOKEN'])
        parser = create_parser({args['COMMAND']: nested_dict[args['COMMAND']]}, parser=ArgumentParser(prog="dshell"))
        namespace = parser.parse_args(argv)

        if hasattr(namespace, 'func'):
            call_func_with_signature(dict(namespace._get_kwargs()))
    elif args['COMMAND'] in batch_commands:
        ntwrk.bootstrap_auth(args['--username'] or data['USERNAME'], args['--password'],
                             args['--token'] or data['TOKEN'])
        module = importlib.import_module('.dshell_%s' % args['COMMAND'], 'dimensigon.dshell.batch')
        module.main(argv)
    elif args['COMMAND'] is None:
        try:
            ntwrk.bootstrap_auth(args['--username'] or data['USERNAME'], args['--password'],
                                 args['--token'] or data['TOKEN'])
        except Exception as e:
            print(str(e))
        interactive()
    else:
        exit("%r is not a dshell command. See 'dshell --help'." % args['COMMAND'])


if __name__ == '__main__':
    sys.exit(main())
