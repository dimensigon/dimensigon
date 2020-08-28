import copy
import re
import typing as t
from collections import ChainMap


class VariableNotFoundError(Exception):
    pass

class empty:
    pass

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
        self.__cm = ChainMap(self.__variables, self.__defaults, self.__initials)

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

    def get(self, k, d=empty):
        try:
            return self.find_recursive(k)
        except VariableNotFoundError:
            if d != empty:
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
