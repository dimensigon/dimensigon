from datetime import datetime

import sqlalchemy as sa

from dm.model import Base


class Catalog(Base):
    __tablename__ = 'L_catalog'
    entity = sa.Column(sa.String(40), primary_key=True, unique=True)
    last_modified_at = sa.Column(sa.DateTime, nullable=False)

    def __init__(self, entity: str, last_modified_at: datetime):
        self.entity = entity
        self.last_modified_at = last_modified_at

    def __repr__(self):
        return f'<{self.__class__.__name__}({self.entity}, {self.last_modified_at})>'
