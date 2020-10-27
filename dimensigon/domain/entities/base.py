import abc
import functools
import inspect
import random
import string
import uuid
from datetime import datetime

from sqlalchemy import Column, Boolean

from dimensigon import defaults
from dimensigon.utils.typos import UUID, UtcDateTime
from dimensigon.web.helpers import QueryWithSoftDelete


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

    def __new__(cls, *args, **kwargs):
        obj = super(SoftDeleteMixin, cls).__new__(cls)
        obj.query_class = QueryWithSoftDelete
        if hasattr(obj, 'to_json') and callable(getattr(obj, 'to_json')):
            obj.to_json = SoftDeleteMixin.wrapper_to_json(obj, obj.to_json)

        return obj

    def __init__(self, deleted=False, **kwargs):
        self.deleted = deleted
        for attr, value in kwargs.items():
            if attr.startswith(self.__prefix__):
                setattr(self, attr, kwargs.get(attr, None))

    def delete(self):
        if not self.deleted:
            self.deleted = True
            for attr in [attr for attr, value in inspect.getmembers(self) if attr.startswith(self.__prefix__)]:
                original_attr = attr.lstrip(self.__prefix__)
                setattr(self, attr, getattr(self, original_attr))
                setattr(self, original_attr,
                        ''.join(random.choices(string.digits + string.ascii_letters + string.punctuation, k=10)))


    def wrapper_to_json(self, func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            no_delete = kwargs.pop('no_delete', False)
            dto = func(*args, **kwargs)
            if not no_delete:
                dto.update({'deleted': self.deleted})
                for attr in [attr for attr, value in inspect.getmembers(self) if attr.startswith(self.__prefix__)]:
                    dto.update({attr: getattr(self, attr)})
            return dto

        sig = inspect.signature(func)
        param_list = list(sig.parameters.values())
        try:
            v_p_i = max(
                [param_list.index(p) for p in param_list if p.kind == inspect.Parameter.VAR_POSITIONAL])
        except ValueError:
            v_p_i = None
        try:
            var_k_i = min([param_list.index(p) for p in param_list if p.kind == inspect.Parameter.VAR_KEYWORD])
        except ValueError:
            var_k_i = None

        # determine position
        if var_k_i is not None:
            index = var_k_i - 1
        else:
            index = len(param_list)
        # determine type
        if v_p_i is None:
            kind = inspect.Parameter.POSITIONAL_OR_KEYWORD
        else:
            kind = inspect.Parameter.KEYWORD_ONLY
        no_delete = inspect.Parameter("no_delete", kind=kind, default=False)
        param_list.insert(index, no_delete)
        new_sig = sig.replace(parameters=param_list)
        wrapper.__signature__ = new_sig
        return wrapper


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
    id = Column(UUID, primary_key=True, default=lambda: str(uuid.uuid4()))

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
