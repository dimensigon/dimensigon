import copy
from collections import ChainMap


class _empty:
    pass


class Context:

    def __init__(self, variables=None, __globals=None, __locals=None, key_server_ctx=None, server_variables=None,
                 vault=None):
        self._global_envs = __globals if __globals is not None else {}  # environment variables global to a deployment
        self._local_envs = __locals if __locals is not None else {}  # environment variables local to a step
        self.env = ChainMap(self._local_envs, self._global_envs)
        self._container = {'vault': vault if vault is not None else {}}

        self._global_variables = variables if variables is not None else {}  # user data shared between steps
        self._key_server_ctx = key_server_ctx
        self._server_variables = server_variables if server_variables is not None else {}
        if key_server_ctx:
            if key_server_ctx not in self._server_variables:
                self._server_variables.update({key_server_ctx: {}})
            self._container['input'] = ChainMap(self._server_variables.get(self._key_server_ctx), self._global_variables)
        else:
            self._container['input'] = self._global_variables

    def __contains__(self, item):
        return item in self.input

    def __getattr__(self, item):
        if item not in self._container:
            raise AttributeError(f"'{item}' is not a valid container")
        return self._container[item]

    def __getitem__(self, item):
        return self.input[item]

    def __setitem__(self, key, value):
        self.input[key] = value
        self.merge_common_variables(key)

    def __getstate__(self):
        return self.__dict__

    def __setstate__(self, d):
        self.__dict__ = d

    def __iter__(self):
        for k, v in self.input.items():
            yield k, v

    def __str__(self):
        return str(self.dict())

    def __repr__(self):
        return repr(self.dict())

    def dict(self):
        return {k: copy.deepcopy(dict(v)) for k, v in self._container.items()}

    def get(self, key, default=None):
        return self.input.get(key, default)

    def set(self, item, value):
        self.input.update({item: value})
        self.merge_common_variables(item)

    def pop(self, item):
        return self.input.pop(item)

    def keys(self):
        return self.input.keys()

    def items(self):
        return self.input.items()

    def values(self):
        return self.input.values()

    def local_ctx(self, __locals=None, key_server_ctx=None) -> 'Context':
        return self.__class__(self._global_variables, self._global_envs, __locals,
                              key_server_ctx=key_server_ctx, server_variables=self._server_variables, vault=self.vault)

    def merge_ctx(self, ctx: 'Context'):
        """Function used for loading context from an older orch"""
        # self._global_envs.update(ctx.__global_envs)
        self._local_envs.update(ctx._local_envs)
        self.input.update(ctx.input)
        for server_id in self._server_variables:
            self._server_variables[server_id].update(ctx._server_variables.get(server_id, {}))
        for server_id in ctx._server_variables:
            if server_id not in self._server_variables:
                self._server_variables[server_id] = ctx._server_variables[server_id]

    def merge_common_variables(self, var=_empty):
        common_variables = None
        for server_id in self._server_variables.keys():
            if common_variables is None:
                common_variables = set(self._server_variables[server_id].keys())
            else:
                common_variables = common_variables.intersection(set(self._server_variables[server_id].keys()))

        if common_variables:
            if var in common_variables:
                common_variables = [var]
            for cv in common_variables:
                value = set([self._server_variables[server_id][cv] for server_id in self._server_variables.keys()])
                if len(value) == 1:
                    self._global_variables.update({cv: value.pop()})
                    [self._server_variables[server_id].pop(cv) for server_id in self._server_variables.keys()]
