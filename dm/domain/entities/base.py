import abc
import uuid
from datetime import datetime

import six
from sqlalchemy import DateTime, Column

from dm import defaults
from dm.utils.typos import UUID


class JSONEntity:

    @abc.abstractmethod
    def to_json(self):
        ...

    @classmethod
    @abc.abstractmethod
    def from_json(cls, kwargs):
        ...


class DistributedEntityMixin(JSONEntity):
    order = None
    last_modified_at = Column(DateTime, nullable=False)

    def __init__(self, **kwargs):
        self.last_modified_at = kwargs.pop('last_modified_at', None)

    def to_json(self):
        try:
            return dict(last_modified_at=self.last_modified_at.strftime(defaults.DATEMARK_FORMAT))
        except AttributeError:
            return dict()

    @classmethod
    def from_json(cls, kwargs):
        if 'last_modified_at' in kwargs:
            last_modified_at = kwargs.pop('last_modified_at')
            last_modified_at = datetime.strptime(last_modified_at, defaults.DATEMARK_FORMAT)
            kwargs.update(last_modified_at=last_modified_at)


class UUIDEntityMixin:
    id = Column(UUID, primary_key=True, default=uuid.uuid4)

    def __init__(self, **kwargs):
        if 'id' in kwargs:
            self.id = uuid.UUID(kwargs['id']) if isinstance(kwargs['id'], six.string_types) else kwargs['id']
        else:
            self.id = uuid.uuid4()


class UUIDistributedEntityMixin(UUIDEntityMixin, DistributedEntityMixin):

    def __init__(self, **kwargs):
        UUIDEntityMixin.__init__(self, **kwargs)
        DistributedEntityMixin.__init__(self, **kwargs)

    def to_json(self):
        data = super().to_json()
        if self.id:
            data['id'] = str(self.id)
        return data

    @classmethod
    @abc.abstractmethod
    def from_json(cls, kwargs):
        super().from_json(kwargs)
        if 'id' in kwargs:
            kwargs['id'] = uuid.UUID(kwargs.get('id'))

        try:
            o = cls.query.get(kwargs.get('id'))
        except RuntimeError as e:
            o = None
        if o:
            for k, v in kwargs.items():
                if getattr(o, k) != v:
                    setattr(o, k, v)
            return o
        else:
            return cls(**kwargs)



class EntityReprMixin:
    id = None

    def __repr__(self):
        if self.id:
            return f'<{self.__class__.__name__} {self.id}>'
        else:
            return f'<{self.__class__.__name__} (transient {id(self)})>'

    def __str__(self):
        return self.__repr__()
