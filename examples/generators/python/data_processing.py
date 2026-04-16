"""Data processing Python action generators - 10 seeds for parsing, transforming, validating data."""

from examples.generators.base_generator import PythonActionGenerator


class DataProcessingGenerator(PythonActionGenerator):
    category = "python.data_processing"
    subcategory = "data_processing"

    def seeds(self):
        return [
            {
                'name': 'parse-json-config',
                'template': {
                    'name': 'Parse JSON config for {service}',
                    'action_type': 'PYTHON',
                    'code': (
                        'import json\n'
                        'import sys\n\n'
                        'config_path = "{{input.config_path}}"\n'
                        'key_path = "{{input.key_path}}"\n\n'
                        'try:\n'
                        '    with open(config_path, "r") as f:\n'
                        '        config = json.load(f)\n\n'
                        '    # Navigate nested keys via dot notation\n'
                        '    value = config\n'
                        '    if key_path:\n'
                        '        for key in key_path.split("."):\n'
                        '            if isinstance(value, dict):\n'
                        '                value = value[key]\n'
                        '            elif isinstance(value, list):\n'
                        '                value = value[int(key)]\n'
                        '            else:\n'
                        '                raise KeyError(f"Cannot traverse into {{type(value).__name__}}")\n\n'
                        '    print(json.dumps({{"status": "ok", "key": key_path, "value": value}}))\n'
                        'except FileNotFoundError:\n'
                        '    print(json.dumps({{"status": "error", "message": f"File not found: {{config_path}}"}}))\n'
                        '    sys.exit(1)\n'
                        'except (KeyError, IndexError) as e:\n'
                        '    print(json.dumps({{"status": "error", "message": f"Key not found: {{e}}"}}))\n'
                        '    sys.exit(1)\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'config_path': {'type': 'string', 'description': 'Path to JSON config file'},
                            'key_path': {'type': 'string', 'description': 'Dot-notation path to key (e.g. database.host)'},
                        },
                        'required': ['config_path'],
                    },
                },
                'params': {'service': ['nginx', 'docker', 'terraform', 'kubernetes', 'consul']},
                'prompts': [
                    'Create a Python action to parse a {service} JSON config and extract a value',
                    'Python script that reads a {service} JSON config file and navigates to a nested key',
                ],
                'explanation': 'Python action that parses a {service} JSON configuration file and extracts a value at a specified dot-notation key path.',
            },
            {
                'name': 'merge-yaml-files',
                'template': {
                    'name': 'Merge YAML config files',
                    'action_type': 'PYTHON',
                    'code': (
                        'import json\n'
                        'import sys\n'
                        'import re\n\n'
                        'def simple_yaml_parse(text):\n'
                        '    """Minimal YAML parser for flat and one-level nested key-value pairs."""\n'
                        '    result = {{}}\n'
                        '    current_key = None\n'
                        '    for line in text.splitlines():\n'
                        '        stripped = line.strip()\n'
                        '        if not stripped or stripped.startswith("#"):\n'
                        '            continue\n'
                        '        indent = len(line) - len(line.lstrip())\n'
                        '        match = re.match(r"^(\\w[\\w.-]*):\\s*(.*)", stripped)\n'
                        '        if match:\n'
                        '            key, val = match.group(1), match.group(2).strip()\n'
                        '            if indent == 0:\n'
                        '                if val:\n'
                        '                    result[key] = val\n'
                        '                else:\n'
                        '                    result[key] = {{}}\n'
                        '                    current_key = key\n'
                        '            elif current_key:\n'
                        '                result[current_key][key] = val\n'
                        '    return result\n\n'
                        'def deep_merge(base, override):\n'
                        '    merged = dict(base)\n'
                        '    for k, v in override.items():\n'
                        '        if k in merged and isinstance(merged[k], dict) and isinstance(v, dict):\n'
                        '            merged[k] = deep_merge(merged[k], v)\n'
                        '        else:\n'
                        '            merged[k] = v\n'
                        '    return merged\n\n'
                        'base_path = "{{input.base_file}}"\n'
                        'override_path = "{{input.override_file}}"\n'
                        'output_path = "{{input.output_file}}"\n\n'
                        'try:\n'
                        '    with open(base_path) as f:\n'
                        '        base = simple_yaml_parse(f.read())\n'
                        '    with open(override_path) as f:\n'
                        '        override = simple_yaml_parse(f.read())\n'
                        '    merged = deep_merge(base, override)\n'
                        '    with open(output_path, "w") as f:\n'
                        '        for k, v in merged.items():\n'
                        '            if isinstance(v, dict):\n'
                        '                f.write(f"{{k}}:\\n")\n'
                        '                for sk, sv in v.items():\n'
                        '                    f.write(f"  {{sk}}: {{sv}}\\n")\n'
                        '            else:\n'
                        '                f.write(f"{{k}}: {{v}}\\n")\n'
                        '    print(json.dumps({{"status": "merged", "output": output_path, "keys": len(merged)}}))\n'
                        'except Exception as e:\n'
                        '    print(json.dumps({{"status": "error", "message": str(e)}}))\n'
                        '    sys.exit(1)\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'base_file': {'type': 'string', 'description': 'Path to base YAML file'},
                            'override_file': {'type': 'string', 'description': 'Path to override YAML file'},
                            'output_file': {'type': 'string', 'description': 'Path for merged output'},
                        },
                        'required': ['base_file', 'override_file', 'output_file'],
                    },
                },
                'params': {'config_type': ['application', 'infrastructure', 'deployment', 'pipeline']},
                'prompts': [
                    'Create a Python action to merge two {config_type} YAML config files',
                    'Python script that deep-merges a base and override {config_type} YAML file',
                ],
                'explanation': 'Python action that deep-merges two {config_type} YAML configuration files, with the override file taking precedence.',
            },
            {
                'name': 'csv-to-json',
                'template': {
                    'name': 'Transform CSV to JSON',
                    'action_type': 'PYTHON',
                    'code': (
                        'import csv\n'
                        'import json\n'
                        'import sys\n\n'
                        'csv_path = "{{input.csv_path}}"\n'
                        'json_path = "{{input.json_path}}"\n'
                        'delimiter = "{{input.delimiter}}" or ","\n\n'
                        'try:\n'
                        '    records = []\n'
                        '    with open(csv_path, "r", newline="") as f:\n'
                        '        reader = csv.DictReader(f, delimiter=delimiter)\n'
                        '        for row in reader:\n'
                        '            records.append(dict(row))\n\n'
                        '    with open(json_path, "w") as f:\n'
                        '        json.dump(records, f, indent=2)\n\n'
                        '    print(json.dumps({{"status": "converted", "records": len(records), "output": json_path}}))\n'
                        'except Exception as e:\n'
                        '    print(json.dumps({{"status": "error", "message": str(e)}}))\n'
                        '    sys.exit(1)\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'csv_path': {'type': 'string', 'description': 'Path to input CSV file'},
                            'json_path': {'type': 'string', 'description': 'Path for output JSON file'},
                            'delimiter': {'type': 'string', 'description': 'CSV delimiter (default comma)'},
                        },
                        'required': ['csv_path', 'json_path'],
                    },
                },
                'params': {'data_type': ['inventory', 'metrics', 'users', 'hosts', 'assets']},
                'prompts': [
                    'Create a Python action to convert a {data_type} CSV file to JSON',
                    'Python script that transforms {data_type} data from CSV to JSON format',
                ],
                'explanation': 'Python action that reads a {data_type} CSV file and converts it to JSON format.',
            },
            {
                'name': 'xml-parse',
                'template': {
                    'name': 'Parse XML document',
                    'action_type': 'PYTHON',
                    'code': (
                        'import json\n'
                        'import sys\n'
                        'import xml.etree.ElementTree as ET\n\n'
                        'xml_path = "{{input.xml_path}}"\n'
                        'xpath = "{{input.xpath}}"\n\n'
                        'def element_to_dict(elem):\n'
                        '    result = {{"tag": elem.tag, "attributes": dict(elem.attrib)}}\n'
                        '    text = (elem.text or "").strip()\n'
                        '    if text:\n'
                        '        result["text"] = text\n'
                        '    children = [element_to_dict(child) for child in elem]\n'
                        '    if children:\n'
                        '        result["children"] = children\n'
                        '    return result\n\n'
                        'try:\n'
                        '    tree = ET.parse(xml_path)\n'
                        '    root = tree.getroot()\n'
                        '    if xpath:\n'
                        '        elements = root.findall(xpath)\n'
                        '        results = [element_to_dict(e) for e in elements]\n'
                        '    else:\n'
                        '        results = [element_to_dict(root)]\n'
                        '    print(json.dumps({{"status": "ok", "count": len(results), "elements": results}}))\n'
                        'except ET.ParseError as e:\n'
                        '    print(json.dumps({{"status": "error", "message": f"XML parse error: {{e}}"}}))\n'
                        '    sys.exit(1)\n'
                        'except Exception as e:\n'
                        '    print(json.dumps({{"status": "error", "message": str(e)}}))\n'
                        '    sys.exit(1)\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'xml_path': {'type': 'string', 'description': 'Path to XML file'},
                            'xpath': {'type': 'string', 'description': 'XPath expression to query (optional)'},
                        },
                        'required': ['xml_path'],
                    },
                },
                'params': {'format_type': ['maven', 'pom', 'ant', 'config', 'sitemap']},
                'prompts': [
                    'Create a Python action to parse a {format_type} XML file and extract elements',
                    'Python script that parses {format_type} XML and converts elements to JSON',
                ],
                'explanation': 'Python action that parses a {format_type} XML file, optionally applying an XPath query, and returns elements as JSON.',
            },
            {
                'name': 'jinja2-template-render',
                'template': {
                    'name': 'Render config from template',
                    'action_type': 'PYTHON',
                    'code': (
                        'import json\n'
                        'import re\n'
                        'import sys\n\n'
                        'template_path = "{{input.template_path}}"\n'
                        'vars_json = \'{{input.variables}}\'\n'
                        'output_path = "{{input.output_path}}"\n\n'
                        'def simple_render(template_str, variables):\n'
                        '    """Simple template renderer replacing {{ var }} patterns."""\n'
                        '    def replacer(match):\n'
                        '        key = match.group(1).strip()\n'
                        '        return str(variables.get(key, match.group(0)))\n'
                        '    return re.sub(r"\\{\\{\\s*(\\w+)\\s*\\}\\}", replacer, template_str)\n\n'
                        'try:\n'
                        '    with open(template_path, "r") as f:\n'
                        '        template = f.read()\n'
                        '    variables = json.loads(vars_json)\n'
                        '    rendered = simple_render(template, variables)\n'
                        '    with open(output_path, "w") as f:\n'
                        '        f.write(rendered)\n'
                        '    print(json.dumps({{"status": "rendered", "output": output_path, "vars_used": len(variables)}}))\n'
                        'except Exception as e:\n'
                        '    print(json.dumps({{"status": "error", "message": str(e)}}))\n'
                        '    sys.exit(1)\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'template_path': {'type': 'string', 'description': 'Path to template file with {{ var }} placeholders'},
                            'variables': {'type': 'string', 'description': 'JSON string of template variables'},
                            'output_path': {'type': 'string', 'description': 'Path for rendered output file'},
                        },
                        'required': ['template_path', 'variables', 'output_path'],
                    },
                },
                'params': {'config_type': ['nginx', 'haproxy', 'systemd', 'docker-compose', 'prometheus']},
                'prompts': [
                    'Create a Python action to render a {config_type} config from a template',
                    'Python script that applies variables to a {config_type} template file',
                ],
                'explanation': 'Python action that renders a {config_type} configuration file from a template with variable substitution.',
            },
            {
                'name': 'diff-configs',
                'template': {
                    'name': 'Diff two config files',
                    'action_type': 'PYTHON',
                    'code': (
                        'import json\n'
                        'import difflib\n'
                        'import sys\n\n'
                        'file_a = "{{input.file_a}}"\n'
                        'file_b = "{{input.file_b}}"\n\n'
                        'try:\n'
                        '    with open(file_a, "r") as f:\n'
                        '        lines_a = f.readlines()\n'
                        '    with open(file_b, "r") as f:\n'
                        '        lines_b = f.readlines()\n\n'
                        '    diff = list(difflib.unified_diff(lines_a, lines_b, fromfile=file_a, tofile=file_b, lineterm=""))\n'
                        '    has_changes = len(diff) > 0\n'
                        '    added = sum(1 for l in diff if l.startswith("+") and not l.startswith("+++"))\n'
                        '    removed = sum(1 for l in diff if l.startswith("-") and not l.startswith("---"))\n\n'
                        '    print(json.dumps({{\n'
                        '        "status": "changed" if has_changes else "identical",\n'
                        '        "lines_added": added,\n'
                        '        "lines_removed": removed,\n'
                        '        "diff": "\\n".join(diff[:50]),\n'
                        '    }}))\n'
                        'except Exception as e:\n'
                        '    print(json.dumps({{"status": "error", "message": str(e)}}))\n'
                        '    sys.exit(1)\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'file_a': {'type': 'string', 'description': 'Path to first config file'},
                            'file_b': {'type': 'string', 'description': 'Path to second config file'},
                        },
                        'required': ['file_a', 'file_b'],
                    },
                },
                'params': {'config_type': ['nginx', 'apache', 'sshd', 'sudoers', 'fstab']},
                'prompts': [
                    'Create a Python action to diff two {config_type} config files',
                    'Python script that compares two {config_type} configuration files and shows differences',
                ],
                'explanation': 'Python action that generates a unified diff between two {config_type} configuration files, reporting added and removed lines.',
            },
            {
                'name': 'validate-json-schema',
                'template': {
                    'name': 'Validate JSON against schema',
                    'action_type': 'PYTHON',
                    'code': (
                        'import json\n'
                        'import sys\n\n'
                        'data_path = "{{input.data_path}}"\n'
                        'schema_path = "{{input.schema_path}}"\n\n'
                        'def validate(data, schema, path=""):\n'
                        '    errors = []\n'
                        '    stype = schema.get("type")\n'
                        '    if stype == "object" and isinstance(data, dict):\n'
                        '        for req in schema.get("required", []):\n'
                        '            if req not in data:\n'
                        '                errors.append(f"{{path}}: missing required field \'{{req}}\'")\n'
                        '        props = schema.get("properties", {})\n'
                        '        for k, v in props.items():\n'
                        '            if k in data:\n'
                        '                errors.extend(validate(data[k], v, str(path) + "." + str(k)))\n'
                        '    elif stype == "string" and not isinstance(data, str):\n'
                        '        errors.append(str(path) + ": expected string, got " + type(data).__name__)\n'
                        '    elif stype == "number" and not isinstance(data, (int, float)):\n'
                        '        errors.append(str(path) + ": expected number, got " + type(data).__name__)\n'
                        '    elif stype == "array" and not isinstance(data, list):\n'
                        '        errors.append(str(path) + ": expected array, got " + type(data).__name__)\n'
                        '    return errors\n\n'
                        'try:\n'
                        '    with open(data_path) as f:\n'
                        '        data = json.load(f)\n'
                        '    with open(schema_path) as f:\n'
                        '        schema = json.load(f)\n'
                        '    errors = validate(data, schema)\n'
                        '    if errors:\n'
                        '        print(json.dumps({{"status": "invalid", "errors": errors}}))\n'
                        '        sys.exit(1)\n'
                        '    print(json.dumps({{"status": "valid", "message": "Schema validation passed"}}))\n'
                        'except Exception as e:\n'
                        '    print(json.dumps({{"status": "error", "message": str(e)}}))\n'
                        '    sys.exit(1)\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'data_path': {'type': 'string', 'description': 'Path to JSON data file'},
                            'schema_path': {'type': 'string', 'description': 'Path to JSON schema file'},
                        },
                        'required': ['data_path', 'schema_path'],
                    },
                },
                'params': {'data_type': ['config', 'manifest', 'payload', 'response', 'template']},
                'prompts': [
                    'Create a Python action to validate a {data_type} JSON file against a schema',
                    'Python script that validates {data_type} data against a JSON schema',
                ],
                'explanation': 'Python action that validates a {data_type} JSON file against a JSON schema definition, reporting any validation errors.',
            },
            {
                'name': 'base64-encode-decode',
                'template': {
                    'name': 'Base64 {operation} data',
                    'action_type': 'PYTHON',
                    'code': (
                        'import base64\n'
                        'import json\n'
                        'import sys\n\n'
                        'operation = "{{input.operation}}" or "encode"\n'
                        'input_path = "{{input.input_path}}"\n'
                        'output_path = "{{input.output_path}}"\n\n'
                        'try:\n'
                        '    with open(input_path, "rb") as f:\n'
                        '        data = f.read()\n\n'
                        '    if operation == "encode":\n'
                        '        result = base64.b64encode(data)\n'
                        '    elif operation == "decode":\n'
                        '        result = base64.b64decode(data)\n'
                        '    else:\n'
                        '        print(json.dumps({{"status": "error", "message": f"Unknown operation: {{operation}}"}}))\n'
                        '        sys.exit(1)\n\n'
                        '    with open(output_path, "wb") as f:\n'
                        '        f.write(result)\n\n'
                        '    print(json.dumps({{\n'
                        '        "status": "ok",\n'
                        '        "operation": operation,\n'
                        '        "input_size": len(data),\n'
                        '        "output_size": len(result),\n'
                        '    }}))\n'
                        'except Exception as e:\n'
                        '    print(json.dumps({{"status": "error", "message": str(e)}}))\n'
                        '    sys.exit(1)\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'operation': {'type': 'string', 'description': 'Operation: encode or decode'},
                            'input_path': {'type': 'string', 'description': 'Path to input file'},
                            'output_path': {'type': 'string', 'description': 'Path for output file'},
                        },
                        'required': ['input_path', 'output_path'],
                    },
                },
                'params': {'operation': ['encode', 'decode']},
                'prompts': [
                    'Create a Python action to base64 {operation} a file',
                    'Python script that performs base64 {operation} on file contents',
                ],
                'explanation': 'Python action that performs base64 {operation} on file data and writes the result to an output file.',
            },
            {
                'name': 'regex-extraction',
                'template': {
                    'name': 'Regex extraction from file',
                    'action_type': 'PYTHON',
                    'code': (
                        'import re\n'
                        'import json\n'
                        'import sys\n\n'
                        'file_path = "{{input.file_path}}"\n'
                        'pattern = "{{input.pattern}}"\n'
                        'group = int("{{input.group}}" or "0")\n\n'
                        'try:\n'
                        '    with open(file_path, "r") as f:\n'
                        '        content = f.read()\n\n'
                        '    matches = re.findall(pattern, content)\n'
                        '    if not matches:\n'
                        '        print(json.dumps({{"status": "no_match", "pattern": pattern}}))\n'
                        '        sys.exit(0)\n\n'
                        '    # If pattern has groups, flatten tuples\n'
                        '    if matches and isinstance(matches[0], tuple):\n'
                        '        extracted = [m[group] if group < len(m) else m[0] for m in matches]\n'
                        '    else:\n'
                        '        extracted = matches\n\n'
                        '    print(json.dumps({{\n'
                        '        "status": "ok",\n'
                        '        "count": len(extracted),\n'
                        '        "matches": extracted[:100],\n'
                        '    }}))\n'
                        'except re.error as e:\n'
                        '    print(json.dumps({{"status": "error", "message": f"Invalid regex: {{e}}"}}))\n'
                        '    sys.exit(1)\n'
                        'except Exception as e:\n'
                        '    print(json.dumps({{"status": "error", "message": str(e)}}))\n'
                        '    sys.exit(1)\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'file_path': {'type': 'string', 'description': 'Path to file to search'},
                            'pattern': {'type': 'string', 'description': 'Regular expression pattern'},
                            'group': {'type': 'string', 'description': 'Capture group index (default 0)'},
                        },
                        'required': ['file_path', 'pattern'],
                    },
                },
                'params': {'target': ['logs', 'configs', 'reports', 'outputs', 'manifests']},
                'prompts': [
                    'Create a Python action to extract regex matches from {target}',
                    'Python script that applies a regex pattern to extract data from {target}',
                ],
                'explanation': 'Python action that applies a regular expression to extract matching data from {target} files.',
            },
            {
                'name': 'env-var-expansion',
                'template': {
                    'name': 'Expand environment variables',
                    'action_type': 'PYTHON',
                    'code': (
                        'import os\n'
                        'import re\n'
                        'import json\n'
                        'import sys\n\n'
                        'input_path = "{{input.input_path}}"\n'
                        'output_path = "{{input.output_path}}"\n'
                        'strict = "{{input.strict}}" == "true"\n\n'
                        'def expand_env(text, strict_mode):\n'
                        '    missing = []\n'
                        '    def replacer(match):\n'
                        '        var = match.group(1) or match.group(2)\n'
                        '        value = os.environ.get(var)\n'
                        '        if value is None:\n'
                        '            missing.append(var)\n'
                        '            return match.group(0) if not strict_mode else ""\n'
                        '        return value\n'
                        '    expanded = re.sub(r"\\$\\{{(\\w+)\\}}|\\$(\\w+)", replacer, text)\n'
                        '    return expanded, missing\n\n'
                        'try:\n'
                        '    with open(input_path, "r") as f:\n'
                        '        content = f.read()\n\n'
                        '    expanded, missing = expand_env(content, strict)\n\n'
                        '    if strict and missing:\n'
                        '        print(json.dumps({{"status": "error", "missing_vars": missing}}))\n'
                        '        sys.exit(1)\n\n'
                        '    with open(output_path, "w") as f:\n'
                        '        f.write(expanded)\n\n'
                        '    print(json.dumps({{\n'
                        '        "status": "expanded",\n'
                        '        "output": output_path,\n'
                        '        "missing_vars": missing,\n'
                        '    }}))\n'
                        'except Exception as e:\n'
                        '    print(json.dumps({{"status": "error", "message": str(e)}}))\n'
                        '    sys.exit(1)\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'input_path': {'type': 'string', 'description': 'Path to template file with $VAR or ${VAR} references'},
                            'output_path': {'type': 'string', 'description': 'Path for expanded output'},
                            'strict': {'type': 'string', 'description': 'Fail on missing vars: true/false (default false)'},
                        },
                        'required': ['input_path', 'output_path'],
                    },
                },
                'params': {'config_type': ['docker-compose', 'env-file', 'systemd-unit', 'shell-script', 'nginx-conf']},
                'prompts': [
                    'Create a Python action to expand env vars in a {config_type} file',
                    'Python script that substitutes environment variables in a {config_type} template',
                ],
                'explanation': 'Python action that expands environment variable references in a {config_type} file, optionally failing on missing variables.',
            },
        ]


def get_generators():
    return [DataProcessingGenerator()]
