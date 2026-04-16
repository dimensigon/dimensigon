"""Database Python action generators - 10 seeds for PostgreSQL, MySQL, Redis, MongoDB, SQLite."""

from examples.generators.base_generator import PythonActionGenerator


class DatabaseGenerator(PythonActionGenerator):
    category = "python.database"
    subcategory = "database"

    def seeds(self):
        return [
            {
                'name': 'postgres-conn-test',
                'template': {
                    'name': 'Test PostgreSQL connection',
                    'action_type': 'PYTHON',
                    'code': (
                        'import json\n'
                        'import socket\n'
                        'import sys\n\n'
                        'host = "{{input.host}}" or "localhost"\n'
                        'port = int("{{input.port}}" or "5432")\n'
                        'timeout = int("{{input.timeout}}" or "5")\n\n'
                        'try:\n'
                        '    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n'
                        '    sock.settimeout(timeout)\n'
                        '    result = sock.connect_ex((host, port))\n'
                        '    sock.close()\n'
                        '    if result == 0:\n'
                        '        print(json.dumps({{"status": "ok", "host": host, "port": port, "message": "PostgreSQL port is open"}}))\n'
                        '    else:\n'
                        '        print(json.dumps({{"status": "error", "host": host, "port": port, "message": "Connection refused"}}))\n'
                        '        sys.exit(1)\n'
                        'except socket.timeout:\n'
                        '    print(json.dumps({{"status": "error", "message": "Connection timed out"}}))\n'
                        '    sys.exit(1)\n'
                        'except Exception as e:\n'
                        '    print(json.dumps({{"status": "error", "message": str(e)}}))\n'
                        '    sys.exit(1)\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'host': {'type': 'string', 'description': 'PostgreSQL host (default localhost)'},
                            'port': {'type': 'string', 'description': 'PostgreSQL port (default 5432)'},
                            'timeout': {'type': 'string', 'description': 'Connection timeout in seconds (default 5)'},
                        },
                        'required': [],
                    },
                },
                'params': {'env': ['production', 'staging', 'development', 'replica']},
                'prompts': [
                    'Create a Python action to test PostgreSQL connectivity on {env}',
                    'Python script that verifies the {env} PostgreSQL port is reachable via socket',
                ],
                'explanation': 'Python action that tests PostgreSQL connectivity on {env} by opening a TCP socket to the database port.',
            },
            {
                'name': 'mysql-ping',
                'template': {
                    'name': 'Ping MySQL server',
                    'action_type': 'PYTHON',
                    'code': (
                        'import json\n'
                        'import socket\n'
                        'import sys\n\n'
                        'host = "{{input.host}}" or "localhost"\n'
                        'port = int("{{input.port}}" or "3306")\n'
                        'timeout = int("{{input.timeout}}" or "5")\n\n'
                        'try:\n'
                        '    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n'
                        '    sock.settimeout(timeout)\n'
                        '    sock.connect((host, port))\n'
                        '    greeting = sock.recv(1024)\n'
                        '    sock.close()\n'
                        '    if len(greeting) > 4:\n'
                        '        version_end = greeting.find(b"\\x00", 5)\n'
                        '        version = greeting[5:version_end].decode("utf-8", errors="replace") if version_end > 5 else "unknown"\n'
                        '        print(json.dumps({{"status": "ok", "host": host, "port": port, "version": version}}))\n'
                        '    else:\n'
                        '        print(json.dumps({{"status": "ok", "host": host, "port": port, "message": "MySQL responded"}}))\n'
                        'except Exception as e:\n'
                        '    print(json.dumps({{"status": "error", "message": str(e)}}))\n'
                        '    sys.exit(1)\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'host': {'type': 'string', 'description': 'MySQL host (default localhost)'},
                            'port': {'type': 'string', 'description': 'MySQL port (default 3306)'},
                            'timeout': {'type': 'string', 'description': 'Connection timeout in seconds (default 5)'},
                        },
                        'required': [],
                    },
                },
                'params': {'env': ['production', 'staging', 'development', 'replica']},
                'prompts': [
                    'Create a Python action to ping a MySQL server on {env}',
                    'Python script that checks {env} MySQL connectivity and reads server version',
                ],
                'explanation': 'Python action that pings the {env} MySQL server by connecting via socket and reading the protocol greeting.',
            },
            {
                'name': 'redis-conn-test',
                'template': {
                    'name': 'Test Redis connection',
                    'action_type': 'PYTHON',
                    'code': (
                        'import json\n'
                        'import socket\n'
                        'import sys\n\n'
                        'host = "{{input.host}}" or "localhost"\n'
                        'port = int("{{input.port}}" or "6379")\n'
                        'password = "{{input.password}}" or ""\n'
                        'timeout = int("{{input.timeout}}" or "5")\n\n'
                        'try:\n'
                        '    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n'
                        '    sock.settimeout(timeout)\n'
                        '    sock.connect((host, port))\n'
                        '    if password:\n'
                        '        sock.sendall(f"AUTH {{password}}\\r\\n".encode())\n'
                        '        auth_resp = sock.recv(1024).decode()\n'
                        '        if not auth_resp.startswith("+OK"):\n'
                        '            print(json.dumps({{"status": "auth_failed", "message": auth_resp.strip()}}))\n'
                        '            sys.exit(1)\n'
                        '    sock.sendall(b"PING\\r\\n")\n'
                        '    resp = sock.recv(1024).decode().strip()\n'
                        '    sock.close()\n'
                        '    if "PONG" in resp:\n'
                        '        print(json.dumps({{"status": "ok", "host": host, "port": port, "response": "PONG"}}))\n'
                        '    else:\n'
                        '        print(json.dumps({{"status": "error", "response": resp}}))\n'
                        '        sys.exit(1)\n'
                        'except Exception as e:\n'
                        '    print(json.dumps({{"status": "error", "message": str(e)}}))\n'
                        '    sys.exit(1)\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'host': {'type': 'string', 'description': 'Redis host (default localhost)'},
                            'port': {'type': 'string', 'description': 'Redis port (default 6379)'},
                            'password': {'type': 'string', 'description': 'Redis password (optional)'},
                            'timeout': {'type': 'string', 'description': 'Connection timeout in seconds (default 5)'},
                        },
                        'required': [],
                    },
                },
                'params': {'env': ['production', 'staging', 'cache', 'session-store']},
                'prompts': [
                    'Create a Python action to test Redis connectivity for {env}',
                    'Python script that sends PING to {env} Redis and checks for PONG',
                ],
                'explanation': 'Python action that tests {env} Redis connectivity by sending a PING command via raw socket protocol.',
            },
            {
                'name': 'mongodb-status',
                'template': {
                    'name': 'Check MongoDB status',
                    'action_type': 'PYTHON',
                    'code': (
                        'import json\n'
                        'import socket\n'
                        'import sys\n\n'
                        'host = "{{input.host}}" or "localhost"\n'
                        'port = int("{{input.port}}" or "27017")\n'
                        'timeout = int("{{input.timeout}}" or "5")\n\n'
                        'try:\n'
                        '    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n'
                        '    sock.settimeout(timeout)\n'
                        '    result = sock.connect_ex((host, port))\n'
                        '    sock.close()\n'
                        '    if result == 0:\n'
                        '        print(json.dumps({{"status": "ok", "host": host, "port": port, "message": "MongoDB port is reachable"}}))\n'
                        '    else:\n'
                        '        print(json.dumps({{"status": "error", "host": host, "port": port, "message": "Connection refused"}}))\n'
                        '        sys.exit(1)\n'
                        'except Exception as e:\n'
                        '    print(json.dumps({{"status": "error", "message": str(e)}}))\n'
                        '    sys.exit(1)\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'host': {'type': 'string', 'description': 'MongoDB host (default localhost)'},
                            'port': {'type': 'string', 'description': 'MongoDB port (default 27017)'},
                            'timeout': {'type': 'string', 'description': 'Connection timeout in seconds (default 5)'},
                        },
                        'required': [],
                    },
                },
                'params': {'env': ['production', 'staging', 'analytics', 'replica-set']},
                'prompts': [
                    'Create a Python action to check MongoDB status on {env}',
                    'Python script that verifies {env} MongoDB is reachable',
                ],
                'explanation': 'Python action that checks {env} MongoDB status by attempting a TCP connection to the database port.',
            },
            {
                'name': 'sqlite-integrity',
                'template': {
                    'name': 'SQLite integrity check',
                    'action_type': 'PYTHON',
                    'code': (
                        'import json\n'
                        'import sqlite3\n'
                        'import os\n'
                        'import sys\n\n'
                        'db_path = "{{input.db_path}}"\n\n'
                        'if not os.path.isfile(db_path):\n'
                        '    print(json.dumps({{"status": "error", "message": f"Database not found: {{db_path}}"}}))\n'
                        '    sys.exit(1)\n\n'
                        'try:\n'
                        '    conn = sqlite3.connect(db_path)\n'
                        '    cursor = conn.execute("PRAGMA integrity_check")\n'
                        '    results = cursor.fetchall()\n'
                        '    conn.close()\n'
                        '    ok = all(row[0] == "ok" for row in results)\n'
                        '    size_bytes = os.path.getsize(db_path)\n'
                        '    print(json.dumps({{\n'
                        '        "status": "ok" if ok else "corrupt",\n'
                        '        "db_path": db_path,\n'
                        '        "size_bytes": size_bytes,\n'
                        '        "integrity": [row[0] for row in results],\n'
                        '    }}))\n'
                        '    if not ok:\n'
                        '        sys.exit(1)\n'
                        'except Exception as e:\n'
                        '    print(json.dumps({{"status": "error", "message": str(e)}}))\n'
                        '    sys.exit(1)\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'db_path': {'type': 'string', 'description': 'Path to SQLite database file'},
                        },
                        'required': ['db_path'],
                    },
                },
                'params': {'db_type': ['application', 'cache', 'config', 'audit', 'metrics']},
                'prompts': [
                    'Create a Python action to run integrity check on a {db_type} SQLite database',
                    'Python script that validates {db_type} SQLite database integrity',
                ],
                'explanation': 'Python action that runs PRAGMA integrity_check on a {db_type} SQLite database and reports the result.',
            },
            {
                'name': 'migration-runner',
                'template': {
                    'name': 'Run DB migration scripts',
                    'action_type': 'PYTHON',
                    'code': (
                        'import json\n'
                        'import os\n'
                        'import sqlite3\n'
                        'import sys\n\n'
                        'db_path = "{{input.db_path}}"\n'
                        'migration_dir = "{{input.migration_dir}}"\n\n'
                        'if not os.path.isdir(migration_dir):\n'
                        '    print(json.dumps({{"status": "error", "message": f"Migration dir not found: {{migration_dir}}"}}))\n'
                        '    sys.exit(1)\n\n'
                        'try:\n'
                        '    conn = sqlite3.connect(db_path)\n'
                        '    conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at TEXT DEFAULT CURRENT_TIMESTAMP)")\n'
                        '    applied = set(row[0] for row in conn.execute("SELECT version FROM schema_migrations").fetchall())\n'
                        '    scripts = sorted(f for f in os.listdir(migration_dir) if f.endswith(".sql"))\n'
                        '    newly_applied = []\n'
                        '    for script in scripts:\n'
                        '        version = script.split("_")[0] if "_" in script else script\n'
                        '        if version not in applied:\n'
                        '            sql_path = os.path.join(migration_dir, script)\n'
                        '            with open(sql_path, "r") as f:\n'
                        '                sql = f.read()\n'
                        '            conn.executescript(sql)\n'
                        '            conn.execute("INSERT INTO schema_migrations (version) VALUES (?)", (version,))\n'
                        '            conn.commit()\n'
                        '            newly_applied.append(script)\n'
                        '    conn.close()\n'
                        '    print(json.dumps({{"status": "ok", "applied": newly_applied, "count": len(newly_applied)}}))\n'
                        'except Exception as e:\n'
                        '    print(json.dumps({{"status": "error", "message": str(e)}}))\n'
                        '    sys.exit(1)\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'db_path': {'type': 'string', 'description': 'Path to database file'},
                            'migration_dir': {'type': 'string', 'description': 'Directory containing SQL migration scripts'},
                        },
                        'required': ['db_path', 'migration_dir'],
                    },
                },
                'params': {'db_engine': ['sqlite', 'postgres', 'mysql', 'mariadb']},
                'prompts': [
                    'Create a Python action to run {db_engine} migration scripts',
                    'Python script that applies pending SQL migrations for {db_engine}',
                ],
                'explanation': 'Python action that runs pending SQL migration scripts against a {db_engine} database, tracking applied versions.',
            },
            {
                'name': 'connection-pool-check',
                'template': {
                    'name': 'Validate {db} conn pool',
                    'action_type': 'PYTHON',
                    'code': (
                        'import json\n'
                        'import socket\n'
                        'import sys\n\n'
                        'host = "{{input.host}}" or "localhost"\n'
                        'port = int("{{input.port}}")\n'
                        'max_connections = int("{{input.max_connections}}" or "10")\n'
                        'timeout = int("{{input.timeout}}" or "3")\n\n'
                        'successful = 0\n'
                        'failed = 0\n'
                        'sockets = []\n\n'
                        'for i in range(max_connections):\n'
                        '    try:\n'
                        '        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n'
                        '        s.settimeout(timeout)\n'
                        '        s.connect((host, port))\n'
                        '        sockets.append(s)\n'
                        '        successful += 1\n'
                        '    except Exception:\n'
                        '        failed += 1\n\n'
                        'for s in sockets:\n'
                        '    try:\n'
                        '        s.close()\n'
                        '    except Exception:\n'
                        '        pass\n\n'
                        'result = {{\n'
                        '    "status": "ok" if failed == 0 else "degraded",\n'
                        '    "host": host,\n'
                        '    "port": port,\n'
                        '    "successful": successful,\n'
                        '    "failed": failed,\n'
                        '    "max_connections": max_connections,\n'
                        '}}\n'
                        'print(json.dumps(result))\n'
                        'if failed > 0:\n'
                        '    sys.exit(1)\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'host': {'type': 'string', 'description': 'Database host (default localhost)'},
                            'port': {'type': 'string', 'description': 'Database port'},
                            'max_connections': {'type': 'string', 'description': 'Number of connections to test (default 10)'},
                            'timeout': {'type': 'string', 'description': 'Connection timeout in seconds (default 3)'},
                        },
                        'required': ['port'],
                    },
                },
                'params': {'db': ['postgres', 'mysql', 'redis', 'mongodb', 'cockroachdb']},
                'prompts': [
                    'Create a Python action to validate {db} connection pool capacity',
                    'Python script that tests {db} can handle multiple concurrent connections',
                ],
                'explanation': 'Python action that validates {db} connection pool by opening multiple simultaneous TCP connections.',
            },
            {
                'name': 'query-timing',
                'template': {
                    'name': 'Time {db} query execution',
                    'action_type': 'PYTHON',
                    'code': (
                        'import json\n'
                        'import sqlite3\n'
                        'import time\n'
                        'import sys\n\n'
                        'db_path = "{{input.db_path}}"\n'
                        'query = "{{input.query}}" or "SELECT 1"\n'
                        'iterations = int("{{input.iterations}}" or "10")\n\n'
                        'try:\n'
                        '    conn = sqlite3.connect(db_path)\n'
                        '    timings = []\n'
                        '    for i in range(iterations):\n'
                        '        start = time.time()\n'
                        '        conn.execute(query).fetchall()\n'
                        '        elapsed = (time.time() - start) * 1000\n'
                        '        timings.append(round(elapsed, 3))\n'
                        '    conn.close()\n'
                        '    avg = round(sum(timings) / len(timings), 3)\n'
                        '    print(json.dumps({{\n'
                        '        "status": "ok",\n'
                        '        "iterations": iterations,\n'
                        '        "avg_ms": avg,\n'
                        '        "min_ms": min(timings),\n'
                        '        "max_ms": max(timings),\n'
                        '    }}))\n'
                        'except Exception as e:\n'
                        '    print(json.dumps({{"status": "error", "message": str(e)}}))\n'
                        '    sys.exit(1)\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'db_path': {'type': 'string', 'description': 'Path to SQLite database file'},
                            'query': {'type': 'string', 'description': 'SQL query to benchmark (default SELECT 1)'},
                            'iterations': {'type': 'string', 'description': 'Number of iterations (default 10)'},
                        },
                        'required': ['db_path'],
                    },
                },
                'params': {'db': ['sqlite', 'postgres', 'mysql', 'mariadb']},
                'prompts': [
                    'Create a Python action to benchmark {db} query execution time',
                    'Python script that measures {db} query latency over multiple iterations',
                ],
                'explanation': 'Python action that benchmarks {db} query execution time over multiple iterations and reports min/avg/max latency.',
            },
            {
                'name': 'table-row-count',
                'template': {
                    'name': 'Count rows in {db} table',
                    'action_type': 'PYTHON',
                    'code': (
                        'import json\n'
                        'import sqlite3\n'
                        'import sys\n\n'
                        'db_path = "{{input.db_path}}"\n'
                        'table_name = "{{input.table_name}}"\n'
                        'min_rows = int("{{input.min_rows}}" or "0")\n\n'
                        'try:\n'
                        '    conn = sqlite3.connect(db_path)\n'
                        '    cursor = conn.execute(f"SELECT COUNT(*) FROM {{table_name}}")\n'
                        '    count = cursor.fetchone()[0]\n'
                        '    conn.close()\n'
                        '    ok = count >= min_rows\n'
                        '    print(json.dumps({{\n'
                        '        "status": "ok" if ok else "below_minimum",\n'
                        '        "table": table_name,\n'
                        '        "row_count": count,\n'
                        '        "min_expected": min_rows,\n'
                        '    }}))\n'
                        '    if not ok:\n'
                        '        sys.exit(1)\n'
                        'except Exception as e:\n'
                        '    print(json.dumps({{"status": "error", "message": str(e)}}))\n'
                        '    sys.exit(1)\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'db_path': {'type': 'string', 'description': 'Path to SQLite database file'},
                            'table_name': {'type': 'string', 'description': 'Table name to count rows in'},
                            'min_rows': {'type': 'string', 'description': 'Minimum expected rows (default 0)'},
                        },
                        'required': ['db_path', 'table_name'],
                    },
                },
                'params': {'db': ['sqlite', 'postgres', 'mysql', 'mariadb', 'cockroachdb']},
                'prompts': [
                    'Create a Python action to count rows in a {db} table',
                    'Python script that checks {db} table row count against a minimum',
                ],
                'explanation': 'Python action that counts rows in a {db} table and alerts if the count falls below the minimum threshold.',
            },
            {
                'name': 'db-size-report',
                'template': {
                    'name': 'Report {db} database size',
                    'action_type': 'PYTHON',
                    'code': (
                        'import json\n'
                        'import sqlite3\n'
                        'import os\n'
                        'import sys\n\n'
                        'db_path = "{{input.db_path}}"\n'
                        'max_size_mb = float("{{input.max_size_mb}}" or "0")\n\n'
                        'if not os.path.isfile(db_path):\n'
                        '    print(json.dumps({{"status": "error", "message": f"Database not found: {{db_path}}"}}))\n'
                        '    sys.exit(1)\n\n'
                        'try:\n'
                        '    size_bytes = os.path.getsize(db_path)\n'
                        '    size_mb = round(size_bytes / (1024 * 1024), 2)\n'
                        '    conn = sqlite3.connect(db_path)\n'
                        '    tables = conn.execute("SELECT name FROM sqlite_master WHERE type=\'table\'").fetchall()\n'
                        '    table_info = []\n'
                        '    for (tname,) in tables:\n'
                        '        count = conn.execute(f"SELECT COUNT(*) FROM {{tname}}").fetchone()[0]\n'
                        '        table_info.append({{"table": tname, "rows": count}})\n'
                        '    conn.close()\n'
                        '    over_limit = max_size_mb > 0 and size_mb > max_size_mb\n'
                        '    print(json.dumps({{\n'
                        '        "status": "warning" if over_limit else "ok",\n'
                        '        "size_mb": size_mb,\n'
                        '        "size_bytes": size_bytes,\n'
                        '        "tables": table_info,\n'
                        '        "table_count": len(table_info),\n'
                        '    }}))\n'
                        '    if over_limit:\n'
                        '        sys.exit(1)\n'
                        'except Exception as e:\n'
                        '    print(json.dumps({{"status": "error", "message": str(e)}}))\n'
                        '    sys.exit(1)\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'db_path': {'type': 'string', 'description': 'Path to SQLite database file'},
                            'max_size_mb': {'type': 'string', 'description': 'Max size alert threshold in MB (0=no limit)'},
                        },
                        'required': ['db_path'],
                    },
                },
                'params': {'db': ['sqlite', 'postgres', 'mysql', 'mariadb', 'cockroachdb']},
                'prompts': [
                    'Create a Python action to report {db} database size and table stats',
                    'Python script that generates a {db} database size report',
                ],
                'explanation': 'Python action that reports {db} database size, table count, and row counts, with optional size threshold alerting.',
            },
            {
                'name': 'db-schema-diff',
                'template': {
                    'name': 'Schema diff for {db} databases',
                    'action_type': 'PYTHON',
                    'code': (
                        'import json\n'
                        'import sqlite3\n'
                        'import sys\n\n'
                        'db_path_a = "{{input.db_path_a}}"\n'
                        'db_path_b = "{{input.db_path_b}}"\n\n'
                        'def get_schema(db_path):\n'
                        '    conn = sqlite3.connect(db_path)\n'
                        '    tables = {{}}\n'
                        '    for (name,) in conn.execute("SELECT name FROM sqlite_master WHERE type=\'table\' ORDER BY name").fetchall():\n'
                        '        cols = conn.execute(f"PRAGMA table_info({{name}})").fetchall()\n'
                        '        tables[name] = [(c[1], c[2], c[3], c[5]) for c in cols]\n'
                        '    conn.close()\n'
                        '    return tables\n\n'
                        'try:\n'
                        '    schema_a = get_schema(db_path_a)\n'
                        '    schema_b = get_schema(db_path_b)\n'
                        '    diffs = []\n'
                        '    all_tables = set(list(schema_a.keys()) + list(schema_b.keys()))\n'
                        '    for t in sorted(all_tables):\n'
                        '        if t not in schema_a:\n'
                        '            diffs.append({{"type": "table_added", "table": t}})\n'
                        '        elif t not in schema_b:\n'
                        '            diffs.append({{"type": "table_removed", "table": t}})\n'
                        '        elif schema_a[t] != schema_b[t]:\n'
                        '            diffs.append({{"type": "table_changed", "table": t, "a_cols": len(schema_a[t]), "b_cols": len(schema_b[t])}})\n'
                        '    print(json.dumps({{\n'
                        '        "status": "ok" if not diffs else "differences_found",\n'
                        '        "tables_a": len(schema_a),\n'
                        '        "tables_b": len(schema_b),\n'
                        '        "differences": diffs,\n'
                        '        "diff_count": len(diffs),\n'
                        '    }}))\n'
                        '    if diffs:\n'
                        '        sys.exit(1)\n'
                        'except Exception as e:\n'
                        '    print(json.dumps({{"status": "error", "message": str(e)}}))\n'
                        '    sys.exit(1)\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'db_path_a': {'type': 'string', 'description': 'Path to the first SQLite database'},
                            'db_path_b': {'type': 'string', 'description': 'Path to the second SQLite database'},
                        },
                        'required': ['db_path_a', 'db_path_b'],
                    },
                },
                'params': {'db': ['sqlite', 'postgres', 'mysql', 'mariadb']},
                'prompts': [
                    'Create a Python action to compare schemas between two {db} databases',
                    'Python script that generates a schema diff between two {db} databases',
                ],
                'explanation': 'Python action that compares table schemas between two {db} databases and reports added, removed, and changed tables.',
            },
            {
                'name': 'slow-query-analysis',
                'template': {
                    'name': 'Analyze {db} slow query log',
                    'action_type': 'PYTHON',
                    'code': (
                        'import json\n'
                        'import os\n'
                        'import re\n'
                        'import sys\n\n'
                        'log_file = "{{input.log_file}}"\n'
                        'threshold_sec = float("{{input.threshold_sec}}" or "1.0")\n'
                        'max_queries = int("{{input.max_queries}}" or "20")\n\n'
                        'if not os.path.isfile(log_file):\n'
                        '    print(json.dumps({{"status": "error", "message": f"Log file not found: {{log_file}}"}}))\n'
                        '    sys.exit(1)\n\n'
                        'slow_queries = []\n'
                        'time_pattern = re.compile(r"Query_time:\\s*([\\d.]+)")\n\n'
                        'with open(log_file, "r", errors="replace") as f:\n'
                        '    current_time = 0\n'
                        '    current_query = ""\n'
                        '    for line in f:\n'
                        '        match = time_pattern.search(line)\n'
                        '        if match:\n'
                        '            if current_query and current_time >= threshold_sec:\n'
                        '                slow_queries.append({{"time_sec": current_time, "query": current_query[:200]}})\n'
                        '            current_time = float(match.group(1))\n'
                        '            current_query = ""\n'
                        '        elif not line.startswith("#") and line.strip():\n'
                        '            current_query += line.strip() + " "\n'
                        '    if current_query and current_time >= threshold_sec:\n'
                        '        slow_queries.append({{"time_sec": current_time, "query": current_query[:200]}})\n\n'
                        'slow_queries.sort(key=lambda x: x["time_sec"], reverse=True)\n'
                        'print(json.dumps({{\n'
                        '    "status": "ok",\n'
                        '    "log_file": log_file,\n'
                        '    "threshold_sec": threshold_sec,\n'
                        '    "total_slow_queries": len(slow_queries),\n'
                        '    "top_queries": slow_queries[:max_queries],\n'
                        '}}))\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'log_file': {'type': 'string', 'description': 'Path to the slow query log file'},
                            'threshold_sec': {'type': 'string', 'description': 'Minimum query time in seconds (default 1.0)'},
                            'max_queries': {'type': 'string', 'description': 'Maximum queries to return (default 20)'},
                        },
                        'required': ['log_file'],
                    },
                },
                'params': {'db': ['mysql', 'postgres', 'mariadb', 'percona']},
                'prompts': [
                    'Create a Python action to analyze the {db} slow query log',
                    'Python script that parses {db} slow query log and ranks slowest queries',
                ],
                'explanation': 'Python action that parses a {db} slow query log, extracts queries above a time threshold, and ranks them by execution time.',
            },
            {
                'name': 'connection-leak-detect',
                'template': {
                    'name': 'Detect {db} connection leaks',
                    'action_type': 'PYTHON',
                    'code': (
                        'import json\n'
                        'import socket\n'
                        'import time\n'
                        'import sys\n\n'
                        'host = "{{input.host}}" or "localhost"\n'
                        'port = int("{{input.port}}")\n'
                        'interval = int("{{input.interval}}" or "5")\n'
                        'samples = int("{{input.samples}}" or "6")\n'
                        'growth_threshold = int("{{input.growth_threshold}}" or "10")\n\n'
                        'def count_connections(h, p):\n'
                        '    count = 0\n'
                        '    try:\n'
                        '        with open("/proc/net/tcp", "r") as f:\n'
                        '            for line in f.readlines()[1:]:\n'
                        '                parts = line.split()\n'
                        '                remote_port = int(parts[2].split(":")[1], 16)\n'
                        '                state = parts[3]\n'
                        '                if remote_port == p and state == "01":\n'
                        '                    count += 1\n'
                        '    except Exception:\n'
                        '        pass\n'
                        '    return count\n\n'
                        'counts = []\n'
                        'for i in range(samples):\n'
                        '    c = count_connections(host, port)\n'
                        '    counts.append(c)\n'
                        '    if i < samples - 1:\n'
                        '        time.sleep(interval)\n\n'
                        'growth = counts[-1] - counts[0] if len(counts) > 1 else 0\n'
                        'leak_detected = growth >= growth_threshold\n'
                        'result = {{\n'
                        '    "status": "leak_suspected" if leak_detected else "ok",\n'
                        '    "host": host,\n'
                        '    "port": port,\n'
                        '    "samples": counts,\n'
                        '    "growth": growth,\n'
                        '    "growth_threshold": growth_threshold,\n'
                        '    "first_count": counts[0],\n'
                        '    "last_count": counts[-1],\n'
                        '}}\n'
                        'print(json.dumps(result))\n'
                        'if leak_detected:\n'
                        '    sys.exit(1)\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'host': {'type': 'string', 'description': 'Database host (default localhost)'},
                            'port': {'type': 'string', 'description': 'Database port'},
                            'interval': {'type': 'string', 'description': 'Seconds between samples (default 5)'},
                            'samples': {'type': 'string', 'description': 'Number of samples to take (default 6)'},
                            'growth_threshold': {'type': 'string', 'description': 'Connection growth to flag as leak (default 10)'},
                        },
                        'required': ['port'],
                    },
                },
                'params': {'db': ['postgres', 'mysql', 'redis', 'mongodb']},
                'prompts': [
                    'Create a Python action to detect {db} connection leaks over time',
                    'Python script that monitors {db} connection count growth to detect leaks',
                ],
                'explanation': 'Python action that samples {db} connection counts over time and alerts if steady growth indicates a connection leak.',
            },
            {
                'name': 'replication-status',
                'template': {
                    'name': 'Check {db} replication status',
                    'action_type': 'PYTHON',
                    'code': (
                        'import json\n'
                        'import socket\n'
                        'import sys\n\n'
                        'primary_host = "{{input.primary_host}}"\n'
                        'primary_port = int("{{input.primary_port}}")\n'
                        'replica_host = "{{input.replica_host}}"\n'
                        'replica_port = int("{{input.replica_port}}")\n'
                        'timeout = int("{{input.timeout}}" or "5")\n\n'
                        'results = {{}}\n'
                        'for label, host, port in [("primary", primary_host, primary_port), ("replica", replica_host, replica_port)]:\n'
                        '    try:\n'
                        '        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n'
                        '        sock.settimeout(timeout)\n'
                        '        result = sock.connect_ex((host, port))\n'
                        '        sock.close()\n'
                        '        results[label] = {{"host": host, "port": port, "reachable": result == 0}}\n'
                        '    except Exception as e:\n'
                        '        results[label] = {{"host": host, "port": port, "reachable": False, "error": str(e)}}\n\n'
                        'both_up = results.get("primary", {{}}).get("reachable", False) and results.get("replica", {{}}).get("reachable", False)\n'
                        'output = {{\n'
                        '    "status": "ok" if both_up else "error",\n'
                        '    "primary": results.get("primary", {{}}),\n'
                        '    "replica": results.get("replica", {{}}),\n'
                        '}}\n'
                        'print(json.dumps(output))\n'
                        'if not both_up:\n'
                        '    sys.exit(1)\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'primary_host': {'type': 'string', 'description': 'Primary/master database host'},
                            'primary_port': {'type': 'string', 'description': 'Primary database port'},
                            'replica_host': {'type': 'string', 'description': 'Replica/slave database host'},
                            'replica_port': {'type': 'string', 'description': 'Replica database port'},
                            'timeout': {'type': 'string', 'description': 'Connection timeout in seconds (default 5)'},
                        },
                        'required': ['primary_host', 'primary_port', 'replica_host', 'replica_port'],
                    },
                },
                'params': {'db': ['postgres', 'mysql', 'redis', 'mongodb']},
                'prompts': [
                    'Create a Python action to check {db} replication status between primary and replica',
                    'Python script that verifies both {db} primary and replica are reachable',
                ],
                'explanation': 'Python action that checks {db} replication status by verifying connectivity to both the primary and replica instances.',
            },
        ]


def get_generators():
    return [DatabaseGenerator()]
