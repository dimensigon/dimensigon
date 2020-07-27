import abc
import inspect
import random
import string
import uuid
from datetime import datetime

from sqlalchemy import Column, Boolean

from dimensigon import defaults
from dimensigon.utils.typos import UUID, UtcDateTime


class JSONEntity:

    @abc.abstractmethod
    def to_json(self):
        ...

    @classmethod
    @abc.abstractmethod
    def from_json(cls, kwargs):
        ...


class SoftDeleteMixin:
    __prefix__ = '_old_'
    deleted = Column(Boolean(), default=False)

    def __init__(self, deleted=False, **kwargs):
        self.deleted = deleted
        for attr in [attr for attr, value in inspect.getmembers(self) if attr.startswith(self.__prefix__)]:
            setattr(self, attr, kwargs.get(attr, None))

    def delete(self):
        if not self.deleted:
            self.deleted = True
            for attr in [attr for attr, value in inspect.getmembers(self) if attr.startswith(self.__prefix__)]:
                original_attr = attr.lstrip(self.__prefix__)
                setattr(self, attr, getattr(self, original_attr))
                setattr(self, original_attr,
                        ''.join(random.choices(string.digits + string.ascii_letters + string.punctuation, k=10)))



class DistributedEntityMixin(JSONEntity):
    order = None
    last_modified_at = Column(UtcDateTime(), nullable=False)

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
    id = Column(UUID, primary_key=True, default=str(uuid.uuid4))

    def __init__(self, **kwargs):
        if 'id' in kwargs:
            self.id = str(kwargs['id']).lower()
        else:
            self.id = str(uuid.uuid4())


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
