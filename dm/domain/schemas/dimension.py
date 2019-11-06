from domain.entities import Dimension
from framework.domain import Schema, fields


class DimensionSchema(Schema):
    __entity__ = Dimension
    id = fields.UUID(required=True)
    name = fields.String(required=True)
    priv = fields.RSAPrivateKey(required=True)
    pub = fields.RSAPublicKey(required=True)
    created = fields.DateTime(required=True)
