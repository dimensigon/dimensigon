import datetime as dt
import ipaddress
import json
import pickle
import typing as t
import uuid

import dill
import rsa
from sqlalchemy import types, DateTime, Enum as _Enum
from sqlalchemy.dialects.postgresql import UUID as pUUID

Kwargs = t.Union[t.MutableMapping['str', t.Any]]
Id = t.TypeVar('Id', int, str, uuid.UUID, tuple)
Ids = t.Sequence[Id]
Id_or_Ids = t.Union[Id, Ids]

IPs = t.Union[ipaddress.IPv4Address, ipaddress.IPv6Address]

Gate = t.Union[t.Tuple[t.Union[str, IPs], int]]

tJSON = t.Union[t.List[t.Dict[str, t.Any]], t.Dict[str, t.Any]]

Callback = t.Tuple[t.Callable[[], None], t.Tuple, t.Dict]

Priority = t.TypeVar('T')

MultiLine = t.Union[str, t.List[str]]


class TypeDecorator(types.TypeDecorator):
    def __repr__(self):
        return self.impl.__repr__()


class ScalarListException(Exception):
    pass


class ScalarListType(TypeDecorator):
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

    impl = types.Text()

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


class UUID(TypeDecorator):
    """Platform-independent GUID type.

    Uses Postgresql's UUID type, otherwise uses
    CHAR(36)

    """
    impl = types.CHAR(36)

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(pUUID())
        else:
            return dialect.type_descriptor(types.CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        return str(value).lower()

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        return value.lower()


class Enum(_Enum):
    """Platform-independent GUID type.

    Uses Postgresql's UUID type, otherwise uses
    CHAR(32), storing as stringified hex values.

    """
    impl = types.VARCHAR(80)


class UUIDEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, uuid.UUID):
            return str(obj)
        # Let the base class default method raise the TypeError
        return json.JSONEncoder.default(self, obj)


class PrivateKey(TypeDecorator):
    impl = types.BLOB

    def process_bind_param(self, value, dialect):
        if value is not None:
            value = value.save_pkcs1()
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            value = rsa.PrivateKey.load_pkcs1(value)
        return value


class PublicKey(TypeDecorator):
    impl = types.BLOB

    def process_bind_param(self, value, dialect):
        if value is not None:
            value = value.save_pkcs1()
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            value = rsa.PublicKey.load_pkcs1(value)
        return value


class IP(TypeDecorator):
    impl = types.VARCHAR(39)

    def process_bind_param(self, value, dialect):
        if value is not None:
            value = str(value)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            value = ipaddress.ip_address(value)
        return value


class Pickle(TypeDecorator):
    impl = types.BLOB

    def process_bind_param(self, value, dialect):
        if value is not None:
            value = pickle.dumps(value)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            value = pickle.loads(value)
        return value


class Dill(TypeDecorator):
    impl = types.BLOB

    def process_bind_param(self, value, dialect):
        if value is not None:
            value = dill.dumps(value)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            value = dill.loads(value)
        return value


class Utc(dt.tzinfo):
    __slots__ = ()

    zero = dt.timedelta(0)

    def utcoffset(self, _):
        return self.zero

    def dst(self, _):
        return self.zero

    def tzname(self, _):
        return 'UTC'


try:
    utc = dt.timezone.utc
except AttributeError:
    utc = Utc()


class UtcDateTime(TypeDecorator):
    """Almost equivalent to :class:`~sqlalchemy.types.DateTime` with
    ``timezone=True`` option, but it differs from that by:
    - Never silently take naive :class:`~datetime.datetime`, instead it
      always raise :exc:`ValueError` unless time zone aware value.
    - :class:`~datetime.datetime` value's :attr:`~datetime.datetime.tzinfo`
      is always converted to UTC.
    - Unlike SQLAlchemy's built-in :class:`~sqlalchemy.types.DateTime`,
      it never return naive :class:`~datetime.datetime`, but time zone
      aware value, even with SQLite or MySQL.
    """

    impl = DateTime(timezone=True)

    def process_bind_param(self, value, dialect):
        if value is not None:
            if not isinstance(value, dt.datetime):
                raise TypeError('expected datetime.datetime, not ' +
                                repr(value))
            elif value.tzinfo is None:
                raise ValueError('naive datetime is disallowed')
            return value.astimezone(utc)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        elif value.tzinfo is None:
            value = value.replace(tzinfo=utc)
        return value
