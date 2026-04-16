"""Service management Ansible action generators - 8 seeds for systemd, timers, sockets."""

from examples.generators.base_generator import AnsibleActionGenerator


class ServicesGenerator(AnsibleActionGenerator):
    category = "ansible.services"
    subcategory = "services"

    def seeds(self):
        return [
            {
                'name': 'systemd-start-enable',
                'template': {
                    'name': 'Start and enable {service}',
                    'action_type': 'ANSIBLE',
                    'code': (
                        '- name: Start and enable {{input.service_name}}\n'
                        '  systemd:\n'
                        '    name: "{{input.service_name}}"\n'
                        '    state: started\n'
                        '    enabled: yes\n'
                        '    daemon_reload: yes\n'
                        '\n'
                        '- name: Verify {{input.service_name}} is running\n'
                        '  command: "systemctl is-active {{input.service_name}}"\n'
                        '  register: service_status\n'
                        '  changed_when: false\n'
                        '  failed_when: service_status.rc != 0\n'
                    ),
                    'schema': {
                        'input': {
                            'service_name': {'type': 'string', 'description': 'Systemd service name'},
                        },
                        'required': ['service_name'],
                    },
                },
                'params': {'service': ['nginx', 'docker', 'postgresql', 'redis', 'prometheus', 'grafana', 'sshd', 'haproxy']},
                'prompts': [
                    'Create an Ansible action to start and enable {service}',
                    'Ansible playbook that ensures {service} is running and enabled on boot',
                ],
                'explanation': 'Ansible action that starts {service}, enables it on boot, triggers daemon reload, and verifies it is active.',
            },
            {
                'name': 'service-restart-handler',
                'template': {
                    'name': 'Restart {service} with handler',
                    'action_type': 'ANSIBLE',
                    'code': (
                        '- name: Deploy {{input.service_name}} config\n'
                        '  template:\n'
                        '    src: "{{input.config_src}}"\n'
                        '    dest: "{{input.config_dest}}"\n'
                        '    owner: root\n'
                        '    group: root\n'
                        '    mode: "0644"\n'
                        '  notify: restart {{input.service_name}}\n'
                        '\n'
                        '- name: Validate config before restart\n'
                        '  command: "{{input.validate_cmd}}"\n'
                        '  register: validate_result\n'
                        '  changed_when: false\n'
                        '  when: input.validate_cmd is defined and input.validate_cmd != ""\n'
                        '\n'
                        '- name: Restart {{input.service_name}}\n'
                        '  systemd:\n'
                        '    name: "{{input.service_name}}"\n'
                        '    state: restarted\n'
                    ),
                    'schema': {
                        'input': {
                            'service_name': {'type': 'string', 'description': 'Service name to restart'},
                            'config_src': {'type': 'string', 'description': 'Source config template path'},
                            'config_dest': {'type': 'string', 'description': 'Destination config path'},
                            'validate_cmd': {'type': 'string', 'description': 'Command to validate config (optional)'},
                        },
                        'required': ['service_name', 'config_src', 'config_dest'],
                    },
                },
                'params': {'service': ['nginx', 'haproxy', 'apache2', 'postfix', 'sshd']},
                'prompts': [
                    'Create an Ansible action to deploy config and restart {service}',
                    'Ansible playbook that updates {service} config and triggers a restart',
                ],
                'explanation': 'Ansible action that deploys a new {service} configuration, validates it, and restarts the service via handler.',
            },
            {
                'name': 'service-stop-graceful',
                'template': {
                    'name': 'Gracefully stop {service}',
                    'action_type': 'ANSIBLE',
                    'code': (
                        '- name: Check if {{input.service_name}} is running\n'
                        '  command: "systemctl is-active {{input.service_name}}"\n'
                        '  register: is_active\n'
                        '  changed_when: false\n'
                        '  failed_when: false\n'
                        '\n'
                        '- name: Gracefully stop {{input.service_name}}\n'
                        '  systemd:\n'
                        '    name: "{{input.service_name}}"\n'
                        '    state: stopped\n'
                        '  when: is_active.rc == 0\n'
                        '\n'
                        '- name: Disable {{input.service_name}} on boot\n'
                        '  systemd:\n'
                        '    name: "{{input.service_name}}"\n'
                        '    enabled: no\n'
                        '  when: input.disable_on_boot is defined and input.disable_on_boot == "true"\n'
                        '\n'
                        '- name: Verify {{input.service_name}} is stopped\n'
                        '  command: "systemctl is-active {{input.service_name}}"\n'
                        '  register: verify_stopped\n'
                        '  changed_when: false\n'
                        '  failed_when: verify_stopped.rc == 0\n'
                    ),
                    'schema': {
                        'input': {
                            'service_name': {'type': 'string', 'description': 'Service name to stop'},
                            'disable_on_boot': {'type': 'string', 'description': 'Also disable on boot: true/false'},
                        },
                        'required': ['service_name'],
                    },
                },
                'params': {'service': ['nginx', 'docker', 'postgresql', 'redis', 'apache2']},
                'prompts': [
                    'Create an Ansible action to gracefully stop {service}',
                    'Ansible playbook that stops {service} and optionally disables it on boot',
                ],
                'explanation': 'Ansible action that gracefully stops {service}, optionally disables it, and verifies it is no longer running.',
            },
            {
                'name': 'timer-unit-creation',
                'template': {
                    'name': 'Create systemd timer unit',
                    'action_type': 'ANSIBLE',
                    'code': (
                        '- name: Create timer unit for {{input.timer_name}}\n'
                        '  copy:\n'
                        '    dest: "/etc/systemd/system/{{input.timer_name}}.timer"\n'
                        '    content: |\n'
                        '      [Unit]\n'
                        '      Description={{input.description}}\n'
                        '\n'
                        '      [Timer]\n'
                        '      OnCalendar={{input.schedule}}\n'
                        '      Persistent=true\n'
                        '\n'
                        '      [Install]\n'
                        '      WantedBy=timers.target\n'
                        '    owner: root\n'
                        '    group: root\n'
                        '    mode: "0644"\n'
                        '\n'
                        '- name: Reload systemd daemon\n'
                        '  systemd:\n'
                        '    daemon_reload: yes\n'
                        '\n'
                        '- name: Enable and start timer\n'
                        '  systemd:\n'
                        '    name: "{{input.timer_name}}.timer"\n'
                        '    state: started\n'
                        '    enabled: yes\n'
                    ),
                    'schema': {
                        'input': {
                            'timer_name': {'type': 'string', 'description': 'Timer unit name (without .timer)'},
                            'description': {'type': 'string', 'description': 'Timer description'},
                            'schedule': {'type': 'string', 'description': 'OnCalendar schedule (e.g. daily, *-*-* 02:00:00)'},
                        },
                        'required': ['timer_name', 'schedule'],
                    },
                },
                'params': {'schedule': ['daily', 'hourly', 'weekly', '*-*-* 02:00:00', '*-*-* 00/6:00:00']},
                'prompts': [
                    'Create an Ansible action to set up a systemd timer running {schedule}',
                    'Ansible playbook that creates a {schedule} systemd timer unit',
                ],
                'explanation': 'Ansible action that creates a systemd timer unit with {schedule} schedule, reloads the daemon, and enables the timer.',
            },
            {
                'name': 'socket-activation',
                'template': {
                    'name': 'Socket activation for {service}',
                    'action_type': 'ANSIBLE',
                    'code': (
                        '- name: Create socket unit for {{input.service_name}}\n'
                        '  copy:\n'
                        '    dest: "/etc/systemd/system/{{input.service_name}}.socket"\n'
                        '    content: |\n'
                        '      [Unit]\n'
                        '      Description=Socket for {{input.service_name}}\n'
                        '\n'
                        '      [Socket]\n'
                        '      ListenStream={{input.listen_address}}\n'
                        '      Accept=no\n'
                        '\n'
                        '      [Install]\n'
                        '      WantedBy=sockets.target\n'
                        '    owner: root\n'
                        '    group: root\n'
                        '    mode: "0644"\n'
                        '\n'
                        '- name: Reload systemd\n'
                        '  systemd:\n'
                        '    daemon_reload: yes\n'
                        '\n'
                        '- name: Enable and start socket\n'
                        '  systemd:\n'
                        '    name: "{{input.service_name}}.socket"\n'
                        '    state: started\n'
                        '    enabled: yes\n'
                    ),
                    'schema': {
                        'input': {
                            'service_name': {'type': 'string', 'description': 'Service name for socket activation'},
                            'listen_address': {'type': 'string', 'description': 'Listen address (e.g. 0.0.0.0:8080 or /run/myapp.sock)'},
                        },
                        'required': ['service_name', 'listen_address'],
                    },
                },
                'params': {'service': ['gunicorn', 'uwsgi', 'myapp', 'api-server', 'webhook-receiver']},
                'prompts': [
                    'Create an Ansible action to set up socket activation for {service}',
                    'Ansible playbook that configures systemd socket activation for {service}',
                ],
                'explanation': 'Ansible action that creates a systemd socket unit for {service} with socket-based activation.',
            },
            {
                'name': 'service-file-template',
                'template': {
                    'name': 'Create {service} service file',
                    'action_type': 'ANSIBLE',
                    'code': (
                        '- name: Create systemd service file for {{input.service_name}}\n'
                        '  copy:\n'
                        '    dest: "/etc/systemd/system/{{input.service_name}}.service"\n'
                        '    content: |\n'
                        '      [Unit]\n'
                        '      Description={{input.description}}\n'
                        '      After=network.target\n'
                        '\n'
                        '      [Service]\n'
                        '      Type=simple\n'
                        '      User={{input.user}}\n'
                        '      ExecStart={{input.exec_start}}\n'
                        '      Restart=on-failure\n'
                        '      RestartSec=5\n'
                        '      StandardOutput=journal\n'
                        '      StandardError=journal\n'
                        '\n'
                        '      [Install]\n'
                        '      WantedBy=multi-user.target\n'
                        '    owner: root\n'
                        '    group: root\n'
                        '    mode: "0644"\n'
                        '\n'
                        '- name: Reload systemd daemon\n'
                        '  systemd:\n'
                        '    daemon_reload: yes\n'
                        '\n'
                        '- name: Enable {{input.service_name}}\n'
                        '  systemd:\n'
                        '    name: "{{input.service_name}}"\n'
                        '    enabled: yes\n'
                    ),
                    'schema': {
                        'input': {
                            'service_name': {'type': 'string', 'description': 'Service name'},
                            'description': {'type': 'string', 'description': 'Service description'},
                            'user': {'type': 'string', 'description': 'User to run service as'},
                            'exec_start': {'type': 'string', 'description': 'ExecStart command'},
                        },
                        'required': ['service_name', 'exec_start'],
                    },
                },
                'params': {'service': ['webapp', 'api', 'worker', 'scheduler', 'agent']},
                'prompts': [
                    'Create an Ansible action to create a systemd service file for {service}',
                    'Ansible playbook that deploys a custom {service} systemd unit file',
                ],
                'explanation': 'Ansible action that creates a systemd service unit file for {service} with auto-restart and journal logging.',
            },
            {
                'name': 'daemon-reload',
                'template': {
                    'name': 'Systemd daemon reload',
                    'action_type': 'ANSIBLE',
                    'code': (
                        '- name: Reload systemd daemon\n'
                        '  systemd:\n'
                        '    daemon_reload: yes\n'
                        '\n'
                        '- name: List failed units\n'
                        '  command: systemctl list-units --failed --no-legend\n'
                        '  register: failed_units\n'
                        '  changed_when: false\n'
                        '\n'
                        '- name: Report failed units\n'
                        '  debug:\n'
                        '    msg: "Failed units: {{ failed_units.stdout_lines }}"\n'
                        '  when: failed_units.stdout_lines | length > 0\n'
                    ),
                    'schema': {
                        'input': {},
                        'required': [],
                    },
                },
                'params': {'context': ['post-deploy', 'maintenance', 'troubleshooting', 'upgrade']},
                'prompts': [
                    'Create an Ansible action to reload systemd daemon during {context}',
                    'Ansible playbook that reloads systemd and checks for failed units after {context}',
                ],
                'explanation': 'Ansible action that reloads the systemd daemon during {context} and reports any failed service units.',
            },
            {
                'name': 'service-status-assertion',
                'template': {
                    'name': 'Assert {service} is running',
                    'action_type': 'ANSIBLE',
                    'code': (
                        '- name: Get {{input.service_name}} status\n'
                        '  systemd:\n'
                        '    name: "{{input.service_name}}"\n'
                        '  register: service_state\n'
                        '\n'
                        '- name: Assert {{input.service_name}} is active\n'
                        '  assert:\n'
                        '    that:\n'
                        '      - service_state.status.ActiveState == "active"\n'
                        '    fail_msg: "{{input.service_name}} is not active (state: {{ service_state.status.ActiveState }})"\n'
                        '    success_msg: "{{input.service_name}} is running"\n'
                        '\n'
                        '- name: Assert {{input.service_name}} is enabled\n'
                        '  assert:\n'
                        '    that:\n'
                        '      - service_state.status.UnitFileState == "enabled"\n'
                        '    fail_msg: "{{input.service_name}} is not enabled"\n'
                        '    success_msg: "{{input.service_name}} is enabled on boot"\n'
                    ),
                    'schema': {
                        'input': {
                            'service_name': {'type': 'string', 'description': 'Service name to assert status'},
                        },
                        'required': ['service_name'],
                    },
                },
                'params': {'service': ['nginx', 'docker', 'postgresql', 'redis', 'sshd', 'prometheus']},
                'prompts': [
                    'Create an Ansible action to assert {service} is running and enabled',
                    'Ansible playbook that validates {service} systemd state with assertions',
                ],
                'explanation': 'Ansible action that asserts {service} is both active and enabled using systemd facts and assertion checks.',
            },
            {
                'name': 'service-mask',
                'template': {
                    'name': 'Mask {service} service',
                    'action_type': 'ANSIBLE',
                    'code': (
                        '- name: Stop {{input.service_name}} if running\n'
                        '  systemd:\n'
                        '    name: "{{input.service_name}}"\n'
                        '    state: stopped\n'
                        '  failed_when: false\n'
                        '\n'
                        '- name: Mask {{input.service_name}}\n'
                        '  systemd:\n'
                        '    name: "{{input.service_name}}"\n'
                        '    masked: yes\n'
                        '\n'
                        '- name: Verify {{input.service_name}} is masked\n'
                        '  command: "systemctl is-enabled {{input.service_name}}"\n'
                        '  register: mask_check\n'
                        '  changed_when: false\n'
                        '  failed_when: mask_check.stdout != "masked"\n'
                    ),
                    'schema': {
                        'input': {
                            'service_name': {'type': 'string', 'description': 'Service name to mask'},
                        },
                        'required': ['service_name'],
                    },
                },
                'params': {'service': ['cups', 'bluetooth', 'avahi-daemon', 'rpcbind', 'nfs-server', 'firewalld']},
                'prompts': [
                    'Create an Ansible action to mask the {service} service',
                    'Ansible playbook that stops and masks {service} to prevent it from starting',
                ],
                'explanation': 'Ansible action that stops and masks the {service} service, preventing it from being started manually or automatically.',
            },
            {
                'name': 'service-limit-override',
                'template': {
                    'name': 'Override limits for {service}',
                    'action_type': 'ANSIBLE',
                    'code': (
                        '- name: Create systemd override directory for {{input.service_name}}\n'
                        '  file:\n'
                        '    path: "/etc/systemd/system/{{input.service_name}}.service.d"\n'
                        '    state: directory\n'
                        '    mode: "0755"\n'
                        '\n'
                        '- name: Deploy limits override for {{input.service_name}}\n'
                        '  copy:\n'
                        '    dest: "/etc/systemd/system/{{input.service_name}}.service.d/limits.conf"\n'
                        '    content: |\n'
                        '      [Service]\n'
                        '      LimitNOFILE={{input.limit_nofile}}\n'
                        '      LimitNPROC={{input.limit_nproc}}\n'
                        '      LimitMEMLOCK={{input.limit_memlock}}\n'
                        '    mode: "0644"\n'
                        '  notify: reload systemd and restart service\n'
                        '\n'
                        '- name: Reload systemd daemon\n'
                        '  systemd:\n'
                        '    daemon_reload: yes\n'
                        '\n'
                        '- name: Restart {{input.service_name}} to apply limits\n'
                        '  systemd:\n'
                        '    name: "{{input.service_name}}"\n'
                        '    state: restarted\n'
                    ),
                    'schema': {
                        'input': {
                            'service_name': {'type': 'string', 'description': 'Service name to set limits for'},
                            'limit_nofile': {'type': 'string', 'description': 'Max open files limit (e.g. 65536)'},
                            'limit_nproc': {'type': 'string', 'description': 'Max processes limit (e.g. 4096)'},
                            'limit_memlock': {'type': 'string', 'description': 'Max locked memory (e.g. infinity, 67108864)'},
                        },
                        'required': ['service_name', 'limit_nofile'],
                    },
                },
                'params': {'service': ['nginx', 'elasticsearch', 'postgresql', 'redis', 'haproxy', 'docker']},
                'prompts': [
                    'Create an Ansible action to set resource limits for {service} via systemd override',
                    'Ansible playbook that applies LimitNOFILE and LimitNPROC to {service}',
                ],
                'explanation': 'Ansible action that creates a systemd drop-in override to set file, process, and memory limits for {service}.',
            },
            {
                'name': 'service-environment-file',
                'template': {
                    'name': 'Deploy environment file for {service}',
                    'action_type': 'ANSIBLE',
                    'code': (
                        '- name: Create environment file for {{input.service_name}}\n'
                        '  copy:\n'
                        '    dest: "{{input.env_file_path}}"\n'
                        '    content: "{{input.env_content}}"\n'
                        '    owner: root\n'
                        '    group: root\n'
                        '    mode: "0640"\n'
                        '\n'
                        '- name: Create systemd override for EnvironmentFile\n'
                        '  copy:\n'
                        '    dest: "/etc/systemd/system/{{input.service_name}}.service.d/env.conf"\n'
                        '    content: |\n'
                        '      [Service]\n'
                        '      EnvironmentFile={{input.env_file_path}}\n'
                        '    mode: "0644"\n'
                        '\n'
                        '- name: Reload systemd and restart service\n'
                        '  systemd:\n'
                        '    name: "{{input.service_name}}"\n'
                        '    state: restarted\n'
                        '    daemon_reload: yes\n'
                    ),
                    'schema': {
                        'input': {
                            'service_name': {'type': 'string', 'description': 'Service name'},
                            'env_file_path': {'type': 'string', 'description': 'Path for the environment file'},
                            'env_content': {'type': 'string', 'description': 'Environment file content (KEY=value format)'},
                        },
                        'required': ['service_name', 'env_file_path', 'env_content'],
                    },
                },
                'params': {'service': ['webapp', 'api', 'worker', 'scheduler', 'nginx']},
                'prompts': [
                    'Create an Ansible action to deploy an environment file for {service}',
                    'Ansible playbook that sets up a systemd EnvironmentFile for {service}',
                ],
                'explanation': 'Ansible action that deploys an environment file for {service} and configures systemd to load it via a drop-in override.',
            },
            {
                'name': 'multi-service-orchestration',
                'template': {
                    'name': 'Orchestrate {service} service stack',
                    'action_type': 'ANSIBLE',
                    'code': (
                        '- name: Stop services in reverse order\n'
                        '  systemd:\n'
                        '    name: "{{ item }}"\n'
                        '    state: stopped\n'
                        '  loop: "{{ (input.service_list | split(\',\')) | reverse | list }}"\n'
                        '  failed_when: false\n'
                        '\n'
                        '- name: Start services in order\n'
                        '  systemd:\n'
                        '    name: "{{ item }}"\n'
                        '    state: started\n'
                        '    enabled: yes\n'
                        '  loop: "{{ input.service_list | split(\',\') }}"\n'
                        '\n'
                        '- name: Verify all services are active\n'
                        '  command: "systemctl is-active {{ item }}"\n'
                        '  loop: "{{ input.service_list | split(\',\') }}"\n'
                        '  register: service_checks\n'
                        '  changed_when: false\n'
                        '  failed_when: service_checks.rc != 0\n'
                    ),
                    'schema': {
                        'input': {
                            'service_list': {'type': 'string', 'description': 'Comma-separated list of services in startup order'},
                        },
                        'required': ['service_list'],
                    },
                },
                'params': {'service': ['web-stack', 'monitoring-stack', 'database-stack', 'app-platform']},
                'prompts': [
                    'Create an Ansible action to orchestrate the {service} services in order',
                    'Ansible playbook that restarts {service} services in the correct dependency order',
                ],
                'explanation': 'Ansible action that orchestrates the {service} service stack by stopping in reverse order and starting in dependency order.',
            },
        ]


def get_generators():
    return [ServicesGenerator()]
