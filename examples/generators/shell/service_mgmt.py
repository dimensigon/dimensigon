"""Shell action generators for service management operations."""

from examples.generators.base_generator import ShellActionGenerator


class ServiceMgmtGenerator(ShellActionGenerator):
    category = "shell.service_mgmt"
    subcategory = "service_mgmt"

    def seeds(self):
        return [
            {
                'name': 'restart-service',
                'template': {
                    'name': '{service}-restart',
                    'action_type': 'SHELL',
                    'code': 'systemctl restart {{input.service_name}} && systemctl is-active --quiet {{input.service_name}} && echo "Service restarted successfully" || (echo "FAILED: Service did not restart" >&2; exit 1)',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'service_name': {'type': 'string', 'description': 'Name of the systemd service to restart'},
                        },
                        'required': ['service_name'],
                    },
                },
                'params': {'service': ['nginx', 'postgresql', 'mysql', 'redis', 'haproxy', 'docker', 'prometheus']},
                'prompts': [
                    'Restart the {service} service using systemctl',
                    'Create a DM shell action to restart {service}',
                    'Write an action template that restarts {service} and verifies it is running',
                ],
                'explanation': 'Restarts the {service} systemd service and verifies it becomes active.',
                'features': ['schema_variables'],
            },
            {
                'name': 'start-service',
                'template': {
                    'name': '{service}-start',
                    'action_type': 'SHELL',
                    'code': 'if systemctl is-active --quiet {{input.service_name}}; then echo "Service already running"; else systemctl start {{input.service_name}} && echo "Service started"; fi',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'service_name': {'type': 'string', 'description': 'Name of the systemd service to start'},
                        },
                        'required': ['service_name'],
                    },
                },
                'params': {'service': ['nginx', 'apache2', 'mysql', 'redis-server', 'docker', 'grafana-server']},
                'prompts': [
                    'Start the {service} service if it is not already running',
                    'Create a shell action to start {service}',
                    'Write a DM action that safely starts {service}',
                ],
                'explanation': 'Starts the {service} service only if it is not already running.',
                'features': ['schema_variables'],
            },
            {
                'name': 'stop-service',
                'template': {
                    'name': '{service}-stop',
                    'action_type': 'SHELL',
                    'code': 'systemctl stop {{input.service_name}} && systemctl is-active --quiet {{input.service_name}} && (echo "FAILED: Service still running" >&2; exit 1) || echo "Service stopped successfully"',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'service_name': {'type': 'string', 'description': 'Name of the systemd service to stop'},
                        },
                        'required': ['service_name'],
                    },
                },
                'params': {'service': ['nginx', 'postgresql', 'mysql', 'redis', 'haproxy', 'docker']},
                'prompts': [
                    'Stop the {service} service and verify it is no longer running',
                    'Create a DM action to stop {service}',
                    'Write a shell action template to stop {service} gracefully',
                ],
                'explanation': 'Stops the {service} service and confirms it is no longer active.',
                'features': ['schema_variables'],
            },
            {
                'name': 'enable-service',
                'template': {
                    'name': '{service}-enable',
                    'action_type': 'SHELL',
                    'code': 'systemctl enable {{input.service_name}} 2>&1 && systemctl is-enabled --quiet {{input.service_name}} && echo "Service enabled for boot" || (echo "FAILED: Could not enable service" >&2; exit 1)',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'service_name': {'type': 'string', 'description': 'Name of the systemd service to enable at boot'},
                        },
                        'required': ['service_name'],
                    },
                },
                'params': {'service': ['nginx', 'postgresql', 'redis', 'docker', 'prometheus', 'node-exporter']},
                'prompts': [
                    'Enable {service} to start automatically at boot',
                    'Create a DM shell action to enable {service} on startup',
                    'Write an action that enables the {service} service at boot time',
                ],
                'explanation': 'Enables the {service} service to start automatically on system boot.',
                'features': ['schema_variables'],
            },
            {
                'name': 'disable-service',
                'template': {
                    'name': '{service}-disable',
                    'action_type': 'SHELL',
                    'code': 'systemctl disable {{input.service_name}} 2>&1 && echo "Service disabled from boot" || (echo "FAILED: Could not disable service" >&2; exit 1)',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'service_name': {'type': 'string', 'description': 'Name of the systemd service to disable at boot'},
                        },
                        'required': ['service_name'],
                    },
                },
                'params': {'service': ['cups', 'avahi-daemon', 'bluetooth', 'postfix', 'nfs-server']},
                'prompts': [
                    'Disable {service} from starting at boot',
                    'Create a shell action to disable {service} autostart',
                    'Write a DM action to prevent {service} from starting on boot',
                ],
                'explanation': 'Disables the {service} service so it does not start automatically at boot.',
                'features': ['schema_variables'],
            },
            {
                'name': 'status-service',
                'template': {
                    'name': '{service}-status',
                    'action_type': 'SHELL',
                    'code': 'echo "=== Service Status ===" && systemctl status {{input.service_name}} --no-pager -l 2>&1; echo "=== Enabled State ===" && systemctl is-enabled {{input.service_name}} 2>&1; echo "=== Active State ===" && systemctl is-active {{input.service_name}} 2>&1; exit 0',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'service_name': {'type': 'string', 'description': 'Name of the systemd service to check'},
                        },
                        'required': ['service_name'],
                    },
                },
                'params': {'service': ['nginx', 'postgresql', 'mysql', 'redis', 'docker', 'haproxy', 'sshd']},
                'prompts': [
                    'Check the status of {service} service',
                    'Create a DM action to get {service} service status',
                    'Write a shell action that shows full status of {service}',
                ],
                'explanation': 'Retrieves the full status, enabled state, and active state of the {service} service.',
                'features': ['schema_variables'],
            },
            {
                'name': 'is-active-check',
                'template': {
                    'name': '{service}-is-active',
                    'action_type': 'SHELL',
                    'code': 'if systemctl is-active --quiet {{input.service_name}}; then echo "ACTIVE"; exit 0; else echo "INACTIVE"; exit 1; fi',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'service_name': {'type': 'string', 'description': 'Name of the systemd service to check active state'},
                        },
                        'required': ['service_name'],
                    },
                },
                'params': {'service': ['nginx', 'mysql', 'redis', 'docker', 'prometheus', 'grafana-server']},
                'prompts': [
                    'Check if {service} is currently active',
                    'Create a DM action to verify {service} is running',
                    'Write a shell action that returns active/inactive for {service}',
                ],
                'explanation': 'Checks whether the {service} service is currently active and returns a clear status.',
                'features': ['schema_variables'],
            },
            {
                'name': 'reload-service',
                'template': {
                    'name': '{service}-reload',
                    'action_type': 'SHELL',
                    'code': 'if systemctl is-active --quiet {{input.service_name}}; then systemctl reload {{input.service_name}} && echo "Service reloaded"; else echo "Service not running, starting instead" && systemctl start {{input.service_name}}; fi',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'service_name': {'type': 'string', 'description': 'Name of the systemd service to reload'},
                        },
                        'required': ['service_name'],
                    },
                },
                'params': {'service': ['nginx', 'apache2', 'haproxy', 'sshd', 'rsyslog', 'php-fpm']},
                'prompts': [
                    'Reload the {service} service configuration without downtime',
                    'Create a DM action to reload {service}',
                    'Write a shell action that gracefully reloads {service}',
                ],
                'explanation': 'Reloads the {service} service configuration without a full restart, or starts it if not running.',
                'features': ['schema_variables'],
            },
            {
                'name': 'unit-file-create',
                'template': {
                    'name': '{service}-unit-create',
                    'action_type': 'SHELL',
                    'code': 'cat > /etc/systemd/system/{{input.service_name}}.service <<UNIT\n[Unit]\nDescription={{input.description}}\nAfter=network.target\n\n[Service]\nType=simple\nUser={{input.run_user}}\nExecStart={{input.exec_start}}\nRestart=on-failure\nRestartSec=5\nStandardOutput=journal\nStandardError=journal\n\n[Install]\nWantedBy=multi-user.target\nUNIT\nsystemctl daemon-reload && echo "Unit file created and daemon reloaded"',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'service_name': {'type': 'string', 'description': 'Name for the new systemd service'},
                            'description': {'type': 'string', 'description': 'Description of the service'},
                            'run_user': {'type': 'string', 'description': 'User to run the service as'},
                            'exec_start': {'type': 'string', 'description': 'Full path to the executable command'},
                        },
                        'required': ['service_name', 'description', 'run_user', 'exec_start'],
                    },
                },
                'params': {'service': ['myapp', 'webapp', 'worker', 'api-server']},
                'prompts': [
                    'Create a systemd unit file for {service}',
                    'Write a DM action to create a custom systemd service for {service}',
                    'Generate a systemd service unit for {service} application',
                ],
                'explanation': 'Creates a new systemd unit file for {service} with configurable user, description, and executable.',
                'features': ['schema_variables'],
                'difficulty': 'intermediate',
            },
            {
                'name': 'service-dep-check',
                'template': {
                    'name': '{service}-dep-check',
                    'action_type': 'SHELL',
                    'code': 'echo "=== Dependencies for {{input.service_name}} ===" && systemctl list-dependencies {{input.service_name}} --no-pager 2>&1 && echo "=== Reverse dependencies ===" && systemctl list-dependencies {{input.service_name}} --reverse --no-pager 2>&1',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'service_name': {'type': 'string', 'description': 'Name of the systemd service to check dependencies for'},
                        },
                        'required': ['service_name'],
                    },
                },
                'params': {'service': ['nginx', 'postgresql', 'docker', 'haproxy', 'mysql']},
                'prompts': [
                    'List all dependencies for the {service} service',
                    'Create a DM action to show {service} dependency tree',
                    'Write a shell action to check what {service} depends on',
                ],
                'explanation': 'Lists forward and reverse dependencies for the {service} systemd service.',
                'features': ['schema_variables'],
            },
            {
                'name': 'journal-log-query',
                'template': {
                    'name': '{service}-journal-query',
                    'action_type': 'SHELL',
                    'code': 'journalctl -u {{input.service_name}} --since "{{input.since}}" --until "{{input.until}}" --no-pager -l --output=short-iso 2>&1 | tail -n {{input.max_lines}}',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'service_name': {'type': 'string', 'description': 'Name of the systemd service to query logs for'},
                            'since': {'type': 'string', 'description': 'Start time (e.g. "1 hour ago", "2024-01-01 00:00:00")'},
                            'until': {'type': 'string', 'description': 'End time (e.g. "now", "2024-01-01 23:59:59")'},
                            'max_lines': {'type': 'integer', 'description': 'Maximum number of log lines to return'},
                        },
                        'required': ['service_name', 'since', 'until', 'max_lines'],
                    },
                },
                'params': {'service': ['nginx', 'postgresql', 'mysql', 'redis', 'docker', 'sshd']},
                'prompts': [
                    'Query journal logs for {service} within a time range',
                    'Create a DM action to fetch {service} logs from journald',
                    'Write a shell action to get recent {service} journal entries',
                ],
                'explanation': 'Queries journald logs for the {service} service within a specified time range.',
                'features': ['schema_variables'],
                'difficulty': 'intermediate',
            },
            {
                'name': 'masked-svc-detect',
                'template': {
                    'name': '{service}-mask-detect',
                    'action_type': 'SHELL',
                    'code': 'STATE=$(systemctl is-enabled {{input.service_name}} 2>&1); if [ "$STATE" = "masked" ]; then echo "WARNING: {{input.service_name}} is masked"; echo "To unmask: systemctl unmask {{input.service_name}}"; exit 1; else echo "Service is not masked (state: $STATE)"; exit 0; fi',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'service_name': {'type': 'string', 'description': 'Name of the systemd service to check mask status'},
                        },
                        'required': ['service_name'],
                    },
                },
                'params': {'service': ['nginx', 'firewalld', 'iptables', 'docker', 'cups', 'bluetooth']},
                'prompts': [
                    'Detect if the {service} service is masked',
                    'Create a DM action to check whether {service} is masked',
                    'Write a shell action to warn if {service} is masked',
                ],
                'explanation': 'Checks whether the {service} service is masked and provides instructions to unmask if so.',
                'features': ['schema_variables'],
            },
            {
                'name': 'timer-create',
                'template': {
                    'name': '{service}-timer-create',
                    'action_type': 'SHELL',
                    'code': 'cat > /etc/systemd/system/{{input.timer_name}}.timer <<TIMER\n[Unit]\nDescription=Timer for {{input.timer_name}}\n\n[Timer]\nOnCalendar={{input.schedule}}\nPersistent=true\nUnit={{input.timer_name}}.service\n\n[Install]\nWantedBy=timers.target\nTIMER\nsystemctl daemon-reload && systemctl enable --now {{input.timer_name}}.timer && echo "Timer created and enabled"',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'timer_name': {'type': 'string', 'description': 'Name for the systemd timer'},
                            'schedule': {'type': 'string', 'description': 'OnCalendar schedule (e.g. "daily", "*-*-* 02:00:00")'},
                        },
                        'required': ['timer_name', 'schedule'],
                    },
                },
                'params': {'service': ['backup', 'cleanup', 'report', 'healthcheck']},
                'prompts': [
                    'Create a systemd timer for scheduled {service} tasks',
                    'Write a DM action to set up a recurring {service} timer',
                    'Generate a systemd timer unit for {service}',
                ],
                'explanation': 'Creates a systemd timer unit for scheduling recurring {service} tasks.',
                'features': ['schema_variables'],
                'difficulty': 'intermediate',
            },
            {
                'name': 'socket-activation',
                'template': {
                    'name': '{service}-socket-activate',
                    'action_type': 'SHELL',
                    'code': 'cat > /etc/systemd/system/{{input.service_name}}.socket <<SOCK\n[Unit]\nDescription=Socket for {{input.service_name}}\n\n[Socket]\nListenStream={{input.listen_port}}\nAccept=false\n\n[Install]\nWantedBy=sockets.target\nSOCK\nsystemctl daemon-reload && systemctl enable --now {{input.service_name}}.socket && echo "Socket activation enabled on port {{input.listen_port}}"',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'service_name': {'type': 'string', 'description': 'Name of the service for socket activation'},
                            'listen_port': {'type': 'integer', 'description': 'TCP port to listen on'},
                        },
                        'required': ['service_name', 'listen_port'],
                    },
                },
                'params': {'service': ['myapp', 'api-server', 'webhook-handler', 'proxy']},
                'prompts': [
                    'Set up socket activation for {service}',
                    'Create a DM action to enable socket-based activation for {service}',
                    'Write a systemd socket unit for on-demand {service} startup',
                ],
                'explanation': 'Creates a systemd socket unit for on-demand activation of the {service} service.',
                'features': ['schema_variables'],
                'difficulty': 'advanced',
            },
            {
                'name': 'svc-resource-limits',
                'template': {
                    'name': '{service}-resource-limits',
                    'action_type': 'SHELL',
                    'code': 'mkdir -p /etc/systemd/system/{{input.service_name}}.service.d && cat > /etc/systemd/system/{{input.service_name}}.service.d/limits.conf <<LIMITS\n[Service]\nMemoryLimit={{input.memory_limit}}\nCPUQuota={{input.cpu_quota}}\nLimitNOFILE={{input.max_open_files}}\nLIMITS\nsystemctl daemon-reload && systemctl restart {{input.service_name}} && echo "Resource limits applied to {{input.service_name}}"',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'service_name': {'type': 'string', 'description': 'Name of the systemd service to limit'},
                            'memory_limit': {'type': 'string', 'description': 'Memory limit (e.g. 512M, 2G)'},
                            'cpu_quota': {'type': 'string', 'description': 'CPU quota percentage (e.g. 50%, 200%)'},
                            'max_open_files': {'type': 'integer', 'description': 'Maximum number of open file descriptors'},
                        },
                        'required': ['service_name', 'memory_limit', 'cpu_quota', 'max_open_files'],
                    },
                },
                'params': {'service': ['nginx', 'postgresql', 'mysql', 'redis', 'docker', 'elasticsearch']},
                'prompts': [
                    'Set resource limits for {service} using systemd drop-in',
                    'Create a DM action to apply memory and CPU limits to {service}',
                    'Write a shell action to configure resource constraints for {service}',
                ],
                'explanation': 'Applies memory, CPU, and file descriptor limits to the {service} service using a systemd drop-in override.',
                'features': ['schema_variables'],
                'difficulty': 'intermediate',
            },
            {
                'name': 'systemd-timer-list',
                'template': {
                    'name': '{service}-timer-list',
                    'action_type': 'SHELL',
                    'code': 'echo "=== Active Timers ===" && systemctl list-timers --all --no-pager 2>&1 && echo "=== Timer Units ===" && systemctl list-unit-files --type=timer --no-pager 2>&1',
                    'expected_rc': 0,
                    'schema': {
                        'input': {},
                        'required': [],
                    },
                },
                'params': {'service': ['system', 'backup', 'monitoring', 'maintenance']},
                'prompts': [
                    'List all systemd timers on the {service} host',
                    'Create a DM action to show active {service} timers',
                    'Write a shell action that displays all systemd timer units for {service}',
                ],
                'explanation': 'Lists all active and configured systemd timers on the {service} host.',
                'features': ['schema_variables'],
            },
            {
                'name': 'service-log-extraction',
                'template': {
                    'name': '{service}-log-extract',
                    'action_type': 'SHELL',
                    'code': 'journalctl -u {{input.service_name}} --since "{{input.since}}" --no-pager --priority={{input.priority}} -o json 2>&1 | head -n {{input.max_lines}} && echo "Log extraction complete for {{input.service_name}}"',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'service_name': {'type': 'string', 'description': 'Name of the systemd service'},
                            'since': {'type': 'string', 'description': 'Time range (e.g. "1 hour ago", "today")'},
                            'priority': {'type': 'string', 'description': 'Minimum priority level (emerg, alert, crit, err, warning, notice, info, debug)'},
                            'max_lines': {'type': 'integer', 'description': 'Maximum number of log lines to return'},
                        },
                        'required': ['service_name', 'since', 'priority', 'max_lines'],
                    },
                },
                'params': {'service': ['nginx', 'postgresql', 'docker', 'redis', 'mysql', 'sshd']},
                'prompts': [
                    'Extract {service} logs filtered by priority level',
                    'Create a DM action to get {service} journal logs in JSON format',
                    'Write a shell action to pull structured logs from {service}',
                ],
                'explanation': 'Extracts journal logs from the {service} service filtered by time range and priority in JSON format.',
                'features': ['schema_variables'],
                'difficulty': 'intermediate',
            },
            {
                'name': 'service-memory-limit',
                'template': {
                    'name': '{service}-memory-limit',
                    'action_type': 'SHELL',
                    'code': 'mkdir -p /etc/systemd/system/{{input.service_name}}.service.d && cat > /etc/systemd/system/{{input.service_name}}.service.d/memory.conf <<MEMLIMIT\n[Service]\nMemoryMax={{input.memory_max}}\nMemoryHigh={{input.memory_high}}\nMEMLIMIT\nsystemctl daemon-reload && systemctl restart {{input.service_name}} && systemctl show {{input.service_name}} --property=MemoryMax,MemoryHigh --no-pager && echo "Memory limits applied to {{input.service_name}}"',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'service_name': {'type': 'string', 'description': 'Name of the systemd service'},
                            'memory_max': {'type': 'string', 'description': 'Hard memory limit (e.g. 1G, 512M)'},
                            'memory_high': {'type': 'string', 'description': 'Soft memory limit triggering reclaim (e.g. 768M)'},
                        },
                        'required': ['service_name', 'memory_max', 'memory_high'],
                    },
                },
                'params': {'service': ['nginx', 'postgresql', 'mysql', 'redis', 'elasticsearch', 'docker']},
                'prompts': [
                    'Set memory limits for the {service} service',
                    'Create a DM action to cap {service} memory usage with systemd cgroups',
                    'Write a shell action that applies MemoryMax and MemoryHigh to {service}',
                ],
                'explanation': 'Applies cgroup v2 memory limits to the {service} service using a systemd drop-in override.',
                'features': ['schema_variables'],
                'difficulty': 'intermediate',
            },
            {
                'name': 'multi-service-restart',
                'template': {
                    'name': '{service}-multi-restart',
                    'action_type': 'SHELL',
                    'code': 'SERVICES="{{input.service_list}}" && FAILED="" && for SVC in $SERVICES; do echo "Restarting $SVC..." && systemctl restart "$SVC" 2>&1 && if systemctl is-active --quiet "$SVC"; then echo "  OK: $SVC is active"; else echo "  FAIL: $SVC did not start" >&2; FAILED="$FAILED $SVC"; fi; done && if [ -n "$FAILED" ]; then echo "FAILED services:$FAILED" >&2; exit 1; else echo "All services restarted successfully"; fi',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'service_list': {'type': 'string', 'description': 'Space-separated list of systemd service names'},
                        },
                        'required': ['service_list'],
                    },
                },
                'params': {'service': ['web-stack', 'monitoring-stack', 'database-stack', 'app-stack']},
                'prompts': [
                    'Restart multiple services in the {service} at once',
                    'Create a DM action to restart all {service} services sequentially',
                    'Write a shell action that restarts a list of services for {service} and reports failures',
                ],
                'explanation': 'Restarts multiple services in the {service} sequentially and reports any that fail to become active.',
                'features': ['schema_variables'],
            },
            {
                'name': 'service-socket-check',
                'template': {
                    'name': '{service}-socket-check',
                    'action_type': 'SHELL',
                    'code': 'echo "=== Listening sockets for {{input.service_name}} ===" && PID=$(systemctl show {{input.service_name}} --property=MainPID --value 2>/dev/null) && if [ -z "$PID" ] || [ "$PID" = "0" ]; then echo "Service {{input.service_name}} is not running or has no main PID" >&2; exit 1; fi && echo "Main PID: $PID" && ss -tlnp 2>/dev/null | grep "pid=$PID" && echo "=== Established connections ===" && ss -tnp 2>/dev/null | grep "pid=$PID" | head -20 && echo "Socket check complete for {{input.service_name}}"',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'service_name': {'type': 'string', 'description': 'Name of the systemd service to check sockets for'},
                        },
                        'required': ['service_name'],
                    },
                },
                'params': {'service': ['nginx', 'postgresql', 'mysql', 'redis', 'haproxy', 'sshd']},
                'prompts': [
                    'Check listening sockets for the {service} service',
                    'Create a DM action to inspect {service} socket bindings',
                    'Write a shell action that shows what ports {service} is listening on',
                ],
                'explanation': 'Checks listening sockets and established connections for the {service} service by its main PID.',
                'features': ['schema_variables'],
            },
            {
                'name': 'watchdog-config',
                'template': {
                    'name': '{service}-watchdog-config',
                    'action_type': 'SHELL',
                    'code': 'mkdir -p /etc/systemd/system/{{input.service_name}}.service.d && cat > /etc/systemd/system/{{input.service_name}}.service.d/watchdog.conf <<WATCHDOG\n[Service]\nWatchdogSec={{input.watchdog_sec}}\nRestart=on-watchdog\nRestartSec={{input.restart_sec}}\nStartLimitIntervalSec={{input.limit_interval}}\nStartLimitBurst={{input.limit_burst}}\nWATCHDOG\nsystemctl daemon-reload && systemctl restart {{input.service_name}} && systemctl show {{input.service_name}} --property=WatchdogUSec,Restart --no-pager && echo "Watchdog configured for {{input.service_name}} (timeout: {{input.watchdog_sec}})"',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'service_name': {'type': 'string', 'description': 'Name of the systemd service'},
                            'watchdog_sec': {'type': 'string', 'description': 'Watchdog timeout (e.g. 30s, 60s)'},
                            'restart_sec': {'type': 'string', 'description': 'Delay before restart (e.g. 5s)'},
                            'limit_interval': {'type': 'string', 'description': 'Rate limit interval (e.g. 300s)'},
                            'limit_burst': {'type': 'integer', 'description': 'Maximum restarts within interval'},
                        },
                        'required': ['service_name', 'watchdog_sec', 'restart_sec', 'limit_interval', 'limit_burst'],
                    },
                },
                'params': {'service': ['nginx', 'postgresql', 'redis', 'docker', 'haproxy', 'myapp']},
                'prompts': [
                    'Configure a systemd watchdog for the {service} service',
                    'Create a DM action to set up watchdog monitoring for {service}',
                    'Write a shell action that enables watchdog-based auto-restart for {service}',
                ],
                'explanation': 'Configures a systemd watchdog for the {service} service with automatic restart on timeout and rate limiting.',
                'features': ['schema_variables'],
                'difficulty': 'advanced',
            },
        ]


def get_generators():
    return [ServiceMgmtGenerator()]
