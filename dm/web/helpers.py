import datetime
import re
import threading
import typing as t
from json import JSONEncoder

from flask import abort, current_app
from flask_sqlalchemy import BaseQuery

from dm import defaults
from dm.utils.asyncio import run


class BaseQueryJSON(BaseQuery):
    """SQLAlchemy :class:`~sqlalchemy.orm.query.Query` subclass with convenience methods for querying in a web application.

    This is the default :attr:`~Model.query` object used for models, and exposed as :attr:`~SQLAlchemy.Query`.
    Override the query class for an individual model by subclassing this and setting :attr:`~Model.query_class`.
    """

    def get_or_404(self, ident, description=None):
        """Like :meth:`get` but aborts with 404 if not found instead of returning ``None``."""

        rv = self.get(ident)
        if rv is None:
            abort(404, dict(error=f"{self.column_descriptions[0]['name']} id '{ident}' not found"))
        return rv

    def first_or_404(self, description=None):
        """Like :meth:`first` but aborts with 404 if not found instead of returning ``None``."""

        rv = self.first()
        if rv is None:
            abort(404, dict(error=f"No data in {self.column_descriptions[0]['name']} collection"))
        return rv


def filter_query(entity, filters, exclude: t.Container = None):
    """Generates a sqlalchemy query object filtered by filters.

    entity: entity to filter
    filters: filters in JSON API format https://jsonapi.org/format/#fetching-filtering
    exclude: columns to exclude on filter

    """
    filters = [(re.search('^filter\[(\w+)\]$', k).group(1), v) for k, v in filters.items() if
               k.startswith('filter[')]
    query = entity.query
    for k, v in filters:
        column = getattr(entity, k, None)
        if not column or k in (exclude or []):
            return {'error': f'Invalid filter column: {k}'}, 404
        if ',' in v:
            values = v.split(',')
            query = query.filter(column.in_(values))
        else:
            if v.lower() == 'true':
                v = True
            elif v.lower() == 'false':
                v = False
            query = query.filter(column == v)
    return query


def run_in_background(func: t.Callable, app=None, args=None, kwargs=None):
    args = args or ()
    kwargs = kwargs or {}
    try:
        app = current_app._get_current_object()
    except RuntimeError:
        app = app

    def thread_with_app_context():
        with app.app_context():
            run(func(*args, **kwargs))

    th = threading.Thread(target=thread_with_app_context)
    # th.daemon = True
    th.start()


class DatetimeEncoder(JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            return obj.strftime(defaults.DATETIME_FORMAT)
        return JSONEncoder.default(self, obj)
