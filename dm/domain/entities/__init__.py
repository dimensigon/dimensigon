from datetime import datetime

from flask import g
from sqlalchemy import event
from sqlalchemy.orm import object_session

from .action_template import ActionTemplate, ActionType
from .catalog import Catalog
from .dimension import Dimension
from .execution import Execution
from .log import Log
from .orchestration import Orchestration
from .route import Route
from .server import Server
from .service import Service
from .software import Software, SoftwareServerAssociation, Family as SoftwareFamily

__all__ = [
    "ActionTemplate",
    "ActionType",
    "Catalog",
    "Dimension",
    "Execution",
    "Orchestration",
    "Log",
    "Route",
    "Service",
    "Server",
    "Software",
    "SoftwareFamily",
    "SoftwareServerAssociation"
]

from dm.utils.helpers import get_distributed_entities
from dm.web import db, session_scope

for name, entity in get_distributed_entities():
    def receive_before_insert(mapper, connection, target):
        target.last_modified_at = datetime.now()
        if 'catalog' not in g:
            g.catalog = {}
        if not entity in g.catalog:
            g.catalog.update({entity: target.last_modified_at})


    def receive_before_update(mapper, connection, target):
        if object_session(target).is_modified(target, include_collections=False):
            target.last_modified_at = datetime.now()
            if 'catalog' not in g:
                g.catalog = {}
            if not entity in g.catalog:
                g.catalog.update({entity: target.last_modified_at})


    event.listen(entity, 'before_insert', receive_before_insert)
    event.listen(entity, 'before_update', receive_before_update)



@event.listens_for(db.session, 'after_commit')
def receive_after_commit(session):
    # TODO: run this peace of code in a thread to allow the request end while executing the queries
    if 'catalog' in g:
        with session_scope() as s:
            for e, last_modified_at in g.catalog.items():
                # last_modified_at = s.query(func.max(e.last_modified_at)).scalar()
                c = s.query(Catalog).filter_by(entity=e.__name__).first()
                if c is None:
                    c = Catalog(entity=e.__name__, last_modified_at=last_modified_at)
                else:
                    if c.last_modified_at < last_modified_at:
                        c.last_modified_at = last_modified_at
                s.add(c)
                s.commit()
