"""Shell action generators for health check operations."""

from examples.generators.base_generator import ShellActionGenerator


class HealthChecksGenerator(ShellActionGenerator):
    category = "shell.health_checks"
    subcategory = "health_checks"

    def seeds(self):
        return [
            {
                'name': 'http-200-check',
                'template': {
                    'name': '{service}-http-check',
                    'action_type': 'SHELL',
                    'code': 'HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout {{input.timeout}} --max-time {{input.max_time}} "{{input.url}}") && if [ "$HTTP_CODE" = "200" ]; then echo "OK: {{input.url}} returned HTTP $HTTP_CODE"; else echo "FAILED: {{input.url}} returned HTTP $HTTP_CODE" >&2; exit 1; fi',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'url': {'type': 'string', 'description': 'URL to check (e.g. http://localhost:8080/health)'},
                            'timeout': {'type': 'integer', 'description': 'Connection timeout in seconds'},
                            'max_time': {'type': 'integer', 'description': 'Maximum total time in seconds'},
                        },
                        'required': ['url', 'timeout', 'max_time'],
                    },
                },
                'params': {'service': ['webapp', 'api', 'nginx', 'haproxy', 'grafana', 'prometheus']},
                'prompts': [
                    'Check if the {service} endpoint returns HTTP 200',
                    'Create a DM action to verify {service} HTTP health',
                    'Write a shell action that checks {service} returns a 200 status',
                ],
                'explanation': 'Checks that the {service} HTTP endpoint returns a 200 status code within the timeout period.',
                'features': ['schema_variables'],
            },
            {
                'name': 'tcp-port-check',
                'template': {
                    'name': '{service}-tcp-check',
                    'action_type': 'SHELL',
                    'code': 'if nc -z -w {{input.timeout}} {{input.host}} {{input.port}} 2>&1; then echo "OK: TCP port {{input.port}} is open on {{input.host}}"; else echo "FAILED: TCP port {{input.port}} is not reachable on {{input.host}}" >&2; exit 1; fi',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'host': {'type': 'string', 'description': 'Target hostname or IP address'},
                            'port': {'type': 'integer', 'description': 'TCP port number to check'},
                            'timeout': {'type': 'integer', 'description': 'Connection timeout in seconds'},
                        },
                        'required': ['host', 'port', 'timeout'],
                    },
                },
                'params': {'service': ['postgres', 'mysql', 'redis', 'elasticsearch', 'rabbitmq', 'ssh']},
                'prompts': [
                    'Check if the {service} TCP port is open',
                    'Create a DM action to verify {service} port connectivity',
                    'Write a shell action that tests TCP reachability of {service}',
                ],
                'explanation': 'Checks that the {service} TCP port is open and accepting connections using netcat.',
                'features': ['schema_variables'],
            },
            {
                'name': 'process-running-check',
                'template': {
                    'name': '{service}-process-check',
                    'action_type': 'SHELL',
                    'code': 'PIDS=$(pgrep -f "{{input.process_pattern}}" 2>/dev/null) && if [ -n "$PIDS" ]; then COUNT=$(echo "$PIDS" | wc -l) && echo "OK: {{input.process_pattern}} is running ($COUNT process(es), PIDs: $(echo $PIDS | tr "\\n" " "))"; else echo "FAILED: {{input.process_pattern}} is not running" >&2; exit 1; fi',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'process_pattern': {'type': 'string', 'description': 'Process name or pattern to match with pgrep -f'},
                        },
                        'required': ['process_pattern'],
                    },
                },
                'params': {'service': ['nginx', 'postgres', 'mysql', 'redis', 'java', 'node', 'python']},
                'prompts': [
                    'Check if the {service} process is running',
                    'Create a DM action to verify {service} process existence',
                    'Write a shell action that checks {service} is alive via pgrep',
                ],
                'explanation': 'Checks whether the {service} process is running and reports the process count and PIDs.',
                'features': ['schema_variables'],
            },
            {
                'name': 'memory-usage-threshold',
                'template': {
                    'name': '{target}-memory-check',
                    'action_type': 'SHELL',
                    'code': 'MEM_TOTAL=$(free -m | awk \'/^Mem:/ {print $2}\') && MEM_USED=$(free -m | awk \'/^Mem:/ {print $3}\') && MEM_AVAIL=$(free -m | awk \'/^Mem:/ {print $7}\') && MEM_PCT=$((MEM_USED * 100 / MEM_TOTAL)) && echo "Memory: ${MEM_USED}MB / ${MEM_TOTAL}MB (${MEM_PCT}% used, ${MEM_AVAIL}MB available)" && if [ "$MEM_PCT" -ge "{{input.critical_pct}}" ]; then echo "CRITICAL: Memory usage at ${MEM_PCT}% exceeds {{input.critical_pct}}% threshold" >&2; exit 2; elif [ "$MEM_PCT" -ge "{{input.warning_pct}}" ]; then echo "WARNING: Memory usage at ${MEM_PCT}% exceeds {{input.warning_pct}}% threshold" >&2; exit 1; else echo "OK: Memory usage is within thresholds"; fi',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'warning_pct': {'type': 'integer', 'description': 'Warning threshold percentage (e.g. 80)'},
                            'critical_pct': {'type': 'integer', 'description': 'Critical threshold percentage (e.g. 95)'},
                        },
                        'required': ['warning_pct', 'critical_pct'],
                    },
                },
                'params': {'target': ['server', 'host', 'node', 'worker', 'database']},
                'prompts': [
                    'Check memory usage against thresholds on the {target}',
                    'Create a DM action to monitor {target} memory consumption',
                    'Write a shell action that alerts when {target} memory exceeds a threshold',
                ],
                'explanation': 'Checks memory usage on the {target} against warning and critical percentage thresholds.',
                'features': ['schema_variables'],
            },
            {
                'name': 'cpu-load-check',
                'template': {
                    'name': '{target}-cpu-load-check',
                    'action_type': 'SHELL',
                    'code': 'NPROC=$(nproc) && LOAD_1=$(awk \'{print $1}\' /proc/loadavg) && LOAD_5=$(awk \'{print $2}\' /proc/loadavg) && LOAD_15=$(awk \'{print $3}\' /proc/loadavg) && echo "Load average: ${LOAD_1} (1m), ${LOAD_5} (5m), ${LOAD_15} (15m) | CPUs: $NPROC" && LOAD_INT=$(echo "$LOAD_5" | awk \'{printf "%d", $1 * 100}\') && THRESHOLD=$(echo "{{input.load_threshold}} $NPROC" | awk \'{printf "%d", $1 * $2 * 100}\') && if [ "$LOAD_INT" -ge "$THRESHOLD" ]; then echo "CRITICAL: 5-min load ($LOAD_5) exceeds threshold ({{input.load_threshold}} * $NPROC CPUs)" >&2; exit 1; else echo "OK: CPU load is within threshold ({{input.load_threshold}} * $NPROC CPUs)"; fi',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'load_threshold': {'type': 'number', 'description': 'Load threshold per CPU (e.g. 0.8 means 80% per core)'},
                        },
                        'required': ['load_threshold'],
                    },
                },
                'params': {'target': ['server', 'host', 'node', 'worker', 'database']},
                'prompts': [
                    'Check CPU load average against thresholds on the {target}',
                    'Create a DM action to monitor {target} CPU load',
                    'Write a shell action that alerts when {target} CPU load is too high',
                ],
                'explanation': 'Checks the 5-minute CPU load average on the {target} against a per-core threshold.',
                'features': ['schema_variables'],
            },
            {
                'name': 'disk-iowait-check',
                'template': {
                    'name': '{target}-iowait-check',
                    'action_type': 'SHELL',
                    'code': 'IOWAIT=$(iostat -c 1 2 | tail -1 | awk \'{print $4}\') && IOWAIT_INT=$(echo "$IOWAIT" | awk \'{printf "%d", $1 * 100}\') && THRESHOLD_INT=$(echo "{{input.threshold_pct}}" | awk \'{printf "%d", $1 * 100}\') && echo "I/O Wait: ${IOWAIT}%" && if [ "$IOWAIT_INT" -ge "$THRESHOLD_INT" ]; then echo "WARNING: I/O wait at ${IOWAIT}% exceeds {{input.threshold_pct}}% threshold" >&2; echo "=== Top I/O processes ===" && iotop -b -n 1 -o 2>/dev/null | head -10 || iostat -xd 1 1 2>&1; exit 1; else echo "OK: I/O wait is within threshold ({{input.threshold_pct}}%)"; fi',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'threshold_pct': {'type': 'number', 'description': 'I/O wait percentage threshold (e.g. 20)'},
                        },
                        'required': ['threshold_pct'],
                    },
                },
                'params': {'target': ['server', 'host', 'database', 'storage', 'node']},
                'prompts': [
                    'Check disk I/O wait on the {target}',
                    'Create a DM action to monitor {target} I/O wait percentage',
                    'Write a shell action that alerts when {target} I/O wait is high',
                ],
                'explanation': 'Checks the I/O wait percentage on the {target} and reports top I/O processes if the threshold is exceeded.',
                'features': ['schema_variables'],
            },
            {
                'name': 'dns-resolution-test',
                'template': {
                    'name': '{target}-dns-test',
                    'action_type': 'SHELL',
                    'code': 'echo "Resolving {{input.hostname}} via {{input.dns_server}}..." && RESULT=$(dig +short +time={{input.timeout}} @{{input.dns_server}} {{input.hostname}} {{input.record_type}} 2>&1) && if [ -z "$RESULT" ]; then echo "FAILED: DNS resolution returned no results for {{input.hostname}} ({{input.record_type}})" >&2; exit 1; else echo "OK: {{input.hostname}} ({{input.record_type}}) resolved to:"; echo "$RESULT"; fi',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'hostname': {'type': 'string', 'description': 'Hostname to resolve'},
                            'dns_server': {'type': 'string', 'description': 'DNS server to query (e.g. 8.8.8.8, 1.1.1.1)'},
                            'record_type': {'type': 'string', 'description': 'DNS record type (A, AAAA, CNAME, MX, TXT)'},
                            'timeout': {'type': 'integer', 'description': 'Query timeout in seconds'},
                        },
                        'required': ['hostname', 'dns_server', 'record_type', 'timeout'],
                    },
                },
                'params': {'target': ['external', 'internal', 'service', 'cdn', 'mail']},
                'prompts': [
                    'Test DNS resolution for an {target} hostname',
                    'Create a DM action to verify {target} DNS record resolution',
                    'Write a shell action that checks {target} DNS resolution',
                ],
                'explanation': 'Tests DNS resolution for an {target} hostname against a specified DNS server and record type.',
                'features': ['schema_variables'],
            },
            {
                'name': 'ssl-cert-expiry-check',
                'template': {
                    'name': '{service}-ssl-expiry',
                    'action_type': 'SHELL',
                    'code': 'EXPIRY_DATE=$(echo | openssl s_client -servername {{input.hostname}} -connect {{input.hostname}}:{{input.port}} 2>/dev/null | openssl x509 -noout -enddate 2>/dev/null | cut -d= -f2) && if [ -z "$EXPIRY_DATE" ]; then echo "FAILED: Could not retrieve certificate for {{input.hostname}}:{{input.port}}" >&2; exit 1; fi && EXPIRY_EPOCH=$(date -d "$EXPIRY_DATE" +%s 2>/dev/null || date -j -f "%b %d %T %Y %Z" "$EXPIRY_DATE" +%s 2>/dev/null) && NOW_EPOCH=$(date +%s) && DAYS_LEFT=$(( (EXPIRY_EPOCH - NOW_EPOCH) / 86400 )) && echo "Certificate for {{input.hostname}} expires: $EXPIRY_DATE ($DAYS_LEFT days remaining)" && if [ "$DAYS_LEFT" -le "{{input.critical_days}}" ]; then echo "CRITICAL: Certificate expires in $DAYS_LEFT days" >&2; exit 2; elif [ "$DAYS_LEFT" -le "{{input.warning_days}}" ]; then echo "WARNING: Certificate expires in $DAYS_LEFT days" >&2; exit 1; else echo "OK: Certificate is valid for $DAYS_LEFT more days"; fi',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'hostname': {'type': 'string', 'description': 'Hostname to check the SSL certificate for'},
                            'port': {'type': 'integer', 'description': 'TLS port number (typically 443)'},
                            'warning_days': {'type': 'integer', 'description': 'Warn if certificate expires within this many days'},
                            'critical_days': {'type': 'integer', 'description': 'Critical alert if certificate expires within this many days'},
                        },
                        'required': ['hostname', 'port', 'warning_days', 'critical_days'],
                    },
                },
                'params': {'service': ['webapp', 'api', 'mail', 'cdn', 'vpn', 'ldap']},
                'prompts': [
                    'Check SSL certificate expiry for the {service} endpoint',
                    'Create a DM action to monitor {service} TLS cert expiration',
                    'Write a shell action that warns when {service} SSL cert is near expiry',
                ],
                'explanation': 'Checks the SSL certificate expiry date for the {service} endpoint and alerts based on warning/critical thresholds.',
                'features': ['schema_variables'],
            },
            {
                'name': 'service-response-time',
                'template': {
                    'name': '{service}-response-time',
                    'action_type': 'SHELL',
                    'code': 'TIMES=$(curl -s -o /dev/null -w "dns:%{time_namelookup} connect:%{time_connect} ttfb:%{time_starttransfer} total:%{time_total}" --connect-timeout {{input.timeout}} --max-time {{input.max_time}} "{{input.url}}") && TOTAL=$(echo "$TIMES" | grep -oP "total:\\K[0-9.]+") && TOTAL_MS=$(echo "$TOTAL" | awk \'{printf "%d", $1 * 1000}\') && echo "Response times for {{input.url}}: $TIMES" && if [ "$TOTAL_MS" -ge "{{input.threshold_ms}}" ]; then echo "WARNING: Response time (${TOTAL_MS}ms) exceeds {{input.threshold_ms}}ms threshold" >&2; exit 1; else echo "OK: Response time ${TOTAL_MS}ms is within {{input.threshold_ms}}ms threshold"; fi',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'url': {'type': 'string', 'description': 'URL to measure response time for'},
                            'timeout': {'type': 'integer', 'description': 'Connection timeout in seconds'},
                            'max_time': {'type': 'integer', 'description': 'Maximum total time in seconds'},
                            'threshold_ms': {'type': 'integer', 'description': 'Response time threshold in milliseconds'},
                        },
                        'required': ['url', 'timeout', 'max_time', 'threshold_ms'],
                    },
                },
                'params': {'service': ['webapp', 'api', 'frontend', 'gateway', 'search']},
                'prompts': [
                    'Measure response time of the {service} endpoint',
                    'Create a DM action to check {service} response latency',
                    'Write a shell action that monitors {service} response time against a threshold',
                ],
                'explanation': 'Measures DNS, connect, TTFB, and total response time for the {service} endpoint and alerts if the threshold is exceeded.',
                'features': ['schema_variables'],
            },
            {
                'name': 'app-error-count-log',
                'template': {
                    'name': '{service}-error-count',
                    'action_type': 'SHELL',
                    'code': 'if [ ! -f "{{input.log_file}}" ]; then echo "FAILED: Log file not found: {{input.log_file}}" >&2; exit 1; fi && ERROR_COUNT=$(grep -c -i "{{input.error_pattern}}" "{{input.log_file}}" 2>/dev/null || echo 0) && echo "Error count in {{input.log_file}}: $ERROR_COUNT (pattern: {{input.error_pattern}})" && if [ "$ERROR_COUNT" -ge "{{input.threshold}}" ]; then echo "CRITICAL: $ERROR_COUNT errors found (threshold: {{input.threshold}})" >&2; echo "=== Recent matching lines ===" && grep -i "{{input.error_pattern}}" "{{input.log_file}}" | tail -5; exit 1; else echo "OK: Error count ($ERROR_COUNT) is below threshold ({{input.threshold}})"; fi',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'log_file': {'type': 'string', 'description': 'Path to the application log file'},
                            'error_pattern': {'type': 'string', 'description': 'Grep pattern to match errors (e.g. ERROR, FATAL, Exception)'},
                            'threshold': {'type': 'integer', 'description': 'Maximum acceptable error count'},
                            'lookback_minutes': {'type': 'integer', 'description': 'Number of minutes to look back in the log'},
                        },
                        'required': ['log_file', 'error_pattern', 'threshold', 'lookback_minutes'],
                    },
                },
                'params': {'service': ['webapp', 'api', 'worker', 'scheduler', 'nginx', 'java']},
                'prompts': [
                    'Count errors in the {service} application log',
                    'Create a DM action to check {service} log error rate',
                    'Write a shell action that alerts when {service} error count exceeds a threshold',
                ],
                'explanation': 'Counts error occurrences in the {service} application log and alerts if the count exceeds the threshold.',
                'features': ['schema_variables'],
            },
            {
                'name': 'http-body-check',
                'template': {
                    'name': '{service}-http-body-check',
                    'action_type': 'SHELL',
                    'code': 'RESPONSE=$(curl -s --connect-timeout {{input.timeout}} --max-time {{input.max_time}} "{{input.url}}") && if echo "$RESPONSE" | grep -q "{{input.expected_string}}"; then echo "OK: Response body contains expected string"; echo "Match: {{input.expected_string}}"; else echo "FAILED: Expected string not found in response body" >&2; echo "Expected: {{input.expected_string}}" >&2; echo "Response (first 500 chars): $(echo "$RESPONSE" | head -c 500)" >&2; exit 1; fi',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'url': {'type': 'string', 'description': 'URL to check response body'},
                            'expected_string': {'type': 'string', 'description': 'String that must be present in the response body'},
                            'timeout': {'type': 'integer', 'description': 'Connection timeout in seconds'},
                            'max_time': {'type': 'integer', 'description': 'Maximum total time in seconds'},
                        },
                        'required': ['url', 'expected_string', 'timeout', 'max_time'],
                    },
                },
                'params': {'service': ['webapp', 'api', 'nginx', 'haproxy', 'grafana']},
                'prompts': [
                    'Check if the {service} HTTP response body contains an expected string',
                    'Create a DM action to verify {service} response content',
                    'Write a shell action that validates {service} HTTP response body',
                ],
                'explanation': 'Checks that the {service} HTTP response body contains an expected string for content-level health verification.',
                'features': ['schema_variables'],
            },
            {
                'name': 'redis-latency-test',
                'template': {
                    'name': '{service}-redis-latency',
                    'action_type': 'SHELL',
                    'code': 'echo "=== Redis Latency Test ===" && LATENCY=$(redis-cli -h {{input.host}} -p {{input.port}} --latency-history -i 1 2>&1 | head -5) && echo "$LATENCY" && AVG_MS=$(echo "$LATENCY" | tail -1 | grep -oP "avg:\\s*\\K[0-9.]+") && if [ -n "$AVG_MS" ]; then AVG_INT=$(echo "$AVG_MS" | awk \'{printf "%d", $1 * 100}\') && THRESH_INT=$(echo "{{input.threshold_ms}}" | awk \'{printf "%d", $1 * 100}\') && if [ "$AVG_INT" -ge "$THRESH_INT" ]; then echo "WARNING: Average latency ${AVG_MS}ms exceeds {{input.threshold_ms}}ms threshold" >&2; exit 1; else echo "OK: Average latency ${AVG_MS}ms within {{input.threshold_ms}}ms threshold"; fi; else echo "OK: Latency test completed"; fi',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'host': {'type': 'string', 'description': 'Redis host address'},
                            'port': {'type': 'integer', 'description': 'Redis port number'},
                            'threshold_ms': {'type': 'number', 'description': 'Maximum acceptable average latency in milliseconds'},
                        },
                        'required': ['host', 'port', 'threshold_ms'],
                    },
                },
                'params': {'service': ['cache', 'session', 'queue', 'pubsub']},
                'prompts': [
                    'Test Redis latency for the {service} instance',
                    'Create a DM action to measure {service} Redis response latency',
                    'Write a shell action that checks {service} Redis latency against a threshold',
                ],
                'explanation': 'Tests Redis latency for the {service} instance and alerts if average latency exceeds the threshold.',
                'features': ['schema_variables'],
            },
            {
                'name': 'mysql-replication-lag',
                'template': {
                    'name': '{service}-mysql-repl-lag',
                    'action_type': 'SHELL',
                    'code': 'SLAVE_STATUS=$(mysql -h {{input.host}} -u {{input.username}} -e "SHOW SLAVE STATUS\\G" 2>/dev/null || mysql -h {{input.host}} -u {{input.username}} -e "SHOW REPLICA STATUS\\G" 2>/dev/null) && if [ -z "$SLAVE_STATUS" ]; then echo "FAILED: Could not retrieve replication status" >&2; exit 1; fi && IO_RUNNING=$(echo "$SLAVE_STATUS" | grep -E "Slave_IO_Running|Replica_IO_Running" | awk \'{print $2}\') && SQL_RUNNING=$(echo "$SLAVE_STATUS" | grep -E "Slave_SQL_Running|Replica_SQL_Running" | head -1 | awk \'{print $2}\') && LAG=$(echo "$SLAVE_STATUS" | grep "Seconds_Behind" | awk \'{print $2}\') && echo "IO Thread: $IO_RUNNING, SQL Thread: $SQL_RUNNING, Lag: ${LAG}s" && if [ "$IO_RUNNING" != "Yes" ] || [ "$SQL_RUNNING" != "Yes" ]; then echo "CRITICAL: Replication threads not running" >&2; exit 2; fi && if [ "$LAG" = "NULL" ]; then echo "WARNING: Replication lag is NULL" >&2; exit 1; fi && if [ "$LAG" -ge "{{input.critical_lag}}" ]; then echo "CRITICAL: Replication lag ${LAG}s exceeds {{input.critical_lag}}s" >&2; exit 2; elif [ "$LAG" -ge "{{input.warning_lag}}" ]; then echo "WARNING: Replication lag ${LAG}s exceeds {{input.warning_lag}}s" >&2; exit 1; else echo "OK: Replication healthy, lag ${LAG}s"; fi',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'host': {'type': 'string', 'description': 'MySQL replica host address'},
                            'username': {'type': 'string', 'description': 'MySQL user with REPLICATION CLIENT privilege'},
                            'warning_lag': {'type': 'integer', 'description': 'Warning threshold for replication lag in seconds'},
                            'critical_lag': {'type': 'integer', 'description': 'Critical threshold for replication lag in seconds'},
                        },
                        'required': ['host', 'username', 'warning_lag', 'critical_lag'],
                    },
                },
                'params': {'service': ['production-replica', 'read-replica', 'dr-replica', 'analytics-replica']},
                'prompts': [
                    'Check MySQL replication lag on the {service}',
                    'Create a DM action to monitor {service} replication delay',
                    'Write a shell action that alerts when {service} MySQL replication falls behind',
                ],
                'explanation': 'Checks MySQL replication status and lag on the {service}, alerting on thread failures or excessive delay.',
                'features': ['schema_variables'],
                'difficulty': 'intermediate',
            },
            {
                'name': 'cert-chain-verify',
                'template': {
                    'name': '{service}-cert-chain-verify',
                    'action_type': 'SHELL',
                    'code': 'echo "=== Certificate Chain Verification for {{input.hostname}}:{{input.port}} ===" && CERT_CHAIN=$(echo | openssl s_client -servername {{input.hostname}} -connect {{input.hostname}}:{{input.port}} -showcerts 2>/dev/null) && if [ -z "$CERT_CHAIN" ]; then echo "FAILED: Could not connect to {{input.hostname}}:{{input.port}}" >&2; exit 1; fi && VERIFY=$(echo | openssl s_client -servername {{input.hostname}} -connect {{input.hostname}}:{{input.port}} 2>&1 | grep "Verify return code") && echo "$VERIFY" && CERT_COUNT=$(echo "$CERT_CHAIN" | grep -c "BEGIN CERTIFICATE") && echo "Certificates in chain: $CERT_COUNT" && echo "$CERT_CHAIN" | openssl x509 -noout -subject -issuer -dates 2>/dev/null && if echo "$VERIFY" | grep -q "0 (ok)"; then echo "OK: Certificate chain is valid"; else echo "FAILED: Certificate chain verification failed" >&2; exit 1; fi',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'hostname': {'type': 'string', 'description': 'Hostname to verify certificate chain for'},
                            'port': {'type': 'integer', 'description': 'TLS port number (typically 443)'},
                        },
                        'required': ['hostname', 'port'],
                    },
                },
                'params': {'service': ['webapp', 'api', 'mail', 'cdn', 'vpn']},
                'prompts': [
                    'Verify the full SSL certificate chain for the {service} endpoint',
                    'Create a DM action to validate the {service} TLS certificate chain',
                    'Write a shell action that checks the {service} certificate chain is complete and valid',
                ],
                'explanation': 'Verifies the complete SSL/TLS certificate chain for the {service} endpoint including chain depth and validity.',
                'features': ['schema_variables'],
            },
            {
                'name': 'disk-smart-check',
                'template': {
                    'name': '{target}-disk-smart',
                    'action_type': 'SHELL',
                    'code': 'if ! command -v smartctl > /dev/null 2>&1; then echo "FAILED: smartmontools not installed" >&2; exit 1; fi && echo "=== SMART Health for {{input.device}} ===" && HEALTH=$(smartctl -H {{input.device}} 2>&1) && echo "$HEALTH" && ATTRS=$(smartctl -A {{input.device}} 2>&1) && echo "=== Key Attributes ===" && echo "$ATTRS" | grep -E "Reallocated_Sector|Current_Pending|Offline_Uncorrectable|Temperature|Power_On_Hours|Wear_Leveling" 2>/dev/null && if echo "$HEALTH" | grep -qi "PASSED\\|OK"; then echo "OK: Disk {{input.device}} SMART health is good"; else echo "WARNING: Disk {{input.device}} SMART health check failed" >&2; exit 1; fi',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'device': {'type': 'string', 'description': 'Disk device path (e.g. /dev/sda, /dev/nvme0n1)'},
                        },
                        'required': ['device'],
                    },
                },
                'params': {'target': ['server', 'storage', 'database', 'node']},
                'prompts': [
                    'Check disk SMART health on the {target}',
                    'Create a DM action to monitor {target} disk SMART status',
                    'Write a shell action that reads SMART attributes for {target} disk health',
                ],
                'explanation': 'Checks disk SMART health status and key attributes on the {target} for early failure detection.',
                'features': ['schema_variables'],
            },
        ]


def get_generators():
    return [HealthChecksGenerator()]
