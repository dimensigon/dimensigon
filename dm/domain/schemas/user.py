from dm.domain.entities import User
from dm.framework.domain import fields, Schema
from dm.utils.datamark import data_mark


@data_mark
class UserSchema(Schema):
    __entity__ = User
    id = fields.UUID(required=True)
    username = fields.Str(required=True)
    password = fields.Str(required=True)
    created_on = fields.DateTime(required=True)