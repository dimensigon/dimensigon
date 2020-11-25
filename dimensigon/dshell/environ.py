_server2id_map = {}

_environ = {}

_access_token = None
_refresh_token = None
_username = None


def set_dict_in_environ(data: dict, **kwargs):
    for k, v in data.items():
        set(k, v)
    for k, v in kwargs.items():
        set(k, v)


def set(key, value):
    if key == 'ACCESS_TOKEN':
        raise ValueError('ACCESS_TOKEN is not settable')
    _environ.update({key: value})


def get(key, default=None):
    if key == 'ACCESS_TOKEN':
        return _access_token
    return _environ.get(key, default)


def set_server2id_map(data):
    for server in data:
        _server2id_map[server.get('name')] = server.get('id')


def server2id(server):
    return _server2id_map.get(server, None)
