import abc
import inspect
import random
import string
import uuid
from datetime import datetime

from sqlalchemy import Column, Boolean

from dimensigon import defaults
from dimensigon.utils.typos import UUID, UtcDateTime
from dimensigon.web.helpers import QueryWithSoftDelete


class SoftDeleteMixin:
    __prefix__ = '_old_'
    deleted = Column(Boolean(), default=False)
    query_class = QueryWithSoftDelete

    def __init__(self, deleted=False, **kwargs):
        # def wrapper_to_json(_self, func):
        #     @functools.wraps(func)
        #     def wrapper(*args, **kwargs):
        #         no_delete = kwargs.pop('no_delete', False)
        #         dto = func(*args, **kwargs)
        #         if not no_delete:
        #             dto.update({'deleted': _self.deleted})
        #             for attr in [attr for attr, value in inspect.getmembers(_self) if
        #                          attr.startswith(_self.__prefix__)]:
        #                 dto.update({attr: getattr(_self, attr)})
        #         return dto
        #
        #     sig = inspect.signature(func)
        #     param_list = list(sig.parameters.values())
        #     try:
        #         v_p_i = max(
        #             [param_list.index(p) for p in param_list if p.kind == inspect.Parameter.VAR_POSITIONAL])
        #     except ValueError:
        #         v_p_i = None
        #     try:
        #         var_k_i = min([param_list.index(p) for p in param_list if p.kind == inspect.Parameter.VAR_KEYWORD])
        #     except ValueError:
        #         var_k_i = None
        #
        #     # determine position
        #     if var_k_i is not None:
        #         index = var_k_i - 1
        #     else:
        #         index = len(param_list)
        #     # determine type
        #     if v_p_i is None:
        #         kind = inspect.Parameter.POSITIONAL_OR_KEYWORD
        #     else:
        #         kind = inspect.Parameter.KEYWORD_ONLY
        #     if 'no_delete' not in sig.parameters:
        #         no_delete = inspect.Parameter("no_delete", kind=kind, default=False)
        #         param_list.insert(index, no_delete)
        #         new_sig = sig.replace(parameters=param_list)
        #         wrapper.__signature__ = new_sig
        #         return wrapper
        #     else:
        #         return func

        super().__init__(**kwargs)
        self.deleted = deleted
        for attr, value in kwargs.items():
            if attr.startswith(self.__prefix__):
                setattr(self, attr, kwargs.get(attr, None))
        # if hasattr(self, 'to_json') and callable(getattr(self, 'to_json')):
        #     self.to_json = wrapper_to_json(self, self.to_json)

    def to_json(self, no_delete=False, **kwargs):
        if hasattr(super(), 'to_json'):
            dto = super().to_json(**kwargs)
        else:
            dto = {}
        if not no_delete:
            dto.update({'deleted': self.deleted})
            for attr in [attr for attr, value in inspect.getmembers(self) if attr.startswith(self.__prefix__)]:
                dto.update({attr: getattr(self, attr)})
        return dto

    def delete(self):
        if not self.deleted:
            self.deleted = True
            for attr in [attr for attr, value in inspect.getmembers(self) if attr.startswith(self.__prefix__)]:
                original_attr = attr.lstrip(self.__prefix__)
                setattr(self, attr, getattr(self, original_attr))
                setattr(self, original_attr,
                        ''.join(random.choices(string.digits + string.ascii_letters + string.punctuation, k=10)))


class DistributedEntityMixin:
    order = None
    last_modified_at = Column(UtcDateTime(), nullable=False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.last_modified_at = kwargs.pop('last_modified_at', None)

    def to_json(self, **kwargs):
        if hasattr(super(), 'to_json'):
            dto = super().to_json(**kwargs)
        else:
            dto = {}
        if self.last_modified_at:
            dto.update(last_modified_at=self.last_modified_at.strftime(defaults.DATEMARK_FORMAT))
        return dto

    @classmethod
    def from_json(cls, kwargs):
        if 'last_modified_at' in kwargs:
            last_modified_at = kwargs.pop('last_modified_at')
            last_modified_at = datetime.strptime(last_modified_at, defaults.DATEMARK_FORMAT)
            kwargs.update(last_modified_at=last_modified_at)


class UUIDEntityMixin:
    id = Column(UUID, primary_key=True, default=lambda: str(uuid.uuid4()))

    def __init__(self, *args, id=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.id = id or str(uuid.uuid4())

    def to_json(self, **kwargs):
        if hasattr(super(), 'to_json'):
            dto = super().to_json(**kwargs)
        else:
            dto = {}
        if self.id:
            dto.update(id=str(self.id))
        return dto


class UUIDistributedEntityMixin(UUIDEntityMixin, DistributedEntityMixin):

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
