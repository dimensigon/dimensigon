from datetime import datetime

from dm.web import db


class Catalog(db.Model):
    entity = db.Column(db.String(40), primary_key=True, unique=True)
    last_modified_at = db.Column(db.DateTime, nullable=False)

    def __init__(self, entity: str, last_modified_at: datetime):
        self.entity = entity
        self.last_modified_at = last_modified_at

    def __repr__(self):
        return f'<{self.__class__.__name__}({self.entity}, {self.last_modified_at})>'



