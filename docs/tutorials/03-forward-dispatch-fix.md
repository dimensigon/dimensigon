# Forward/Dispatch GET Request Fix

## Overview

In Dimensigon's mesh architecture, any node can forward a request to another
node using the `forward_or_dispatch` decorator. A bug in the forwarding logic
caused GET requests to fail with HTTP 400 (Bad Request) or 415 (Unsupported
Media Type) when the request had no body. Dimensigon 3.0 fixes this by using
`request.get_json(silent=True)` instead of `request.get_json()`.

This is a brief tutorial explaining the bug, the fix, and its impact.

## What Was the Bug

The `forward_or_dispatch` decorator in `dimensigon/web/decorators.py` extracts
a possible `destination` field from the request body to decide whether to
forward the request to another node:

```python
data = request.get_json(silent=True)
if data is not None and 'destination' in data:
    destination_id = data.get('destination')
```

Before the fix, the code called `request.get_json()` without the `silent=True`
parameter. When a GET request arrived with no body (which is normal and correct
per HTTP semantics), Flask raised a `BadRequest` exception because it could not
parse the empty body as JSON. In some Flask versions this manifested as a 415
Unsupported Media Type error if the `Content-Type` header was missing.

The same issue existed in the `_proxy_request()` helper, which reads the
request body to forward it to the destination node:

```python
req_data = request.get_json(silent=True)
```

## How `get_json(silent=True)` Fixes It

Flask's `request.get_json()` has two behaviours:

| Call | No body / invalid JSON |
|---|---|
| `request.get_json()` | Raises `BadRequest` (400) |
| `request.get_json(silent=True)` | Returns `None` |

By passing `silent=True`, the decorator gracefully handles bodyless GET
requests: `data` is `None`, the destination check is skipped, and the request
is dispatched locally as intended.

## Impact on Existing API Consumers

This fix is fully backward-compatible:

- **GET requests without a body**: Now work correctly. Previously they returned
  400 or 415.
- **GET requests with a JSON body**: Continue to work. If the body contains a
  `destination` field, the request is still forwarded.
- **POST/PUT/PATCH requests**: No change. These already had a body and were
  unaffected.
- **The `D-Destination` header**: The preferred way to specify the destination
  node. This mechanism was not affected by the bug and continues to work. The
  body-based `destination` field is a legacy compatibility path.

## Testing

### Test 1: GET request without body (previously failed)

```bash
# Basic API call -- should return 200 with server data
curl -s -w "\nHTTP %{http_code}\n" \
  -X GET https://localhost:5000/api/v1.0/servers \
  -H "Authorization: Bearer $TOKEN"

# Expected: 200 with JSON array of servers
```

### Test 2: GET request with D-Destination header

```bash
# Forward the request to a specific node
curl -s -w "\nHTTP %{http_code}\n" \
  -X GET https://localhost:5000/api/v1.0/servers \
  -H "Authorization: Bearer $TOKEN" \
  -H "D-Destination: 12345678-1234-5678-1234-567812345678"

# Expected: 200 with data from the destination node
```

### Test 3: POST request with body (always worked)

```bash
# Create an orchestration -- body is present, so no issue
curl -s -w "\nHTTP %{http_code}\n" \
  -X POST https://localhost:5000/api/v1.0/orchestrations \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "deploy-app",
    "description": "Deploy the application"
  }'

# Expected: 201 with orchestration ID
```

### Test 4: GET with destination in body (legacy compatibility)

```bash
# Legacy pattern: destination specified in the body of a GET request
curl -s -w "\nHTTP %{http_code}\n" \
  -X GET https://localhost:5000/api/v1.0/servers \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"destination": "12345678-1234-5678-1234-567812345678"}'

# Expected: 200 with data forwarded from the destination node
# Note: prefer the D-Destination header over this pattern
```

## Troubleshooting

### Still getting 400 on GET requests

Verify that you are running Dimensigon 3.0 or later. Check the version:

```bash
curl -s https://localhost:5000/health | python3 -m json.tool
# Look for "version": "2.1.0" or later
```

If the version is correct and you still get 400, the issue may be in the
`securizer` decorator rather than `forward_or_dispatch`. Check that the
`Content-Type` header is not set to `application/json` when there is no body,
as the securizer enforces JSON content type for non-GET methods:

```python
# From the securizer decorator:
if request.method != 'GET':
    if request.is_json:
        # ... process JSON body
    else:
        if request.data:
            return {'error': 'Content Type must be application/json'}, 400
```

### 415 Unsupported Media Type

This typically happens when a client sends `Content-Type: application/json`
with an empty body. Remove the `Content-Type` header for GET requests that
have no body.

## Related Features

- [Security Layer Tutorial](02-security-layer.md) -- the securizer decorator
  works alongside `forward_or_dispatch`
- Source code: `dimensigon/web/decorators.py` (functions `forward_or_dispatch`,
  `_proxy_request`, `securizer`)
