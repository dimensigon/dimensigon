import typing as t

from sqlalchemy import String
from sqlalchemy.dialects import postgresql
from sqlalchemy.types import TypeDecorator, CHAR
from sqlalchemy.dialects.postgresql import UUID
import uuid

Params = t.NewType('Params', t.Union[t.Dict['str', t.Any], t.ChainMap])

Callback = t.Tuple[t.Callable[[], None], t.Tuple, t.Dict]

Priority = t.TypeVar('T')


class GUID(TypeDecorator):
    """Platform-independent GUID type.

    Uses PostgreSQL's UUID type, otherwise uses
    CHAR(32), storing as stringified hex values.

    """
    impl = CHAR

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(UUID())
        else:
            return dialect.type_descriptor(CHAR(32))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == 'postgresql':
            return str(value)
        else:
            if not isinstance(value, uuid.UUID):
                return "%.32x" % uuid.UUID(value).int
            else:
                # hexstring
                return "%.32x" % value.int

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        else:
            if not isinstance(value, uuid.UUID):
                value = uuid.UUID(value)
            return value

    def compare_against_backend(self, dialect, conn_type):
        # return True if this type is the same as the given database type,
        # or None to allow the default implementation to compare these
        # types. a return value of False means the given type does not
        # match this type.

        if dialect.name == 'postgresql':
            return isinstance(conn_type, postgresql.UUID)
        else:
            return isinstance(conn_type, String)