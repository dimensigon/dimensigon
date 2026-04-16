"""HTTP/API Python action generators - 12 seeds for REST, webhooks, GraphQL, etc."""

from examples.generators.base_generator import PythonActionGenerator


class HttpApiGenerator(PythonActionGenerator):
    category = "python.http_api"
    subcategory = "http_api"

    def seeds(self):
        return [
            {
                'name': 'http-get-status',
                'template': {
                    'name': 'HTTP GET {service} health',
                    'action_type': 'PYTHON',
                    'code': (
                        'import json\n'
                        'import urllib.request\n'
                        'import sys\n\n'
                        'url = "{{input.url}}"\n'
                        'req = urllib.request.Request(url, method="GET")\n'
                        'if "{{input.auth_header}}":\n'
                        '    req.add_header("Authorization", "{{input.auth_header}}")\n'
                        'try:\n'
                        '    resp = urllib.request.urlopen(req, timeout=30)\n'
                        '    body = json.loads(resp.read().decode())\n'
                        '    status = resp.getcode()\n'
                        '    if status == 200:\n'
                        '        print(json.dumps({{"status": "ok", "code": status, "body": body}}))\n'
                        '    else:\n'
                        '        print(json.dumps({{"status": "error", "code": status}}))\n'
                        '        sys.exit(1)\n'
                        'except Exception as e:\n'
                        '    print(json.dumps({{"status": "error", "message": str(e)}}))\n'
                        '    sys.exit(1)\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'url': {'type': 'string', 'description': 'URL to send GET request to'},
                            'auth_header': {'type': 'string', 'description': 'Authorization header value (optional)'},
                        },
                        'required': ['url'],
                    },
                },
                'params': {'service': ['nginx', 'apache', 'traefik', 'haproxy', 'envoy', 'caddy']},
                'prompts': [
                    'Create a Python action to GET {service} health endpoint and check status',
                    'Python script that performs HTTP GET against {service} and validates response',
                ],
                'explanation': 'Python action that sends an HTTP GET request to a {service} endpoint, checks the response status code, and returns the result as JSON.',
            },
            {
                'name': 'http-post-json',
                'template': {
                    'name': 'HTTP POST JSON to {service}',
                    'action_type': 'PYTHON',
                    'code': (
                        'import json\n'
                        'import urllib.request\n'
                        'import sys\n\n'
                        'url = "{{input.url}}"\n'
                        'payload = json.loads(\'{{input.payload}}\')\n'
                        'data = json.dumps(payload).encode("utf-8")\n'
                        'req = urllib.request.Request(url, data=data, method="POST")\n'
                        'req.add_header("Content-Type", "application/json")\n'
                        'if "{{input.api_key}}":\n'
                        '    req.add_header("Authorization", "Bearer {{input.api_key}}")\n'
                        'try:\n'
                        '    resp = urllib.request.urlopen(req, timeout=30)\n'
                        '    body = resp.read().decode()\n'
                        '    print(json.dumps({{"status": resp.getcode(), "response": json.loads(body)}}))\n'
                        'except urllib.error.HTTPError as e:\n'
                        '    print(json.dumps({{"status": e.code, "error": e.read().decode()}}))\n'
                        '    sys.exit(1)\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'url': {'type': 'string', 'description': 'Target URL for POST request'},
                            'payload': {'type': 'string', 'description': 'JSON payload string'},
                            'api_key': {'type': 'string', 'description': 'Bearer token for auth'},
                        },
                        'required': ['url', 'payload'],
                    },
                },
                'params': {'service': ['slack', 'jira', 'github', 'gitlab', 'datadog', 'pagerduty']},
                'prompts': [
                    'Create a Python action to POST JSON data to {service} API',
                    'Python script that sends a JSON payload via HTTP POST to {service}',
                ],
                'explanation': 'Python action that sends an HTTP POST request with a JSON payload to {service}, including optional bearer token authentication.',
            },
            {
                'name': 'http-put-update',
                'template': {
                    'name': 'HTTP PUT update {service}',
                    'action_type': 'PYTHON',
                    'code': (
                        'import json\n'
                        'import urllib.request\n'
                        'import sys\n\n'
                        'url = "{{input.url}}"\n'
                        'payload = json.loads(\'{{input.payload}}\')\n'
                        'data = json.dumps(payload).encode("utf-8")\n'
                        'req = urllib.request.Request(url, data=data, method="PUT")\n'
                        'req.add_header("Content-Type", "application/json")\n'
                        'req.add_header("Authorization", "Bearer {{input.api_key}}")\n'
                        'try:\n'
                        '    resp = urllib.request.urlopen(req, timeout=30)\n'
                        '    result = json.loads(resp.read().decode())\n'
                        '    print(json.dumps({{"status": "updated", "code": resp.getcode(), "result": result}}))\n'
                        'except urllib.error.HTTPError as e:\n'
                        '    print(json.dumps({{"status": "failed", "code": e.code, "error": e.read().decode()}}))\n'
                        '    sys.exit(1)\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'url': {'type': 'string', 'description': 'Resource URL to update'},
                            'payload': {'type': 'string', 'description': 'JSON update payload'},
                            'api_key': {'type': 'string', 'description': 'API key for auth'},
                        },
                        'required': ['url', 'payload', 'api_key'],
                    },
                },
                'params': {'service': ['consul', 'vault', 'etcd', 'zookeeper']},
                'prompts': [
                    'Create a Python action to update a {service} resource via HTTP PUT',
                    'Python script for PUT request to modify {service} configuration',
                ],
                'explanation': 'Python action that sends an HTTP PUT request to update a resource in {service} with JSON payload and bearer auth.',
            },
            {
                'name': 'http-delete-resource',
                'template': {
                    'name': 'HTTP DELETE {service} resource',
                    'action_type': 'PYTHON',
                    'code': (
                        'import json\n'
                        'import urllib.request\n'
                        'import sys\n\n'
                        'url = "{{input.url}}"\n'
                        'req = urllib.request.Request(url, method="DELETE")\n'
                        'req.add_header("Authorization", "Bearer {{input.api_key}}")\n'
                        'req.add_header("Content-Type", "application/json")\n'
                        'try:\n'
                        '    resp = urllib.request.urlopen(req, timeout=30)\n'
                        '    code = resp.getcode()\n'
                        '    if code in (200, 202, 204):\n'
                        '        print(json.dumps({{"status": "deleted", "code": code}}))\n'
                        '    else:\n'
                        '        print(json.dumps({{"status": "unexpected", "code": code}}))\n'
                        '        sys.exit(1)\n'
                        'except urllib.error.HTTPError as e:\n'
                        '    print(json.dumps({{"status": "error", "code": e.code}}))\n'
                        '    sys.exit(1)\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'url': {'type': 'string', 'description': 'Resource URL to delete'},
                            'api_key': {'type': 'string', 'description': 'API key for auth'},
                        },
                        'required': ['url', 'api_key'],
                    },
                },
                'params': {'service': ['kong', 'nginx', 'consul', 'vault', 'kubernetes']},
                'prompts': [
                    'Create a Python action to DELETE a {service} resource via API',
                    'Python script to remove a {service} resource via HTTP DELETE',
                ],
                'explanation': 'Python action that sends an HTTP DELETE request to remove a {service} resource with bearer token authentication.',
            },
            {
                'name': 'http-poll-ready',
                'template': {
                    'name': 'Poll {service} until ready',
                    'action_type': 'PYTHON',
                    'code': (
                        'import json\n'
                        'import urllib.request\n'
                        'import time\n'
                        'import sys\n\n'
                        'url = "{{input.url}}"\n'
                        'max_retries = int("{{input.max_retries}}" or "30")\n'
                        'interval = int("{{input.interval}}" or "10")\n\n'
                        'for attempt in range(1, max_retries + 1):\n'
                        '    try:\n'
                        '        req = urllib.request.Request(url, method="GET")\n'
                        '        resp = urllib.request.urlopen(req, timeout=10)\n'
                        '        body = json.loads(resp.read().decode())\n'
                        '        if resp.getcode() == 200:\n'
                        '            print(json.dumps({{"status": "ready", "attempt": attempt, "body": body}}))\n'
                        '            sys.exit(0)\n'
                        '    except Exception:\n'
                        '        pass\n'
                        '    print(f"Attempt {{attempt}}/{{max_retries}} - not ready, waiting {{interval}}s...")\n'
                        '    time.sleep(interval)\n\n'
                        'print(json.dumps({{"status": "timeout", "attempts": max_retries}}))\n'
                        'sys.exit(1)\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'url': {'type': 'string', 'description': 'Endpoint URL to poll'},
                            'max_retries': {'type': 'string', 'description': 'Max number of retries (default 30)'},
                            'interval': {'type': 'string', 'description': 'Seconds between retries (default 10)'},
                        },
                        'required': ['url'],
                    },
                },
                'params': {'service': ['elasticsearch', 'rabbitmq', 'kafka', 'redis', 'postgres']},
                'prompts': [
                    'Create a Python action that polls {service} endpoint until it is ready',
                    'Python script to wait for {service} to become available by polling',
                ],
                'explanation': 'Python action that repeatedly polls a {service} health endpoint until it returns HTTP 200 or max retries are exhausted.',
            },
            {
                'name': 'http-download-file',
                'template': {
                    'name': 'Download file from {service}',
                    'action_type': 'PYTHON',
                    'code': (
                        'import urllib.request\n'
                        'import os\n'
                        'import json\n'
                        'import sys\n\n'
                        'url = "{{input.url}}"\n'
                        'dest = "{{input.destination}}"\n\n'
                        'dest_dir = os.path.dirname(dest)\n'
                        'if dest_dir and not os.path.isdir(dest_dir):\n'
                        '    os.makedirs(dest_dir, exist_ok=True)\n\n'
                        'try:\n'
                        '    urllib.request.urlretrieve(url, dest)\n'
                        '    size = os.path.getsize(dest)\n'
                        '    print(json.dumps({{"status": "downloaded", "path": dest, "size_bytes": size}}))\n'
                        'except Exception as e:\n'
                        '    print(json.dumps({{"status": "error", "message": str(e)}}))\n'
                        '    sys.exit(1)\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'url': {'type': 'string', 'description': 'URL of the file to download'},
                            'destination': {'type': 'string', 'description': 'Local file path to save to'},
                        },
                        'required': ['url', 'destination'],
                    },
                },
                'params': {'service': ['github', 'artifactory', 'nexus', 's3', 'gcs']},
                'prompts': [
                    'Create a Python action to download a file from {service}',
                    'Python script that downloads an artifact from {service} to local disk',
                ],
                'explanation': 'Python action that downloads a file from {service} to a specified local path, creating directories as needed.',
            },
            {
                'name': 'http-upload-file',
                'template': {
                    'name': 'Upload file to {service}',
                    'action_type': 'PYTHON',
                    'code': (
                        'import urllib.request\n'
                        'import os\n'
                        'import json\n'
                        'import sys\n\n'
                        'url = "{{input.url}}"\n'
                        'filepath = "{{input.filepath}}"\n'
                        'api_key = "{{input.api_key}}"\n\n'
                        'if not os.path.isfile(filepath):\n'
                        '    print(json.dumps({{"status": "error", "message": f"File not found: {{filepath}}"}}))\n'
                        '    sys.exit(1)\n\n'
                        'with open(filepath, "rb") as f:\n'
                        '    data = f.read()\n\n'
                        'req = urllib.request.Request(url, data=data, method="PUT")\n'
                        'req.add_header("Content-Type", "application/octet-stream")\n'
                        'req.add_header("Authorization", "Bearer " + api_key)\n'
                        'try:\n'
                        '    resp = urllib.request.urlopen(req, timeout=120)\n'
                        '    print(json.dumps({{"status": "uploaded", "code": resp.getcode(), "size": len(data)}}))\n'
                        'except urllib.error.HTTPError as e:\n'
                        '    print(json.dumps({{"status": "error", "code": e.code, "message": e.read().decode()}}))\n'
                        '    sys.exit(1)\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'url': {'type': 'string', 'description': 'Upload destination URL'},
                            'filepath': {'type': 'string', 'description': 'Local file path to upload'},
                            'api_key': {'type': 'string', 'description': 'API key for authentication'},
                        },
                        'required': ['url', 'filepath', 'api_key'],
                    },
                },
                'params': {'service': ['artifactory', 'nexus', 's3', 'minio', 'gcs']},
                'prompts': [
                    'Create a Python action to upload a file to {service}',
                    'Python script for uploading artifacts to {service} via HTTP PUT',
                ],
                'explanation': 'Python action that uploads a local file to {service} via HTTP PUT with bearer token auth.',
            },
            {
                'name': 'http-pagination',
                'template': {
                    'name': 'Paginated GET from {service}',
                    'action_type': 'PYTHON',
                    'code': (
                        'import json\n'
                        'import urllib.request\n'
                        'import urllib.parse\n'
                        'import sys\n\n'
                        'base_url = "{{input.url}}"\n'
                        'max_pages = int("{{input.max_pages}}" or "10")\n'
                        'all_items = []\n'
                        'page = 1\n\n'
                        'while page <= max_pages:\n'
                        '    params = urllib.parse.urlencode({{"page": page, "per_page": 100}})\n'
                        '    url = f"{{base_url}}?{{params}}"\n'
                        '    req = urllib.request.Request(url, method="GET")\n'
                        '    req.add_header("Authorization", "Bearer {{input.api_key}}")\n'
                        '    try:\n'
                        '        resp = urllib.request.urlopen(req, timeout=30)\n'
                        '        data = json.loads(resp.read().decode())\n'
                        '        items = data if isinstance(data, list) else data.get("items", data.get("results", []))\n'
                        '        if not items:\n'
                        '            break\n'
                        '        all_items.extend(items)\n'
                        '        page += 1\n'
                        '    except Exception as e:\n'
                        '        print(json.dumps({{"status": "error", "page": page, "message": str(e)}}))\n'
                        '        sys.exit(1)\n\n'
                        'print(json.dumps({{"status": "ok", "total_items": len(all_items), "pages_fetched": page - 1}}))\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'url': {'type': 'string', 'description': 'Base API URL (without pagination params)'},
                            'api_key': {'type': 'string', 'description': 'API key for auth'},
                            'max_pages': {'type': 'string', 'description': 'Maximum pages to fetch (default 10)'},
                        },
                        'required': ['url', 'api_key'],
                    },
                },
                'params': {'service': ['github', 'gitlab', 'jira', 'confluence', 'bitbucket']},
                'prompts': [
                    'Create a Python action that paginates through {service} API results',
                    'Python script to collect all pages of results from {service} API',
                ],
                'explanation': 'Python action that fetches paginated results from {service} API, collecting all items across multiple pages.',
            },
            {
                'name': 'oauth-token-refresh',
                'template': {
                    'name': 'OAuth token refresh for {service}',
                    'action_type': 'PYTHON',
                    'code': (
                        'import json\n'
                        'import urllib.request\n'
                        'import urllib.parse\n'
                        'import sys\n\n'
                        'token_url = "{{input.token_url}}"\n'
                        'client_id = "{{input.client_id}}"\n'
                        'client_secret = "{{input.client_secret}}"\n'
                        'refresh_token = "{{input.refresh_token}}"\n\n'
                        'data = urllib.parse.urlencode({{\n'
                        '    "grant_type": "refresh_token",\n'
                        '    "client_id": client_id,\n'
                        '    "client_secret": client_secret,\n'
                        '    "refresh_token": refresh_token,\n'
                        '}}).encode("utf-8")\n\n'
                        'req = urllib.request.Request(token_url, data=data, method="POST")\n'
                        'req.add_header("Content-Type", "application/x-www-form-urlencoded")\n'
                        'try:\n'
                        '    resp = urllib.request.urlopen(req, timeout=30)\n'
                        '    tokens = json.loads(resp.read().decode())\n'
                        '    print(json.dumps({{\n'
                        '        "status": "refreshed",\n'
                        '        "access_token": tokens.get("access_token", "")[:10] + "...",\n'
                        '        "expires_in": tokens.get("expires_in"),\n'
                        '    }}))\n'
                        'except urllib.error.HTTPError as e:\n'
                        '    print(json.dumps({{"status": "error", "code": e.code, "message": e.read().decode()}}))\n'
                        '    sys.exit(1)\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'token_url': {'type': 'string', 'description': 'OAuth token endpoint URL'},
                            'client_id': {'type': 'string', 'description': 'OAuth client ID'},
                            'client_secret': {'type': 'string', 'description': 'OAuth client secret'},
                            'refresh_token': {'type': 'string', 'description': 'Refresh token'},
                        },
                        'required': ['token_url', 'client_id', 'client_secret', 'refresh_token'],
                    },
                },
                'params': {'service': ['google', 'azure', 'okta', 'auth0', 'keycloak']},
                'prompts': [
                    'Create a Python action to refresh an OAuth token for {service}',
                    'Python script that uses a refresh token to get a new access token from {service}',
                ],
                'explanation': 'Python action that refreshes an OAuth2 access token using a refresh token grant against {service} token endpoint.',
            },
            {
                'name': 'webhook-dispatch',
                'template': {
                    'name': 'Dispatch webhook to {service}',
                    'action_type': 'PYTHON',
                    'code': (
                        'import json\n'
                        'import urllib.request\n'
                        'import hashlib\n'
                        'import hmac\n'
                        'import sys\n\n'
                        'webhook_url = "{{input.webhook_url}}"\n'
                        'event_type = "{{input.event_type}}"\n'
                        'payload_str = \'{{input.payload}}\'\n'
                        'secret = "{{input.secret}}"\n\n'
                        'payload = {{"event": event_type, "data": json.loads(payload_str)}}\n'
                        'body = json.dumps(payload).encode("utf-8")\n\n'
                        'req = urllib.request.Request(webhook_url, data=body, method="POST")\n'
                        'req.add_header("Content-Type", "application/json")\n'
                        'req.add_header("X-Event-Type", event_type)\n'
                        'if secret:\n'
                        '    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()\n'
                        '    req.add_header("X-Signature", "sha256=" + sig)\n\n'
                        'try:\n'
                        '    resp = urllib.request.urlopen(req, timeout=30)\n'
                        '    print(json.dumps({{"status": "dispatched", "code": resp.getcode()}}))\n'
                        'except urllib.error.HTTPError as e:\n'
                        '    print(json.dumps({{"status": "error", "code": e.code}}))\n'
                        '    sys.exit(1)\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'webhook_url': {'type': 'string', 'description': 'Webhook endpoint URL'},
                            'event_type': {'type': 'string', 'description': 'Event type identifier'},
                            'payload': {'type': 'string', 'description': 'JSON payload string'},
                            'secret': {'type': 'string', 'description': 'HMAC secret for signing (optional)'},
                        },
                        'required': ['webhook_url', 'event_type', 'payload'],
                    },
                },
                'params': {'service': ['github', 'gitlab', 'jenkins', 'argocd', 'flux']},
                'prompts': [
                    'Create a Python action to dispatch a signed webhook to {service}',
                    'Python script to send an HMAC-signed webhook event to {service}',
                ],
                'explanation': 'Python action that dispatches a webhook event to {service} with optional HMAC-SHA256 signature verification.',
            },
            {
                'name': 'graphql-query',
                'template': {
                    'name': 'GraphQL query to {service}',
                    'action_type': 'PYTHON',
                    'code': (
                        'import json\n'
                        'import urllib.request\n'
                        'import sys\n\n'
                        'url = "{{input.graphql_url}}"\n'
                        'query = "{{input.query}}"\n'
                        'variables = json.loads(\'{{input.variables}}\' or "{{}}")\n\n'
                        'payload = json.dumps({{"query": query, "variables": variables}}).encode("utf-8")\n'
                        'req = urllib.request.Request(url, data=payload, method="POST")\n'
                        'req.add_header("Content-Type", "application/json")\n'
                        'req.add_header("Authorization", "Bearer {{input.api_token}}")\n\n'
                        'try:\n'
                        '    resp = urllib.request.urlopen(req, timeout=30)\n'
                        '    result = json.loads(resp.read().decode())\n'
                        '    if "errors" in result:\n'
                        '        print(json.dumps({{"status": "error", "errors": result["errors"]}}))\n'
                        '        sys.exit(1)\n'
                        '    print(json.dumps({{"status": "ok", "data": result.get("data", {{}})}}))\n'
                        'except urllib.error.HTTPError as e:\n'
                        '    print(json.dumps({{"status": "error", "code": e.code}}))\n'
                        '    sys.exit(1)\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'graphql_url': {'type': 'string', 'description': 'GraphQL endpoint URL'},
                            'query': {'type': 'string', 'description': 'GraphQL query string'},
                            'variables': {'type': 'string', 'description': 'JSON string of query variables'},
                            'api_token': {'type': 'string', 'description': 'Bearer token for auth'},
                        },
                        'required': ['graphql_url', 'query', 'api_token'],
                    },
                },
                'params': {'service': ['github', 'gitlab', 'shopify', 'hasura', 'apollo']},
                'prompts': [
                    'Create a Python action to execute a GraphQL query against {service}',
                    'Python script that runs a GraphQL query on {service} API',
                ],
                'explanation': 'Python action that executes a GraphQL query against {service} API with variables and bearer token auth.',
            },
            {
                'name': 'rate-limited-retry',
                'template': {
                    'name': 'Rate-limited request to {service}',
                    'action_type': 'PYTHON',
                    'code': (
                        'import json\n'
                        'import urllib.request\n'
                        'import urllib.error\n'
                        'import time\n'
                        'import sys\n\n'
                        'url = "{{input.url}}"\n'
                        'max_retries = int("{{input.max_retries}}" or "5")\n'
                        'api_key = "{{input.api_key}}"\n\n'
                        'for attempt in range(max_retries):\n'
                        '    req = urllib.request.Request(url, method="GET")\n'
                        '    req.add_header("Authorization", "Bearer " + api_key)\n'
                        '    try:\n'
                        '        resp = urllib.request.urlopen(req, timeout=30)\n'
                        '        data = json.loads(resp.read().decode())\n'
                        '        remaining = resp.headers.get("X-RateLimit-Remaining", "unknown")\n'
                        '        print(json.dumps({{"status": "ok", "attempt": attempt + 1, "rate_remaining": remaining, "data": data}}))\n'
                        '        sys.exit(0)\n'
                        '    except urllib.error.HTTPError as e:\n'
                        '        if e.code == 429:\n'
                        '            retry_after = int(e.headers.get("Retry-After", 2 ** attempt))\n'
                        '            print(f"Rate limited, retrying in {{retry_after}}s (attempt {{attempt + 1}}/{{max_retries}})")\n'
                        '            time.sleep(retry_after)\n'
                        '        else:\n'
                        '            print(json.dumps({{"status": "error", "code": e.code}}))\n'
                        '            sys.exit(1)\n\n'
                        'print(json.dumps({{"status": "exhausted", "message": "Max retries reached"}}))\n'
                        'sys.exit(1)\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'url': {'type': 'string', 'description': 'API endpoint URL'},
                            'api_key': {'type': 'string', 'description': 'API key for auth'},
                            'max_retries': {'type': 'string', 'description': 'Max retries on rate limit (default 5)'},
                        },
                        'required': ['url', 'api_key'],
                    },
                },
                'params': {'service': ['github', 'twitter', 'stripe', 'cloudflare', 'datadog']},
                'prompts': [
                    'Create a Python action with rate-limit retry logic for {service} API',
                    'Python script that handles HTTP 429 rate limiting when calling {service}',
                ],
                'explanation': 'Python action that calls {service} API with automatic retry on HTTP 429 rate limits using exponential backoff.',
            },
            {
                'name': 'soap-request',
                'template': {
                    'name': 'SOAP request to {service}',
                    'action_type': 'PYTHON',
                    'code': (
                        'import json\n'
                        'import urllib.request\n'
                        'import sys\n\n'
                        'url = "{{input.wsdl_url}}"\n'
                        'soap_action = "{{input.soap_action}}"\n'
                        'soap_body = \'{{input.soap_body}}\'\n\n'
                        'envelope = (\n'
                        '    \'<?xml version="1.0" encoding="UTF-8"?>\'\n'
                        '    \'<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">\'\n'
                        '    \'<soap:Body>\' + soap_body + \'</soap:Body>\'\n'
                        '    \'</soap:Envelope>\'\n'
                        ')\n\n'
                        'req = urllib.request.Request(url, data=envelope.encode("utf-8"), method="POST")\n'
                        'req.add_header("Content-Type", "text/xml; charset=utf-8")\n'
                        'req.add_header("SOAPAction", soap_action)\n'
                        'try:\n'
                        '    resp = urllib.request.urlopen(req, timeout=30)\n'
                        '    body = resp.read().decode()\n'
                        '    print(json.dumps({{"status": "ok", "code": resp.getcode(), "response_length": len(body)}}))\n'
                        'except urllib.error.HTTPError as e:\n'
                        '    print(json.dumps({{"status": "error", "code": e.code, "message": e.read().decode()[:500]}}))\n'
                        '    sys.exit(1)\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'wsdl_url': {'type': 'string', 'description': 'SOAP endpoint URL'},
                            'soap_action': {'type': 'string', 'description': 'SOAPAction header value'},
                            'soap_body': {'type': 'string', 'description': 'XML content for the SOAP body'},
                        },
                        'required': ['wsdl_url', 'soap_action', 'soap_body'],
                    },
                },
                'params': {'service': ['payment-gateway', 'erp', 'crm', 'legacy-api']},
                'prompts': [
                    'Create a Python action to send a SOAP request to {service}',
                    'Python script that calls a {service} SOAP web service with an XML envelope',
                ],
                'explanation': 'Python action that sends a SOAP XML request to {service} endpoint with proper envelope wrapping and SOAPAction header.',
            },
            {
                'name': 'grpc-health-http2',
                'template': {
                    'name': 'gRPC health check for {service}',
                    'action_type': 'PYTHON',
                    'code': (
                        'import json\n'
                        'import http.client\n'
                        'import ssl\n'
                        'import sys\n\n'
                        'host = "{{input.host}}"\n'
                        'port = int("{{input.port}}" or "443")\n'
                        'use_tls = "{{input.use_tls}}" != "false"\n'
                        'timeout = int("{{input.timeout}}" or "10")\n\n'
                        'try:\n'
                        '    if use_tls:\n'
                        '        ctx = ssl.create_default_context()\n'
                        '        conn = http.client.HTTPSConnection(host, port, timeout=timeout, context=ctx)\n'
                        '    else:\n'
                        '        conn = http.client.HTTPConnection(host, port, timeout=timeout)\n'
                        '    conn.request("POST", "/grpc.health.v1.Health/Check",\n'
                        '                 headers={{"Content-Type": "application/grpc", "TE": "trailers"}})\n'
                        '    resp = conn.getresponse()\n'
                        '    body = resp.read()\n'
                        '    conn.close()\n'
                        '    if resp.status == 200:\n'
                        '        print(json.dumps({{"status": "ok", "code": resp.status, "message": "gRPC service healthy"}}))\n'
                        '    else:\n'
                        '        print(json.dumps({{"status": "error", "code": resp.status}}))\n'
                        '        sys.exit(1)\n'
                        'except Exception as e:\n'
                        '    print(json.dumps({{"status": "error", "message": str(e)}}))\n'
                        '    sys.exit(1)\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'host': {'type': 'string', 'description': 'gRPC server hostname'},
                            'port': {'type': 'string', 'description': 'gRPC server port (default 443)'},
                            'use_tls': {'type': 'string', 'description': 'Use TLS: true/false (default true)'},
                            'timeout': {'type': 'string', 'description': 'Connection timeout in seconds (default 10)'},
                        },
                        'required': ['host'],
                    },
                },
                'params': {'service': ['api-gateway', 'microservice', 'auth-service', 'data-service']},
                'prompts': [
                    'Create a Python action to perform a gRPC health check on {service}',
                    'Python script that checks {service} gRPC health endpoint over HTTP/2',
                ],
                'explanation': 'Python action that performs a gRPC health check on {service} using the standard Health/Check endpoint over HTTP.',
            },
            {
                'name': 'websocket-ping',
                'template': {
                    'name': 'WebSocket ping to {service}',
                    'action_type': 'PYTHON',
                    'code': (
                        'import json\n'
                        'import socket\n'
                        'import hashlib\n'
                        'import base64\n'
                        'import os\n'
                        'import sys\n\n'
                        'host = "{{input.host}}"\n'
                        'port = int("{{input.port}}" or "80")\n'
                        'path = "{{input.path}}" or "/"\n'
                        'timeout = int("{{input.timeout}}" or "10")\n\n'
                        'ws_key = base64.b64encode(os.urandom(16)).decode()\n'
                        'try:\n'
                        '    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n'
                        '    sock.settimeout(timeout)\n'
                        '    sock.connect((host, port))\n'
                        '    handshake = (\n'
                        '        f"GET {{path}} HTTP/1.1\\r\\n"\n'
                        '        f"Host: {{host}}\\r\\n"\n'
                        '        f"Upgrade: websocket\\r\\n"\n'
                        '        f"Connection: Upgrade\\r\\n"\n'
                        '        f"Sec-WebSocket-Key: {{ws_key}}\\r\\n"\n'
                        '        f"Sec-WebSocket-Version: 13\\r\\n\\r\\n"\n'
                        '    )\n'
                        '    sock.sendall(handshake.encode())\n'
                        '    resp = sock.recv(4096).decode()\n'
                        '    sock.close()\n'
                        '    if "101" in resp and "Upgrade" in resp:\n'
                        '        print(json.dumps({{"status": "ok", "message": "WebSocket handshake successful"}}))\n'
                        '    else:\n'
                        '        print(json.dumps({{"status": "error", "message": "Handshake failed", "response": resp[:200]}}))\n'
                        '        sys.exit(1)\n'
                        'except Exception as e:\n'
                        '    print(json.dumps({{"status": "error", "message": str(e)}}))\n'
                        '    sys.exit(1)\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'host': {'type': 'string', 'description': 'WebSocket server hostname'},
                            'port': {'type': 'string', 'description': 'WebSocket server port (default 80)'},
                            'path': {'type': 'string', 'description': 'WebSocket endpoint path (default /)'},
                            'timeout': {'type': 'string', 'description': 'Connection timeout in seconds (default 10)'},
                        },
                        'required': ['host'],
                    },
                },
                'params': {'service': ['chat', 'realtime', 'notifications', 'streaming', 'dashboard']},
                'prompts': [
                    'Create a Python action to ping a {service} WebSocket endpoint',
                    'Python script that tests the {service} WebSocket handshake',
                ],
                'explanation': 'Python action that tests {service} WebSocket connectivity by performing the HTTP upgrade handshake.',
            },
            {
                'name': 'multipart-upload',
                'template': {
                    'name': 'Multipart upload to {service}',
                    'action_type': 'PYTHON',
                    'code': (
                        'import json\n'
                        'import urllib.request\n'
                        'import os\n'
                        'import uuid\n'
                        'import sys\n\n'
                        'url = "{{input.url}}"\n'
                        'filepath = "{{input.filepath}}"\n'
                        'field_name = "{{input.field_name}}" or "file"\n'
                        'api_key = "{{input.api_key}}"\n\n'
                        'if not os.path.isfile(filepath):\n'
                        '    print(json.dumps({{"status": "error", "message": f"File not found: {{filepath}}"}}))\n'
                        '    sys.exit(1)\n\n'
                        'boundary = uuid.uuid4().hex\n'
                        'filename = os.path.basename(filepath)\n'
                        'with open(filepath, "rb") as f:\n'
                        '    file_data = f.read()\n\n'
                        'body = (\n'
                        '    f"--{{boundary}}\\r\\n"\n'
                        '    f"Content-Disposition: form-data; name=\\"{{field_name}}\\"; filename=\\"{{filename}}\\"\\r\\n"\n'
                        '    f"Content-Type: application/octet-stream\\r\\n\\r\\n"\n'
                        ').encode() + file_data + f"\\r\\n--{{boundary}}--\\r\\n".encode()\n\n'
                        'req = urllib.request.Request(url, data=body, method="POST")\n'
                        'req.add_header("Content-Type", f"multipart/form-data; boundary={{boundary}}")\n'
                        'if api_key:\n'
                        '    req.add_header("Authorization", "Bearer " + api_key)\n'
                        'try:\n'
                        '    resp = urllib.request.urlopen(req, timeout=120)\n'
                        '    print(json.dumps({{"status": "uploaded", "code": resp.getcode(), "size": len(file_data), "filename": filename}}))\n'
                        'except urllib.error.HTTPError as e:\n'
                        '    print(json.dumps({{"status": "error", "code": e.code, "message": e.read().decode()[:500]}}))\n'
                        '    sys.exit(1)\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'url': {'type': 'string', 'description': 'Upload endpoint URL'},
                            'filepath': {'type': 'string', 'description': 'Local file path to upload'},
                            'field_name': {'type': 'string', 'description': 'Form field name for the file (default: file)'},
                            'api_key': {'type': 'string', 'description': 'Bearer token for auth (optional)'},
                        },
                        'required': ['url', 'filepath'],
                    },
                },
                'params': {'service': ['s3', 'artifactory', 'nexus', 'minio', 'github']},
                'prompts': [
                    'Create a Python action to upload a file via multipart form to {service}',
                    'Python script that performs a multipart file upload to {service}',
                ],
                'explanation': 'Python action that uploads a file to {service} using multipart/form-data encoding with optional bearer auth.',
            },
            {
                'name': 'api-version-check',
                'template': {
                    'name': 'API version check for {service}',
                    'action_type': 'PYTHON',
                    'code': (
                        'import json\n'
                        'import urllib.request\n'
                        'import sys\n\n'
                        'url = "{{input.url}}"\n'
                        'expected_version = "{{input.expected_version}}"\n'
                        'version_field = "{{input.version_field}}" or "version"\n\n'
                        'req = urllib.request.Request(url, method="GET")\n'
                        'req.add_header("Accept", "application/json")\n'
                        'if "{{input.api_key}}":\n'
                        '    req.add_header("Authorization", "Bearer {{input.api_key}}")\n'
                        'try:\n'
                        '    resp = urllib.request.urlopen(req, timeout=15)\n'
                        '    data = json.loads(resp.read().decode())\n'
                        '    actual_version = str(data.get(version_field, ""))\n'
                        '    if not actual_version:\n'
                        '        for key in data:\n'
                        '            if "version" in key.lower():\n'
                        '                actual_version = str(data[key])\n'
                        '                break\n'
                        '    match = actual_version == expected_version\n'
                        '    print(json.dumps({{\n'
                        '        "status": "ok" if match else "mismatch",\n'
                        '        "expected": expected_version,\n'
                        '        "actual": actual_version,\n'
                        '        "match": match,\n'
                        '    }}))\n'
                        '    if not match:\n'
                        '        sys.exit(1)\n'
                        'except Exception as e:\n'
                        '    print(json.dumps({{"status": "error", "message": str(e)}}))\n'
                        '    sys.exit(1)\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'url': {'type': 'string', 'description': 'API version endpoint URL'},
                            'expected_version': {'type': 'string', 'description': 'Expected API version string'},
                            'version_field': {'type': 'string', 'description': 'JSON field containing the version (default: version)'},
                            'api_key': {'type': 'string', 'description': 'Bearer token for auth (optional)'},
                        },
                        'required': ['url', 'expected_version'],
                    },
                },
                'params': {'service': ['api-gateway', 'backend', 'microservice', 'platform']},
                'prompts': [
                    'Create a Python action to check the {service} API version',
                    'Python script that verifies the deployed {service} API version matches expected',
                ],
                'explanation': 'Python action that checks the deployed {service} API version against an expected value for deployment verification.',
            },
        ]


def get_generators():
    return [HttpApiGenerator()]
