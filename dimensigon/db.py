import logging
import os
import time
import typing as t

from sqlalchemy import create_engine, text
from sqlalchemy.exc import InternalError, OperationalError
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.sql.ddl import CreateTable

from dimensigon import defaults
from dimensigon.core import Dimensigon
from dimensigon.domain.entities import SCHEMA_VERSION, SchemaChanges
from dimensigon.utils.helpers import session_scope
from dimensigon.web import db

_LOGGER = logging.getLogger('dimensigon.db')

PROGRESS_FILE = ".migration_progress"


def setup_db(dm: Dimensigon):
    """Ensure database is ready to fly."""

    dm.engine = create_engine(dm.config.db_uri)
    if not os.path.exists(dm.config.db_uri[len(defaults.DB_PREFIX):]):
        _LOGGER.info(f"Creating database {dm.config.db_uri[len(defaults.DB_PREFIX):]}")
        db.Model.metadata.create_all(dm.engine)
        time.sleep(5)
    else:
        _LOGGER.debug(f"Database {dm.config.db_uri[len(defaults.DB_PREFIX):]} already exists")
    dm.get_session = scoped_session(sessionmaker(bind=dm.engine))
    migrate_schema(dm)

    populate_initial_data(dm)


def migrate_schema(dm: Dimensigon):
    progress_path = dm.config.path(PROGRESS_FILE)
    with session_scope(session=dm.get_session()) as session:

        res = (
            session.query(SchemaChanges)
                .order_by(SchemaChanges.change_id.desc())
                .first()
        )
        current_version = getattr(res, "schema_version", None)

        if current_version is None:
            # first time running database
            sc = SchemaChanges(schema_version=SCHEMA_VERSION)
            session.add(sc)
            current_version = SCHEMA_VERSION

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
    from dimensigon.domain.entities import ActionTemplate, Locker, Server, User, Parameter

    with session_scope(session=dm.get_session()) as session:
        gates = dm.config.http_conf.get('binds', None)

        Server.set_initial(session, gates)

        Locker.set_initial(session)
        ActionTemplate.set_initial(session)
        User.set_initial(session)
        Parameter.set_initial(session)


def _add_columns(engine, table_name, columns_def):
    """Add columns to a table."""
    _LOGGER.warning(
        "Adding columns %s to table %s. Note: this can take several "
        "minutes on large databases and slow computers. Please "
        "be patient!",
        ", ".join(column.split(" ")[0] for column in columns_def),
        table_name,
    )

    columns_def = [f"ADD {col_def}" for col_def in columns_def]

    # try:
    #     engine.execute(
    #         text(
    #             "ALTER TABLE {table} {columns_def}".format(
    #                 table=table_name, columns_def=", ".join(columns_def)
    #             )
    #         )
    #     )
    #     return
    # except (InternalError, OperationalError):
    #     # Some engines support adding all columns at once,
    #     # this error is when they don't
    #     _LOGGER.info("Unable to use quick column add. Adding 1 by 1")

    with engine.connect() as connection:
        for column_def in columns_def:
            try:
                connection.execute(
                    text(
                        "ALTER TABLE {table} {column_def}".format(
                            table=table_name, column_def=column_def
                        )
                    )
                )
            except (InternalError, OperationalError) as err:
                if "duplicate" not in str(err).lower():
                    raise

                _LOGGER.warning(
                    "Column %s already exists on %s, continuing",
                    column_def.split(" ")[1],
                    table_name,
                )


def _rename_columns(engine, tablename, column_renames: t.List[t.Tuple[str, str]]):
    temp_tablename = tablename + '_temp'
    table = db.Model.metadata.tables[tablename]
    tmp_ddl = CreateTable(table).compile(engine).string.replace(tablename, temp_tablename)

    map2old = {t[1]: t[0] for t in column_renames}
    new_column_table = table.columns.keys()

    old_column_table = [map2old.get(item, item) for item in new_column_table]

    with engine.connect() as connection:
        old_c_s = [f'"{c}"' for c in old_column_table]
        new_c_s = [f'"{c}"' for c in new_column_table]
        connection.execute(tmp_ddl)
        try:
            connection.execute(f'INSERT INTO {temp_tablename}({", ".join(new_c_s)}) '
                               f'SELECT {", ".join(old_c_s)} FROM {tablename}')

        except:
            connection.execute(f"DROP TABLE {temp_tablename}")
            raise
        else:
            connection.execute(f"DROP TABLE {tablename}")
            connection.execute(f"ALTER TABLE {temp_tablename} RENAME TO {tablename}")


def _delete_columns(engine, tablename, column_deletes: t.List[str]):
    temp_tablename = tablename + '_temp'
    table = db.Model.metadata.tables[tablename]
    tmp_ddl = CreateTable(table).compile(engine).string.replace(tablename, temp_tablename)

    new_column_table = [k for k in table.columns.keys() if k not in column_deletes]

    with engine.connect() as connection:
        new_c_s = [f'"{c}"' for c in new_column_table]
        connection.execute(tmp_ddl)
        try:
            connection.execute(f'INSERT INTO {temp_tablename}({", ".join(new_c_s)}) '
                               f'SELECT {", ".join(new_c_s)} FROM {tablename}')

        except:
            connection.execute(f"DROP TABLE {temp_tablename}")
            raise
        else:
            connection.execute(f"DROP TABLE {tablename}")
            connection.execute(f"ALTER TABLE {temp_tablename} RENAME TO {tablename}")


def _rename_and_delete_columns(engine, tablename,
                               column_renames: t.List[t.Tuple[str, str]],
                               column_deletes: t.List[str]):
    temp_tablename = tablename + '_temp'
    table = db.Model.metadata.tables[tablename]
    tmp_ddl = CreateTable(table).compile(engine).string.replace(tablename, temp_tablename)

    map2old = {t[1]: t[0] for t in column_renames}
    new_column_table = [k for k in table.columns.keys() if k not in column_deletes]

    old_column_table = [map2old.get(item, item) for item in new_column_table]

    with engine.connect() as connection:
        old_c_s = [f'"{c}"' for c in old_column_table]
        new_c_s = [f'"{c}"' for c in new_column_table]
        connection.execute(tmp_ddl)
        try:
            connection.execute(f'INSERT INTO {temp_tablename}({", ".join(new_c_s)}) '
                               f'SELECT {", ".join(old_c_s)} FROM {tablename}')

        except:
            connection.execute(f"DROP TABLE {temp_tablename}")
            raise
        else:
            connection.execute(f"DROP TABLE {tablename}")
            connection.execute(f"ALTER TABLE {temp_tablename} RENAME TO {tablename}")


def _create_table(engine, tablename):
    table = db.Model.metadata.tables[tablename]
    ddl = CreateTable(table).compile(engine).string
    with engine.connect() as connection:
        connection.execute(ddl)


def _apply_update(engine, new_version, old_version):
    if new_version == 2:
        _rename_columns(engine, 'D_server', [('unreachable', 'alive')])
    elif new_version == 3:
        _add_columns(engine, 'D_server', ['created_on DATETIME'])
        _delete_columns(engine, 'D_server', ['alive'])
        with engine.connect() as connection:
            date = defaults.INITIAL_DATEMARK.strftime('%Y-%m-%d %H:%M:%S.%f')
            connection.execute(
                f"UPDATE D_server SET created_on = '{date}' WHERE created_on IS NULL")
    elif new_version == 4:
        _create_table(engine, 'L_parameter')
