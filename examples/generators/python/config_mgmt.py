"""Configuration management Python action generators - 5 seeds for templating, diffing, validating."""

from examples.generators.base_generator import PythonActionGenerator


class ConfigMgmtGenerator(PythonActionGenerator):
    category = "python.config_mgmt"
    subcategory = "config_mgmt"

    def seeds(self):
        return [
            {
                'name': 'config-from-template',
                'template': {
                    'name': 'Generate {service} config',
                    'action_type': 'PYTHON',
                    'code': (
                        'import json\n'
                        'import re\n'
                        'import sys\n\n'
                        'template_str = \'{{input.template}}\'\n'
                        'vars_json = \'{{input.variables}}\'\n'
                        'output_path = "{{input.output_path}}"\n\n'
                        'try:\n'
                        '    variables = json.loads(vars_json)\n'
                        '    def replacer(match):\n'
                        '        key = match.group(1).strip()\n'
                        '        return str(variables.get(key, match.group(0)))\n'
                        '    rendered = re.sub(r"\\{\\{\\s*(\\w+)\\s*\\}\\}", replacer, template_str)\n'
                        '    with open(output_path, "w") as f:\n'
                        '        f.write(rendered)\n'
                        '    print(json.dumps({{\n'
                        '        "status": "ok",\n'
                        '        "output": output_path,\n'
                        '        "vars_applied": len(variables),\n'
                        '    }}))\n'
                        'except Exception as e:\n'
                        '    print(json.dumps({{"status": "error", "message": str(e)}}))\n'
                        '    sys.exit(1)\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'template': {'type': 'string', 'description': 'Config template string with {{ var }} placeholders'},
                            'variables': {'type': 'string', 'description': 'JSON string of template variables'},
                            'output_path': {'type': 'string', 'description': 'Output file path for rendered config'},
                        },
                        'required': ['template', 'variables', 'output_path'],
                    },
                },
                'params': {'service': ['nginx', 'haproxy', 'prometheus', 'grafana', 'traefik']},
                'prompts': [
                    'Create a Python action to generate a {service} config from a dict template',
                    'Python script that renders a {service} configuration from template variables',
                ],
                'explanation': 'Python action that generates a {service} configuration file by rendering a template with variable substitution.',
            },
            {
                'name': 'config-diff',
                'template': {
                    'name': 'Diff {service} configs',
                    'action_type': 'PYTHON',
                    'code': (
                        'import json\n'
                        'import difflib\n'
                        'import sys\n\n'
                        'current_path = "{{input.current_path}}"\n'
                        'desired_path = "{{input.desired_path}}"\n\n'
                        'try:\n'
                        '    with open(current_path, "r") as f:\n'
                        '        current = f.readlines()\n'
                        '    with open(desired_path, "r") as f:\n'
                        '        desired = f.readlines()\n'
                        '    diff = list(difflib.unified_diff(current, desired, fromfile="current", tofile="desired", lineterm=""))\n'
                        '    added = sum(1 for l in diff if l.startswith("+") and not l.startswith("+++"))\n'
                        '    removed = sum(1 for l in diff if l.startswith("-") and not l.startswith("---"))\n'
                        '    has_changes = len(diff) > 0\n'
                        '    print(json.dumps({{\n'
                        '        "status": "changed" if has_changes else "identical",\n'
                        '        "lines_added": added,\n'
                        '        "lines_removed": removed,\n'
                        '        "diff_preview": "\\n".join(diff[:30]),\n'
                        '    }}))\n'
                        'except Exception as e:\n'
                        '    print(json.dumps({{"status": "error", "message": str(e)}}))\n'
                        '    sys.exit(1)\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'current_path': {'type': 'string', 'description': 'Path to current config file'},
                            'desired_path': {'type': 'string', 'description': 'Path to desired config file'},
                        },
                        'required': ['current_path', 'desired_path'],
                    },
                },
                'params': {'service': ['nginx', 'sshd', 'apache', 'postfix', 'sudoers']},
                'prompts': [
                    'Create a Python action to diff current vs desired {service} config',
                    'Python script that compares the running {service} config against the desired state',
                ],
                'explanation': 'Python action that diffs the current {service} configuration against the desired state, reporting changes.',
            },
            {
                'name': 'validate-syntax',
                'template': {
                    'name': 'Validate {format} syntax',
                    'action_type': 'PYTHON',
                    'code': (
                        'import json\n'
                        'import re\n'
                        'import sys\n\n'
                        'file_path = "{{input.file_path}}"\n'
                        'file_format = "{{input.format}}" or "json"\n\n'
                        'try:\n'
                        '    with open(file_path, "r") as f:\n'
                        '        content = f.read()\n'
                        '    if file_format == "json":\n'
                        '        json.loads(content)\n'
                        '        print(json.dumps({{"status": "valid", "format": "json", "file": file_path}}))\n'
                        '    elif file_format == "yaml":\n'
                        '        lines = content.splitlines()\n'
                        '        errors = []\n'
                        '        for i, line in enumerate(lines, 1):\n'
                        '            stripped = line.strip()\n'
                        '            if stripped and not stripped.startswith("#"):\n'
                        '                if "\\t" in line:\n'
                        '                    errors.append(f"Line {{i}}: tab character found")\n'
                        '        if errors:\n'
                        '            print(json.dumps({{"status": "invalid", "format": "yaml", "errors": errors}}))\n'
                        '            sys.exit(1)\n'
                        '        print(json.dumps({{"status": "valid", "format": "yaml", "file": file_path}}))\n'
                        '    else:\n'
                        '        print(json.dumps({{"status": "error", "message": f"Unknown format: {{file_format}}"}}))\n'
                        '        sys.exit(1)\n'
                        'except json.JSONDecodeError as e:\n'
                        '    print(json.dumps({{"status": "invalid", "format": "json", "error": str(e)}}))\n'
                        '    sys.exit(1)\n'
                        'except Exception as e:\n'
                        '    print(json.dumps({{"status": "error", "message": str(e)}}))\n'
                        '    sys.exit(1)\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'file_path': {'type': 'string', 'description': 'Path to configuration file to validate'},
                            'format': {'type': 'string', 'description': 'File format: json or yaml (default json)'},
                        },
                        'required': ['file_path'],
                    },
                },
                'params': {'format': ['json', 'yaml']},
                'prompts': [
                    'Create a Python action to validate {format} config syntax',
                    'Python script that checks a {format} configuration file for syntax errors',
                ],
                'explanation': 'Python action that validates {format} configuration file syntax, reporting any parse errors.',
            },
            {
                'name': 'backup-config',
                'template': {
                    'name': 'Backup {service} config file',
                    'action_type': 'PYTHON',
                    'code': (
                        'import json\n'
                        'import os\n'
                        'import shutil\n'
                        'import sys\n'
                        'from datetime import datetime, timezone\n\n'
                        'config_path = "{{input.config_path}}"\n'
                        'backup_dir = "{{input.backup_dir}}" or "/tmp/config_backups"\n'
                        'max_backups = int("{{input.max_backups}}" or "10")\n\n'
                        'if not os.path.isfile(config_path):\n'
                        '    print(json.dumps({{"status": "error", "message": f"Config not found: {{config_path}}"}}))\n'
                        '    sys.exit(1)\n\n'
                        'os.makedirs(backup_dir, exist_ok=True)\n'
                        'ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")\n'
                        'filename = os.path.basename(config_path)\n'
                        'backup_path = os.path.join(backup_dir, f"{{filename}}.{{ts}}.bak")\n'
                        'shutil.copy2(config_path, backup_path)\n\n'
                        'backups = sorted(\n'
                        '    [f for f in os.listdir(backup_dir) if f.startswith(filename) and f.endswith(".bak")],\n'
                        '    reverse=True,\n'
                        ')\n'
                        'removed = []\n'
                        'for old in backups[max_backups:]:\n'
                        '    os.remove(os.path.join(backup_dir, old))\n'
                        '    removed.append(old)\n\n'
                        'print(json.dumps({{\n'
                        '    "status": "backed_up",\n'
                        '    "source": config_path,\n'
                        '    "backup": backup_path,\n'
                        '    "size_bytes": os.path.getsize(backup_path),\n'
                        '    "pruned": len(removed),\n'
                        '}}))\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'config_path': {'type': 'string', 'description': 'Path to config file to back up'},
                            'backup_dir': {'type': 'string', 'description': 'Directory to store backups (default /tmp/config_backups)'},
                            'max_backups': {'type': 'string', 'description': 'Max backups to keep (default 10)'},
                        },
                        'required': ['config_path'],
                    },
                },
                'params': {'service': ['nginx', 'haproxy', 'sshd', 'postgres', 'redis']},
                'prompts': [
                    'Create a Python action to backup a {service} config file with rotation',
                    'Python script that creates timestamped backups of {service} config with pruning',
                ],
                'explanation': 'Python action that creates a timestamped backup of the {service} config file and prunes old backups.',
            },
            {
                'name': 'config-rollback',
                'template': {
                    'name': 'Rollback {service} config',
                    'action_type': 'PYTHON',
                    'code': (
                        'import json\n'
                        'import os\n'
                        'import shutil\n'
                        'import sys\n\n'
                        'config_path = "{{input.config_path}}"\n'
                        'backup_dir = "{{input.backup_dir}}" or "/tmp/config_backups"\n'
                        'version = "{{input.version}}" or "latest"\n\n'
                        'filename = os.path.basename(config_path)\n'
                        'backups = sorted(\n'
                        '    [f for f in os.listdir(backup_dir) if f.startswith(filename) and f.endswith(".bak")],\n'
                        '    reverse=True,\n'
                        ')\n\n'
                        'if not backups:\n'
                        '    print(json.dumps({{"status": "error", "message": "No backups found"}}))\n'
                        '    sys.exit(1)\n\n'
                        'if version == "latest":\n'
                        '    restore_file = backups[0]\n'
                        'else:\n'
                        '    restore_file = next((b for b in backups if version in b), None)\n'
                        '    if not restore_file:\n'
                        '        print(json.dumps({{"status": "error", "message": f"Backup version {{version}} not found"}}))\n'
                        '        sys.exit(1)\n\n'
                        'restore_path = os.path.join(backup_dir, restore_file)\n'
                        'shutil.copy2(restore_path, config_path)\n\n'
                        'print(json.dumps({{\n'
                        '    "status": "rolled_back",\n'
                        '    "config": config_path,\n'
                        '    "restored_from": restore_file,\n'
                        '    "size_bytes": os.path.getsize(config_path),\n'
                        '}}))\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'config_path': {'type': 'string', 'description': 'Path to config file to restore'},
                            'backup_dir': {'type': 'string', 'description': 'Directory containing backups'},
                            'version': {'type': 'string', 'description': 'Backup version to restore (default latest)'},
                        },
                        'required': ['config_path'],
                    },
                },
                'params': {'service': ['nginx', 'haproxy', 'sshd', 'postgres', 'redis']},
                'prompts': [
                    'Create a Python action to rollback {service} config from backup',
                    'Python script that restores a {service} config file from a previous backup',
                ],
                'explanation': 'Python action that rolls back the {service} configuration by restoring from a backup version.',
            },
        ]


def get_generators():
    return [ConfigMgmtGenerator()]
