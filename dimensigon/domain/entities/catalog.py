import typing as t
from datetime import datetime

from dimensigon import defaults
from dimensigon.utils.typos import UtcDateTime
from dimensigon.web import db


class Catalog(db.Model):
    __tablename__ = 'L_catalog'
    entity = db.Column(db.String(40), primary_key=True, unique=True)
    last_modified_at = db.Column(UtcDateTime(timezone=True), nullable=False)

    def __init__(self, entity: str, last_modified_at: datetime):
        self.entity = entity
        self.last_modified_at = last_modified_at

    def __repr__(self):
        return f'<{self.__class__.__name__}({self.entity}, {self.last_modified_at})>'

    @classmethod
    def max_catalog(cls, out=None) -> t.Union[datetime, str]:
        catalog_ver = db.session.query(db.func.max(Catalog.last_modified_at)).scalar()
        if catalog_ver is None:
            catalog_ver = defaults.INITIAL_DATEMARK
        return catalog_ver.strftime(defaults.DATEMARK_FORMAT) if out is str else catalog_ver
