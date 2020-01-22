from sqlalchemy import DateTime, Column


class DistributedEntityMixin:
    last_modified_at = Column(DateTime, nullable=False)

    def __init__(self, **kwargs):
        self.last_modified_at = kwargs.pop('last_modified_at', None)


class EntityReprMixin:
    id=None

    def __repr__(self):
        if self.id:
            return f'<{self.__class__.__name__} {self.id}>'
        else:
            return f'<{self.__class__.__name__} (transient {id(self)})>'

    def __str__(self):
        return self.__repr__()