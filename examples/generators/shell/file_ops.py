"""Shell action generators for file operations."""

from examples.generators.base_generator import ShellActionGenerator


class FileOpsGenerator(ShellActionGenerator):
    category = "shell.file_ops"
    subcategory = "file_ops"

    def seeds(self):
        return [
            {
                'name': 'cp-with-perms',
                'template': {
                    'name': 'cp-preserve-{target}',
                    'action_type': 'SHELL',
                    'code': 'if [ ! -e "{{input.source}}" ]; then echo "Source not found: {{input.source}}" >&2; exit 1; fi && cp -a "{{input.source}}" "{{input.destination}}" && echo "Copied {{input.source}} -> {{input.destination}} (permissions preserved)" && ls -la "{{input.destination}}"',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'source': {'type': 'string', 'description': 'Source file or directory path'},
                            'destination': {'type': 'string', 'description': 'Destination path'},
                        },
                        'required': ['source', 'destination'],
                    },
                },
                'params': {'target': ['config', 'data', 'backup', 'archive']},
                'prompts': [
                    'Copy {target} files preserving permissions',
                    'Create a DM action to cp {target} files with attributes intact',
                    'Write a shell action to copy {target} files preserving ownership and permissions',
                ],
                'explanation': 'Copies {target} files while preserving all file attributes including permissions, ownership, and timestamps.',
                'features': ['schema_variables'],
            },
            {
                'name': 'mv-with-backup',
                'template': {
                    'name': 'mv-backup-{target}',
                    'action_type': 'SHELL',
                    'code': 'if [ ! -e "{{input.source}}" ]; then echo "Source not found" >&2; exit 1; fi && if [ -e "{{input.destination}}" ]; then BACKUP="{{input.destination}}.bak.$(date +%%Y%%m%%d%%H%%M%%S)" && cp -a "{{input.destination}}" "$BACKUP" && echo "Backup created: $BACKUP"; fi && mv "{{input.source}}" "{{input.destination}}" && echo "Moved {{input.source}} -> {{input.destination}}"',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'source': {'type': 'string', 'description': 'Source file path'},
                            'destination': {'type': 'string', 'description': 'Destination file path'},
                        },
                        'required': ['source', 'destination'],
                    },
                },
                'params': {'target': ['config', 'data', 'log', 'certificate']},
                'prompts': [
                    'Move a {target} file with automatic backup of the destination',
                    'Create a DM action to safely move {target} files with backup',
                    'Write a shell action to mv {target} files creating a timestamped backup first',
                ],
                'explanation': 'Moves {target} files, automatically creating a timestamped backup if the destination already exists.',
                'features': ['schema_variables'],
            },
            {
                'name': 'sed-inplace',
                'template': {
                    'name': 'sed-edit-{target}',
                    'action_type': 'SHELL',
                    'code': 'if [ ! -f "{{input.file_path}}" ]; then echo "File not found" >&2; exit 1; fi && cp "{{input.file_path}}" "{{input.file_path}}.bak" && sed -i "s|{{input.search_pattern}}|{{input.replacement}}|g" "{{input.file_path}}" && CHANGES=$(diff "{{input.file_path}}.bak" "{{input.file_path}}" | wc -l) && echo "Applied $CHANGES line changes to {{input.file_path}}"',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'file_path': {'type': 'string', 'description': 'Path to the file to edit'},
                            'search_pattern': {'type': 'string', 'description': 'Pattern to search for (sed compatible)'},
                            'replacement': {'type': 'string', 'description': 'Replacement string'},
                        },
                        'required': ['file_path', 'search_pattern', 'replacement'],
                    },
                },
                'params': {'target': ['config', 'properties', 'ini', 'yaml']},
                'prompts': [
                    'Edit a {target} file in-place using sed',
                    'Create a DM action to find-and-replace in a {target} file',
                    'Write a shell action for in-place editing of {target} files with backup',
                ],
                'explanation': 'Performs in-place find-and-replace in a {target} file using sed, with automatic backup.',
                'features': ['schema_variables'],
            },
            {
                'name': 'config-template',
                'template': {
                    'name': 'envsubst-{target}',
                    'action_type': 'SHELL',
                    'code': 'if [ ! -f "{{input.template_file}}" ]; then echo "Template not found" >&2; exit 1; fi && export APP_NAME="{{input.app_name}}" APP_PORT="{{input.app_port}}" APP_ENV="{{input.app_env}}" && envsubst < "{{input.template_file}}" > "{{input.output_file}}" && echo "Config generated: {{input.output_file}}" && wc -l "{{input.output_file}}"',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'template_file': {'type': 'string', 'description': 'Path to the template file with $VAR placeholders'},
                            'output_file': {'type': 'string', 'description': 'Path for the generated config output'},
                            'app_name': {'type': 'string', 'description': 'Application name to substitute'},
                            'app_port': {'type': 'string', 'description': 'Application port to substitute'},
                            'app_env': {'type': 'string', 'description': 'Environment name to substitute'},
                        },
                        'required': ['template_file', 'output_file', 'app_name', 'app_port', 'app_env'],
                    },
                },
                'params': {'target': ['nginx', 'app', 'haproxy', 'systemd']},
                'prompts': [
                    'Generate a {target} config from a template using envsubst',
                    'Create a DM action to render a {target} config template',
                    'Write a shell action to populate a {target} config from environment variables',
                ],
                'explanation': 'Generates a {target} configuration file from a template using envsubst for variable substitution.',
                'features': ['schema_variables'],
                'difficulty': 'intermediate',
            },
            {
                'name': 'symlink-manage',
                'template': {
                    'name': 'symlink-{action}',
                    'action_type': 'SHELL',
                    'code': 'if [ ! -e "{{input.target}}" ]; then echo "Target does not exist: {{input.target}}" >&2; exit 1; fi && if [ -L "{{input.link_path}}" ]; then rm "{{input.link_path}}"; echo "Removed existing symlink"; fi && ln -s "{{input.target}}" "{{input.link_path}}" && echo "Symlink created: {{input.link_path}} -> {{input.target}}" && ls -la "{{input.link_path}}"',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'target': {'type': 'string', 'description': 'Target path the symlink points to'},
                            'link_path': {'type': 'string', 'description': 'Path for the symbolic link'},
                        },
                        'required': ['target', 'link_path'],
                    },
                },
                'params': {'action': ['create', 'update', 'replace']},
                'prompts': [
                    '{action} a symbolic link',
                    'Create a DM action to {action} a symlink',
                    'Write a shell action to {action} a symbolic link safely',
                ],
                'explanation': 'Creates or replaces a symbolic link ({action} operation), removing any existing symlink first.',
                'features': ['schema_variables'],
            },
            {
                'name': 'find-delete-old',
                'template': {
                    'name': 'cleanup-old-{target}',
                    'action_type': 'SHELL',
                    'code': 'if [ ! -d "{{input.directory}}" ]; then echo "Directory not found" >&2; exit 1; fi && COUNT=$(find "{{input.directory}}" -name "{{input.pattern}}" -type f -mtime +{{input.days_old}} | wc -l) && echo "Found $COUNT files older than {{input.days_old}} days" && find "{{input.directory}}" -name "{{input.pattern}}" -type f -mtime +{{input.days_old}} -delete && echo "Cleanup complete: $COUNT files removed"',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'directory': {'type': 'string', 'description': 'Directory to search in'},
                            'pattern': {'type': 'string', 'description': 'File name pattern (e.g. *.log, *.tmp)'},
                            'days_old': {'type': 'integer', 'description': 'Delete files older than this many days'},
                        },
                        'required': ['directory', 'pattern', 'days_old'],
                    },
                },
                'params': {'target': ['logs', 'temp-files', 'backups', 'cache']},
                'prompts': [
                    'Find and delete old {target} files',
                    'Create a DM action to clean up {target} older than N days',
                    'Write a shell action to remove stale {target} by age',
                ],
                'explanation': 'Finds and deletes {target} files older than a specified number of days.',
                'features': ['schema_variables'],
            },
            {
                'name': 'tar-create-extract',
                'template': {
                    'name': 'tar-{action}',
                    'action_type': 'SHELL',
                    'code': 'if [ "{{input.action}}" = "create" ]; then tar -czf "{{input.archive_path}}" -C "$(dirname {{input.source_path}})" "$(basename {{input.source_path}})" && echo "Archive created: {{input.archive_path}}" && ls -lh "{{input.archive_path}}"; elif [ "{{input.action}}" = "extract" ]; then mkdir -p "{{input.dest_path}}" && tar -xzf "{{input.archive_path}}" -C "{{input.dest_path}}" && echo "Extracted to: {{input.dest_path}}" && ls -la "{{input.dest_path}}"; fi',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'action': {'type': 'string', 'description': 'Action to perform: create or extract'},
                            'archive_path': {'type': 'string', 'description': 'Path to the tar.gz archive'},
                            'source_path': {'type': 'string', 'description': 'Source path for create (directory or file)'},
                            'dest_path': {'type': 'string', 'description': 'Destination path for extract'},
                        },
                        'required': ['action', 'archive_path'],
                    },
                },
                'params': {'action': ['create', 'extract']},
                'prompts': [
                    '{action} a tar.gz archive',
                    'Create a DM action to {action} a compressed tar archive',
                    'Write a shell action to {action} a tar.gz file',
                ],
                'explanation': 'Performs tar archive {action} operation with gzip compression.',
                'features': ['schema_variables'],
            },
            {
                'name': 'rsync-local',
                'template': {
                    'name': 'rsync-{sync_type}',
                    'action_type': 'SHELL',
                    'code': 'if [ ! -d "{{input.source}}" ]; then echo "Source directory not found" >&2; exit 1; fi && rsync -avh --progress --delete {{input.exclude_flags}} "{{input.source}}/" "{{input.destination}}/" 2>&1 && echo "Sync complete: {{input.source}} -> {{input.destination}}"',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'source': {'type': 'string', 'description': 'Source directory path'},
                            'destination': {'type': 'string', 'description': 'Destination directory path'},
                            'exclude_flags': {'type': 'string', 'description': 'Exclude flags (e.g. --exclude=*.log --exclude=.git)'},
                        },
                        'required': ['source', 'destination'],
                    },
                },
                'params': {'sync_type': ['mirror', 'backup', 'deploy']},
                'prompts': [
                    'Rsync {sync_type} a directory locally',
                    'Create a DM action to {sync_type} files using rsync',
                    'Write a shell action for local rsync {sync_type} with delete',
                ],
                'explanation': 'Synchronizes directories locally using rsync with {sync_type} semantics, including delete to mirror source.',
                'features': ['schema_variables'],
            },
            {
                'name': 'file-integrity',
                'template': {
                    'name': 'sha256-verify-{target}',
                    'action_type': 'SHELL',
                    'code': 'if [ ! -f "{{input.file_path}}" ]; then echo "File not found" >&2; exit 1; fi && ACTUAL=$(sha256sum "{{input.file_path}}" | awk \'{{print $1}}\') && if [ "$ACTUAL" = "{{input.expected_hash}}" ]; then echo "PASS: Checksum matches"; echo "SHA256: $ACTUAL"; exit 0; else echo "FAIL: Checksum mismatch" >&2; echo "Expected: {{input.expected_hash}}" >&2; echo "Actual:   $ACTUAL" >&2; exit 1; fi',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'file_path': {'type': 'string', 'description': 'Path to the file to verify'},
                            'expected_hash': {'type': 'string', 'description': 'Expected SHA256 hash'},
                        },
                        'required': ['file_path', 'expected_hash'],
                    },
                },
                'params': {'target': ['binary', 'config', 'download', 'package']},
                'prompts': [
                    'Verify SHA256 integrity of a {target} file',
                    'Create a DM action to check {target} file SHA256 hash',
                    'Write a shell action to validate {target} integrity with sha256sum',
                ],
                'explanation': 'Verifies the SHA256 checksum of a {target} file against an expected hash value.',
                'features': ['schema_variables'],
            },
            {
                'name': 'dir-structure',
                'template': {
                    'name': 'create-dirs-{project}',
                    'action_type': 'SHELL',
                    'code': 'BASE="{{input.base_path}}" && mkdir -p "$BASE"/{{{input.subdirs}}} && chown -R {{input.owner}}:{{input.group}} "$BASE" && chmod -R {{input.mode}} "$BASE" && echo "Directory structure created under $BASE:" && find "$BASE" -type d | head -20',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'base_path': {'type': 'string', 'description': 'Base directory path'},
                            'subdirs': {'type': 'string', 'description': 'Comma-separated subdirectories (e.g. src,bin,conf,logs,data)'},
                            'owner': {'type': 'string', 'description': 'Owner user'},
                            'group': {'type': 'string', 'description': 'Owner group'},
                            'mode': {'type': 'string', 'description': 'Directory mode (e.g. 755)'},
                        },
                        'required': ['base_path', 'subdirs', 'owner', 'group', 'mode'],
                    },
                },
                'params': {'project': ['app', 'service', 'deployment', 'workspace']},
                'prompts': [
                    'Create a standard {project} directory structure',
                    'Create a DM action to scaffold {project} directories',
                    'Write a shell action to initialize {project} directory layout',
                ],
                'explanation': 'Creates a standardized {project} directory structure with proper ownership and permissions.',
                'features': ['schema_variables'],
            },
        ]


def get_generators():
    return [FileOpsGenerator()]
