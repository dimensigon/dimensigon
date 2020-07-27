_server2id_map = {}

_environ = {}

def set_dict_in_environ(data: dict):
    for k, v in data.items():
        set(k, v)


def set(key, value):
    _environ.update({key: value})


def get(key, default=None):
    return _environ.get(key, default)


def set_server2id_map(data):
    for server in data:
        _server2id_map[server.get('name')] = server.get('id')


def server2id(server):
    return _server2id_map.get(server, None)
