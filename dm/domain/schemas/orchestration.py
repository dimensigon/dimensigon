import typing as t

from dm.domain.entities import Step, Orchestration
from dm.utils.datamark import data_mark
from dm.framework.domain import fields, Schema

if t.TYPE_CHECKING:
    pass


@data_mark
class StepSchema(Schema):
    __entity__ = Step
    id = fields.UUID(required=True)
    undo = fields.Bool(required=True)
    stop_on_error = fields.Bool(required=True)
    action_template = fields.PluckEntity('ActionTemplateSchema', required=True, field_name='id')
    step_expected_output = fields.Str(allow_none=True)
    step_expected_rc = fields.Int(allow_none=True)
    step_parameters = fields.Dict(allow_none=True)
    step_system_kwargs = fields.Dict(allow_none=True)


@data_mark
class OrchestrationSchema(Schema):
    __entity__ = Orchestration
    id = fields.UUID(required=True)
    name = fields.Str(required=True)
    version = fields.Int(required=True)
    steps = fields.PluckEntity(StepSchema, required=True, many=True, field_name='id')
    dependencies = fields.Dict(keys=fields.UUID(),
                               values=fields.List(fields.UUID()), attribute='dependencies')
    description = fields.Str(allow_none=True)


class OrchestrationSchemaNested(OrchestrationSchema):
    __entity__ = Orchestration
    steps = fields.Nested(StepSchema, required=True, many=True)
