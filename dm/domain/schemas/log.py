from marshmallow.validate import ContainsOnly

from dm.domain.entities.log import Log

from dm.framework.domain import fields, Schema


class LogSchema(Schema):
    __entity__ = Log
    file = fields.Str(required=True)
    server = fields.PluckEntity('ServerSchema', required=True, field_name='id')
    dest_folder = fields.Str(required=True)
    dest_name = fields.Str(allow_none=True)
    read_from_end = fields.Bool()
    binary = fields.Bool()
    log_patterns = fields.List(fields.Str, allow_none=True)
    full_lines = fields.Bool(allow_none=True)
    encoding = fields.Str(allow_none=True)
    errors = fields.Str(validate=[ContainsOnly(['strict', 'ignore', 'replace', 'surrogateescape', 'backslashreplace'])],
                        allow_none=True)
