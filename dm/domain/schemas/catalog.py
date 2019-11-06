from dm.domain.entities.catalog import Catalog
from dm.framework.domain import Schema, fields


class CatalogSchema(Schema):
    __entity__ = Catalog
    entity = fields.Str(required=True)
    data_mark = fields.DateTime(required=True, format='%Y%m%d%H%M%S%f')
