import configparser
import os
from os.path import expanduser

import dimensigon.dshell.network as ntwrk
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


def bootstrap_environ(run_config):
    data = load_config_file(os.path.join(expanduser(run_config['--config-file'])))

    server = run_config['--server'] or os.environ.get('DM_SERVER') or data.get('SERVER', None)
    port = run_config['--port'] or os.environ.get('DM_PORT') or data.get('PORT', None)

    env.set_dict_in_environ({'SERVER': server, 'PORT': port, 'SCHEME': 'https', 'SSL_VERIFY': False,
                             'FILE_HISTORY': '~/.dshell_history', 'DEBUG': False})

    # auth data
    username = run_config['--username'] or os.environ.get('DM_USERNAME') or data.get('USERNAME', None)
    password = run_config['--password'] or os.environ.get('DM_PASSWORD')
    refresh_token = run_config['--token'] or os.environ.get('DM_TOKEN')

    if refresh_token:
        ntwrk._refresh_token = refresh_token
    else:
        if password and username:
            ntwrk.login(username, password)
        elif username:
            ntwrk._username = username
