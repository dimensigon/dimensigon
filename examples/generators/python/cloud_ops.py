"""Cloud operations Python action generators - 10 seeds for metadata, S3, DNS, CDN, etc."""

from examples.generators.base_generator import PythonActionGenerator


class CloudOpsGenerator(PythonActionGenerator):
    category = "python.cloud_ops"
    subcategory = "cloud_ops"

    def seeds(self):
        return [
            {
                'name': 'cloud-metadata-get',
                'template': {
                    'name': 'GET {provider} instance metadata',
                    'action_type': 'PYTHON',
                    'code': (
                        'import json\n'
                        'import urllib.request\n'
                        'import sys\n\n'
                        'metadata_url = "{{input.metadata_url}}"\n'
                        'token_header = "{{input.token_header}}" or ""\n'
                        'token_value = "{{input.token_value}}" or ""\n\n'
                        'req = urllib.request.Request(metadata_url, method="GET")\n'
                        'if token_header and token_value:\n'
                        '    req.add_header(token_header, token_value)\n'
                        'try:\n'
                        '    resp = urllib.request.urlopen(req, timeout=5)\n'
                        '    body = resp.read().decode()\n'
                        '    try:\n'
                        '        data = json.loads(body)\n'
                        '    except json.JSONDecodeError:\n'
                        '        data = body\n'
                        '    print(json.dumps({{"status": "ok", "metadata": data}}))\n'
                        'except Exception as e:\n'
                        '    print(json.dumps({{"status": "error", "message": str(e)}}))\n'
                        '    sys.exit(1)\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'metadata_url': {'type': 'string', 'description': 'Cloud metadata endpoint URL'},
                            'token_header': {'type': 'string', 'description': 'Auth header name (optional)'},
                            'token_value': {'type': 'string', 'description': 'Auth header value (optional)'},
                        },
                        'required': ['metadata_url'],
                    },
                },
                'params': {'provider': ['aws', 'gcp', 'azure', 'digitalocean', 'hetzner']},
                'prompts': [
                    'Create a Python action to fetch {provider} cloud instance metadata',
                    'Python script that queries the {provider} metadata API for instance info',
                ],
                'explanation': 'Python action that sends an HTTP GET to the {provider} instance metadata endpoint and returns the result.',
            },
            {
                'name': 's3-presigned-url',
                'template': {
                    'name': 'Generate S3 presigned URL',
                    'action_type': 'PYTHON',
                    'code': (
                        'import json\n'
                        'import hashlib\n'
                        'import hmac\n'
                        'import urllib.parse\n'
                        'import sys\n'
                        'from datetime import datetime, timezone\n\n'
                        'access_key = "{{input.access_key}}"\n'
                        'secret_key = "{{input.secret_key}}"\n'
                        'bucket = "{{input.bucket}}"\n'
                        'object_key = "{{input.object_key}}"\n'
                        'region = "{{input.region}}" or "us-east-1"\n'
                        'expires = int("{{input.expires}}" or "3600")\n\n'
                        'now = datetime.now(timezone.utc)\n'
                        'datestamp = now.strftime("%Y%m%d")\n'
                        'amz_date = now.strftime("%Y%m%dT%H%M%SZ")\n'
                        'host = f"{{bucket}}.s3.{{region}}.amazonaws.com"\n'
                        'credential_scope = f"{{datestamp}}/{{region}}/s3/aws4_request"\n'
                        'credential = f"{{access_key}}/{{credential_scope}}"\n\n'
                        'params = {{\n'
                        '    "X-Amz-Algorithm": "AWS4-HMAC-SHA256",\n'
                        '    "X-Amz-Credential": credential,\n'
                        '    "X-Amz-Date": amz_date,\n'
                        '    "X-Amz-Expires": str(expires),\n'
                        '    "X-Amz-SignedHeaders": "host",\n'
                        '}}\n'
                        'query = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)\n'
                        'url = f"https://{{host}}/{{object_key}}?{{query}}"\n'
                        'print(json.dumps({{"status": "ok", "presigned_url": url, "expires_in": expires}}))\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'access_key': {'type': 'string', 'description': 'AWS access key ID'},
                            'secret_key': {'type': 'string', 'description': 'AWS secret access key'},
                            'bucket': {'type': 'string', 'description': 'S3 bucket name'},
                            'object_key': {'type': 'string', 'description': 'S3 object key path'},
                            'region': {'type': 'string', 'description': 'AWS region (default us-east-1)'},
                            'expires': {'type': 'string', 'description': 'URL expiry in seconds (default 3600)'},
                        },
                        'required': ['access_key', 'secret_key', 'bucket', 'object_key'],
                    },
                },
                'params': {'provider': ['aws', 'minio', 'wasabi', 'backblaze', 'digitalocean-spaces']},
                'prompts': [
                    'Create a Python action to generate an S3-style presigned URL for {provider}',
                    'Python script that creates a presigned download URL for {provider} object storage',
                ],
                'explanation': 'Python action that generates an S3-compatible presigned URL for {provider} object storage access.',
            },
            {
                'name': 'dns-record-update',
                'template': {
                    'name': 'Update DNS via {provider} API',
                    'action_type': 'PYTHON',
                    'code': (
                        'import json\n'
                        'import urllib.request\n'
                        'import sys\n\n'
                        'api_url = "{{input.api_url}}"\n'
                        'api_key = "{{input.api_key}}"\n'
                        'domain = "{{input.domain}}"\n'
                        'record_type = "{{input.record_type}}" or "A"\n'
                        'record_name = "{{input.record_name}}"\n'
                        'record_value = "{{input.record_value}}"\n'
                        'ttl = int("{{input.ttl}}" or "300")\n\n'
                        'payload = {{\n'
                        '    "type": record_type,\n'
                        '    "name": record_name,\n'
                        '    "content": record_value,\n'
                        '    "ttl": ttl,\n'
                        '}}\n'
                        'data = json.dumps(payload).encode("utf-8")\n'
                        'req = urllib.request.Request(api_url, data=data, method="PUT")\n'
                        'req.add_header("Content-Type", "application/json")\n'
                        'req.add_header("Authorization", "Bearer " + api_key)\n'
                        'try:\n'
                        '    resp = urllib.request.urlopen(req, timeout=30)\n'
                        '    result = json.loads(resp.read().decode())\n'
                        '    print(json.dumps({{"status": "updated", "domain": domain, "record": record_name, "type": record_type}}))\n'
                        'except Exception as e:\n'
                        '    print(json.dumps({{"status": "error", "message": str(e)}}))\n'
                        '    sys.exit(1)\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'api_url': {'type': 'string', 'description': 'DNS provider API URL'},
                            'api_key': {'type': 'string', 'description': 'API key for auth'},
                            'domain': {'type': 'string', 'description': 'Domain name'},
                            'record_type': {'type': 'string', 'description': 'DNS record type (default A)'},
                            'record_name': {'type': 'string', 'description': 'Record name (subdomain)'},
                            'record_value': {'type': 'string', 'description': 'Record value (IP or target)'},
                            'ttl': {'type': 'string', 'description': 'TTL in seconds (default 300)'},
                        },
                        'required': ['api_url', 'api_key', 'domain', 'record_name', 'record_value'],
                    },
                },
                'params': {'provider': ['cloudflare', 'route53', 'digitalocean', 'gcloud-dns', 'azure-dns']},
                'prompts': [
                    'Create a Python action to update a DNS record via {provider} API',
                    'Python script that modifies DNS records through {provider}',
                ],
                'explanation': 'Python action that updates a DNS record via {provider} API with configurable type, name, value, and TTL.',
            },
            {
                'name': 'cdn-cache-purge',
                'template': {
                    'name': 'Purge CDN cache on {provider}',
                    'action_type': 'PYTHON',
                    'code': (
                        'import json\n'
                        'import urllib.request\n'
                        'import sys\n\n'
                        'api_url = "{{input.api_url}}"\n'
                        'api_key = "{{input.api_key}}"\n'
                        'paths = "{{input.paths}}"\n\n'
                        'path_list = [p.strip() for p in paths.split(",") if p.strip()]\n'
                        'payload = {{"purge_paths": path_list}}\n'
                        'data = json.dumps(payload).encode("utf-8")\n'
                        'req = urllib.request.Request(api_url, data=data, method="POST")\n'
                        'req.add_header("Content-Type", "application/json")\n'
                        'req.add_header("Authorization", "Bearer " + api_key)\n'
                        'try:\n'
                        '    resp = urllib.request.urlopen(req, timeout=30)\n'
                        '    result = json.loads(resp.read().decode())\n'
                        '    print(json.dumps({{"status": "purged", "paths": path_list, "count": len(path_list)}}))\n'
                        'except Exception as e:\n'
                        '    print(json.dumps({{"status": "error", "message": str(e)}}))\n'
                        '    sys.exit(1)\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'api_url': {'type': 'string', 'description': 'CDN purge API endpoint'},
                            'api_key': {'type': 'string', 'description': 'API key for auth'},
                            'paths': {'type': 'string', 'description': 'Comma-separated paths to purge'},
                        },
                        'required': ['api_url', 'api_key', 'paths'],
                    },
                },
                'params': {'provider': ['cloudflare', 'fastly', 'akamai', 'cloudfront', 'bunnycdn']},
                'prompts': [
                    'Create a Python action to purge {provider} CDN cache for specific paths',
                    'Python script that triggers a cache purge on {provider} CDN',
                ],
                'explanation': 'Python action that purges cached content on {provider} CDN for specified URL paths.',
            },
            {
                'name': 'instance-tagging',
                'template': {
                    'name': 'Tag {provider} instance via API',
                    'action_type': 'PYTHON',
                    'code': (
                        'import json\n'
                        'import urllib.request\n'
                        'import sys\n\n'
                        'api_url = "{{input.api_url}}"\n'
                        'api_key = "{{input.api_key}}"\n'
                        'instance_id = "{{input.instance_id}}"\n'
                        'tags_json = \'{{input.tags}}\'\n\n'
                        'tags = json.loads(tags_json)\n'
                        'payload = {{"instance_id": instance_id, "tags": tags}}\n'
                        'data = json.dumps(payload).encode("utf-8")\n'
                        'req = urllib.request.Request(api_url, data=data, method="POST")\n'
                        'req.add_header("Content-Type", "application/json")\n'
                        'req.add_header("Authorization", "Bearer " + api_key)\n'
                        'try:\n'
                        '    resp = urllib.request.urlopen(req, timeout=30)\n'
                        '    print(json.dumps({{"status": "tagged", "instance": instance_id, "tags": tags}}))\n'
                        'except Exception as e:\n'
                        '    print(json.dumps({{"status": "error", "message": str(e)}}))\n'
                        '    sys.exit(1)\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'api_url': {'type': 'string', 'description': 'Cloud API URL for tagging'},
                            'api_key': {'type': 'string', 'description': 'API key for auth'},
                            'instance_id': {'type': 'string', 'description': 'Instance ID to tag'},
                            'tags': {'type': 'string', 'description': 'JSON string of key-value tags'},
                        },
                        'required': ['api_url', 'api_key', 'instance_id', 'tags'],
                    },
                },
                'params': {'provider': ['aws', 'gcp', 'azure', 'digitalocean', 'hetzner']},
                'prompts': [
                    'Create a Python action to tag a {provider} cloud instance via API',
                    'Python script that applies tags to a {provider} instance',
                ],
                'explanation': 'Python action that applies key-value tags to a {provider} cloud instance via API.',
            },
            {
                'name': 'cloud-health-check',
                'template': {
                    'name': 'Check {provider} service health',
                    'action_type': 'PYTHON',
                    'code': (
                        'import json\n'
                        'import urllib.request\n'
                        'import sys\n\n'
                        'health_url = "{{input.health_url}}"\n'
                        'api_key = "{{input.api_key}}" or ""\n'
                        'expected_status = int("{{input.expected_status}}" or "200")\n\n'
                        'req = urllib.request.Request(health_url, method="GET")\n'
                        'if api_key:\n'
                        '    req.add_header("Authorization", "Bearer " + api_key)\n'
                        'try:\n'
                        '    resp = urllib.request.urlopen(req, timeout=15)\n'
                        '    code = resp.getcode()\n'
                        '    body = resp.read().decode()\n'
                        '    try:\n'
                        '        data = json.loads(body)\n'
                        '    except json.JSONDecodeError:\n'
                        '        data = body\n'
                        '    healthy = code == expected_status\n'
                        '    print(json.dumps({{"status": "healthy" if healthy else "unhealthy", "code": code, "body": data}}))\n'
                        '    if not healthy:\n'
                        '        sys.exit(1)\n'
                        'except Exception as e:\n'
                        '    print(json.dumps({{"status": "unreachable", "message": str(e)}}))\n'
                        '    sys.exit(1)\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'health_url': {'type': 'string', 'description': 'Health check endpoint URL'},
                            'api_key': {'type': 'string', 'description': 'API key for auth (optional)'},
                            'expected_status': {'type': 'string', 'description': 'Expected HTTP status code (default 200)'},
                        },
                        'required': ['health_url'],
                    },
                },
                'params': {'provider': ['aws', 'gcp', 'azure', 'cloudflare', 'heroku']},
                'prompts': [
                    'Create a Python action to check {provider} cloud service health',
                    'Python script that performs a health check on {provider} services',
                ],
                'explanation': 'Python action that checks {provider} cloud service health by querying an endpoint and validating the response code.',
            },
            {
                'name': 'storage-bucket-list',
                'template': {
                    'name': 'List {provider} storage buckets',
                    'action_type': 'PYTHON',
                    'code': (
                        'import json\n'
                        'import urllib.request\n'
                        'import sys\n\n'
                        'api_url = "{{input.api_url}}"\n'
                        'api_key = "{{input.api_key}}"\n\n'
                        'req = urllib.request.Request(api_url, method="GET")\n'
                        'req.add_header("Authorization", "Bearer " + api_key)\n'
                        'try:\n'
                        '    resp = urllib.request.urlopen(req, timeout=30)\n'
                        '    data = json.loads(resp.read().decode())\n'
                        '    buckets = data if isinstance(data, list) else data.get("buckets", data.get("items", []))\n'
                        '    print(json.dumps({{"status": "ok", "count": len(buckets), "buckets": buckets}}))\n'
                        'except Exception as e:\n'
                        '    print(json.dumps({{"status": "error", "message": str(e)}}))\n'
                        '    sys.exit(1)\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'api_url': {'type': 'string', 'description': 'Storage API list endpoint'},
                            'api_key': {'type': 'string', 'description': 'API key for auth'},
                        },
                        'required': ['api_url', 'api_key'],
                    },
                },
                'params': {'provider': ['aws-s3', 'gcs', 'azure-blob', 'minio', 'backblaze']},
                'prompts': [
                    'Create a Python action to list {provider} storage buckets',
                    'Python script that retrieves all buckets from {provider} storage API',
                ],
                'explanation': 'Python action that queries {provider} storage API to list all available buckets.',
            },
            {
                'name': 'lb-status-check',
                'template': {
                    'name': 'Check {provider} LB status',
                    'action_type': 'PYTHON',
                    'code': (
                        'import json\n'
                        'import urllib.request\n'
                        'import sys\n\n'
                        'api_url = "{{input.api_url}}"\n'
                        'api_key = "{{input.api_key}}"\n'
                        'lb_id = "{{input.lb_id}}"\n\n'
                        'url = f"{{api_url}}/{{lb_id}}/status"\n'
                        'req = urllib.request.Request(url, method="GET")\n'
                        'req.add_header("Authorization", "Bearer " + api_key)\n'
                        'try:\n'
                        '    resp = urllib.request.urlopen(req, timeout=30)\n'
                        '    data = json.loads(resp.read().decode())\n'
                        '    healthy = data.get("status", "").lower() in ("active", "healthy", "running")\n'
                        '    print(json.dumps({{"status": "healthy" if healthy else "unhealthy", "lb_id": lb_id, "details": data}}))\n'
                        '    if not healthy:\n'
                        '        sys.exit(1)\n'
                        'except Exception as e:\n'
                        '    print(json.dumps({{"status": "error", "message": str(e)}}))\n'
                        '    sys.exit(1)\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'api_url': {'type': 'string', 'description': 'Load balancer API base URL'},
                            'api_key': {'type': 'string', 'description': 'API key for auth'},
                            'lb_id': {'type': 'string', 'description': 'Load balancer ID'},
                        },
                        'required': ['api_url', 'api_key', 'lb_id'],
                    },
                },
                'params': {'provider': ['aws-alb', 'gcp-lb', 'azure-lb', 'haproxy', 'nginx-plus']},
                'prompts': [
                    'Create a Python action to check {provider} load balancer status',
                    'Python script that queries {provider} load balancer health',
                ],
                'explanation': 'Python action that checks the status of a {provider} load balancer via API.',
            },
            {
                'name': 'autoscaling-trigger',
                'template': {
                    'name': 'Trigger {provider} auto-scale',
                    'action_type': 'PYTHON',
                    'code': (
                        'import json\n'
                        'import urllib.request\n'
                        'import sys\n\n'
                        'api_url = "{{input.api_url}}"\n'
                        'api_key = "{{input.api_key}}"\n'
                        'group_id = "{{input.group_id}}"\n'
                        'desired_count = int("{{input.desired_count}}")\n\n'
                        'payload = {{"group_id": group_id, "desired_capacity": desired_count}}\n'
                        'data = json.dumps(payload).encode("utf-8")\n'
                        'req = urllib.request.Request(api_url, data=data, method="POST")\n'
                        'req.add_header("Content-Type", "application/json")\n'
                        'req.add_header("Authorization", "Bearer " + api_key)\n'
                        'try:\n'
                        '    resp = urllib.request.urlopen(req, timeout=30)\n'
                        '    result = json.loads(resp.read().decode())\n'
                        '    print(json.dumps({{"status": "scaled", "group": group_id, "desired": desired_count}}))\n'
                        'except Exception as e:\n'
                        '    print(json.dumps({{"status": "error", "message": str(e)}}))\n'
                        '    sys.exit(1)\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'api_url': {'type': 'string', 'description': 'Auto-scaling API endpoint'},
                            'api_key': {'type': 'string', 'description': 'API key for auth'},
                            'group_id': {'type': 'string', 'description': 'Auto-scaling group ID'},
                            'desired_count': {'type': 'string', 'description': 'Desired instance count'},
                        },
                        'required': ['api_url', 'api_key', 'group_id', 'desired_count'],
                    },
                },
                'params': {'provider': ['aws-asg', 'gcp-mig', 'azure-vmss', 'kubernetes-hpa', 'nomad']},
                'prompts': [
                    'Create a Python action to trigger {provider} auto-scaling to a desired count',
                    'Python script that adjusts {provider} auto-scaling group capacity',
                ],
                'explanation': 'Python action that triggers {provider} auto-scaling by setting the desired instance capacity via API.',
            },
            {
                'name': 'cloud-backup-trigger',
                'template': {
                    'name': 'Trigger {provider} backup',
                    'action_type': 'PYTHON',
                    'code': (
                        'import json\n'
                        'import urllib.request\n'
                        'import sys\n\n'
                        'api_url = "{{input.api_url}}"\n'
                        'api_key = "{{input.api_key}}"\n'
                        'resource_id = "{{input.resource_id}}"\n'
                        'backup_name = "{{input.backup_name}}" or "auto-backup"\n\n'
                        'payload = {{"resource_id": resource_id, "name": backup_name}}\n'
                        'data = json.dumps(payload).encode("utf-8")\n'
                        'req = urllib.request.Request(api_url, data=data, method="POST")\n'
                        'req.add_header("Content-Type", "application/json")\n'
                        'req.add_header("Authorization", "Bearer " + api_key)\n'
                        'try:\n'
                        '    resp = urllib.request.urlopen(req, timeout=60)\n'
                        '    result = json.loads(resp.read().decode())\n'
                        '    print(json.dumps({{"status": "backup_initiated", "resource": resource_id, "backup": backup_name}}))\n'
                        'except Exception as e:\n'
                        '    print(json.dumps({{"status": "error", "message": str(e)}}))\n'
                        '    sys.exit(1)\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'api_url': {'type': 'string', 'description': 'Backup API endpoint URL'},
                            'api_key': {'type': 'string', 'description': 'API key for auth'},
                            'resource_id': {'type': 'string', 'description': 'Resource ID to back up'},
                            'backup_name': {'type': 'string', 'description': 'Backup name label (optional)'},
                        },
                        'required': ['api_url', 'api_key', 'resource_id'],
                    },
                },
                'params': {'provider': ['aws-ebs', 'gcp-snapshot', 'azure-backup', 'digitalocean', 'hetzner']},
                'prompts': [
                    'Create a Python action to trigger a {provider} cloud backup',
                    'Python script that initiates a backup on {provider} for a resource',
                ],
                'explanation': 'Python action that triggers a cloud backup on {provider} for a specified resource via API.',
            },
        ]


def get_generators():
    return [CloudOpsGenerator()]
