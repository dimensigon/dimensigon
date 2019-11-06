from dm.domain.entities import ActionTemplate, ActionType
from dm.utils.datamark import data_mark
from dm.framework.domain import fields, Schema


@data_mark
class ActionTemplateSchema(Schema):
    __entity__ = ActionTemplate
    id = fields.UUID(required=True)
    name = fields.Str(required=True)
    version = fields.Int(required=True)
    action_type = fields.Enum(ActionType, required=True)
    code = fields.Str(required=True)
    parameters = fields.Mapping(missing={}, allow_none=True)
    system_kwargs = fields.Mapping(missing={}, allow_none=True)
    expected_output = fields.Str(missing=None, allow_none=True)
    expected_rc = fields.Int(missing=0, allow_none=True)
