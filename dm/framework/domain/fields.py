# noinspection PyUnresolvedReferences
import copy
import ipaddress

import rsa
from marshmallow import utils, class_registry
from marshmallow.base import SchemaABC
from marshmallow.fields import *
# noinspection PyUnresolvedReferences
from marshmallow_enum import EnumField as Enum
import typing as t

if t.TYPE_CHECKING:
    from dm.framework.domain import Schema


class PluckEntity(Nested):

    def __init__(self, nested, field_name, **kwargs):
        super().__init__(nested, **kwargs)
        self.field_name = field_name

    @property
    def _field_data_key(self):
        only_field = self.schema.fields[self.field_name]
        return only_field.data_key or self.field_name

    def _serialize(self, nested_obj, attr, obj, **kwargs):
        ret = super()._serialize(nested_obj, attr, obj, **kwargs)
        if ret is None:
            return None
        if self.many:
            return str(utils.pluck(ret, key=self._field_data_key))
        return str(ret[self._field_data_key])

    def _deserialize(self, value, attr, data, partial=None, **kwargs):
        self._test_collection(value)
        return self._load(value, data, partial=partial)


TypeIPAddress = t.Union[ipaddress.IPv4Address, ipaddress.IPv6Address]


class IPAddress(Field):
    """An IP Address field"""

    default_error_messages = {"invalid_ip": "Not a valid IP Address.",
                              "decode_error": "Unable to decode ip"}

    def _validated(self, value) -> t.Optional[TypeIPAddress]:
        """Format the value or raise a :exc:`ValidationError` if an error occurs."""
        if value is None:
            return None
        if isinstance(value, (ipaddress.IPv4Address, ipaddress.IPv6Address)):
            return value
        try:
            if isinstance(value, bytes):
                return ipaddress.ip_address(value.decode())
            else:
                return ipaddress.ip_address(value)
        except ValueError as error:
            raise self.make_error("invalid_ip") from error
        except UnicodeDecodeError as error:
            raise self.make_error("decode_error") from error

    def _serialize(self, value, attr, obj, **kwargs):
        val = str(value) if value is not None else None
        return super()._serialize(val, attr, obj, **kwargs)

    def _deserialize(self, value, attr, data, **kwargs) -> t.Optional[TypeIPAddress]:
        return self._validated(value)


class RSAPublicKey(Field):
    """A Public Key"""

    def _serialize(self, value, attr, obj, **kwargs):
        val = rsa.PublicKey.save_pkcs1(value) if value is not None else None
        return super()._serialize(val, attr, obj, **kwargs)

    def _deserialize(self, value, attr, data, **kwargs) -> t.Optional[rsa.PublicKey]:
        return rsa.PublicKey.load_pkcs1(value)


class RSAPrivateKey(Field):
    """A Public Key"""

    def _serialize(self, value, attr, obj, **kwargs):
        val = rsa.PrivateKey.save_pkcs1(value) if value is not None else None
        return super()._serialize(val, attr, obj, **kwargs)

    def _deserialize(self, value, attr, data, **kwargs) -> t.Optional[rsa.PrivateKey]:
        return rsa.PrivateKey.load_pkcs1(value)
