"""Shell action generators for process management operations."""

from examples.generators.base_generator import ShellActionGenerator


class ProcessMgmtGenerator(ShellActionGenerator):
    category = "shell.process_mgmt"
    subcategory = "process_mgmt"

    def seeds(self):
        return [
            {
                'name': 'crontab-add-entry',
                'template': {
                    'name': '{user}-crontab-add',
                    'action_type': 'SHELL',
                    'code': '(crontab -u {{input.user}} -l 2>/dev/null || true; echo "{{input.schedule}} {{input.command}}") | sort -u | crontab -u {{input.user}} - && echo "Cron entry added for user {{input.user}}" || (echo "FAILED: Could not add crontab entry" >&2; exit 1)',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'user': {'type': 'string', 'description': 'System user who owns the crontab'},
                            'schedule': {'type': 'string', 'description': 'Cron schedule expression (e.g. "0 2 * * *")'},
                            'command': {'type': 'string', 'description': 'Command to execute on schedule'},
                        },
                        'required': ['user', 'schedule', 'command'],
                    },
                },
                'params': {'user': ['root', 'www-data', 'deploy', 'app', 'postgres']},
                'prompts': [
                    'Add a crontab entry for user {user}',
                    'Create a DM shell action to schedule a cron job for {user}',
                    'Write an action template that adds a cron entry for {user}',
                ],
                'explanation': 'Adds a crontab entry for the {user} user without duplicating existing entries.',
                'features': ['schema_variables'],
            },
            {
                'name': 'crontab-remove-entry',
                'template': {
                    'name': '{user}-crontab-remove',
                    'action_type': 'SHELL',
                    'code': 'crontab -u {{input.user}} -l 2>/dev/null | grep -v -F "{{input.pattern}}" | crontab -u {{input.user}} - && echo "Matching cron entries removed for {{input.user}}" || (echo "FAILED: Could not modify crontab" >&2; exit 1)',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'user': {'type': 'string', 'description': 'System user who owns the crontab'},
                            'pattern': {'type': 'string', 'description': 'Fixed string pattern to match and remove from crontab'},
                        },
                        'required': ['user', 'pattern'],
                    },
                },
                'params': {'user': ['root', 'www-data', 'deploy', 'app', 'postgres']},
                'prompts': [
                    'Remove a crontab entry for user {user} matching a pattern',
                    'Create a DM action to delete a cron job for {user}',
                    'Write a shell action that removes matching cron entries for {user}',
                ],
                'explanation': 'Removes crontab entries matching a given pattern for the {user} user.',
                'features': ['schema_variables'],
            },
            {
                'name': 'kill-process-by-name',
                'template': {
                    'name': '{target}-kill-by-name',
                    'action_type': 'SHELL',
                    'code': 'PIDS=$(pgrep -f "{{input.process_name}}" 2>/dev/null); if [ -z "$PIDS" ]; then echo "No matching processes found"; exit 0; fi; echo "Sending signal {{input.signal}} to PIDs: $PIDS"; kill -{{input.signal}} $PIDS && sleep 2 && if pgrep -f "{{input.process_name}}" > /dev/null 2>&1; then echo "WARNING: Some processes still running"; exit 1; else echo "All matching processes terminated"; fi',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'process_name': {'type': 'string', 'description': 'Process name or pattern to match'},
                            'signal': {'type': 'string', 'description': 'Signal to send (e.g. TERM, KILL, HUP, 9, 15)'},
                        },
                        'required': ['process_name', 'signal'],
                    },
                },
                'params': {'target': ['java', 'python', 'node', 'ruby', 'worker', 'gunicorn']},
                'prompts': [
                    'Kill all {target} processes by name',
                    'Create a DM action to terminate {target} processes with a given signal',
                    'Write a shell action that kills matching {target} processes',
                ],
                'explanation': 'Finds and terminates {target} processes matching a name pattern using a configurable signal.',
                'features': ['schema_variables'],
            },
            {
                'name': 'nice-renice-priority',
                'template': {
                    'name': '{target}-renice',
                    'action_type': 'SHELL',
                    'code': 'PIDS=$(pgrep -f "{{input.process_name}}" 2>/dev/null); if [ -z "$PIDS" ]; then echo "FAILED: No matching processes found" >&2; exit 1; fi; for PID in $PIDS; do renice {{input.priority}} -p "$PID" 2>&1; done && echo "Priority set to {{input.priority}} for process {{input.process_name}}"',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'process_name': {'type': 'string', 'description': 'Process name or pattern to match'},
                            'priority': {'type': 'integer', 'description': 'Nice priority value (-20 highest to 19 lowest)'},
                        },
                        'required': ['process_name', 'priority'],
                    },
                },
                'params': {'target': ['java', 'mysql', 'postgres', 'nginx', 'backup']},
                'prompts': [
                    'Change the nice priority of {target} processes',
                    'Create a DM action to renice {target} to a given priority',
                    'Write a shell action that adjusts scheduling priority for {target}',
                ],
                'explanation': 'Adjusts the nice priority of running {target} processes.',
                'features': ['schema_variables'],
            },
            {
                'name': 'ulimit-config',
                'template': {
                    'name': '{target}-ulimit-config',
                    'action_type': 'SHELL',
                    'code': 'cat >> /etc/security/limits.d/99-{{input.user}}.conf <<LIMITS\n{{input.user}} soft nofile {{input.soft_nofile}}\n{{input.user}} hard nofile {{input.hard_nofile}}\n{{input.user}} soft nproc {{input.soft_nproc}}\n{{input.user}} hard nproc {{input.hard_nproc}}\nLIMITS\necho "Limits configured for {{input.user}} (nofile: {{input.soft_nofile}}/{{input.hard_nofile}}, nproc: {{input.soft_nproc}}/{{input.hard_nproc}})"',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'user': {'type': 'string', 'description': 'System user to configure limits for'},
                            'soft_nofile': {'type': 'integer', 'description': 'Soft limit for open files'},
                            'hard_nofile': {'type': 'integer', 'description': 'Hard limit for open files'},
                            'soft_nproc': {'type': 'integer', 'description': 'Soft limit for processes'},
                            'hard_nproc': {'type': 'integer', 'description': 'Hard limit for processes'},
                        },
                        'required': ['user', 'soft_nofile', 'hard_nofile', 'soft_nproc', 'hard_nproc'],
                    },
                },
                'params': {'target': ['elasticsearch', 'nginx', 'postgres', 'redis', 'app']},
                'prompts': [
                    'Configure ulimits for the {target} service user',
                    'Create a DM action to set file and process limits for {target}',
                    'Write a shell action that sets ulimit values for {target}',
                ],
                'explanation': 'Configures per-user resource limits (nofile, nproc) for the {target} service user via limits.d.',
                'features': ['schema_variables'],
                'difficulty': 'intermediate',
            },
            {
                'name': 'systemd-cgroup-limits',
                'template': {
                    'name': '{target}-cgroup-limits',
                    'action_type': 'SHELL',
                    'code': 'mkdir -p /etc/systemd/system/{{input.service_name}}.service.d && cat > /etc/systemd/system/{{input.service_name}}.service.d/cgroup-limits.conf <<EOF\n[Service]\nMemoryMax={{input.memory_max}}\nMemoryHigh={{input.memory_high}}\nCPUWeight={{input.cpu_weight}}\nTasksMax={{input.tasks_max}}\nEOF\nsystemctl daemon-reload && systemctl restart {{input.service_name}} && echo "Cgroup limits applied: MemoryMax={{input.memory_max}}, CPUWeight={{input.cpu_weight}}, TasksMax={{input.tasks_max}}"',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'service_name': {'type': 'string', 'description': 'Systemd service to apply cgroup limits to'},
                            'memory_max': {'type': 'string', 'description': 'Hard memory limit (e.g. 1G, 512M)'},
                            'memory_high': {'type': 'string', 'description': 'Memory throttle threshold (e.g. 800M)'},
                            'cpu_weight': {'type': 'integer', 'description': 'CPU weight 1-10000 (default 100)'},
                            'tasks_max': {'type': 'integer', 'description': 'Maximum number of tasks/threads'},
                        },
                        'required': ['service_name', 'memory_max', 'memory_high', 'cpu_weight', 'tasks_max'],
                    },
                },
                'params': {'target': ['nginx', 'postgresql', 'mysql', 'redis', 'elasticsearch', 'docker']},
                'prompts': [
                    'Set systemd cgroup resource limits for {target}',
                    'Create a DM action to apply cgroup memory and CPU limits to {target}',
                    'Write a shell action to configure cgroup constraints for {target}',
                ],
                'explanation': 'Applies cgroup v2 resource limits (memory, CPU, tasks) to the {target} service via a systemd drop-in.',
                'features': ['schema_variables'],
                'difficulty': 'intermediate',
            },
            {
                'name': 'at-job-scheduling',
                'template': {
                    'name': '{target}-at-job',
                    'action_type': 'SHELL',
                    'code': 'echo "{{input.command}}" | at {{input.time_spec}} 2>&1 && echo "Job scheduled at {{input.time_spec}}" || (echo "FAILED: Could not schedule at job" >&2; exit 1)',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'command': {'type': 'string', 'description': 'Command to execute at the scheduled time'},
                            'time_spec': {'type': 'string', 'description': 'Time specification (e.g. "now + 1 hour", "2am tomorrow", "teatime")'},
                        },
                        'required': ['command', 'time_spec'],
                    },
                },
                'params': {'target': ['maintenance', 'backup', 'restart', 'cleanup', 'report']},
                'prompts': [
                    'Schedule a one-time {target} job using at',
                    'Create a DM action to run a {target} command at a future time',
                    'Write a shell action that schedules a {target} task with at',
                ],
                'explanation': 'Schedules a one-time {target} command to run at a specified future time using the at scheduler.',
                'features': ['schema_variables'],
            },
            {
                'name': 'zombie-process-cleanup',
                'template': {
                    'name': '{target}-zombie-cleanup',
                    'action_type': 'SHELL',
                    'code': 'ZOMBIES=$(ps aux | awk \'$8=="Z" {print $2}\'); if [ -z "$ZOMBIES" ]; then echo "No zombie processes found"; exit 0; fi; echo "Found zombie PIDs: $ZOMBIES"; for ZPID in $ZOMBIES; do PPID=$(ps -o ppid= -p "$ZPID" 2>/dev/null | tr -d " "); if [ -n "$PPID" ] && [ "$PPID" != "1" ]; then echo "Sending SIGCHLD to parent PID $PPID of zombie $ZPID"; kill -SIGCHLD "$PPID" 2>/dev/null; fi; done; sleep 1; REMAINING=$(ps aux | awk \'$8=="Z"\' | wc -l); echo "Zombie processes remaining: $REMAINING"',
                    'expected_rc': 0,
                    'schema': {
                        'input': {},
                        'required': [],
                    },
                },
                'params': {'target': ['system', 'server', 'host', 'node']},
                'prompts': [
                    'Clean up zombie processes on the {target}',
                    'Create a DM action to find and clean zombie processes on {target}',
                    'Write a shell action that detects and resolves zombie processes on {target}',
                ],
                'explanation': 'Finds zombie processes on the {target} and sends SIGCHLD to their parents to trigger cleanup.',
                'features': ['schema_variables'],
            },
        ]


def get_generators():
    return [ProcessMgmtGenerator()]
