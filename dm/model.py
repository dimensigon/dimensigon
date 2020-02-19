from flask_sqlalchemy import DefaultMeta
from sqlalchemy import orm
from sqlalchemy.ext.declarative import declarative_base, DeclarativeMeta
from sqlalchemy.orm import Query
from sqlalchemy.orm.exc import UnmappedClassError

from dm.db import Session


class Model(object):
    """Base class for SQLAlchemy declarative base model.
    To define models, subclass :attr:`db.Model <SQLAlchemy.Model>`, not this
    class. To customize ``db.Model``, subclass this and pass it as
    ``model_class`` to :class:`SQLAlchemy`.
    """

    #: Query class used by :attr:`query`. Defaults to
    # :class:`SQLAlchemy.Query`, which defaults to :class:`BaseQuery`.
    query_class = None

    #: Convenience property to query the database for instances of this model
    # using the current session. Equivalent to ``db.session.query(Model)``
    # unless :attr:`query_class` has been changed.
    query = None


class _QueryProperty(object):

    def __get__(self, obj, type):
        try:
            mapper = orm.class_mapper(type)
            if mapper:
                return type.query_class(mapper, session=Session())
        except UnmappedClassError:
            return None


def make_declarative_base(model, metadata=None):
    """Creates the declarative base that all models will inherit from.
    :param model: base model class (or a tuple of base classes) to pass
        to :func:`~sqlalchemy.ext.declarative.declarative_base`. Or a class
        returned from ``declarative_base``, in which case a new base class
        is not created.
    :param metadata: :class:`~sqlalchemy.MetaData` instance to use, or
        none to use SQLAlchemy's default.
    .. versionchanged 2.3.0::
        ``model`` can be an existing declarative base in order to support
        complex customization such as changing the metaclass.
    """
    if not isinstance(model, DeclarativeMeta):
        model = declarative_base(
            cls=model,
            name='Model',
            metadata=metadata,
            metaclass=DefaultMeta
        )

    # if user passed in a declarative base and a metaclass for some reason,
    # make sure the base uses the metaclass
    if metadata is not None and model.metadata is not metadata:
        model.metadata = metadata

    if not getattr(model, 'query_class', None):
        model.query_class = Query

    model.query = _QueryProperty()
    return model


Base = make_declarative_base(Model)
