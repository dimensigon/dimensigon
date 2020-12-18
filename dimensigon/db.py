import json
import logging
import os
import time
import typing as t

from sqlalchemy import create_engine, text
from sqlalchemy.exc import InternalError, OperationalError, SQLAlchemyError
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.sql.ddl import CreateTable

from dimensigon import defaults
from dimensigon.core import Dimensigon
from dimensigon.domain.entities import SCHEMA_VERSION, SchemaChanges
from dimensigon.utils.helpers import session_scope
from dimensigon.web import db

_LOGGER = logging.getLogger('dm.db')

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
                _LOGGER.info("Upgrading db schema to version %s", new_version)
                _apply_update(dm.engine, new_version, current_version)
                session.add(SchemaChanges(schema_version=new_version))

                _LOGGER.info("Upgrade to version %s done", new_version)
        finally:
            os.remove(dm.config.path(PROGRESS_FILE))


def populate_initial_data(dm: Dimensigon):
    from dimensigon.domain.entities import ActionTemplate, Locker, Server, User, Parameter

    with session_scope(session=dm.get_session()) as session:
        gates = dm.config.http_conf.get('binds', None)

        SchemaChanges.set_initial(session)
        dm.server_id = Server.set_initial(session, gates)

        Locker.set_initial(session, unlock=True)
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


def _rename_table(engine, old_table_name, new_table_name):
    with engine.connect() as connection:
        connection.execute(f"ALTER TABLE {old_table_name} RENAME TO {new_table_name}")


def _rename_columns(engine, table_name, column_renames: t.List[t.Tuple[str, str]]):
    temp_table_name = table_name + '_temp'
    table = db.Model.metadata.tables[table_name]
    tmp_ddl = CreateTable(table).compile(engine).string.replace(table_name, temp_table_name)

    map2old = {t[1]: t[0] for t in column_renames}
    new_column_table = table.columns.keys()

    old_column_table = [map2old.get(item, item) for item in new_column_table]

    with engine.connect() as connection:
        old_c_s = [f'"{c}"' for c in old_column_table]
        new_c_s = [f'"{c}"' for c in new_column_table]
        connection.execute(tmp_ddl)
        try:
            connection.execute(f'INSERT INTO {temp_table_name}({", ".join(new_c_s)}) '
                               f'SELECT {", ".join(old_c_s)} FROM {table_name}')

        except:
            connection.execute(f"DROP TABLE {temp_table_name}")
            raise
        else:
            connection.execute(f"DROP TABLE {table_name}")
            connection.execute(f"ALTER TABLE {temp_table_name} RENAME TO {table_name}")


def _delete_columns(engine, table_name, column_deletes: t.List[str]):
    temp_table_name = table_name + '_temp'
    table = db.Model.metadata.tables[table_name]
    tmp_ddl = CreateTable(table).compile(engine).string.replace(table_name, temp_table_name)

    new_column_table = [k for k in table.columns.keys() if k not in column_deletes]

    with engine.connect() as connection:
        new_c_s = [f'"{c}"' for c in new_column_table]
        connection.execute(tmp_ddl)
        try:
            connection.execute(f'INSERT INTO {temp_table_name}({", ".join(new_c_s)}) '
                               f'SELECT {", ".join(new_c_s)} FROM {table_name}')

        except:
            connection.execute(f"DROP TABLE {temp_table_name}")
            raise
        else:
            connection.execute(f"DROP TABLE {table_name}")
            connection.execute(f"ALTER TABLE {temp_table_name} RENAME TO {table_name}")


def _rename_and_delete_columns(engine, table_name,
                               column_renames: t.List[t.Tuple[str, str]],
                               column_deletes: t.List[str]):
    temp_table_name = table_name + '_temp'
    table = db.Model.metadata.tables[table_name]
    tmp_ddl = CreateTable(table).compile(engine).string.replace(table_name, temp_table_name)

    map2old = {t[1]: t[0] for t in column_renames}
    new_column_table = [k for k in table.columns.keys() if k not in column_deletes]

    old_column_table = [map2old.get(item, item) for item in new_column_table]

    with engine.connect() as connection:
        old_c_s = [f'"{c}"' for c in old_column_table]
        new_c_s = [f'"{c}"' for c in new_column_table]
        connection.execute(tmp_ddl)
        try:
            connection.execute(f'INSERT INTO {temp_table_name}({", ".join(new_c_s)}) '
                               f'SELECT {", ".join(old_c_s)} FROM {table_name}')

        except:
            connection.execute(f"DROP TABLE {temp_table_name}")
            raise
        else:
            connection.execute(f"DROP TABLE {table_name}")
            connection.execute(f"ALTER TABLE {temp_table_name} RENAME TO {table_name}")


def _create_table(engine, table_name):
    table = db.Model.metadata.tables[table_name]
    ddl = CreateTable(table).compile(engine).string
    with engine.connect() as connection:
        connection.execute(ddl)


def _recreate_table(engine, table_name):
    _rename_columns(engine, table_name, [])


def _create_index(engine, table_name, index_name):
    """Create an index for the specified table.
    The index name should match the name given for the index
    within the table definition described in the models
    """
    table = db.Model.metadata.tables[table_name]
    _LOGGER.debug("Looking up index %s for table %s", index_name, table_name)
    # Look up the index object by name from the table is the models
    index_list = [idx for idx in table.indexes if idx.name == index_name]
    if not index_list:
        _LOGGER.debug("The index %s no longer exists", index_name)
        return
    index = index_list[0]
    _LOGGER.debug("Creating %s index", index_name)
    _LOGGER.warning(
        "Adding index `%s` to database. Note: this can take several "
        "minutes on large databases and slow computers. Please "
        "be patient!",
        index_name,
    )
    try:
        index.create(engine)
    except OperationalError as err:
        lower_err_str = str(err).lower()

        if "already exists" not in lower_err_str and "duplicate" not in lower_err_str:
            raise

        _LOGGER.warning(
            "Index %s already exists on %s, continuing", index_name, table_name
        )
    except InternalError as err:
        if "duplicate" not in str(err).lower():
            raise

        _LOGGER.warning(
            "Index %s already exists on %s, continuing", index_name, table_name
        )

    _LOGGER.debug("Finished creating %s", index_name)


def _drop_index(engine, table_name, index_name):
    """Drop an index from a specified table.
    There is no universal way to do something like `DROP INDEX IF EXISTS`
    so we will simply execute the DROP command and ignore any exceptions
    WARNING: Due to some engines (MySQL at least) being unable to use bind
    parameters in a DROP INDEX statement (at least via SQLAlchemy), the query
    string here is generated from the method parameters without sanitizing.
    DO NOT USE THIS FUNCTION IN ANY OPERATION THAT TAKES USER INPUT.
    """
    _LOGGER.debug("Dropping index %s from table %s", index_name, table_name)
    success = False

    # Engines like DB2/Oracle
    try:
        engine.execute(text(f"DROP INDEX {index_name}"))
    except SQLAlchemyError:
        pass
    else:
        success = True

    # Engines like SQLite, SQL Server
    if not success:
        try:
            engine.execute(
                text(
                    "DROP INDEX {table}.{index}".format(
                        index=index_name, table=table_name
                    )
                )
            )
        except SQLAlchemyError:
            pass
        else:
            success = True

    if not success:
        # Engines like MySQL, MS Access
        try:
            engine.execute(
                text(
                    "DROP INDEX {index} ON {table}".format(
                        index=index_name, table=table_name
                    )
                )
            )
        except SQLAlchemyError:
            pass
        else:
            success = True

    if success:
        _LOGGER.debug(
            "Finished dropping index %s from table %s", index_name, table_name
        )
    else:
        if index_name == "ix_states_context_parent_id":
            # Was only there on nightly so we do not want
            # to generate log noise or issues about it.
            return

        _LOGGER.warning(
            "Failed to drop index %s from table %s. Schema "
            "Migration will continue; this is not a "
            "critical operation",
            index_name,
            table_name,
        )


def _apply_update(engine, new_version, old_version):
    pass
    # if new_version == 2:
    #     _rename_columns(engine, 'D_server', [('unreachable', 'alive')])
    # elif new_version == 3:
    #     _add_columns(engine, 'D_server', ['created_on DATETIME'])
    #     _delete_columns(engine, 'D_server', ['alive'])
    #     with engine.connect() as connection:
    #         date = defaults.INITIAL_DATEMARK.strftime('%Y-%m-%d %H:%M:%S.%f')
    #         connection.execute(
    #             f"UPDATE D_server SET created_on = '{date}' WHERE created_on IS NULL")
    # elif new_version == 4:
    #     _create_table(engine, 'L_parameter')
    # elif new_version == 5:
    #     _add_columns(engine, 'D_gate', ['deleted BOOLEAN'])
    #     with engine.connect() as connection:
    #         connection.execute(
    #             f"UPDATE D_gate SET deleted = 0")
    #         connection.execute(
    #             f"UPDATE D_gate SET deleted = 1 "
    #             f" WHERE EXISTS(SELECT * "
    #             f"                FROM D_server "
    #             f"               WHERE  D_server.id == D_gate.server_id and D_server.deleted == 1)")
    # elif new_version == 6:
    #     _create_table(engine, 'D_file')
    #     _create_table(engine, 'D_file_server_association')
    #     _add_columns(engine, 'D_action_template', ['schema JSON', 'description TEXT'])
    #     _add_columns(engine, 'D_step', ['name VARCHAR(40)', 'schema JSON', 'description TEXT'])
    #     with engine.connect() as connection:
    #         schema = json.dumps({"input": {"software_id": {"type": "string",
    #                                                        "description": "software id to send"},
    #                                        "server_id": {"type": "string",
    #                                                      "description": "destination server id"},
    #                                        "dest_path": {"type": "string",
    #                                                      "description": "destination path to send software"},
    #                                        "chunk_size": {"type": "integer"},
    #                                        "max_senders": {"type": "integer"},
    #                                        },
    #                              "required": ["software_id", "server_id"],
    #                              "output": ["file"]
    #                              })
    #         post_process = 'import json\nif cp.success:\n  json_data=json.loads(cp.stdout)\n  vc.set("file", json_data.get("file"))'
    #         code = '{"method": "post",' \
    #                '"view":"api_1_0.send",' \
    #                '"json": {"software_id": "{{input[\'software_id\']}}", ' \
    #                '         "dest_server_id": "{{input[\'server_id\']}}"' \
    #                '{% if \'dest_path\' in input %}, "dest_path":"{{input[\'dest_path\']}}"{% endif %}' \
    #                '{% if \'chunk_size\' in input %}, "chunk_size":"{{input[\'chunk_size\']}}"{% endif %}' \
    #                '{% if \'max_senders\' in input %}, "max_senders":"{{input[\'max_senders\']}}"{% endif %}' \
    #                ', "background": false, "include_transfer_data": true, "force": true} }'
    #         connection.execute(text(
    #             f"UPDATE D_action_template SET schema=:schema, post_process=:post_process , code=:code"
    #             f" WHERE id = '00000000-0000-0000-000a-000000000001'"), schema=schema, post_process=post_process,
    #             code=code)
    #
    #         schema = json.dumps({"input": {"list_server_names": {"type": "array",
    #                                                              "items": {"type": "string"}},
    #                                        "timeout": {"type": "integer"}
    #                                        },
    #                              "required": ["list_server_names"]
    #                              })
    #         code = ""
    #         connection.execute(text(
    #             f"UPDATE D_action_template SET schema=:schema, code=:code"
    #             f" WHERE id = '00000000-0000-0000-000a-000000000002'"), schema=schema, code=code)
    #
    #         schema = json.dumps({"input": {"orchestration_id": {"type": "string"},
    #                                        "hosts": {"type": ["string", "array", "object"],
    #                                                  "items": {"type": "string"},
    #                                                  "minItems": 1,
    #                                                  "patternProperties": {
    #                                                      ".*": {"anyOf": [{"type": "string"},
    #                                                                       {"type": "array",
    #                                                                        "items": {"type": "string"},
    #                                                                        "minItems": 1
    #                                                                        },
    #                                                                       ]
    #                                                             },
    #                                                  },
    #                                                  },
    #                                        },
    #                              "required": ["orchestration_id", "hosts"]
    #                              })
    #         code = ""
    #         connection.execute(text(
    #             f"UPDATE D_action_template SET schema=:schema, code=:code"
    #             f" WHERE id = '00000000-0000-0000-000a-000000000003'"), schema=schema, code=code)
    #
    #         schema = json.dumps({"input": {"list_server_names": {"type": "array",
    #                                                              "items": {"type": "string"}},
    #                                        "timeout": {"type": "integer"}
    #                                        },
    #                              "required": ["list_server_names"]
    #                              })
    #         code = ""
    #         connection.execute(text(
    #             f"UPDATE D_action_template SET schema=:schema, code=:code"
    #             f" WHERE id = '00000000-0000-0000-000a-000000000004'"), schema=schema, code=code)
    #
    #         schema = json.dumps({"input": {"list_server_names": {"type": "array",
    #                                                              "items": {"type": "string"}},
    #                                        },
    #                              "required": ["list_server_names"]
    #                              })
    #         code = ""
    #         connection.execute(text(
    #             f"UPDATE D_action_template SET schema=:schema, code=:code"
    #             f" WHERE id = '00000000-0000-0000-000a-000000000005'"), schema=schema, code=code)
    #
    #         _LOGGER.warning("After this database release, attribute 'parameters' from Step and ActionTemplate are "
    #                         "deprecated. You need to recreate all user actions and orchestrations using the schema "
    #                         "attribute. See documentation for more information.")
    # elif new_version == 7:
    #     _rename_table(engine, 'D_software_server', 'D_software_server_association')
    #     _add_columns(engine, 'D_software_server_association', ['deleted BOOLEAN'])
    #     _add_columns(engine, 'D_software', ['deleted BOOLEAN', '"$$name"  VARCHAR(80)'])
    #
    #     with engine.connect() as connection:
    #         connection.execute(text("UPDATE L_parameter SET dump = null, load= null"))
    # elif new_version == 8:
    #     _recreate_table(engine, 'D_gate')
    #     _rename_columns(engine, 'D_user', [('user', 'name')])
    #     _create_table(engine, 'D_vault')
    # elif new_version == 9:
    #     _recreate_table(engine, 'D_gate')
    #     with engine.connect() as connection:
    #         schema = json.dumps({"input": {"software_id": {"type": "string",
    #                                                        "description": "software id to send"},
    #                                        "server_id": {"type": "string",
    #                                                      "description": "destination server id"},
    #                                        "dest_path": {"type": "string",
    #                                                      "description": "destination path to send software"},
    #                                        "chunk_size": {"type": "integer"},
    #                                        "max_senders": {"type": "integer"},
    #                                        },
    #                              "required": ["software_id", "server_id"],
    #                              "output": ["file"]
    #                              })
    #         connection.execute(text(
    #             f"UPDATE D_action_template SET schema=:schema"
    #             f" WHERE id = '00000000-0000-0000-000a-000000000001'"), schema=schema)
    #
    #         schema = json.dumps({"input": {"server_names": {"type": ["array", "string"],
    #                                                         "items": {"type": "string"}},
    #                                        },
    #                              "required": ["server_names"]
    #                              })
    #         connection.execute(text(
    #             f"UPDATE D_action_template SET schema=:schema"
    #             f" WHERE id = '00000000-0000-0000-000a-000000000002'"), schema=schema)
    #
    #         schema = {"input": {"orchestration": {"type": "string",
    #                                               "description": "orchestration name or ID to "
    #                                                              "execute. If no version "
    #                                                              "specified, the last one will "
    #                                                              "be executed"},
    #                             "version": {"type": "integer"},
    #                             "hosts": {"type": ["string", "array", "object"],
    #                                       "items": {"type": "string"},
    #                                       "minItems": 1,
    #                                       "patternProperties": {
    #                                           ".*": {"anyOf": [{"type": "string"},
    #                                                            {"type": "array",
    #                                                             "items": {"type": "string"},
    #                                                             "minItems": 1
    #                                                             },
    #                                                            ]
    #                                                  },
    #                                       },
    #                                       },
    #                             },
    #                   "required": ["orchestration", "hosts"]
    #                   }
    #
    #         connection.execute(text(
    #             f"UPDATE D_action_template SET schema=:schema"
    #             f" WHERE id = '00000000-0000-0000-000a-000000000003'"), schema=schema)
    #
    #         schema = json.dumps({"input": {"server_names": {"type": ["array", "string"],
    #                                                         "items": {"type": "string"}},
    #                                        },
    #                              "required": ["server_names"]
    #                              })
    #         connection.execute(text(
    #             f"UPDATE D_action_template SET schema=:schema"
    #             f" WHERE id = '00000000-0000-0000-000a-000000000004'"), schema=schema)
    # elif new_version == 10:
    #     _recreate_table(engine, 'D_gate')