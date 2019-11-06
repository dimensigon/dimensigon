from dm.domain.entities import Service
from dm.framework.domain import fields, Schema
from dm.utils.datamark import data_mark


@data_mark
class ServiceSchema(Schema):
    __entity__ = Service
    id = fields.UUID(required=True)
    name = fields.Str(required=True)
    servers = fields.PluckEntity('ServerSchema', many=True, field_name='id')
    details = fields.Mapping()
    orchestrations = fields.PluckEntity('OrchestrationSchema', many=True, field_name='id')
    status = fields.Str()
    created = fields.DateTime()
    last_ping = fields.DateTime()