import copy
import re
import typing as t
from collections import ChainMap

from dimensigon.web import errors


class VariableNotFoundError(Exception):
    pass


class _empty:
    pass


class Mapping:

    def __init__(self, source: str, dest: str, action: str, **kwargs):
        self.source = source or kwargs.get('source')
        self.dest = dest or kwargs.get('dest')
        self.action = action or kwargs.get('action')
        assert self.action in ('replace', 'from')


class VarContext:
    _exp = re.compile(r'\{\{\s*([\.\w]+)\s*\}\}')
    __reserved_keys = ('execution_server_id',)

    def __init__(self, globals: t.Mapping[str, t.Any] = None, initials: t.Mapping[str, t.Any] = None,
                 defaults: t.Mapping[str, t.Any] = None,
                 variables: t.Mapping[str, t.Any] = None):

        self.globals = globals if globals is not None else {}
        self.__initials = initials if initials is not None else {}
        self.__defaults = defaults if defaults is not None else {}
        self.__variables = variables if variables is not None else {}
        self.__cm = ChainMap(self.__variables, self.__initials, self.__defaults)

    @property
    def initials(self):
        return copy.deepcopy(self.__initials)

    def create_new_ctx(self, defaults, initials=None):
        return self.__class__(globals=dict(self.globals), initials=dict(initials or self.__initials), defaults=defaults,
                              variables=self.__variables)

    def find_recursive(self, item):
        try:
            value = self.__cm[item]
        except KeyError:
            raise VariableNotFoundError(f"variable {item} not found in stack")
        try:
            match = self._exp.search(value)
        except:
            return value
        if match:
            item = match.groups()[0]
            return self.find_recursive(item)
        else:
            return value

    def __iter__(self):
        for k, v in self.__cm.items():
            match = None
            try:
                match = self._exp.search(v)
            except:
                yield k, v
            if match:
                yield k, self.find_recursive(match.groups()[0])
            else:
                yield k, v

    def __len__(self):
        return len(self.__cm)

    def __contains__(self, item):
        return item in self.__cm

    def get(self, k, d=_empty):
        try:
            return self.find_recursive(k)
        except VariableNotFoundError:
            if d != _empty:
                return d
            else:
                raise

    def set(self, k, v):
        if k in self.__reserved_keys:
            raise KeyError(f"'{k}' is a reserved key")
        else:
            self.__variables.update({k: v})

    def extract_variables(self):
        return dict(self.__variables)

    def update_variables(self, variables):
        self.__variables.update(variables)

    def __str__(self):
        return f"globals: {self.globals}\ninitials: {self.__initials}\ndefaults: {self.__defaults}\nvariables: {self.__variables}"

    def get_input_from_schema(self, schema: t.Dict) -> t.Dict:
        mapping_schema = schema.get('mapping', {})

        params = {}
        for dest, value in mapping_schema.items():
            action, source = tuple(value.items())[0]
            if source not in self:
                raise errors.MissingSourceMapping(source)
            params[dest] = self.get(source)
            if action == 'replace':
                try:
                    self.__variables[dest] = self.__variables.pop(source)
                except KeyError:
                    self.__variables[dest] = self.get(source)

        for key, value in schema.get('input', {}).items():
            if key in self:
                params[key] = self.get(key)
            else:
                if 'default' in value:
                    params[key] = value.get('default')

        return params


class Context:

    def __init__(self, variables=None, __globals=None, __locals=None, key_server_ctx=None, server_variables=None):
        self._global_envs = __globals if __globals is not None else {}  # environment variables global to a deployment
        self._local_envs = __locals if __locals is not None else {}  # environment variables local to a step
        self.env = ChainMap(self._local_envs, self._global_envs)

        self._global_variables = variables if variables is not None else {}  # user data shared between steps
        self._key_server_ctx = key_server_ctx
        self._server_variables = server_variables if server_variables is not None else {}
        if key_server_ctx:
            if key_server_ctx not in self._server_variables:
                self._server_variables.update({key_server_ctx: {}})
            self._variables = ChainMap(self._server_variables.get(self._key_server_ctx), self._global_variables)
        else:
            self._variables = self._global_variables

    def __contains__(self, item):
        return item in self._variables

    def __getitem__(self, item):
        return self._variables[item]

    def __setitem__(self, key, value):
        self._variables[key] = value
        self.merge_common_variables(key)

    def __iter__(self):
        for k, v in self._variables.items():
            yield k, v

    def __str__(self):
        return str(self.dict())

    def __repr__(self):
        return repr(self.dict())

    def dict(self):
        return {'env': dict(self.env), 'variables': dict(self._variables)}

    def get(self, key, default=None):
        return self._variables.get(key, default)

    def set(self, item, value):
        self._variables.update({item: value})
        self.merge_common_variables(item)

    def pop(self, item):
        return self._variables.pop(item)

    def keys(self):
        return self._variables.keys()

    def items(self):
        return self._variables.items()

    def values(self):

        return self._variables.values()

    def local_ctx(self, __locals=None, key_server_ctx=None) -> 'Context':
        return self.__class__(self._global_variables, self._global_envs, __locals,
                              key_server_ctx=key_server_ctx, server_variables=self._server_variables)

    def merge_ctx(self, ctx: 'Context'):
        """Function used for loading context from an older orch"""
        # self._global_envs.update(ctx.__global_envs)
        self._local_envs.update(ctx._local_envs)
        self._variables.update(ctx._variables)
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
