import logging
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session

from dimensigon.core import Dimensigon
from dimensigon.domain.entities import SCHEMA_VERSION, SchemaChanges
from dimensigon.utils.helpers import session_scope
from dimensigon.web import db

_LOGGER = logging.getLogger(__name__)

PROGRESS_FILE = ".migration_progress"


def setup_db(dm: Dimensigon):
    """Ensure database is ready to fly."""

    dm.engine = create_engine(dm.config.db_uri)

    dm.get_session = scoped_session(sessionmaker(bind=dm.engine))
    db.Model.metadata.create_all(dm.engine)

    migrate_schema(dm)

    populate_initial_data(dm)


def migrate_schema(dm: Dimensigon):
    progress_path = dm.config.path(PROGRESS_FILE)
    with session_scope(session=dm.get_session()) as session:
        result = session.query(SchemaChanges).count()

        res = (
            session.query(SchemaChanges)
                .order_by(SchemaChanges.change_id.desc())
                .first()
        )
        current_version = getattr(res, "schema_version", None)

        if current_version is None:
            # first time running database
            sc = SchemaChanges(schema_version=0)
            session.add(sc)
            current_version = 0

        if current_version == SCHEMA_VERSION:
            # Clean up if old migration left file
            if os.path.isfile(progress_path):
                _LOGGER.warning("Found existing migration file, cleaning up")
                os.remove(dm.config.path(PROGRESS_FILE))
            return

        with open(progress_path, "w"):
            pass

        _LOGGER.warning(
            "Database is about to upgrade. Schema version: %s", current_version
        )

        try:
            for version in range(current_version, SCHEMA_VERSION):
                new_version = version + 1
                _LOGGER.info("Upgrading recorder db schema to version %s", new_version)
                _apply_update(dm.engine, new_version, current_version)
                session.add(SchemaChanges(schema_version=new_version))

                _LOGGER.info("Upgrade to version %s done", new_version)
        finally:
            os.remove(dm.config.path(PROGRESS_FILE))


def populate_initial_data(dm: Dimensigon):
    from dimensigon.domain.entities import ActionTemplate, Locker, Server, User

    with session_scope(session=dm.get_session()) as session:
        gates = dm.config.http_conf.get('binds', None)

        Server.set_initial(session, gates)

        Locker.set_initial(session)
        ActionTemplate.set_initial(session)
        User.set_initial(session)



def _apply_update(engine, new_version, old_version):
    pass
