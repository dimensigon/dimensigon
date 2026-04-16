"""Shell action generators for user and permission management."""

from examples.generators.base_generator import ShellActionGenerator


class UserPermsGenerator(ShellActionGenerator):
    category = "shell.user_perms"
    subcategory = "user_perms"

    def seeds(self):
        return [
            {
                'name': 'useradd',
                'template': {
                    'name': 'create-user-{user_type}',
                    'action_type': 'SHELL',
                    'code': 'if id "{{input.username}}" &>/dev/null; then echo "User already exists"; exit 0; fi && useradd -m -s {{input.shell}} -c "{{input.comment}}" {{input.username}} && echo "User {{input.username}} created successfully"',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'username': {'type': 'string', 'description': 'Username to create'},
                            'shell': {'type': 'string', 'description': 'Login shell (e.g. /bin/bash)'},
                            'comment': {'type': 'string', 'description': 'User description/comment field'},
                        },
                        'required': ['username', 'shell', 'comment'],
                    },
                },
                'params': {'user_type': ['app', 'system', 'service', 'developer']},
                'prompts': [
                    'Create a new {user_type} user account',
                    'Write a DM action to add a {user_type} user to the system',
                    'Generate a shell action for creating {user_type} users',
                ],
                'explanation': 'Creates a new {user_type} user account with specified shell and description.',
                'features': ['schema_variables'],
            },
            {
                'name': 'userdel',
                'template': {
                    'name': 'delete-user-{user_type}',
                    'action_type': 'SHELL',
                    'code': 'if ! id "{{input.username}}" &>/dev/null; then echo "User does not exist"; exit 0; fi && userdel -r {{input.username}} 2>&1 && echo "User {{input.username}} and home directory removed" || (echo "User removed but home dir may remain"; exit 0)',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'username': {'type': 'string', 'description': 'Username to delete'},
                        },
                        'required': ['username'],
                    },
                },
                'params': {'user_type': ['app', 'service', 'temporary', 'developer']},
                'prompts': [
                    'Delete a {user_type} user and their home directory',
                    'Create a DM action to remove a {user_type} user account',
                    'Write a shell action to safely delete a {user_type} user',
                ],
                'explanation': 'Deletes a {user_type} user account and removes their home directory.',
                'features': ['schema_variables'],
            },
            {
                'name': 'usermod',
                'template': {
                    'name': 'modify-user-{action}',
                    'action_type': 'SHELL',
                    'code': 'id "{{input.username}}" &>/dev/null || (echo "User not found" >&2; exit 1) && usermod -aG {{input.groups}} {{input.username}} && echo "User {{input.username}} added to groups: {{input.groups}}" && id {{input.username}}',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'username': {'type': 'string', 'description': 'Username to modify'},
                            'groups': {'type': 'string', 'description': 'Comma-separated list of groups to add'},
                        },
                        'required': ['username', 'groups'],
                    },
                },
                'params': {'action': ['add-groups', 'update-groups', 'set-groups']},
                'prompts': [
                    'Modify a user to {action} to supplementary groups',
                    'Create a DM action to {action} for a user',
                    'Write a shell action to {action} on a user account',
                ],
                'explanation': 'Modifies a user account to {action} to their supplementary group membership.',
                'features': ['schema_variables'],
            },
            {
                'name': 'groupadd',
                'template': {
                    'name': 'create-group-{group_type}',
                    'action_type': 'SHELL',
                    'code': 'if getent group "{{input.group_name}}" &>/dev/null; then echo "Group already exists"; exit 0; fi && groupadd {{input.group_name}} && echo "Group {{input.group_name}} created" && getent group {{input.group_name}}',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'group_name': {'type': 'string', 'description': 'Name of the group to create'},
                        },
                        'required': ['group_name'],
                    },
                },
                'params': {'group_type': ['app', 'admin', 'deploy', 'monitoring', 'backup']},
                'prompts': [
                    'Create a new {group_type} group',
                    'Write a DM action to add a {group_type} system group',
                    'Generate a shell action for creating a {group_type} group',
                ],
                'explanation': 'Creates a new {group_type} group if it does not already exist.',
                'features': ['schema_variables'],
            },
            {
                'name': 'chmod',
                'template': {
                    'name': 'chmod-{scope}',
                    'action_type': 'SHELL',
                    'code': 'if [ ! -e "{{input.path}}" ]; then echo "Path not found: {{input.path}}" >&2; exit 1; fi && chmod {{input.recursive}} {{input.mode}} "{{input.path}}" && echo "Permissions set to {{input.mode}} on {{input.path}}" && ls -la "{{input.path}}"',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'path': {'type': 'string', 'description': 'File or directory path'},
                            'mode': {'type': 'string', 'description': 'Permission mode (e.g. 755, 644, u+x)'},
                            'recursive': {'type': 'string', 'description': 'Use -R for recursive, empty string otherwise'},
                        },
                        'required': ['path', 'mode'],
                    },
                },
                'params': {'scope': ['file', 'directory', 'recursive']},
                'prompts': [
                    'Change permissions on a {scope}',
                    'Create a DM action to chmod a {scope}',
                    'Write a shell action to set file permissions on a {scope}',
                ],
                'explanation': 'Changes file permissions on a {scope} with the specified mode.',
                'features': ['schema_variables'],
            },
            {
                'name': 'chown',
                'template': {
                    'name': 'chown-{scope}',
                    'action_type': 'SHELL',
                    'code': 'if [ ! -e "{{input.path}}" ]; then echo "Path not found: {{input.path}}" >&2; exit 1; fi && chown {{input.recursive}} {{input.owner}}:{{input.group}} "{{input.path}}" && echo "Ownership set to {{input.owner}}:{{input.group}} on {{input.path}}" && ls -la "{{input.path}}"',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'path': {'type': 'string', 'description': 'File or directory path'},
                            'owner': {'type': 'string', 'description': 'Owner user name'},
                            'group': {'type': 'string', 'description': 'Owner group name'},
                            'recursive': {'type': 'string', 'description': 'Use -R for recursive, empty string otherwise'},
                        },
                        'required': ['path', 'owner', 'group'],
                    },
                },
                'params': {'scope': ['file', 'directory', 'recursive']},
                'prompts': [
                    'Change ownership of a {scope}',
                    'Create a DM action to chown a {scope}',
                    'Write a shell action to set ownership on a {scope}',
                ],
                'explanation': 'Changes ownership of a {scope} to the specified user and group.',
                'features': ['schema_variables'],
            },
            {
                'name': 'setfacl',
                'template': {
                    'name': 'setfacl-{acl_type}',
                    'action_type': 'SHELL',
                    'code': 'if [ ! -e "{{input.path}}" ]; then echo "Path not found" >&2; exit 1; fi && setfacl -m {{input.acl_spec}} "{{input.path}}" && echo "ACL applied to {{input.path}}" && getfacl "{{input.path}}"',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'path': {'type': 'string', 'description': 'File or directory path'},
                            'acl_spec': {'type': 'string', 'description': 'ACL specification (e.g. u:www-data:rx, g:deploy:rwx)'},
                        },
                        'required': ['path', 'acl_spec'],
                    },
                },
                'params': {'acl_type': ['user', 'group', 'default']},
                'prompts': [
                    'Set a {acl_type} ACL on a file or directory',
                    'Create a DM action to apply {acl_type} ACL permissions',
                    'Write a shell action to configure {acl_type} ACLs',
                ],
                'explanation': 'Sets a {acl_type}-level ACL on a file or directory using setfacl.',
                'features': ['schema_variables'],
                'difficulty': 'intermediate',
            },
            {
                'name': 'ssh-key-setup',
                'template': {
                    'name': 'ssh-key-{action}',
                    'action_type': 'SHELL',
                    'code': 'USER_HOME=$(eval echo "~{{input.username}}") && mkdir -p "$USER_HOME/.ssh" && chmod 700 "$USER_HOME/.ssh" && echo "{{input.public_key}}" >> "$USER_HOME/.ssh/authorized_keys" && sort -u "$USER_HOME/.ssh/authorized_keys" -o "$USER_HOME/.ssh/authorized_keys" && chmod 600 "$USER_HOME/.ssh/authorized_keys" && chown -R {{input.username}}:{{input.username}} "$USER_HOME/.ssh" && echo "SSH key added for {{input.username}}"',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'username': {'type': 'string', 'description': 'Username to add the SSH key for'},
                            'public_key': {'type': 'string', 'description': 'SSH public key string'},
                        },
                        'required': ['username', 'public_key'],
                    },
                },
                'params': {'action': ['deploy', 'add', 'authorize']},
                'prompts': [
                    '{action} an SSH public key for a user',
                    'Create a DM action to {action} SSH authorized_keys',
                    'Write a shell action to {action} an SSH key for a user',
                ],
                'explanation': 'Adds an SSH public key to a user authorized_keys file ({action} operation).',
                'features': ['schema_variables'],
                'difficulty': 'intermediate',
            },
            {
                'name': 'sudoers-edit',
                'template': {
                    'name': 'sudoers-{action}',
                    'action_type': 'SHELL',
                    'code': 'SUDOERS_FILE="/etc/sudoers.d/{{input.username}}" && echo "{{input.username}} {{input.sudoers_rule}}" > "$SUDOERS_FILE" && chmod 440 "$SUDOERS_FILE" && visudo -cf "$SUDOERS_FILE" && echo "Sudoers rule applied for {{input.username}}" || (rm -f "$SUDOERS_FILE"; echo "FAILED: Invalid sudoers syntax" >&2; exit 1)',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'username': {'type': 'string', 'description': 'Username to grant sudo privileges'},
                            'sudoers_rule': {'type': 'string', 'description': 'Sudoers rule (e.g. ALL=(ALL) NOPASSWD: ALL)'},
                        },
                        'required': ['username', 'sudoers_rule'],
                    },
                },
                'params': {'action': ['grant', 'configure', 'setup']},
                'prompts': [
                    '{action} sudo privileges for a user',
                    'Create a DM action to {action} sudoers rules',
                    'Write a shell action to {action} sudo access for a user',
                ],
                'explanation': 'Configures sudoers rules to {action} sudo privileges for a user with syntax validation.',
                'features': ['schema_variables'],
                'difficulty': 'intermediate',
            },
            {
                'name': 'password-aging',
                'template': {
                    'name': 'passwd-aging-{policy}',
                    'action_type': 'SHELL',
                    'code': 'chage -M {{input.max_days}} -m {{input.min_days}} -W {{input.warn_days}} -I {{input.inactive_days}} {{input.username}} && echo "Password aging policy applied for {{input.username}}" && chage -l {{input.username}}',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'username': {'type': 'string', 'description': 'Username to apply password aging policy'},
                            'max_days': {'type': 'integer', 'description': 'Maximum days between password changes'},
                            'min_days': {'type': 'integer', 'description': 'Minimum days between password changes'},
                            'warn_days': {'type': 'integer', 'description': 'Days before expiry to warn user'},
                            'inactive_days': {'type': 'integer', 'description': 'Days after expiry before account is disabled'},
                        },
                        'required': ['username', 'max_days', 'min_days', 'warn_days', 'inactive_days'],
                    },
                },
                'params': {'policy': ['standard', 'strict', 'compliance']},
                'prompts': [
                    'Apply a {policy} password aging policy to a user',
                    'Create a DM action to set {policy} password expiration',
                    'Write a shell action to enforce {policy} password aging',
                ],
                'explanation': 'Applies a {policy} password aging policy to a user account using chage.',
                'features': ['schema_variables'],
                'difficulty': 'intermediate',
            },
        ]


def get_generators():
    return [UserPermsGenerator()]
