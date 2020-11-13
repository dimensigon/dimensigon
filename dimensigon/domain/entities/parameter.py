import typing as t

from dimensigon.utils.typos import Dill
from dimensigon.web import db


class _Empty:
    pass


class Parameter(db.Model):
    __tablename__ = 'L_parameter'

    parameter = db.Column(db.String(80), primary_key=True)
    value = db.Column(db.Text)
    dump = db.Column(Dill)
    load = db.Column(Dill)

    def __init__(self, parameter: str, dump: t.Callable[[t.Any], str] = None, load: t.Callable[[str], t.Any] = None):
        self.parameter = parameter
        self.dump = dump
        self.load = load

    @staticmethod
    def _convert(param: 'Parameter'):
        if param.load:
            try:
                value = param.load(param.value)
            except:
                return None
            else:
                return value
        else:
            return param.value

    @classmethod
    def _get_parameter(cls, key: str):
        p = cls.query.get(key)
        if p:
            return p
        else:
            raise KeyError(key)

    @classmethod
    def get(cls, key: str, default=_Empty):
        try:
            p = cls._get_parameter(key)
        except KeyError:
            if default == _Empty:
                raise
            else:
                return default
        value = cls._convert(p)
        if value is None and default != _Empty:
            return default
        else:
            return value

    def set_functions(self, dump: t.Callable[[t.Any], str] = _Empty, load: t.Callable[[str], t.Any] = _Empty):
        if dump != _Empty:
            self.dump = dump
        if load != _Empty:
            self.load = load

    @classmethod
    def set(cls, key, value):
        p = cls.query.get(key)
        if p.dump:
            p.value = p.dump(value)
        else:
            p.value = value

    @classmethod
    def set_initial(cls, session=None):
        if session is None:
            session = db.session

        if not session.query(cls).get('last_graceful_shutdown'):
            p = Parameter('last_graceful_shutdown')
            session.add(p)
        if not session.query(cls).get('fetching_catalog'):
            p = Parameter('fetching_catalog')
            session.add(p)
        if not session.query(cls).get('join_server'):
            p = Parameter('join_server')
            session.add(p)
        if not session.query(cls).get('new_gates_server'):
            p = Parameter('new_gates_server')
            session.add(p)
