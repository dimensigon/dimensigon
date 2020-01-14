import uuid

from sqlalchemy import DateTime, Column

from dm.utils.typos import UUID
from dm.web import db


class DistributedEntityMixin:
    last_modified_at = Column(DateTime, nullable=False)

    def __init__(self, **kwargs):
        self.last_modified_at = kwargs.pop('last_modified_at', None)


class EntityWithId(db.Model):
    id = db.Column(UUID, primary_key=True, default=uuid.uuid4)

    def __repr__(self):
        if self.id:
            return f'<{self.__class__.__name__} {self.id}>'
        else:
            return f'<{self.__class__.__name__} (transient {id(self)})>'

    def __str__(self):
        return self.__repr__()