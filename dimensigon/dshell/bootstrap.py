import configparser
import os
from os.path import expanduser

from dimensigon.dshell import environ as env


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


def boostrap_environ(run_config):
    data = load_config_file(os.path.join(expanduser(run_config['--config-file'])))

    SERVER = run_config['--server'] or os.environ.get('DM_SERVER') or data['SERVER']
    PORT = run_config['--port'] or os.environ.get('DM_PORT') or data['PORT']

    env.set_dict_in_environ({'SERVER': SERVER, 'PORT': PORT, 'SCHEME': 'https', 'SSL_VERIFY': False,
                             'FILE_HISTORY': '~/.dshell_history'})
