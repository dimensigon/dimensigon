"""File and template Ansible action generators - 8 seeds for template, copy, lineinfile, etc."""

from examples.generators.base_generator import AnsibleActionGenerator


class FilesTemplatesGenerator(AnsibleActionGenerator):
    category = "ansible.files_templates"
    subcategory = "files_templates"

    def seeds(self):
        return [
            {
                'name': 'template-deploy',
                'template': {
                    'name': 'Deploy config via template',
                    'action_type': 'ANSIBLE',
                    'code': (
                        '- name: Deploy {{input.service_name}} config from template\n'
                        '  template:\n'
                        '    src: "{{input.template_src}}"\n'
                        '    dest: "{{input.dest_path}}"\n'
                        '    owner: "{{input.owner}}"\n'
                        '    group: "{{input.group}}"\n'
                        '    mode: "{{input.mode}}"\n'
                        '    backup: yes\n'
                        '    validate: "{{input.validate_cmd}}"\n'
                        '  notify: restart {{input.service_name}}\n'
                    ),
                    'schema': {
                        'input': {
                            'service_name': {'type': 'string', 'description': 'Service name for notification'},
                            'template_src': {'type': 'string', 'description': 'Template source path'},
                            'dest_path': {'type': 'string', 'description': 'Destination path on target'},
                            'owner': {'type': 'string', 'description': 'File owner (default root)'},
                            'group': {'type': 'string', 'description': 'File group (default root)'},
                            'mode': {'type': 'string', 'description': 'File mode (default 0644)'},
                            'validate_cmd': {'type': 'string', 'description': 'Validation command (optional)'},
                        },
                        'required': ['template_src', 'dest_path'],
                    },
                },
                'params': {'service_name': ['nginx', 'haproxy', 'apache', 'sshd', 'postfix']},
                'prompts': [
                    'Create an Ansible action to deploy {service_name} config from template',
                    'Ansible playbook that renders and deploys a {service_name} configuration template',
                ],
                'explanation': 'Ansible action that deploys a {service_name} configuration file from a Jinja2 template with backup and validation.',
            },
            {
                'name': 'copy-file',
                'template': {
                    'name': 'Copy file to target',
                    'action_type': 'ANSIBLE',
                    'code': (
                        '- name: Copy {{input.filename}} to target\n'
                        '  copy:\n'
                        '    src: "{{input.src_path}}"\n'
                        '    dest: "{{input.dest_path}}"\n'
                        '    owner: "{{input.owner}}"\n'
                        '    group: "{{input.group}}"\n'
                        '    mode: "{{input.mode}}"\n'
                        '    backup: yes\n'
                        '\n'
                        '- name: Verify file exists\n'
                        '  stat:\n'
                        '    path: "{{input.dest_path}}"\n'
                        '  register: file_check\n'
                        '  failed_when: not file_check.stat.exists\n'
                    ),
                    'schema': {
                        'input': {
                            'filename': {'type': 'string', 'description': 'File description for task name'},
                            'src_path': {'type': 'string', 'description': 'Source file path'},
                            'dest_path': {'type': 'string', 'description': 'Destination file path'},
                            'owner': {'type': 'string', 'description': 'File owner (default root)'},
                            'group': {'type': 'string', 'description': 'File group (default root)'},
                            'mode': {'type': 'string', 'description': 'File mode (default 0644)'},
                        },
                        'required': ['src_path', 'dest_path'],
                    },
                },
                'params': {'file_type': ['script', 'certificate', 'binary', 'config', 'data']},
                'prompts': [
                    'Create an Ansible action to copy a {file_type} file to target host',
                    'Ansible playbook that copies a {file_type} to a remote server with verification',
                ],
                'explanation': 'Ansible action that copies a {file_type} file to the target host with ownership, permissions, and verification.',
            },
            {
                'name': 'lineinfile-update',
                'template': {
                    'name': 'Update line in config file',
                    'action_type': 'ANSIBLE',
                    'code': (
                        '- name: Ensure line in {{input.file_path}}\n'
                        '  lineinfile:\n'
                        '    path: "{{input.file_path}}"\n'
                        '    regexp: "{{input.regexp}}"\n'
                        '    line: "{{input.line}}"\n'
                        '    state: present\n'
                        '    backup: yes\n'
                        '    create: yes\n'
                    ),
                    'schema': {
                        'input': {
                            'file_path': {'type': 'string', 'description': 'Path to file to modify'},
                            'regexp': {'type': 'string', 'description': 'Regex to match existing line'},
                            'line': {'type': 'string', 'description': 'Line content to ensure'},
                        },
                        'required': ['file_path', 'regexp', 'line'],
                    },
                },
                'params': {'config': ['sshd_config', 'sysctl.conf', 'limits.conf', 'sudoers', 'fstab']},
                'prompts': [
                    'Create an Ansible action to update a line in {config}',
                    'Ansible playbook that uses lineinfile to modify {config}',
                ],
                'explanation': 'Ansible action that uses lineinfile to ensure a specific line exists in {config} with regex matching and backup.',
            },
            {
                'name': 'blockinfile-insert',
                'template': {
                    'name': 'Insert config block',
                    'action_type': 'ANSIBLE',
                    'code': (
                        '- name: Insert config block in {{input.file_path}}\n'
                        '  blockinfile:\n'
                        '    path: "{{input.file_path}}"\n'
                        '    marker: "# {{mark}} ANSIBLE MANAGED BLOCK - {{input.block_name}}"\n'
                        '    block: "{{input.content}}"\n'
                        '    state: present\n'
                        '    backup: yes\n'
                        '    create: yes\n'
                    ),
                    'schema': {
                        'input': {
                            'file_path': {'type': 'string', 'description': 'Path to file'},
                            'block_name': {'type': 'string', 'description': 'Block identifier name'},
                            'content': {'type': 'string', 'description': 'Block content to insert'},
                        },
                        'required': ['file_path', 'block_name', 'content'],
                    },
                },
                'params': {'file_type': ['bashrc', 'profile', 'crontab', 'hosts', 'nginx-conf']},
                'prompts': [
                    'Create an Ansible action to insert a managed block in {file_type}',
                    'Ansible playbook that adds a marked configuration block to {file_type}',
                ],
                'explanation': 'Ansible action that inserts an Ansible-managed configuration block in {file_type} with markers for idempotent updates.',
            },
            {
                'name': 'file-permissions',
                'template': {
                    'name': 'Set file permissions',
                    'action_type': 'ANSIBLE',
                    'code': (
                        '- name: Set permissions on {{input.path}}\n'
                        '  file:\n'
                        '    path: "{{input.path}}"\n'
                        '    owner: "{{input.owner}}"\n'
                        '    group: "{{input.group}}"\n'
                        '    mode: "{{input.mode}}"\n'
                        '    recurse: "{{input.recurse}}"\n'
                        '\n'
                        '- name: Verify permissions\n'
                        '  stat:\n'
                        '    path: "{{input.path}}"\n'
                        '  register: perm_check\n'
                    ),
                    'schema': {
                        'input': {
                            'path': {'type': 'string', 'description': 'File or directory path'},
                            'owner': {'type': 'string', 'description': 'Owner username'},
                            'group': {'type': 'string', 'description': 'Group name'},
                            'mode': {'type': 'string', 'description': 'Permission mode (e.g. 0755)'},
                            'recurse': {'type': 'string', 'description': 'Recurse into directories: yes/no'},
                        },
                        'required': ['path', 'owner', 'mode'],
                    },
                },
                'params': {'target': ['app-directory', 'ssl-certs', 'log-directory', 'config-files', 'data-directory']},
                'prompts': [
                    'Create an Ansible action to set permissions on {target}',
                    'Ansible playbook that enforces ownership and permissions on {target}',
                ],
                'explanation': 'Ansible action that sets file ownership and permissions on {target} with optional recursive application.',
            },
            {
                'name': 'directory-creation',
                'template': {
                    'name': 'Create directory structure',
                    'action_type': 'ANSIBLE',
                    'code': (
                        '- name: Create directory {{input.path}}\n'
                        '  file:\n'
                        '    path: "{{input.path}}"\n'
                        '    state: directory\n'
                        '    owner: "{{input.owner}}"\n'
                        '    group: "{{input.group}}"\n'
                        '    mode: "{{input.mode}}"\n'
                        '\n'
                        '- name: Verify directory exists\n'
                        '  stat:\n'
                        '    path: "{{input.path}}"\n'
                        '  register: dir_check\n'
                        '  failed_when: not dir_check.stat.isdir\n'
                    ),
                    'schema': {
                        'input': {
                            'path': {'type': 'string', 'description': 'Directory path to create'},
                            'owner': {'type': 'string', 'description': 'Directory owner'},
                            'group': {'type': 'string', 'description': 'Directory group'},
                            'mode': {'type': 'string', 'description': 'Directory mode (default 0755)'},
                        },
                        'required': ['path'],
                    },
                },
                'params': {'purpose': ['application', 'logs', 'data', 'backups', 'tmp', 'configs']},
                'prompts': [
                    'Create an Ansible action to create a {purpose} directory structure',
                    'Ansible playbook that ensures {purpose} directories exist with proper permissions',
                ],
                'explanation': 'Ansible action that creates a {purpose} directory with specified ownership and permissions.',
            },
            {
                'name': 'archive-unarchive',
                'template': {
                    'name': 'Extract archive to target',
                    'action_type': 'ANSIBLE',
                    'code': (
                        '- name: Extract {{input.archive_src}} to target\n'
                        '  unarchive:\n'
                        '    src: "{{input.archive_src}}"\n'
                        '    dest: "{{input.dest_path}}"\n'
                        '    remote_src: "{{input.remote_src}}"\n'
                        '    owner: "{{input.owner}}"\n'
                        '    group: "{{input.group}}"\n'
                        '    creates: "{{input.creates}}"\n'
                    ),
                    'schema': {
                        'input': {
                            'archive_src': {'type': 'string', 'description': 'Archive source path or URL'},
                            'dest_path': {'type': 'string', 'description': 'Destination extraction directory'},
                            'remote_src': {'type': 'string', 'description': 'Archive is on remote: yes/no'},
                            'owner': {'type': 'string', 'description': 'Owner for extracted files'},
                            'group': {'type': 'string', 'description': 'Group for extracted files'},
                            'creates': {'type': 'string', 'description': 'Path that should exist after extraction (idempotency)'},
                        },
                        'required': ['archive_src', 'dest_path'],
                    },
                },
                'params': {'archive_type': ['tarball', 'zip', 'tgz', 'release', 'backup']},
                'prompts': [
                    'Create an Ansible action to extract a {archive_type} archive',
                    'Ansible playbook that unarchives a {archive_type} to a target directory',
                ],
                'explanation': 'Ansible action that extracts a {archive_type} archive to a destination directory with ownership and idempotency control.',
            },
            {
                'name': 'synchronize-files',
                'template': {
                    'name': 'Synchronize files to target',
                    'action_type': 'ANSIBLE',
                    'code': (
                        '- name: Synchronize {{input.src_path}} to target\n'
                        '  synchronize:\n'
                        '    src: "{{input.src_path}}"\n'
                        '    dest: "{{input.dest_path}}"\n'
                        '    delete: "{{input.delete_extra}}"\n'
                        '    recursive: yes\n'
                        '    rsync_opts:\n'
                        '      - "--exclude=.git"\n'
                        '      - "--exclude=*.pyc"\n'
                        '      - "--exclude=__pycache__"\n'
                    ),
                    'schema': {
                        'input': {
                            'src_path': {'type': 'string', 'description': 'Source directory path'},
                            'dest_path': {'type': 'string', 'description': 'Destination directory path'},
                            'delete_extra': {'type': 'string', 'description': 'Delete files not in source: yes/no'},
                        },
                        'required': ['src_path', 'dest_path'],
                    },
                },
                'params': {'sync_type': ['deployment', 'backup', 'mirror', 'replication']},
                'prompts': [
                    'Create an Ansible action to synchronize files for {sync_type}',
                    'Ansible playbook that uses rsync to perform a {sync_type} file sync',
                ],
                'explanation': 'Ansible action that synchronizes files for {sync_type} using rsync with common exclusions and optional deletion of extra files.',
            },
            {
                'name': 'ini-file-update',
                'template': {
                    'name': 'Update INI config file',
                    'action_type': 'ANSIBLE',
                    'code': (
                        '- name: Set {{input.option}} in {{input.section}} of {{input.file_path}}\n'
                        '  ini_file:\n'
                        '    path: "{{input.file_path}}"\n'
                        '    section: "{{input.section}}"\n'
                        '    option: "{{input.option}}"\n'
                        '    value: "{{input.value}}"\n'
                        '    backup: yes\n'
                        '    mode: "{{input.mode}}"\n'
                        '\n'
                        '- name: Verify INI file is valid\n'
                        '  stat:\n'
                        '    path: "{{input.file_path}}"\n'
                        '  register: ini_check\n'
                        '  failed_when: not ini_check.stat.exists\n'
                    ),
                    'schema': {
                        'input': {
                            'file_path': {'type': 'string', 'description': 'Path to the INI config file'},
                            'section': {'type': 'string', 'description': 'INI section name'},
                            'option': {'type': 'string', 'description': 'Option/key name within the section'},
                            'value': {'type': 'string', 'description': 'Value to set'},
                            'mode': {'type': 'string', 'description': 'File permissions (default 0644)'},
                        },
                        'required': ['file_path', 'section', 'option', 'value'],
                    },
                },
                'params': {'config': ['php.ini', 'my.cnf', 'grafana.ini', 'supervisord.conf', 'odoo.conf']},
                'prompts': [
                    'Create an Ansible action to update a setting in {config}',
                    'Ansible playbook that uses ini_file to modify {config} configuration',
                ],
                'explanation': 'Ansible action that uses the ini_file module to update a key-value pair in {config} with backup.',
            },
            {
                'name': 'xml-file-update',
                'template': {
                    'name': 'Update XML config file',
                    'action_type': 'ANSIBLE',
                    'code': (
                        '- name: Ensure python3-lxml is installed\n'
                        '  package:\n'
                        '    name: python3-lxml\n'
                        '    state: present\n'
                        '\n'
                        '- name: Update XML element in {{input.file_path}}\n'
                        '  xml:\n'
                        '    path: "{{input.file_path}}"\n'
                        '    xpath: "{{input.xpath}}"\n'
                        '    value: "{{input.value}}"\n'
                        '    backup: yes\n'
                        '\n'
                        '- name: Verify XML file is parseable\n'
                        '  command: "python3 -c \\"import xml.etree.ElementTree; xml.etree.ElementTree.parse(\'{{input.file_path}}\')\\""\n'
                        '  register: xml_check\n'
                        '  changed_when: false\n'
                    ),
                    'schema': {
                        'input': {
                            'file_path': {'type': 'string', 'description': 'Path to the XML file'},
                            'xpath': {'type': 'string', 'description': 'XPath expression to target element'},
                            'value': {'type': 'string', 'description': 'New value for the XML element'},
                        },
                        'required': ['file_path', 'xpath', 'value'],
                    },
                },
                'params': {'config': ['tomcat-server.xml', 'web.xml', 'pom.xml', 'logback.xml', 'beans.xml']},
                'prompts': [
                    'Create an Ansible action to update an XML element in {config}',
                    'Ansible playbook that modifies {config} using the xml module and XPath',
                ],
                'explanation': 'Ansible action that uses the xml module to update an element in {config} via XPath with backup and validation.',
            },
            {
                'name': 'json-patch-file',
                'template': {
                    'name': 'Patch JSON config file',
                    'action_type': 'ANSIBLE',
                    'code': (
                        '- name: Read current {{input.file_path}} content\n'
                        '  slurp:\n'
                        '    src: "{{input.file_path}}"\n'
                        '  register: json_content\n'
                        '\n'
                        '- name: Parse and patch JSON\n'
                        '  set_fact:\n'
                        '    json_data: "{{ json_content.content | b64decode | from_json | combine(input.patch_data | from_json, recursive=True) }}"\n'
                        '\n'
                        '- name: Write patched JSON to {{input.file_path}}\n'
                        '  copy:\n'
                        '    content: "{{ json_data | to_nice_json }}"\n'
                        '    dest: "{{input.file_path}}"\n'
                        '    backup: yes\n'
                        '    mode: "{{input.mode}}"\n'
                        '\n'
                        '- name: Validate JSON syntax\n'
                        '  command: "python3 -c \\"import json; json.load(open(\'{{input.file_path}}\')); print(\'Valid JSON\')\\""\n'
                        '  register: json_check\n'
                        '  changed_when: false\n'
                    ),
                    'schema': {
                        'input': {
                            'file_path': {'type': 'string', 'description': 'Path to the JSON file to patch'},
                            'patch_data': {'type': 'string', 'description': 'JSON string with keys to merge/update'},
                            'mode': {'type': 'string', 'description': 'File permissions (default 0644)'},
                        },
                        'required': ['file_path', 'patch_data'],
                    },
                },
                'params': {'config': ['config.json', 'package.json', 'settings.json', 'tsconfig.json', 'manifest.json']},
                'prompts': [
                    'Create an Ansible action to patch a {config} file with new values',
                    'Ansible playbook that merges updates into a {config} JSON file',
                ],
                'explanation': 'Ansible action that reads, patches, and writes a {config} JSON file using recursive merge with backup and validation.',
            },
            {
                'name': 'recursive-permission-set',
                'template': {
                    'name': 'Set recursive permissions on directory',
                    'action_type': 'ANSIBLE',
                    'code': (
                        '- name: Set directory permissions on {{input.path}}\n'
                        '  file:\n'
                        '    path: "{{input.path}}"\n'
                        '    state: directory\n'
                        '    owner: "{{input.owner}}"\n'
                        '    group: "{{input.group}}"\n'
                        '    mode: "{{input.dir_mode}}"\n'
                        '\n'
                        '- name: Set file permissions recursively under {{input.path}}\n'
                        '  command: "find {{input.path}} -type f -exec chmod {{input.file_mode}} {} +"\n'
                        '  register: file_perms\n'
                        '\n'
                        '- name: Set directory permissions recursively under {{input.path}}\n'
                        '  command: "find {{input.path}} -type d -exec chmod {{input.dir_mode}} {} +"\n'
                        '  register: dir_perms\n'
                        '\n'
                        '- name: Set ownership recursively on {{input.path}}\n'
                        '  file:\n'
                        '    path: "{{input.path}}"\n'
                        '    owner: "{{input.owner}}"\n'
                        '    group: "{{input.group}}"\n'
                        '    recurse: yes\n'
                    ),
                    'schema': {
                        'input': {
                            'path': {'type': 'string', 'description': 'Root directory path'},
                            'owner': {'type': 'string', 'description': 'Owner username'},
                            'group': {'type': 'string', 'description': 'Group name'},
                            'file_mode': {'type': 'string', 'description': 'Permission mode for files (e.g. 0644)'},
                            'dir_mode': {'type': 'string', 'description': 'Permission mode for directories (e.g. 0755)'},
                        },
                        'required': ['path', 'owner', 'file_mode', 'dir_mode'],
                    },
                },
                'params': {'target': ['web-root', 'app-directory', 'data-directory', 'upload-directory', 'log-directory']},
                'prompts': [
                    'Create an Ansible action to set recursive permissions on a {target}',
                    'Ansible playbook that applies different file and directory permissions to a {target}',
                ],
                'explanation': 'Ansible action that sets different permissions for files and directories recursively within a {target} with ownership enforcement.',
            },
        ]


def get_generators():
    return [FilesTemplatesGenerator()]
