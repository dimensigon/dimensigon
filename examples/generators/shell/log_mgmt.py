"""Shell action generators for log management operations."""

from examples.generators.base_generator import ShellActionGenerator


class LogMgmtGenerator(ShellActionGenerator):
    category = "shell.log_mgmt"
    subcategory = "log_mgmt"

    def seeds(self):
        return [
            {
                'name': 'logrotate-config',
                'template': {
                    'name': '{service}-logrotate-config',
                    'action_type': 'SHELL',
                    'code': 'cat > /etc/logrotate.d/{{input.service_name}} <<LOGROTATE\n{{input.log_path}} {{\n    {{input.rotation_schedule}}\n    rotate {{input.keep_count}}\n    compress\n    delaycompress\n    missingok\n    notifempty\n    create 0640 {{input.owner}} {{input.group}}\n    sharedscripts\n    postrotate\n        systemctl reload {{input.service_name}} 2>/dev/null || true\n    endscript\n}}\nLOGROTATE\nlogrotate -d /etc/logrotate.d/{{input.service_name}} 2>&1 && echo "Logrotate config validated for {{input.service_name}}"',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'service_name': {'type': 'string', 'description': 'Service name for the logrotate config'},
                            'log_path': {'type': 'string', 'description': 'Path to the log file(s) (e.g. /var/log/nginx/*.log)'},
                            'rotation_schedule': {'type': 'string', 'description': 'Rotation frequency (daily, weekly, monthly)'},
                            'keep_count': {'type': 'integer', 'description': 'Number of rotated files to keep'},
                            'owner': {'type': 'string', 'description': 'File owner for new log files'},
                            'group': {'type': 'string', 'description': 'File group for new log files'},
                        },
                        'required': ['service_name', 'log_path', 'rotation_schedule', 'keep_count', 'owner', 'group'],
                    },
                },
                'params': {'service': ['nginx', 'apache2', 'haproxy', 'tomcat', 'app']},
                'prompts': [
                    'Create a logrotate configuration for {service}',
                    'Write a DM action to set up log rotation for {service}',
                    'Generate a logrotate config for {service} logs',
                ],
                'explanation': 'Creates a logrotate configuration for the {service} service with compression and post-rotation reload.',
                'features': ['schema_variables'],
                'difficulty': 'intermediate',
            },
            {
                'name': 'compress-old-logs',
                'template': {
                    'name': 'compress-logs-{target}',
                    'action_type': 'SHELL',
                    'code': 'LOG_DIR="{{input.log_directory}}" && if [ ! -d "$LOG_DIR" ]; then echo "Directory not found" >&2; exit 1; fi && COUNT=$(find "$LOG_DIR" -name "{{input.pattern}}" -type f -mtime +{{input.days_old}} ! -name "*.gz" | wc -l) && echo "Compressing $COUNT log files older than {{input.days_old}} days..." && find "$LOG_DIR" -name "{{input.pattern}}" -type f -mtime +{{input.days_old}} ! -name "*.gz" -exec gzip -9 {{}} \\; && echo "Compression complete: $COUNT files compressed"',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'log_directory': {'type': 'string', 'description': 'Directory containing log files'},
                            'pattern': {'type': 'string', 'description': 'File name pattern (e.g. *.log)'},
                            'days_old': {'type': 'integer', 'description': 'Compress files older than this many days'},
                        },
                        'required': ['log_directory', 'pattern', 'days_old'],
                    },
                },
                'params': {'target': ['application', 'system', 'access', 'audit']},
                'prompts': [
                    'Compress old {target} log files',
                    'Create a DM action to gzip {target} logs older than N days',
                    'Write a shell action to compress aged {target} log files',
                ],
                'explanation': 'Finds and compresses {target} log files older than a specified number of days using gzip.',
                'features': ['schema_variables'],
            },
            {
                'name': 'journalctl-size-limit',
                'template': {
                    'name': 'journal-size-{action}',
                    'action_type': 'SHELL',
                    'code': 'echo "Current journal disk usage:" && journalctl --disk-usage && journalctl --vacuum-size={{input.max_size}} && journalctl --vacuum-time={{input.max_age}} && sed -i "s/^#\\?SystemMaxUse=.*/SystemMaxUse={{input.max_size}}/" /etc/systemd/journald.conf && systemctl restart systemd-journald && echo "Journal size limited to {{input.max_size}}, max age {{input.max_age}}"',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'max_size': {'type': 'string', 'description': 'Maximum journal disk usage (e.g. 500M, 1G)'},
                            'max_age': {'type': 'string', 'description': 'Maximum retention time (e.g. 30d, 2weeks)'},
                        },
                        'required': ['max_size', 'max_age'],
                    },
                },
                'params': {'action': ['limit', 'cleanup', 'configure']},
                'prompts': [
                    '{action} systemd journal disk usage',
                    'Create a DM action to {action} journald storage size',
                    'Write a shell action to {action} journal log retention',
                ],
                'explanation': 'Configures systemd journal size limits to {action} disk usage and sets retention policy.',
                'features': ['schema_variables'],
                'difficulty': 'intermediate',
            },
            {
                'name': 'log-ship-rsync',
                'template': {
                    'name': 'ship-logs-{target}',
                    'action_type': 'SHELL',
                    'code': 'rsync -avz --include="*.log" --include="*.log.gz" --exclude="*" "{{input.source_dir}}/" "{{input.remote_user}}@{{input.remote_host}}:{{input.remote_dir}}/" -e "ssh -o StrictHostKeyChecking=no -p {{input.ssh_port}}" && echo "Logs shipped to {{input.remote_host}}:{{input.remote_dir}}"',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'source_dir': {'type': 'string', 'description': 'Local log directory'},
                            'remote_host': {'type': 'string', 'description': 'Remote log server hostname/IP'},
                            'remote_dir': {'type': 'string', 'description': 'Remote destination directory'},
                            'remote_user': {'type': 'string', 'description': 'SSH user for remote connection'},
                            'ssh_port': {'type': 'integer', 'description': 'SSH port number'},
                        },
                        'required': ['source_dir', 'remote_host', 'remote_dir', 'remote_user', 'ssh_port'],
                    },
                },
                'params': {'target': ['application', 'system', 'security', 'audit']},
                'prompts': [
                    'Ship {target} logs to a remote server using rsync',
                    'Create a DM action to transfer {target} logs offsite',
                    'Write a shell action to rsync {target} logs to a central server',
                ],
                'explanation': 'Ships {target} log files to a remote server using rsync over SSH.',
                'features': ['schema_variables'],
                'difficulty': 'intermediate',
            },
            {
                'name': 'grep-error-pattern',
                'template': {
                    'name': 'grep-errors-{target}',
                    'action_type': 'SHELL',
                    'code': 'if [ ! -f "{{input.log_file}}" ]; then echo "Log file not found" >&2; exit 1; fi && echo "=== Error Pattern Analysis ===" && echo "ERROR count: $(grep -c -i "error" "{{input.log_file}}" 2>/dev/null || echo 0)" && echo "FATAL count: $(grep -c -i "fatal" "{{input.log_file}}" 2>/dev/null || echo 0)" && echo "WARNING count: $(grep -c -i "warn" "{{input.log_file}}" 2>/dev/null || echo 0)" && echo "=== Last 10 Errors ===" && grep -i "{{input.pattern}}" "{{input.log_file}}" | tail -{{input.max_lines}}',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'log_file': {'type': 'string', 'description': 'Path to the log file to analyze'},
                            'pattern': {'type': 'string', 'description': 'Error pattern to search for'},
                            'max_lines': {'type': 'integer', 'description': 'Maximum number of matching lines to return'},
                        },
                        'required': ['log_file', 'pattern', 'max_lines'],
                    },
                },
                'params': {'target': ['application', 'nginx', 'syslog', 'auth']},
                'prompts': [
                    'Search for error patterns in {target} logs',
                    'Create a DM action to grep {target} logs for errors',
                    'Write a shell action to analyze {target} log error patterns',
                ],
                'explanation': 'Searches {target} log files for error patterns and provides a summary with recent matches.',
                'features': ['schema_variables'],
            },
            {
                'name': 'log-truncation',
                'template': {
                    'name': 'truncate-log-{target}',
                    'action_type': 'SHELL',
                    'code': 'if [ ! -f "{{input.log_file}}" ]; then echo "Log file not found" >&2; exit 1; fi && SIZE_BEFORE=$(du -sh "{{input.log_file}}" | cut -f1) && cp "{{input.log_file}}" "{{input.log_file}}.truncated.$(date +%%Y%%m%%d%%H%%M%%S)" && truncate -s 0 "{{input.log_file}}" && echo "Truncated {{input.log_file}}: $SIZE_BEFORE -> 0 (backup created)"',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'log_file': {'type': 'string', 'description': 'Path to the log file to truncate'},
                        },
                        'required': ['log_file'],
                    },
                },
                'params': {'target': ['application', 'debug', 'access', 'error']},
                'prompts': [
                    'Truncate a {target} log file with backup',
                    'Create a DM action to safely truncate {target} logs',
                    'Write a shell action to clear a {target} log file',
                ],
                'explanation': 'Truncates a {target} log file to zero bytes after creating a timestamped backup.',
                'features': ['schema_variables'],
            },
            {
                'name': 'syslog-config',
                'template': {
                    'name': 'syslog-{action}',
                    'action_type': 'SHELL',
                    'code': 'cat >> /etc/rsyslog.d/60-{{input.config_name}}.conf <<SYSLOG\n# {{input.config_name}} syslog forwarding\n{{input.facility}}.{{input.severity}}    @@{{input.remote_host}}:{{input.remote_port}}\nSYSLOG\nrsyslogd -N1 2>&1 && systemctl restart rsyslog && echo "Syslog forwarding configured: {{input.facility}}.{{input.severity}} -> {{input.remote_host}}:{{input.remote_port}}"',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'config_name': {'type': 'string', 'description': 'Name for the rsyslog config file'},
                            'facility': {'type': 'string', 'description': 'Syslog facility (e.g. local0, auth, kern)'},
                            'severity': {'type': 'string', 'description': 'Syslog severity (e.g. *, err, warning, info)'},
                            'remote_host': {'type': 'string', 'description': 'Remote syslog server hostname/IP'},
                            'remote_port': {'type': 'integer', 'description': 'Remote syslog port (typically 514)'},
                        },
                        'required': ['config_name', 'facility', 'severity', 'remote_host', 'remote_port'],
                    },
                },
                'params': {'action': ['forward', 'configure', 'setup']},
                'prompts': [
                    '{action} rsyslog remote forwarding',
                    'Create a DM action to {action} syslog remote logging',
                    'Write a shell action to {action} rsyslog forwarding rules',
                ],
                'explanation': 'Configures rsyslog to {action} log forwarding to a remote syslog server.',
                'features': ['schema_variables'],
                'difficulty': 'intermediate',
            },
            {
                'name': 'access-log-analysis',
                'template': {
                    'name': 'analyze-access-{service}',
                    'action_type': 'SHELL',
                    'code': 'if [ ! -f "{{input.log_file}}" ]; then echo "Log file not found" >&2; exit 1; fi && echo "=== Access Log Analysis ===" && echo "Total requests: $(wc -l < "{{input.log_file}}")" && echo "" && echo "=== Top 10 IPs ===" && awk \'{{print $1}}\' "{{input.log_file}}" | sort | uniq -c | sort -rn | head -10 && echo "" && echo "=== HTTP Status Codes ===" && awk \'{{print $9}}\' "{{input.log_file}}" | sort | uniq -c | sort -rn | head -10 && echo "" && echo "=== Top 10 Requested URLs ===" && awk \'{{print $7}}\' "{{input.log_file}}" | sort | uniq -c | sort -rn | head -10',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'log_file': {'type': 'string', 'description': 'Path to the access log file'},
                        },
                        'required': ['log_file'],
                    },
                },
                'params': {'service': ['nginx', 'apache', 'haproxy', 'caddy']},
                'prompts': [
                    'Analyze {service} access log for top IPs and URLs',
                    'Create a DM action to generate {service} access log statistics',
                    'Write a shell action to parse {service} access log metrics',
                ],
                'explanation': 'Analyzes {service} access logs to show top IPs, HTTP status codes, and most requested URLs.',
                'features': ['schema_variables'],
            },
        ]


def get_generators():
    return [LogMgmtGenerator()]
