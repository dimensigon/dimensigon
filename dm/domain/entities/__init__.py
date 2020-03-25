import threading
from contextlib import contextmanager

from sqlalchemy import event
from sqlalchemy.orm import sessionmaker, object_session

from dm.utils.helpers import get_distributed_entities, get_now
from dm.web import db
from .action_template import ActionTemplate, ActionType
from .catalog import Catalog
from .dimension import Dimension
from .execution import Execution
from .gate import Gate
from .locker import Locker, State, Scope
from .log import Log
from .orchestration import Orchestration
from .route import Route
from .server import Server
from .service import Service
from .software import Software, SoftwareServerAssociation
from .transfer import Transfer, Status as TransferStatus

__all__ = [
    "ActionTemplate",
    "ActionType",
    "Catalog",
    "Dimension",
    "Execution",
    "Gate",
    "Orchestration",
    "Log",
    "Route",
    "Service",
    "Server",
    "Software",
    "SoftwareServerAssociation",
    "Transfer",
    "TransferStatus",
    "Locker"
]

catalog = threading.local()


@contextmanager
def bypass_datamark_update():
    update_datamark(False)
    try:
        yield None
    finally:
        update_datamark(True)


def update_datamark(set):
    catalog.datamark = set


def set_events():
    for name, entity in get_distributed_entities():
        def receive_before_insert(mapper, connection, target):
            if not hasattr(catalog, 'data'):
                catalog.data = {}
            if getattr(catalog, 'datamark', True):
                target.last_modified_at = get_now()
            if not target.__class__ in catalog.data:
                catalog.data.update({target.__class__: target.last_modified_at})
            else:
                catalog.data.update(
                    {target.__class__: max(target.last_modified_at, catalog.data[target.__class__])})

        def receive_before_update(mapper, connection, target):
            # validate if target is updated
            if object_session(target).is_modified(target, include_collections=False):
                if not hasattr(catalog, 'data'):
                    catalog.data = {}
                if getattr(catalog, 'datamark', True):
                    target.last_modified_at = get_now()
                if not target.__class__ in catalog.data:
                    catalog.data.update({target.__class__: target.last_modified_at})
                else:
                    catalog.data.update(
                        {target.__class__: max(target.last_modified_at, catalog.data[target.__class__])})

        event.listen(entity, 'before_insert', receive_before_insert, propagate=False)
        event.listen(entity, 'before_update', receive_before_update, propagate=False)


set_events()


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
            s.add(c)
            s.commit()
        catalog.data = {}
        s.close()
