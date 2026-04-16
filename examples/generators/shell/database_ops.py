"""Shell action generators for database operations."""

from examples.generators.base_generator import ShellActionGenerator


class DatabaseOpsGenerator(ShellActionGenerator):
    category = "shell.database_ops"
    subcategory = "database_ops"

    def seeds(self):
        return [
            {
                'name': 'psql-create-database',
                'template': {
                    'name': '{env}-psql-create-db',
                    'action_type': 'SHELL',
                    'code': 'if psql -h {{input.host}} -U {{input.admin_user}} -lqt 2>/dev/null | cut -d"|" -f1 | grep -qw "{{input.database}}"; then echo "Database {{input.database}} already exists"; else psql -h {{input.host}} -U {{input.admin_user}} -c "CREATE DATABASE {{input.database}} OWNER {{input.owner}} ENCODING \'{{input.encoding}}\' LC_COLLATE \'{{input.locale}}\' LC_CTYPE \'{{input.locale}}\' TEMPLATE template0;" 2>&1 && echo "Database {{input.database}} created (owner: {{input.owner}}, encoding: {{input.encoding}})"; fi',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'host': {'type': 'string', 'description': 'PostgreSQL host address'},
                            'admin_user': {'type': 'string', 'description': 'Admin user with CREATE DATABASE privilege'},
                            'database': {'type': 'string', 'description': 'Name of the database to create'},
                            'owner': {'type': 'string', 'description': 'Database owner role'},
                            'encoding': {'type': 'string', 'description': 'Character encoding (e.g. UTF8)'},
                            'locale': {'type': 'string', 'description': 'Locale for collation (e.g. en_US.UTF-8)'},
                        },
                        'required': ['host', 'admin_user', 'database', 'owner', 'encoding', 'locale'],
                    },
                },
                'params': {'env': ['production', 'staging', 'development', 'test']},
                'prompts': [
                    'Create a PostgreSQL database in the {env} environment',
                    'Write a DM action to create a new {env} PostgreSQL database',
                    'Generate a shell action for psql database creation in {env}',
                ],
                'explanation': 'Creates a new PostgreSQL database in the {env} environment with specified owner and encoding.',
                'features': ['schema_variables'],
            },
            {
                'name': 'psql-create-user',
                'template': {
                    'name': '{env}-psql-create-user',
                    'action_type': 'SHELL',
                    'code': 'psql -h {{input.host}} -U {{input.admin_user}} <<SQL\nDO \\$\\$\nBEGIN\n  IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = \'{{input.new_user}}\') THEN\n    CREATE ROLE {{input.new_user}} LOGIN PASSWORD \'{{input.password}}\';\n    RAISE NOTICE \'Role created: {{input.new_user}}\';\n  ELSE\n    RAISE NOTICE \'Role already exists: {{input.new_user}}\';\n  END IF;\nEND\n\\$\\$;\nGRANT CONNECT ON DATABASE {{input.database}} TO {{input.new_user}};\nGRANT USAGE ON SCHEMA public TO {{input.new_user}};\nGRANT {{input.privileges}} ON ALL TABLES IN SCHEMA public TO {{input.new_user}};\nALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT {{input.privileges}} ON TABLES TO {{input.new_user}};\nSQL\necho "User {{input.new_user}} configured with {{input.privileges}} on {{input.database}}"',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'host': {'type': 'string', 'description': 'PostgreSQL host address'},
                            'admin_user': {'type': 'string', 'description': 'Admin user with CREATEROLE privilege'},
                            'new_user': {'type': 'string', 'description': 'Username for the new role'},
                            'password': {'type': 'string', 'description': 'Password for the new role'},
                            'database': {'type': 'string', 'description': 'Database to grant access to'},
                            'privileges': {'type': 'string', 'description': 'Privileges to grant (e.g. SELECT, SELECT,INSERT,UPDATE,DELETE, ALL)'},
                        },
                        'required': ['host', 'admin_user', 'new_user', 'password', 'database', 'privileges'],
                    },
                },
                'params': {'env': ['production', 'staging', 'development', 'reporting']},
                'prompts': [
                    'Create a PostgreSQL user with privileges in the {env} environment',
                    'Write a DM action to add a new {env} database user with grants',
                    'Generate a shell action for psql user creation and privilege assignment in {env}',
                ],
                'explanation': 'Creates a PostgreSQL user in the {env} environment with specified database privileges and default grants.',
                'features': ['schema_variables'],
                'difficulty': 'intermediate',
            },
            {
                'name': 'mysql-grant-privileges',
                'template': {
                    'name': '{env}-mysql-grant',
                    'action_type': 'SHELL',
                    'code': 'mysql -h {{input.host}} -u {{input.admin_user}} -e "CREATE USER IF NOT EXISTS \'{{input.grant_user}}\'@\'{{input.grant_host}}\' IDENTIFIED BY \'{{input.password}}\'; GRANT {{input.privileges}} ON {{input.database}}.* TO \'{{input.grant_user}}\'@\'{{input.grant_host}}\'; FLUSH PRIVILEGES;" 2>&1 && mysql -h {{input.host}} -u {{input.admin_user}} -e "SHOW GRANTS FOR \'{{input.grant_user}}\'@\'{{input.grant_host}}\';" 2>&1 && echo "Privileges granted to {{input.grant_user}}@{{input.grant_host}} on {{input.database}}"',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'host': {'type': 'string', 'description': 'MySQL host address'},
                            'admin_user': {'type': 'string', 'description': 'Admin user with GRANT privilege'},
                            'grant_user': {'type': 'string', 'description': 'User to grant privileges to'},
                            'grant_host': {'type': 'string', 'description': 'Host restriction for the user (e.g. localhost, %, 10.0.0.%)'},
                            'password': {'type': 'string', 'description': 'Password for the user'},
                            'database': {'type': 'string', 'description': 'Database name to grant access to'},
                            'privileges': {'type': 'string', 'description': 'MySQL privileges (e.g. SELECT, ALL PRIVILEGES)'},
                        },
                        'required': ['host', 'admin_user', 'grant_user', 'grant_host', 'password', 'database', 'privileges'],
                    },
                },
                'params': {'env': ['production', 'staging', 'development', 'reporting']},
                'prompts': [
                    'Grant MySQL privileges in the {env} environment',
                    'Create a DM action to set up MySQL user permissions in {env}',
                    'Write a shell action for MySQL GRANT in {env}',
                ],
                'explanation': 'Creates a MySQL user and grants specified privileges on a database in the {env} environment.',
                'features': ['schema_variables'],
            },
            {
                'name': 'redis-set-expire',
                'template': {
                    'name': '{env}-redis-set-expire',
                    'action_type': 'SHELL',
                    'code': 'redis-cli -h {{input.host}} -p {{input.port}} SET "{{input.key}}" "{{input.value}}" EX {{input.ttl_seconds}} 2>&1 && RESULT=$(redis-cli -h {{input.host}} -p {{input.port}} GET "{{input.key}}" 2>&1) && TTL=$(redis-cli -h {{input.host}} -p {{input.port}} TTL "{{input.key}}" 2>&1) && echo "Key set: {{input.key}} = $RESULT (TTL: ${TTL}s)" || (echo "FAILED: Redis SET error" >&2; exit 1)',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'host': {'type': 'string', 'description': 'Redis host address'},
                            'port': {'type': 'integer', 'description': 'Redis port number'},
                            'key': {'type': 'string', 'description': 'Redis key name'},
                            'value': {'type': 'string', 'description': 'Value to set'},
                            'ttl_seconds': {'type': 'integer', 'description': 'Time-to-live in seconds'},
                        },
                        'required': ['host', 'port', 'key', 'value', 'ttl_seconds'],
                    },
                },
                'params': {'env': ['production', 'staging', 'cache', 'session']},
                'prompts': [
                    'Set a Redis key with TTL in the {env} instance',
                    'Create a DM action to set and expire a Redis key in {env}',
                    'Write a shell action for redis-cli SET with EX in {env}',
                ],
                'explanation': 'Sets a Redis key with a value and TTL expiration in the {env} instance.',
                'features': ['schema_variables'],
            },
            {
                'name': 'mongo-create-user',
                'template': {
                    'name': '{env}-mongo-create-user',
                    'action_type': 'SHELL',
                    'code': 'mongosh --host {{input.host}} --port {{input.port}} -u {{input.admin_user}} --authenticationDatabase admin --eval \'db.getSiblingDB("{{input.database}}").createUser({user: "{{input.new_user}}", pwd: "{{input.password}}", roles: [{role: "{{input.role}}", db: "{{input.database}}"}]})\' 2>&1 && echo "MongoDB user {{input.new_user}} created with role {{input.role}} on {{input.database}}" || (echo "FAILED: MongoDB user creation error" >&2; exit 1)',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'host': {'type': 'string', 'description': 'MongoDB host address'},
                            'port': {'type': 'integer', 'description': 'MongoDB port number'},
                            'admin_user': {'type': 'string', 'description': 'Admin user for authentication'},
                            'database': {'type': 'string', 'description': 'Database to create the user in'},
                            'new_user': {'type': 'string', 'description': 'Username for the new user'},
                            'password': {'type': 'string', 'description': 'Password for the new user'},
                            'role': {'type': 'string', 'description': 'MongoDB role (e.g. readWrite, read, dbAdmin)'},
                        },
                        'required': ['host', 'port', 'admin_user', 'database', 'new_user', 'password', 'role'],
                    },
                },
                'params': {'env': ['production', 'staging', 'analytics', 'development']},
                'prompts': [
                    'Create a MongoDB user in the {env} environment',
                    'Write a DM action to add a MongoDB user with a role in {env}',
                    'Generate a shell action for MongoDB user creation in {env}',
                ],
                'explanation': 'Creates a MongoDB user with a specified role on a database in the {env} environment.',
                'features': ['schema_variables'],
            },
            {
                'name': 'pg-isready-check',
                'template': {
                    'name': '{env}-pg-isready',
                    'action_type': 'SHELL',
                    'code': 'pg_isready -h {{input.host}} -p {{input.port}} -U {{input.username}} -d {{input.database}} -t {{input.timeout}} 2>&1; RC=$?; if [ $RC -eq 0 ]; then echo "PostgreSQL is accepting connections on {{input.host}}:{{input.port}}"; elif [ $RC -eq 1 ]; then echo "FAILED: Server is rejecting connections" >&2; exit 1; elif [ $RC -eq 2 ]; then echo "FAILED: No response from server" >&2; exit 1; else echo "FAILED: pg_isready error (exit code: $RC)" >&2; exit 1; fi',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'host': {'type': 'string', 'description': 'PostgreSQL host address'},
                            'port': {'type': 'integer', 'description': 'PostgreSQL port number'},
                            'username': {'type': 'string', 'description': 'Database user to check with'},
                            'database': {'type': 'string', 'description': 'Database name to check'},
                            'timeout': {'type': 'integer', 'description': 'Connection timeout in seconds'},
                        },
                        'required': ['host', 'port', 'username', 'database', 'timeout'],
                    },
                },
                'params': {'env': ['production', 'staging', 'replica', 'development']},
                'prompts': [
                    'Check PostgreSQL connection readiness in the {env} environment',
                    'Create a DM action to verify {env} PostgreSQL is accepting connections',
                    'Write a shell action for pg_isready check on {env}',
                ],
                'explanation': 'Checks whether the {env} PostgreSQL server is accepting connections using pg_isready.',
                'features': ['schema_variables'],
            },
            {
                'name': 'mysql-status-check',
                'template': {
                    'name': '{env}-mysql-status',
                    'action_type': 'SHELL',
                    'code': 'mysqladmin -h {{input.host}} -u {{input.username}} ping 2>&1 && echo "=== MySQL Status ===" && mysqladmin -h {{input.host}} -u {{input.username}} status 2>&1 && echo "=== Connection Threads ===" && mysql -h {{input.host}} -u {{input.username}} -e "SHOW STATUS WHERE Variable_name IN (\'Threads_connected\', \'Threads_running\', \'Max_used_connections\', \'Uptime\', \'Questions\');" 2>&1 || (echo "FAILED: MySQL not responding" >&2; exit 1)',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'host': {'type': 'string', 'description': 'MySQL host address'},
                            'username': {'type': 'string', 'description': 'MySQL user for status check'},
                        },
                        'required': ['host', 'username'],
                    },
                },
                'params': {'env': ['production', 'staging', 'replica', 'primary']},
                'prompts': [
                    'Check MySQL server status in the {env} environment',
                    'Create a DM action to verify {env} MySQL health and connections',
                    'Write a shell action for MySQL status check on {env}',
                ],
                'explanation': 'Checks the {env} MySQL server status including ping, uptime, and active connections.',
                'features': ['schema_variables'],
            },
            {
                'name': 'redis-sentinel-failover',
                'template': {
                    'name': '{env}-redis-failover',
                    'action_type': 'SHELL',
                    'code': 'echo "=== Current master ===" && redis-cli -h {{input.sentinel_host}} -p {{input.sentinel_port}} SENTINEL get-master-addr-by-name {{input.master_name}} 2>&1 && echo "=== Initiating failover ===" && redis-cli -h {{input.sentinel_host}} -p {{input.sentinel_port}} SENTINEL failover {{input.master_name}} 2>&1 && sleep 5 && echo "=== New master ===" && redis-cli -h {{input.sentinel_host}} -p {{input.sentinel_port}} SENTINEL get-master-addr-by-name {{input.master_name}} 2>&1 && echo "Sentinel failover completed for {{input.master_name}}"',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'sentinel_host': {'type': 'string', 'description': 'Redis Sentinel host address'},
                            'sentinel_port': {'type': 'integer', 'description': 'Redis Sentinel port number'},
                            'master_name': {'type': 'string', 'description': 'Name of the Redis master group'},
                        },
                        'required': ['sentinel_host', 'sentinel_port', 'master_name'],
                    },
                },
                'params': {'env': ['production', 'staging', 'cluster', 'ha']},
                'prompts': [
                    'Trigger a Redis Sentinel failover in the {env} environment',
                    'Create a DM action to initiate Redis failover on {env}',
                    'Write a shell action for Redis Sentinel manual failover in {env}',
                ],
                'explanation': 'Triggers a manual Redis Sentinel failover in the {env} environment and verifies the new master.',
                'features': ['schema_variables'],
                'difficulty': 'intermediate',
            },
            {
                'name': 'pg-dump-single-table',
                'template': {
                    'name': '{env}-pg-dump-table',
                    'action_type': 'SHELL',
                    'code': 'TIMESTAMP=$(date +%Y%m%d_%H%M%S) && DUMP_FILE="{{input.backup_dir}}/{{input.database}}_{{input.table_name}}_${TIMESTAMP}.sql.gz" && mkdir -p {{input.backup_dir}} && pg_dump -h {{input.host}} -U {{input.username}} -d {{input.database}} -t {{input.schema_name}}.{{input.table_name}} --no-password | gzip > "$DUMP_FILE" && FILESIZE=$(du -sh "$DUMP_FILE" | cut -f1) && echo "Table dump completed: $DUMP_FILE ($FILESIZE)" || (echo "FAILED: pg_dump table error" >&2; exit 1)',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'host': {'type': 'string', 'description': 'PostgreSQL host address'},
                            'username': {'type': 'string', 'description': 'Database user for authentication'},
                            'database': {'type': 'string', 'description': 'Database name'},
                            'schema_name': {'type': 'string', 'description': 'Schema name (e.g. public)'},
                            'table_name': {'type': 'string', 'description': 'Table name to dump'},
                            'backup_dir': {'type': 'string', 'description': 'Directory to store the dump file'},
                        },
                        'required': ['host', 'username', 'database', 'schema_name', 'table_name', 'backup_dir'],
                    },
                },
                'params': {'env': ['production', 'staging', 'analytics', 'reporting']},
                'prompts': [
                    'Dump a single PostgreSQL table in the {env} environment',
                    'Create a DM action to pg_dump one table from {env}',
                    'Write a shell action for single-table PostgreSQL backup in {env}',
                ],
                'explanation': 'Dumps a single PostgreSQL table from the {env} environment to a compressed file with a timestamp.',
                'features': ['schema_variables'],
            },
            {
                'name': 'vacuum-analyze',
                'template': {
                    'name': '{env}-vacuum-analyze',
                    'action_type': 'SHELL',
                    'code': 'echo "=== Starting VACUUM ANALYZE on {{input.database}} ===" && psql -h {{input.host}} -U {{input.username}} -d {{input.database}} -c "VACUUM (VERBOSE, ANALYZE) {{input.table_name}};" 2>&1; RC=$?; echo "=== Table statistics ===" && psql -h {{input.host}} -U {{input.username}} -d {{input.database}} -c "SELECT relname, n_live_tup, n_dead_tup, last_vacuum, last_autovacuum, last_analyze FROM pg_stat_user_tables WHERE relname = \'{{input.table_name}}\';" 2>&1 && if [ $RC -eq 0 ]; then echo "VACUUM ANALYZE completed on {{input.table_name}}"; else echo "WARNING: VACUUM completed with warnings" >&2; fi; exit $RC',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'host': {'type': 'string', 'description': 'PostgreSQL host address'},
                            'username': {'type': 'string', 'description': 'Database user with vacuum privilege'},
                            'database': {'type': 'string', 'description': 'Database name'},
                            'table_name': {'type': 'string', 'description': 'Table to vacuum and analyze'},
                        },
                        'required': ['host', 'username', 'database', 'table_name'],
                    },
                },
                'params': {'env': ['production', 'staging', 'analytics', 'warehouse']},
                'prompts': [
                    'Run VACUUM ANALYZE on a PostgreSQL table in {env}',
                    'Create a DM action for PostgreSQL vacuum maintenance in {env}',
                    'Write a shell action that vacuums and analyzes a table in {env}',
                ],
                'explanation': 'Runs VACUUM ANALYZE on a PostgreSQL table in the {env} environment and displays dead tuple statistics.',
                'features': ['schema_variables'],
            },
        ]


def get_generators():
    return [DatabaseOpsGenerator()]
