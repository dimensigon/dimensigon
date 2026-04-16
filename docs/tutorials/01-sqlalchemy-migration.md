# SQLAlchemy 2.x Migration Guide for Dimensigon Developers

## Overview

Dimensigon 3.0 migrates from SQLAlchemy 1.x query patterns to the modern
SQLAlchemy 2.x style. This tutorial shows how queries work in the new codebase,
how to write new models, and how to use the helpers provided by the framework.

If you are extending Dimensigon with custom entities or writing new API
endpoints, this guide covers every pattern you will need.

## Prerequisites

- Python 3.8 or later
- Dimensigon 3.0 installed (`pip install -e .`)
- Flask-SQLAlchemy 3.x (bundled with Dimensigon)
- Basic familiarity with SQLAlchemy ORM concepts

## 1. The New Query Style: `select()` Replaces `.query`

### Old pattern (SQLAlchemy 1.x / Flask-SQLAlchemy 2.x)

```python
# DO NOT USE -- legacy pattern
servers = Server.query.all()
server = Server.query.filter_by(name='web01').first()
count = Server.query.count()
```

### New pattern (SQLAlchemy 2.x / Flask-SQLAlchemy 3.x)

```python
from sqlalchemy import select
from dimensigon.web import db
from dimensigon.domain.entities import Server

# All rows
servers = db.session.execute(select(Server)).scalars().all()

# Filtered query
server = db.session.execute(
    select(Server).filter_by(name='web01')
).scalars().first()

# Count rows
from sqlalchemy import func
count = db.session.execute(
    select(func.count()).select_from(Server)
).scalar()
```

Key points:

- Always import `select` from `sqlalchemy`, not from Flask-SQLAlchemy.
- `db.session.execute()` returns `Result` objects. Call `.scalars()` to unwrap
  individual column values, then `.all()` or `.first()`.
- `.scalar()` (without the trailing `s`) returns a single value, useful for
  aggregates like `count()` or `max()`.

## 2. Primary-Key Lookups: `db.session.get()`

### Old pattern

```python
server = Server.query.get(server_id)
```

### New pattern

```python
server = db.session.get(Server, server_id)
```

`db.session.get()` uses the identity map, so repeated lookups for the same
primary key within a single request are essentially free.

## 3. The `get_or_raise()` Helper

Dimensigon provides a convenience function that combines a primary-key lookup
with soft-delete awareness. If the entity is not found or has been soft-deleted,
it raises `EntityNotFound`, which the error handler converts to a 404 JSON
response.

```python
from dimensigon.web.helpers import get_or_raise
from dimensigon.domain.entities import Server

# Raises EntityNotFound if missing or deleted
server = get_or_raise(Server, server_id)
```

The implementation lives in `dimensigon/web/helpers.py`:

```python
def get_or_raise(model, ident):
    """Get a model instance by primary key, or raise EntityNotFound.

    Handles soft-delete models by checking the 'deleted' attribute.
    This is the SQLAlchemy 2.x equivalent of Model.query.get_or_raise().
    """
    from dimensigon.web import db

    rv = db.session.get(model, ident)
    if rv is None or (hasattr(rv, 'deleted') and rv.deleted):
        raise EntityNotFound(model.__name__, ident)
    return rv
```

Use `get_or_raise()` in every API resource method where a missing entity should
return 404. See `dimensigon/web/api_1_0/resources/server.py` for real usage.

## 4. Common Query Patterns

### Filtering with `.where()`

```python
from sqlalchemy import select
from dimensigon.domain.entities import Server, Gate

# Simple equality
stmt = select(Server).where(Server.name == 'web01')

# Multiple conditions
stmt = select(Server).where(
    Server.deleted == False,
    Server.name.like('web%')
)

# Join + filter
stmt = (
    select(Server)
    .filter_by(deleted=False)
    .join(Gate.server)
    .where(Gate.ip == '10.0.0.5')
)
servers = db.session.execute(stmt).scalars().all()
```

### Ordering and limiting

```python
stmt = (
    select(Server)
    .order_by(Server.created_on)
    .limit(10)
)
servers = db.session.execute(stmt).scalars().all()
```

### Subqueries for counting

```python
from sqlalchemy import func, select

inner = select(Server).filter_by(l_ignore_on_lock=False)
count = db.session.execute(
    select(func.count()).select_from(inner.subquery())
).scalar()
```

### Exists / one_or_none

```python
user = db.session.execute(
    select(User).filter_by(name='root')
).scalars().one_or_none()
# Returns None if no match, raises if multiple matches
```

## 5. The `filter_query()` Helper

For API endpoints that accept JSON API filter parameters, Dimensigon provides
`filter_query()` which builds a `select()` statement from request arguments:

```python
from dimensigon.web.helpers import filter_query
from dimensigon.domain.entities import Server

# Called from a Flask resource method:
stmt = filter_query(Server, request.args)
results = db.session.execute(stmt).scalars().all()
```

This supports query parameters like `?filter[name]=web01&filter[deleted]=false`.

## 6. Writing New Models Compatible with SQLAlchemy 2.x

### Base classes

Dimensigon provides several mixins in `dimensigon/domain/entities/base.py`:

| Mixin | Provides |
|---|---|
| `UUIDEntityMixin` | UUID primary key with auto-generation |
| `DistributedEntityMixin` | `last_modified_at` for catalog sync |
| `SoftDeleteMixin` | `deleted` flag and `query_class = QueryWithSoftDelete` |
| `UUIDistributedEntityMixin` | Combines UUID + distributed entity |
| `EntityReprMixin` | Clean `__repr__` and `__str__` |

### The `__allow_unmapped__` flag

Every mixin sets `__allow_unmapped__ = True` so that SQLAlchemy 2.0 does not
complain about legacy column definitions:

```python
class SoftDeleteMixin:
    __allow_unmapped__ = True
    deleted = Column(Boolean(), default=False)
    query_class = QueryWithSoftDelete
```

### Example: Adding a new entity

```python
# dimensigon/domain/entities/alert.py

import uuid
from sqlalchemy import Column, String, Boolean, Text
from dimensigon.domain.entities.base import (
    UUIDistributedEntityMixin, SoftDeleteMixin, EntityReprMixin
)
from dimensigon.utils.typos import UtcDateTime
from dimensigon.utils.helpers import get_now
from dimensigon.web import db


class Alert(UUIDistributedEntityMixin, SoftDeleteMixin, EntityReprMixin, db.Model):
    __tablename__ = 'D_alert'
    order = 50  # catalog sync order

    name = db.Column(db.String(100), nullable=False)
    severity = db.Column(db.String(20), nullable=False, default='info')
    message = db.Column(db.Text)
    acknowledged = db.Column(db.Boolean, default=False)
    created_at = db.Column(UtcDateTime(timezone=True), default=get_now)

    def __init__(self, name, severity='info', message=None, **kwargs):
        super().__init__(**kwargs)
        self.name = name
        self.severity = severity
        self.message = message
        self.created_at = get_now()

    def to_json(self, **kwargs):
        data = super().to_json(**kwargs)
        data.update(
            name=self.name,
            severity=self.severity,
            message=self.message,
            acknowledged=self.acknowledged,
        )
        return data

    @classmethod
    def from_json(cls, kwargs):
        super().from_json(kwargs)
        return cls(**kwargs)
```

Then register it in `dimensigon/domain/entities/__init__.py`:

```python
from .alert import Alert
```

### Querying your new entity

```python
from sqlalchemy import select
from dimensigon.domain.entities.alert import Alert
from dimensigon.web import db

# Create
alert = Alert(name='DiskFull', severity='critical', message='/var is 95% full')
db.session.add(alert)
db.session.commit()

# Read all critical alerts
stmt = select(Alert).where(Alert.severity == 'critical', Alert.deleted == False)
alerts = db.session.execute(stmt).scalars().all()

# Lookup by primary key
alert = db.session.get(Alert, alert_id)

# Soft-delete-aware lookup
from dimensigon.web.helpers import get_or_raise
alert = get_or_raise(Alert, alert_id)  # raises 404 if missing or deleted

# Acknowledge
alert.acknowledged = True
db.session.commit()
```

## 7. `cache_ok = True` on TypeDecorators

SQLAlchemy 2.x issues a warning if a custom `TypeDecorator` does not declare
whether it is safe to cache. Dimensigon solves this with a base class in
`dimensigon/utils/typos.py`:

```python
class TypeDecorator(types.TypeDecorator):
    cache_ok = True

    def __repr__(self):
        return self.impl.__repr__()
```

All custom types (`UUID`, `UtcDateTime`, `ScalarListType`, `PrivateKey`,
`PublicKey`, `IP`, `Pickle`, `Dill`) inherit from this base and automatically
have `cache_ok = True`. If you create a new custom type, inherit from
`dimensigon.utils.typos.TypeDecorator` instead of
`sqlalchemy.types.TypeDecorator`:

```python
from dimensigon.utils.typos import TypeDecorator
from sqlalchemy import types

class MyCustomType(TypeDecorator):
    impl = types.Text()
    # cache_ok = True is inherited

    def process_bind_param(self, value, dialect):
        ...

    def process_result_value(self, value, dialect):
        ...
```

## 8. Session Management

Dimensigon uses Flask-SQLAlchemy's scoped session, so `db.session` is
request-scoped in web contexts. A few things to remember:

- Always `db.session.commit()` after writes in API endpoints.
- Use `db.session.rollback()` on errors (the `@rollback_on_error` decorator
  in `dimensigon/web/decorators.py` handles this automatically).
- For background tasks, use the `session_scope()` context manager from
  `dimensigon/web/helpers.py`:

```python
from dimensigon.web.helpers import session_scope

with session_scope() as session:
    server = session.execute(select(Server).filter_by(name='web01')).scalars().first()
    server.granules.append('new-granule')
    # commits on exit, rolls back on exception
```

## Troubleshooting

### `SAWarning: TypeDecorator ... will not produce a cache key`

Your custom type needs `cache_ok = True`. Inherit from
`dimensigon.utils.typos.TypeDecorator` instead of `sqlalchemy.types.TypeDecorator`.

### `AttributeError: 'QueryWithSoftDelete' object has no attribute '_mapper_zero'`

This means code is using the old Flask-SQLAlchemy 2.x internal API. The fix is
to use `sqlalchemy.inspect()` instead. See `dimensigon/web/helpers.py` for the
updated `with_deleted()` method.

### `Model.query.get()` returns deleted records

The `QueryWithSoftDelete` class filters out deleted records by default.
Use `.with_deleted()` to include them:

```python
# Only non-deleted
server = Server.query.get(server_id)

# Including deleted
server = Server.query.with_deleted().get(server_id)

# Preferred 2.x style -- use get_or_raise for soft-delete awareness
from dimensigon.web.helpers import get_or_raise
server = get_or_raise(Server, server_id)
```

### `DetachedInstanceError` in background threads

If you access a model outside the request context, the session is closed.
Use `session_scope()` to create a new session in background tasks.

## Related Features

- **Soft-delete pattern**: `dimensigon/domain/entities/base.py` (SoftDeleteMixin)
- **Catalog synchronization**: `dimensigon/domain/entities/__init__.py` (event listeners)
- **Filter queries for APIs**: `dimensigon/web/helpers.py` (filter_query)
- **Error handling**: `dimensigon/web/errors.py` (EntityNotFound, NoDataFound)
