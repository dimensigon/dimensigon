"""User and group management Ansible action generators - 6 seeds."""

from examples.generators.base_generator import AnsibleActionGenerator


class UsersGroupsGenerator(AnsibleActionGenerator):
    category = "ansible.users_groups"
    subcategory = "users_groups"

    def seeds(self):
        return [
            {
                'name': 'user-create',
                'template': {
                    'name': 'Create user {username}',
                    'action_type': 'ANSIBLE',
                    'code': (
                        '- name: Create user {{input.username}}\n'
                        '  user:\n'
                        '    name: "{{input.username}}"\n'
                        '    comment: "{{input.comment}}"\n'
                        '    shell: "{{input.shell}}"\n'
                        '    groups: "{{input.groups}}"\n'
                        '    append: yes\n'
                        '    create_home: yes\n'
                        '    state: present\n'
                        '\n'
                        '- name: Verify user exists\n'
                        '  command: "id {{input.username}}"\n'
                        '  register: user_check\n'
                        '  changed_when: false\n'
                    ),
                    'schema': {
                        'input': {
                            'username': {'type': 'string', 'description': 'Username to create'},
                            'comment': {'type': 'string', 'description': 'User comment/full name'},
                            'shell': {'type': 'string', 'description': 'Login shell (default /bin/bash)'},
                            'groups': {'type': 'string', 'description': 'Comma-separated list of groups'},
                        },
                        'required': ['username'],
                    },
                },
                'params': {'username': ['deploy', 'appuser', 'svcaccount', 'monitoring', 'backup', 'developer']},
                'prompts': [
                    'Create an Ansible action to create a {username} user account',
                    'Ansible playbook that provisions the {username} user with groups and home directory',
                ],
                'explanation': 'Ansible action that creates the {username} user with specified shell, groups, and home directory.',
            },
            {
                'name': 'group-create',
                'template': {
                    'name': 'Create group {group}',
                    'action_type': 'ANSIBLE',
                    'code': (
                        '- name: Create group {{input.group_name}}\n'
                        '  group:\n'
                        '    name: "{{input.group_name}}"\n'
                        '    gid: "{{input.gid}}"\n'
                        '    state: present\n'
                        '  when: input.gid is defined and input.gid != ""\n'
                        '\n'
                        '- name: Create group {{input.group_name}} without GID\n'
                        '  group:\n'
                        '    name: "{{input.group_name}}"\n'
                        '    state: present\n'
                        '  when: input.gid is not defined or input.gid == ""\n'
                    ),
                    'schema': {
                        'input': {
                            'group_name': {'type': 'string', 'description': 'Group name to create'},
                            'gid': {'type': 'string', 'description': 'Group ID (optional)'},
                        },
                        'required': ['group_name'],
                    },
                },
                'params': {'group': ['docker', 'deploy', 'developers', 'operators', 'monitoring', 'backup']},
                'prompts': [
                    'Create an Ansible action to create the {group} group',
                    'Ansible playbook that provisions the {group} group',
                ],
                'explanation': 'Ansible action that creates the {group} group with optional GID specification.',
            },
            {
                'name': 'authorized-key',
                'template': {
                    'name': 'Add SSH authorized key',
                    'action_type': 'ANSIBLE',
                    'code': (
                        '- name: Add SSH key for {{input.username}}\n'
                        '  authorized_key:\n'
                        '    user: "{{input.username}}"\n'
                        '    key: "{{input.ssh_public_key}}"\n'
                        '    state: present\n'
                        '    exclusive: "{{input.exclusive}}"\n'
                        '\n'
                        '- name: Set .ssh directory permissions\n'
                        '  file:\n'
                        '    path: "/home/{{input.username}}/.ssh"\n'
                        '    state: directory\n'
                        '    owner: "{{input.username}}"\n'
                        '    group: "{{input.username}}"\n'
                        '    mode: "0700"\n'
                    ),
                    'schema': {
                        'input': {
                            'username': {'type': 'string', 'description': 'User to add SSH key for'},
                            'ssh_public_key': {'type': 'string', 'description': 'SSH public key string'},
                            'exclusive': {'type': 'string', 'description': 'Replace all other keys: yes/no (default no)'},
                        },
                        'required': ['username', 'ssh_public_key'],
                    },
                },
                'params': {'key_type': ['ed25519', 'rsa', 'ecdsa']},
                'prompts': [
                    'Create an Ansible action to add an {key_type} SSH authorized key',
                    'Ansible playbook that deploys an {key_type} SSH public key for a user',
                ],
                'explanation': 'Ansible action that adds an {key_type} SSH public key to a user authorized_keys file with proper permissions.',
            },
            {
                'name': 'sudoers-entry',
                'template': {
                    'name': 'Add sudoers entry',
                    'action_type': 'ANSIBLE',
                    'code': (
                        '- name: Add sudoers entry for {{input.username}}\n'
                        '  copy:\n'
                        '    dest: "/etc/sudoers.d/{{input.username}}"\n'
                        '    content: "{{input.username}} {{input.sudoers_rule}}\\n"\n'
                        '    owner: root\n'
                        '    group: root\n'
                        '    mode: "0440"\n'
                        '    validate: "visudo -cf %s"\n'
                    ),
                    'schema': {
                        'input': {
                            'username': {'type': 'string', 'description': 'Username for sudoers entry'},
                            'sudoers_rule': {'type': 'string', 'description': 'Sudoers rule (e.g. ALL=(ALL) NOPASSWD: ALL)'},
                        },
                        'required': ['username', 'sudoers_rule'],
                    },
                },
                'params': {'privilege': ['full', 'service-restart', 'deploy', 'monitoring']},
                'prompts': [
                    'Create an Ansible action to add a {privilege} sudoers entry',
                    'Ansible playbook that configures {privilege}-level sudo access for a user',
                ],
                'explanation': 'Ansible action that creates a validated sudoers entry granting {privilege}-level access to a user.',
            },
            {
                'name': 'password-set',
                'template': {
                    'name': 'Set user password',
                    'action_type': 'ANSIBLE',
                    'code': (
                        '- name: Set password for {{input.username}}\n'
                        '  user:\n'
                        '    name: "{{input.username}}"\n'
                        '    password: "{{input.password_hash}}"\n'
                        '    update_password: always\n'
                        '\n'
                        '- name: Set password expiry policy\n'
                        '  command: "chage -M {{input.max_days}} -W {{input.warn_days}} {{input.username}}"\n'
                        '  when: input.max_days is defined and input.max_days != ""\n'
                        '  changed_when: true\n'
                    ),
                    'schema': {
                        'input': {
                            'username': {'type': 'string', 'description': 'Username to set password for'},
                            'password_hash': {'type': 'string', 'description': 'Password hash (from mkpasswd or openssl)'},
                            'max_days': {'type': 'string', 'description': 'Max days before password expires (optional)'},
                            'warn_days': {'type': 'string', 'description': 'Warn days before expiry (default 7)'},
                        },
                        'required': ['username', 'password_hash'],
                    },
                },
                'params': {'policy': ['standard', 'strict', 'temporary', 'service']},
                'prompts': [
                    'Create an Ansible action to set a user password with {policy} policy',
                    'Ansible playbook that configures user password with {policy} expiry policy',
                ],
                'explanation': 'Ansible action that sets a user password with {policy} expiry policy using a pre-hashed password.',
            },
            {
                'name': 'user-removal',
                'template': {
                    'name': 'Remove user account',
                    'action_type': 'ANSIBLE',
                    'code': (
                        '- name: Kill processes for {{input.username}}\n'
                        '  command: "pkill -u {{input.username}}"\n'
                        '  failed_when: false\n'
                        '  changed_when: false\n'
                        '\n'
                        '- name: Remove user {{input.username}}\n'
                        '  user:\n'
                        '    name: "{{input.username}}"\n'
                        '    state: absent\n'
                        '    remove: yes\n'
                        '    force: yes\n'
                        '\n'
                        '- name: Remove sudoers entry\n'
                        '  file:\n'
                        '    path: "/etc/sudoers.d/{{input.username}}"\n'
                        '    state: absent\n'
                        '\n'
                        '- name: Verify user is removed\n'
                        '  command: "id {{input.username}}"\n'
                        '  register: id_check\n'
                        '  changed_when: false\n'
                        '  failed_when: id_check.rc == 0\n'
                    ),
                    'schema': {
                        'input': {
                            'username': {'type': 'string', 'description': 'Username to remove'},
                        },
                        'required': ['username'],
                    },
                },
                'params': {'reason': ['offboarding', 'security', 'cleanup', 'decommission']},
                'prompts': [
                    'Create an Ansible action to remove a user for {reason}',
                    'Ansible playbook that completely removes a user account for {reason}',
                ],
                'explanation': 'Ansible action that removes a user for {reason}, killing processes, deleting home directory, and cleaning up sudoers.',
            },
        ]


def get_generators():
    return [UsersGroupsGenerator()]
