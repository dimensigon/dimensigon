from dm.domain.entities import Server
from dm.framework.domain import Schema, fields
from dm.utils.datamark import data_mark


@data_mark
class ServerSchema(Schema):
    __entity__ = Server
    id = fields.UUID(required=True)
    name = fields.Str(required=True)
    ip = fields.IPAddress()
    port = fields.Int()
    birth = fields.DateTime(allow_none=True)
    keep_alive = fields.Raw(allow_none=True)
    available = fields.Bool(allow_none=True)
    granules = fields.Raw(many=True, allow_none=True)
    route = fields.PluckEntity('self', field_name='id', many=True)
    alt_route = fields.PluckEntity('self', field_name='id', many=True)
