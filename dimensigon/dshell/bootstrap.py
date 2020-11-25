import configparser
import logging
import os

from dimensigon import defaults
from dimensigon.dshell import environ as env
from dimensigon.dshell import network as ntwrk

_logger = logging.getLogger('dshell')


def load_config_file(file=None):
    data = dict(USERNAME=None, TOKEN=None, SERVER=None, PORT=None)
    config = configparser.ConfigParser()
    if file and os.path.exists(os.path.expanduser(file)):
        config.read(os.path.expanduser(file))
        data['USERNAME'] = config.get('AUTH', 'username', fallback=None)
        data['TOKEN'] = config.get('AUTH', 'token', fallback=None)
        data['SERVER'] = config.get('REMOTE', 'server', fallback=None)
        data['PORT'] = config.getint('REMOTE', 'port', fallback=None)
    return data


def save_config_file(file=None, username=None, token=None, server=None, port=None):
    config = configparser.ConfigParser()
    if file:
        config.read(file)
        if not config.has_section('AUTH'):
            config.add_section('AUTH')
        if not config.has_section('REMOTE'):
            config.add_section('REMOTE')
        if username:
            config.set('AUTH', 'username', username)
        if token:
            config.set('AUTH', 'token', token)
        if server:
            config.set('REMOTE', 'server', server)
        if port:
            config.set('REMOTE', 'port', str(port))
        with open(file, 'w') as fd:
            config.write(fd)
    _logger.info(f"saved data into {file}")


def bootstrap_environ(run_config):
    config_file = run_config['--config-file']
    data = load_config_file(os.path.expanduser(config_file))

    server = run_config['--server'] or os.environ.get('DM_SERVER') or data.get('SERVER', None) or '127.0.0.1'
    port = run_config['--port'] or os.environ.get('DM_PORT') or data.get('PORT', None) or defaults.DEFAULT_PORT

    env.set_dict_in_environ({'SERVER': server, 'PORT': port, 'SCHEME': 'https', 'SSL_VERIFY': False,
                             'FILE_HISTORY': '~/.dshell_history', 'DEBUG': False, 'CONFIG_FILE': config_file})

    # auth data
    username = run_config['--username'] or os.environ.get('DM_USERNAME') or data.get('USERNAME', None)
    password = run_config['--password'] or os.environ.get('DM_PASSWORD')
    refresh_token = run_config['--token'] or os.environ.get('DM_TOKEN') or data.get('TOKEN')

    if refresh_token:
        env._refresh_token = refresh_token
    if username:
        env._username = username
        if password:
            ntwrk.login(username, password)

    env.set('DEBUG', run_config.get('--debug', False))
