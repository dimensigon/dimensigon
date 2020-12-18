import logging
import threading
import time
from contextlib import contextmanager

from sqlalchemy import event, inspect
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import Pool

from dimensigon.utils.helpers import get_distributed_entities, get_now
from dimensigon.web import db
# Server is used in most of the entities. It must be imported first
from .server import Server
from .action_template import ActionTemplate, ActionType
from .catalog import Catalog
from .dimension import Dimension
from .execution import StepExecution, OrchExecution
from .file import File, FileServerAssociation
from .gate import Gate
from .locker import Locker, State, Scope
from .log import Log, Mode as LogMode
from .orchestration import Orchestration
from .parameter import Parameter
from .route import Route
from .schema_changes import SchemaChanges
from .service import Service
from .software import Software, SoftwareServerAssociation
from .step import Step
from .transfer import Transfer, Status as TransferStatus
from .user import User
from .vault import Vault

SCHEMA_VERSION = 1

_LOGGER = logging.getLogger('dm.catalog')

__all__ = [
    "ActionTemplate",
    "ActionType",
    "Catalog",
    "Dimension",
    "StepExecution",
    "OrchExecution",
    "File",
    "FileServerAssociation",
    "Gate",
    "Locker",
    "State",
    "Scope",
    "Log",
    "LogMode",
    "Orchestration",
    "Parameter",
    "Route",
    "SchemaChanges",
    "Service",
    "Server",
    "Software",
    "SoftwareServerAssociation",
    "Step",
    "Transfer",
    "TransferStatus",
    "User",
    "Vault",
]

catalog = threading.local()


@contextmanager
def bypass_datamark_update(session=None):
    if session is None:
        session = db.session

    session.flush()
    update_datemark(False)
    try:
        yield None
    finally:
        session.flush()
        update_datemark(True)


def update_datemark(set):
    catalog.datemark = set


for name, entity in get_distributed_entities():
    def receive_before_insert(mapper, connection, target):
        if not hasattr(catalog, 'data'):
            catalog.data = {}
        if getattr(catalog, 'datemark', True):
            target.last_modified_at = get_now()
        if not target.__class__ in catalog.data:
            catalog.data.update({target.__class__: target.last_modified_at})
        else:
            catalog.data.update(
                {target.__class__: max(target.last_modified_at, catalog.data[target.__class__])})


    def receive_before_update(mapper, connection, target):
        # validate if target is updated
        it = inspect(target)
        columns = [c for c in mapper.columns.keys() if not c.startswith('l_')]
        changed = any([attr.history.has_changes() for attr in it.attrs if attr.key in columns])
        if changed:
            if not hasattr(catalog, 'data'):
                catalog.data = {}
            if getattr(catalog, 'datemark', True):
                target.last_modified_at = get_now()
            if not target.__class__ in catalog.data:
                catalog.data.update({target.__class__: target.last_modified_at})
            else:
                catalog.data.update(
                    {target.__class__: max(target.last_modified_at, catalog.data[target.__class__])})


    event.listen(entity, 'before_insert', receive_before_insert, propagate=False)
    event.listen(entity, 'before_update', receive_before_update, propagate=False)


@event.listens_for(db.session, 'after_commit')
def receive_after_commit(session):
    # TODO: run this peace of code in a thread to allow the request end while executing the queries
    if hasattr(catalog, 'data'):
        # create a different session as the request session is already commited
        engine = db.get_engine()
        Session = sessionmaker(bind=engine)
        s = Session()
        for e, last_modified_at in catalog.data.items():
            # last_modified_at = s.query(func.max(e.last_modified_at)).scalar()
            c = s.query(Catalog).filter_by(entity=e.__name__).first()
            if c is None:
                c = Catalog(entity=e.__name__, last_modified_at=last_modified_at)
            else:
                if c.last_modified_at < last_modified_at:
                    c.last_modified_at = last_modified_at
            _LOGGER.debug(f'changed catalog {c}')
            s.add(c)
            s.commit()
            del c
        catalog.data = {}
        s.close()


@event.listens_for(Orchestration, 'refresh')
def receive_refresh(target, context, attrs):
    "listen for the 'refresh' event"
    target.init_on_load()


@event.listens_for(Pool, "connect")
def my_on_connect(dbapi_con, connection_record):
    # print("New DBAPI connection:", dbapi_con)
    dbapi_con.execute("PRAGMA journal_mode=WAL")
    # dbapi_con.execute("PRAGMA busy_timeout=10000")


_query_logger = logging.getLogger('dm.query')


@event.listens_for(Engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    conn.info.setdefault('query_start_time', []).append(time.time())


@event.listens_for(Engine, "after_cursor_execute")
def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    total = time.time() - conn.info['query_start_time'].pop(-1)
    if total > 1:
        _query_logger.warning("Elapsed Time: %f\n%s\n%s", total, statement, parameters)
