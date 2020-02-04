import ipaddress
import json
import typing as t
import uuid
from abc import ABC

import rsa
from sqlalchemy import types
from sqlalchemy.dialects.postgresql import UUID as pUUID
from sqlalchemy.ext.mutable import MutableDict

Kwargs = Params = t.NewType('Params', t.Union[t.Dict['str', t.Any]])
Id = t.TypeVar('Id', int, str, uuid.UUID)
Ids = t.Sequence[Id]

Callback = t.Tuple[t.Callable[[], None], t.Tuple, t.Dict]

Priority = t.TypeVar('T')


class BaseTypeDecorator(types.TypeDecorator):
    def __repr__(self):
        return self.impl.__repr__()


class ScalarListException(Exception):
    pass


class ScalarListType(BaseTypeDecorator):
    """
    ScalarListType type provides convenient way for saving multiple scalar
    values in one column. ScalarListType works like list on python side and
    saves the result as comma-separated list in the database (custom separators
    can also be used).

    Example ::


        from sqlalchemy_utils import ScalarListType


        class User(Base):
            __tablename__ = 'user'
            id = sa.Column(sa.Integer, autoincrement=True)
            hobbies = sa.Column(ScalarListType())


        user = User()
        user.hobbies = [u'football', u'ice_hockey']
        session.commit()


    You can easily set up integer lists too:

    ::


        from sqlalchemy_utils import ScalarListType


        class Player(Base):
            __tablename__ = 'player'
            id = sa.Column(sa.Integer, autoincrement=True)
            points = sa.Column(ScalarListType(int))


        player = Player()
        player.points = [11, 12, 8, 80]
        session.commit()


    """

    impl = types.UnicodeText()

    def __init__(self, coerce_func=str, separator=':'):
        self.separator = separator
        self.coerce_func = coerce_func

    def process_bind_param(self, value, dialect):
        # Convert list of values to unicode separator-separated list
        # Example: [1, 2, 3, 4] -> u'1, 2, 3, 4'
        if value is not None:
            if any(self.separator in str(item) for item in value):
                raise ScalarListException(
                    "List values can't contain string '%s' (its being used as "
                    "separator. If you wish for scalar list values to contain "
                    "these strings, use a different separator string.)"
                    % self.separator
                )
            return self.separator.join(
                map(str, value)
            )

    def process_result_value(self, value, dialect):
        if value is not None:
            if value == u'':
                return []
            # coerce each value
            return list(map(
                self.coerce_func, value.split(self.separator)
            ))


class UUID(BaseTypeDecorator):
    """Platform-independent GUID type.

    Uses Postgresql's UUID type, otherwise uses
    CHAR(32), storing as stringified hex values.

    """
    impl = types.CHAR

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(pUUID())
        else:
            return dialect.type_descriptor(types.CHAR(32))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        else:
            return uuid.UUID(value)

class JSONEncodedDict(BaseTypeDecorator):
    impl = types.JSON

    def process_bind_param(self, value, dialect):
        if value is not None:
            value = json.dumps(value)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            value = json.loads(value)
        return value


JSON = MutableDict.as_mutable(JSONEncodedDict)


class PrivateKey(BaseTypeDecorator):
    impl = types.BLOB

    def process_bind_param(self, value, dialect):
        if value is not None:
            value = value.save_pkcs1()
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            value = rsa.PrivateKey.load_pkcs1(value)
        return value


class PublicKey(BaseTypeDecorator):
    impl = types.BLOB

    def process_bind_param(self, value, dialect):
        if value is not None:
            value = value.save_pkcs1()
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            value = rsa.PublicKey.load_pkcs1(value)
        return value


class IP(BaseTypeDecorator):
    impl = types.CHAR

    def process_bind_param(self, value, dialect):
        if value is not None:
            value = str(value)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            value = ipaddress.ip_address(value)
        return value
