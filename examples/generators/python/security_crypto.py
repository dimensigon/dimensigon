"""Security and cryptography Python action generators - 8 seeds for hashing, tokens, certs, etc."""

from examples.generators.base_generator import PythonActionGenerator


class SecurityCryptoGenerator(PythonActionGenerator):
    category = "python.security_crypto"
    subcategory = "security_crypto"

    def seeds(self):
        return [
            {
                'name': 'sha256-file-hash',
                'template': {
                    'name': 'SHA256 hash of {target} file',
                    'action_type': 'PYTHON',
                    'code': (
                        'import hashlib\n'
                        'import json\n'
                        'import os\n'
                        'import sys\n\n'
                        'file_path = "{{input.file_path}}"\n'
                        'expected_hash = "{{input.expected_hash}}" or ""\n\n'
                        'if not os.path.isfile(file_path):\n'
                        '    print(json.dumps({{"status": "error", "message": f"File not found: {{file_path}}"}}))\n'
                        '    sys.exit(1)\n\n'
                        'sha256 = hashlib.sha256()\n'
                        'with open(file_path, "rb") as f:\n'
                        '    for chunk in iter(lambda: f.read(8192), b""):\n'
                        '        sha256.update(chunk)\n'
                        'computed = sha256.hexdigest()\n\n'
                        'result = {{"status": "ok", "file": file_path, "sha256": computed, "size_bytes": os.path.getsize(file_path)}}\n'
                        'if expected_hash:\n'
                        '    match = computed == expected_hash.lower()\n'
                        '    result["match"] = match\n'
                        '    result["status"] = "ok" if match else "mismatch"\n'
                        'print(json.dumps(result))\n'
                        'if expected_hash and not match:\n'
                        '    sys.exit(1)\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'file_path': {'type': 'string', 'description': 'Path to file to hash'},
                            'expected_hash': {'type': 'string', 'description': 'Expected SHA256 hash to verify (optional)'},
                        },
                        'required': ['file_path'],
                    },
                },
                'params': {'target': ['binary', 'config', 'artifact', 'backup', 'package']},
                'prompts': [
                    'Create a Python action to compute SHA256 hash of a {target} file',
                    'Python script that calculates and optionally verifies a {target} file SHA256 checksum',
                ],
                'explanation': 'Python action that computes the SHA256 hash of a {target} file and optionally verifies it against an expected value.',
            },
            {
                'name': 'random-token-gen',
                'template': {
                    'name': 'Generate random {token_type}',
                    'action_type': 'PYTHON',
                    'code': (
                        'import secrets\n'
                        'import json\n'
                        'import sys\n\n'
                        'length = int("{{input.length}}" or "32")\n'
                        'format_type = "{{input.format}}" or "hex"\n\n'
                        'if format_type == "hex":\n'
                        '    token = secrets.token_hex(length)\n'
                        'elif format_type == "urlsafe":\n'
                        '    token = secrets.token_urlsafe(length)\n'
                        'elif format_type == "bytes":\n'
                        '    import base64\n'
                        '    token = base64.b64encode(secrets.token_bytes(length)).decode()\n'
                        'else:\n'
                        '    token = secrets.token_hex(length)\n\n'
                        'print(json.dumps({{\n'
                        '    "status": "ok",\n'
                        '    "token": token,\n'
                        '    "format": format_type,\n'
                        '    "length": length,\n'
                        '}}))\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'length': {'type': 'string', 'description': 'Token length in bytes (default 32)'},
                            'format': {'type': 'string', 'description': 'Token format: hex, urlsafe, bytes (default hex)'},
                        },
                        'required': [],
                    },
                },
                'params': {'token_type': ['api-key', 'session-token', 'secret-key', 'nonce']},
                'prompts': [
                    'Create a Python action to generate a random {token_type}',
                    'Python script that creates a cryptographically secure {token_type}',
                ],
                'explanation': 'Python action that generates a cryptographically secure random {token_type} using the secrets module.',
            },
            {
                'name': 'api-key-rotation',
                'template': {
                    'name': 'Rotate API key for {service}',
                    'action_type': 'PYTHON',
                    'code': (
                        'import secrets\n'
                        'import json\n'
                        'import os\n'
                        'import sys\n'
                        'from datetime import datetime, timezone\n\n'
                        'key_file = "{{input.key_file}}"\n'
                        'key_length = int("{{input.key_length}}" or "32")\n'
                        'backup = "{{input.backup}}" != "false"\n\n'
                        'old_key = ""\n'
                        'if os.path.isfile(key_file):\n'
                        '    with open(key_file, "r") as f:\n'
                        '        old_key = f.read().strip()\n'
                        '    if backup:\n'
                        '        ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")\n'
                        '        backup_path = f"{{key_file}}.{{ts}}.bak"\n'
                        '        with open(backup_path, "w") as f:\n'
                        '            f.write(old_key)\n\n'
                        'new_key = secrets.token_urlsafe(key_length)\n'
                        'with open(key_file, "w") as f:\n'
                        '    f.write(new_key)\n'
                        'os.chmod(key_file, 0o600)\n\n'
                        'print(json.dumps({{\n'
                        '    "status": "rotated",\n'
                        '    "key_file": key_file,\n'
                        '    "old_key_prefix": old_key[:8] + "..." if old_key else "none",\n'
                        '    "new_key_prefix": new_key[:8] + "...",\n'
                        '}}))\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'key_file': {'type': 'string', 'description': 'Path to the API key file'},
                            'key_length': {'type': 'string', 'description': 'New key length in bytes (default 32)'},
                            'backup': {'type': 'string', 'description': 'Backup old key: true/false (default true)'},
                        },
                        'required': ['key_file'],
                    },
                },
                'params': {'service': ['internal-api', 'webhook', 'oauth', 'third-party', 'monitoring']},
                'prompts': [
                    'Create a Python action to rotate the {service} API key',
                    'Python script that generates a new {service} API key and backs up the old one',
                ],
                'explanation': 'Python action that rotates the {service} API key, backing up the old key and writing a new secure key to file.',
            },
            {
                'name': 'jwt-decode',
                'template': {
                    'name': 'Decode JWT token',
                    'action_type': 'PYTHON',
                    'code': (
                        'import json\n'
                        'import base64\n'
                        'import sys\n\n'
                        'token = "{{input.token}}"\n\n'
                        'parts = token.split(".")\n'
                        'if len(parts) != 3:\n'
                        '    print(json.dumps({{"status": "error", "message": "Invalid JWT format"}}))\n'
                        '    sys.exit(1)\n\n'
                        'def decode_part(part):\n'
                        '    padding = 4 - len(part) % 4\n'
                        '    part += "=" * padding\n'
                        '    return json.loads(base64.urlsafe_b64decode(part).decode("utf-8"))\n\n'
                        'try:\n'
                        '    header = decode_part(parts[0])\n'
                        '    payload = decode_part(parts[1])\n'
                        '    import time\n'
                        '    exp = payload.get("exp")\n'
                        '    expired = exp is not None and exp < time.time()\n'
                        '    print(json.dumps({{\n'
                        '        "status": "ok",\n'
                        '        "header": header,\n'
                        '        "payload": payload,\n'
                        '        "expired": expired,\n'
                        '    }}))\n'
                        'except Exception as e:\n'
                        '    print(json.dumps({{"status": "error", "message": str(e)}}))\n'
                        '    sys.exit(1)\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'token': {'type': 'string', 'description': 'JWT token string to decode'},
                        },
                        'required': ['token'],
                    },
                },
                'params': {'use_case': ['auth', 'api-access', 'session', 'service-to-service']},
                'prompts': [
                    'Create a Python action to decode a {use_case} JWT token',
                    'Python script that decodes and inspects a {use_case} JWT without verification',
                ],
                'explanation': 'Python action that decodes a {use_case} JWT token header and payload using base64, checking expiration.',
            },
            {
                'name': 'password-hash',
                'template': {
                    'name': 'Hash password with {algorithm}',
                    'action_type': 'PYTHON',
                    'code': (
                        'import hashlib\n'
                        'import os\n'
                        'import json\n'
                        'import sys\n\n'
                        'password = "{{input.password}}"\n'
                        'algorithm = "{{input.algorithm}}" or "sha256"\n'
                        'salt_length = int("{{input.salt_length}}" or "16")\n\n'
                        'salt = os.urandom(salt_length)\n'
                        'salt_hex = salt.hex()\n\n'
                        'if algorithm == "sha256":\n'
                        '    hashed = hashlib.sha256(salt + password.encode()).hexdigest()\n'
                        'elif algorithm == "sha512":\n'
                        '    hashed = hashlib.sha512(salt + password.encode()).hexdigest()\n'
                        'elif algorithm == "pbkdf2":\n'
                        '    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100000)\n'
                        '    hashed = dk.hex()\n'
                        'else:\n'
                        '    print(json.dumps({{"status": "error", "message": f"Unsupported algorithm: {{algorithm}}"}}))\n'
                        '    sys.exit(1)\n\n'
                        'print(json.dumps({{\n'
                        '    "status": "ok",\n'
                        '    "algorithm": algorithm,\n'
                        '    "salt": salt_hex,\n'
                        '    "hash": hashed,\n'
                        '}}))\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'password': {'type': 'string', 'description': 'Password to hash'},
                            'algorithm': {'type': 'string', 'description': 'Hash algorithm: sha256, sha512, pbkdf2 (default sha256)'},
                            'salt_length': {'type': 'string', 'description': 'Salt length in bytes (default 16)'},
                        },
                        'required': ['password'],
                    },
                },
                'params': {'algorithm': ['sha256', 'sha512', 'pbkdf2']},
                'prompts': [
                    'Create a Python action to hash a password using {algorithm}',
                    'Python script that generates a salted {algorithm} password hash',
                ],
                'explanation': 'Python action that hashes a password using {algorithm} with a random salt for secure storage.',
            },
            {
                'name': 'ssl-cert-info',
                'template': {
                    'name': 'Check SSL cert for {target}',
                    'action_type': 'PYTHON',
                    'code': (
                        'import ssl\n'
                        'import socket\n'
                        'import json\n'
                        'import sys\n'
                        'from datetime import datetime\n\n'
                        'hostname = "{{input.hostname}}"\n'
                        'port = int("{{input.port}}" or "443")\n'
                        'warn_days = int("{{input.warn_days}}" or "30")\n\n'
                        'try:\n'
                        '    ctx = ssl.create_default_context()\n'
                        '    with socket.create_connection((hostname, port), timeout=10) as sock:\n'
                        '        with ctx.wrap_socket(sock, server_hostname=hostname) as ssock:\n'
                        '            cert = ssock.getpeercert()\n'
                        '    not_after = cert.get("notAfter", "")\n'
                        '    expiry = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z")\n'
                        '    days_left = (expiry - datetime.utcnow()).days\n'
                        '    issuer = dict(x[0] for x in cert.get("issuer", []))\n'
                        '    subject = dict(x[0] for x in cert.get("subject", []))\n'
                        '    print(json.dumps({{\n'
                        '        "status": "warning" if days_left < warn_days else "ok",\n'
                        '        "hostname": hostname,\n'
                        '        "issuer": issuer.get("organizationName", "unknown"),\n'
                        '        "subject_cn": subject.get("commonName", "unknown"),\n'
                        '        "expires": not_after,\n'
                        '        "days_left": days_left,\n'
                        '    }}))\n'
                        '    if days_left < warn_days:\n'
                        '        sys.exit(1)\n'
                        'except Exception as e:\n'
                        '    print(json.dumps({{"status": "error", "message": str(e)}}))\n'
                        '    sys.exit(1)\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'hostname': {'type': 'string', 'description': 'Hostname to check SSL certificate'},
                            'port': {'type': 'string', 'description': 'Port number (default 443)'},
                            'warn_days': {'type': 'string', 'description': 'Warn if cert expires within N days (default 30)'},
                        },
                        'required': ['hostname'],
                    },
                },
                'params': {'target': ['web-server', 'api-gateway', 'mail-server', 'load-balancer', 'cdn']},
                'prompts': [
                    'Create a Python action to check SSL certificate expiry for a {target}',
                    'Python script that inspects the {target} SSL certificate and warns before expiry',
                ],
                'explanation': 'Python action that checks the SSL certificate of a {target}, reporting issuer, expiry date, and days remaining.',
            },
            {
                'name': 'file-encrypt-b64',
                'template': {
                    'name': 'Base64 {operation} file',
                    'action_type': 'PYTHON',
                    'code': (
                        'import base64\n'
                        'import json\n'
                        'import os\n'
                        'import sys\n\n'
                        'input_path = "{{input.input_path}}"\n'
                        'output_path = "{{input.output_path}}"\n'
                        'operation = "{{input.operation}}" or "encode"\n\n'
                        'if not os.path.isfile(input_path):\n'
                        '    print(json.dumps({{"status": "error", "message": f"File not found: {{input_path}}"}}))\n'
                        '    sys.exit(1)\n\n'
                        'try:\n'
                        '    with open(input_path, "rb") as f:\n'
                        '        data = f.read()\n'
                        '    if operation == "encode":\n'
                        '        result = base64.b64encode(data)\n'
                        '    elif operation == "decode":\n'
                        '        result = base64.b64decode(data)\n'
                        '    else:\n'
                        '        print(json.dumps({{"status": "error", "message": f"Invalid operation: {{operation}}"}}))\n'
                        '        sys.exit(1)\n'
                        '    with open(output_path, "wb") as f:\n'
                        '        f.write(result)\n'
                        '    print(json.dumps({{\n'
                        '        "status": "ok",\n'
                        '        "operation": operation,\n'
                        '        "input_size": len(data),\n'
                        '        "output_size": len(result),\n'
                        '        "output_path": output_path,\n'
                        '    }}))\n'
                        'except Exception as e:\n'
                        '    print(json.dumps({{"status": "error", "message": str(e)}}))\n'
                        '    sys.exit(1)\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'input_path': {'type': 'string', 'description': 'Path to input file'},
                            'output_path': {'type': 'string', 'description': 'Path for output file'},
                            'operation': {'type': 'string', 'description': 'Operation: encode or decode (default encode)'},
                        },
                        'required': ['input_path', 'output_path'],
                    },
                },
                'params': {'operation': ['encode', 'decode']},
                'prompts': [
                    'Create a Python action to base64 {operation} a file for secure transport',
                    'Python script that performs base64 {operation} on a file',
                ],
                'explanation': 'Python action that performs base64 {operation} on a file for secure transport or storage.',
            },
            {
                'name': 'api-key-expiry',
                'template': {
                    'name': 'Check API key expiry',
                    'action_type': 'PYTHON',
                    'code': (
                        'import json\n'
                        'import os\n'
                        'import sys\n'
                        'from datetime import datetime, timezone\n\n'
                        'key_file = "{{input.key_file}}"\n'
                        'max_age_days = int("{{input.max_age_days}}" or "90")\n\n'
                        'if not os.path.isfile(key_file):\n'
                        '    print(json.dumps({{"status": "error", "message": f"Key file not found: {{key_file}}"}}))\n'
                        '    sys.exit(1)\n\n'
                        'mod_time = os.path.getmtime(key_file)\n'
                        'mod_dt = datetime.fromtimestamp(mod_time, tz=timezone.utc)\n'
                        'now = datetime.now(timezone.utc)\n'
                        'age_days = (now - mod_dt).days\n'
                        'expired = age_days > max_age_days\n\n'
                        'print(json.dumps({{\n'
                        '    "status": "expired" if expired else "ok",\n'
                        '    "key_file": key_file,\n'
                        '    "age_days": age_days,\n'
                        '    "max_age_days": max_age_days,\n'
                        '    "last_modified": mod_dt.isoformat(),\n'
                        '}}))\n'
                        'if expired:\n'
                        '    sys.exit(1)\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'key_file': {'type': 'string', 'description': 'Path to the API key file'},
                            'max_age_days': {'type': 'string', 'description': 'Maximum key age in days (default 90)'},
                        },
                        'required': ['key_file'],
                    },
                },
                'params': {'service': ['production-api', 'staging-api', 'webhook', 'monitoring', 'ci-cd']},
                'prompts': [
                    'Create a Python action to check if a {service} API key has expired',
                    'Python script that validates the age of a {service} API key file',
                ],
                'explanation': 'Python action that checks the age of a {service} API key file and alerts if it exceeds the maximum age.',
            },
        ]


def get_generators():
    return [SecurityCryptoGenerator()]
