# Tutorial 16: Audit Log

Track every significant action in your Dimensigon cluster with the immutable audit log. This tutorial covers viewing, filtering, and understanding audit entries for compliance and security purposes.

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [What Gets Logged](#what-gets-logged)
4. [Audit Entry Fields](#audit-entry-fields)
5. [Viewing the Audit Log](#viewing-the-audit-log)
6. [Filtering Audit Entries](#filtering-audit-entries)
7. [Pagination](#pagination)
8. [The @audit_log Decorator](#the-audit_log-decorator)
9. [Immutability](#immutability)
10. [Access Control](#access-control)
11. [Configuration Reference](#configuration-reference)
12. [Related Features](#related-features)

---

## Overview

The audit log provides an immutable, append-only record of every significant action performed within Dimensigon. It answers the fundamental compliance questions:

- **Who** performed the action?
- **What** action was taken?
- **When** did it happen?
- **Where** did the request originate (IP address)?
- **On what** resource was the action performed?

This is essential for:

- Regulatory compliance (SOC 2, ISO 27001, HIPAA)
- Security incident investigation
- Operational troubleshooting
- Change management tracking

---

## Prerequisites

- A running Dimensigon 3.0 cluster
- An **administrator** account (audit log access is restricted to administrators)
- A valid JWT token

### Obtain a JWT Token

```bash
TOKEN=$(curl -s -X POST http://localhost:5000/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "your_password"
  }' | jq -r '.access_token')
```

---

## What Gets Logged

Dimensigon automatically records audit entries for the following categories of actions:

### Authentication Events

| Action              | Description                                  |
|---------------------|----------------------------------------------|
| `login.success`     | Successful user authentication               |
| `login.failed`      | Failed authentication attempt                |
| `token.refreshed`   | JWT token refreshed                          |
| `logout`            | User explicitly logged out                   |

### CRUD Operations

| Action              | Description                                  |
|---------------------|----------------------------------------------|
| `create`            | A new resource was created                   |
| `read`              | A resource was retrieved (sensitive resources only) |
| `update`            | An existing resource was modified            |
| `delete`            | A resource was removed                       |

### Execution Events

| Action                    | Description                              |
|---------------------------|------------------------------------------|
| `execution.launched`      | An orchestration execution was started   |
| `execution.cancelled`     | An orchestration execution was cancelled |
| `execution.completed`     | An orchestration execution finished      |

### Administrative Actions

| Action                    | Description                              |
|---------------------------|------------------------------------------|
| `user.created`            | A new user account was created           |
| `user.updated`            | A user account was modified              |
| `user.deleted`            | A user account was removed               |
| `role.assigned`           | A role was assigned to a user            |
| `role.revoked`            | A role was revoked from a user           |
| `webhook.created`         | A webhook subscription was registered    |
| `webhook.updated`         | A webhook subscription was modified      |
| `webhook.deleted`         | A webhook subscription was removed       |
| `schedule.created`        | A schedule was created                   |
| `schedule.updated`        | A schedule was modified                  |
| `schedule.toggled`        | A schedule was enabled or disabled       |
| `schedule.deleted`        | A schedule was deleted                   |
| `orchestration.rollback`  | An orchestration was rolled back         |

---

## Audit Entry Fields

Every audit log entry contains the following fields:

| Field           | Type   | Description                                              |
|-----------------|--------|----------------------------------------------------------|
| `id`            | string | Unique identifier for the audit entry                    |
| `timestamp`     | string | ISO 8601 timestamp of when the action occurred           |
| `user`          | string | Username of the authenticated user who performed the action |
| `action`        | string | The action that was performed (e.g., `create`, `login.success`) |
| `resource_type` | string | Type of resource affected (e.g., `orchestration`, `webhook`, `user`) |
| `resource_id`   | string | Identifier of the specific resource affected             |
| `ip`            | string | IP address of the client that made the request           |
| `user_agent`    | string | User-Agent header from the client request                |
| `details`       | object | Additional context specific to the action (optional)     |

### Example Entry

```json
{
  "id": "audit-a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "timestamp": "2026-04-07T14:30:22Z",
  "user": "admin",
  "action": "create",
  "resource_type": "orchestration",
  "resource_id": "orch-12345678-abcd-ef01-2345-6789abcdef01",
  "ip": "192.168.1.100",
  "user_agent": "curl/8.5.0",
  "details": {
    "orchestration_name": "Deploy Web Servers",
    "version": 1
  }
}
```

---

## Viewing the Audit Log

**GET** `/dm-webmanager/api/audit`

### Basic Request

```bash
curl -X GET http://localhost:5000/dm-webmanager/api/audit \
  -H "Authorization: Bearer $TOKEN"
```

### Response (200 OK)

```json
{
  "total": 1247,
  "page": 1,
  "per_page": 50,
  "pages": 25,
  "entries": [
    {
      "id": "audit-ffeeddcc-bbaa-9988-7766-554433221100",
      "timestamp": "2026-04-07T14:45:10Z",
      "user": "admin",
      "action": "execution.launched",
      "resource_type": "orchestration",
      "resource_id": "orch-12345678-abcd-ef01-2345-6789abcdef01",
      "ip": "192.168.1.100",
      "user_agent": "Mozilla/5.0 (X11; Linux x86_64)",
      "details": {
        "execution_id": "exec-aabbccdd-1122-3344-5566-778899001122",
        "orchestration_name": "Deploy Web Servers"
      }
    },
    {
      "id": "audit-11223344-5566-7788-99aa-bbccddeeff00",
      "timestamp": "2026-04-07T14:44:55Z",
      "user": "admin",
      "action": "login.success",
      "resource_type": "session",
      "resource_id": null,
      "ip": "192.168.1.100",
      "user_agent": "curl/8.5.0",
      "details": {}
    }
  ]
}
```

Entries are returned in reverse chronological order (newest first).

---

## Filtering Audit Entries

The audit log API supports several query parameters for filtering.

### Filter by User

Retrieve all actions performed by a specific user:

```bash
curl -X GET "http://localhost:5000/dm-webmanager/api/audit?user=admin" \
  -H "Authorization: Bearer $TOKEN"
```

### Filter by Action

Retrieve all entries for a specific action type:

```bash
# All failed login attempts
curl -X GET "http://localhost:5000/dm-webmanager/api/audit?action=login.failed" \
  -H "Authorization: Bearer $TOKEN"
```

```bash
# All resource deletions
curl -X GET "http://localhost:5000/dm-webmanager/api/audit?action=delete" \
  -H "Authorization: Bearer $TOKEN"
```

### Filter by Resource Type

Retrieve all actions on a specific type of resource:

```bash
# All orchestration-related audit entries
curl -X GET "http://localhost:5000/dm-webmanager/api/audit?resource_type=orchestration" \
  -H "Authorization: Bearer $TOKEN"
```

```bash
# All webhook-related audit entries
curl -X GET "http://localhost:5000/dm-webmanager/api/audit?resource_type=webhook" \
  -H "Authorization: Bearer $TOKEN"
```

### Filter by Date Range

Retrieve entries within a specific time window using ISO 8601 timestamps:

```bash
# Entries from the last 24 hours
curl -X GET "http://localhost:5000/dm-webmanager/api/audit?from=2026-04-06T00:00:00Z&to=2026-04-07T23:59:59Z" \
  -H "Authorization: Bearer $TOKEN"
```

```bash
# Entries from a specific hour
curl -X GET "http://localhost:5000/dm-webmanager/api/audit?from=2026-04-07T14:00:00Z&to=2026-04-07T15:00:00Z" \
  -H "Authorization: Bearer $TOKEN"
```

### Combine Multiple Filters

Filters can be combined to narrow results:

```bash
# All failed logins from a specific IP in the last week
curl -X GET "http://localhost:5000/dm-webmanager/api/audit?action=login.failed&from=2026-03-31T00:00:00Z&to=2026-04-07T23:59:59Z" \
  -H "Authorization: Bearer $TOKEN"
```

```bash
# All orchestration deletions by a specific user
curl -X GET "http://localhost:5000/dm-webmanager/api/audit?user=admin&action=delete&resource_type=orchestration" \
  -H "Authorization: Bearer $TOKEN"
```

### Filter Parameters Reference

| Parameter       | Type   | Description                                      |
|-----------------|--------|--------------------------------------------------|
| `user`          | string | Filter by username                               |
| `action`        | string | Filter by action type                            |
| `resource_type` | string | Filter by resource type                          |
| `from`          | string | Start of date range (ISO 8601)                   |
| `to`            | string | End of date range (ISO 8601)                     |

---

## Pagination

The audit log supports pagination to handle large result sets efficiently.

### Parameters

| Parameter  | Type    | Default | Description                    |
|------------|---------|---------|--------------------------------|
| `page`     | integer | 1       | Page number (1-indexed)        |
| `per_page` | integer | 50      | Number of entries per page (max: 200) |

### Paginated Request

```bash
# First page, 20 entries per page
curl -X GET "http://localhost:5000/dm-webmanager/api/audit?page=1&per_page=20" \
  -H "Authorization: Bearer $TOKEN"
```

```bash
# Second page
curl -X GET "http://localhost:5000/dm-webmanager/api/audit?page=2&per_page=20" \
  -H "Authorization: Bearer $TOKEN"
```

### Response Pagination Metadata

Every response includes pagination information:

```json
{
  "total": 1247,
  "page": 2,
  "per_page": 20,
  "pages": 63,
  "entries": [...]
}
```

| Field      | Description                              |
|------------|------------------------------------------|
| `total`    | Total number of matching entries         |
| `page`     | Current page number                      |
| `per_page` | Number of entries per page               |
| `pages`    | Total number of pages                    |

### Iterating Through All Pages

```bash
# Fetch all pages (example script)
PAGE=1
TOTAL_PAGES=1

while [ $PAGE -le $TOTAL_PAGES ]; do
  RESPONSE=$(curl -s -X GET \
    "http://localhost:5000/dm-webmanager/api/audit?page=$PAGE&per_page=100" \
    -H "Authorization: Bearer $TOKEN")

  TOTAL_PAGES=$(echo $RESPONSE | jq '.pages')
  echo "Page $PAGE of $TOTAL_PAGES:"
  echo $RESPONSE | jq '.entries[] | "\(.timestamp) \(.user) \(.action) \(.resource_type)"'

  PAGE=$((PAGE + 1))
done
```

---

## The @audit_log Decorator

When developing custom extensions or endpoints for Dimensigon, you can use the `@audit_log` decorator to automatically log actions to the audit trail.

### Usage

```python
from dimensigon.web.decorators import audit_log

@app.route("/dm-webmanager/api/custom-resource", methods=["POST"])
@audit_log(action="create", resource_type="custom_resource")
def create_custom_resource():
    # Your endpoint logic here
    resource = create_resource(request.json)
    return jsonify(resource), 201
```

### Decorator Parameters

| Parameter       | Type   | Required | Description                                      |
|-----------------|--------|----------|--------------------------------------------------|
| `action`        | string | Yes      | The action name to record (e.g., `create`)       |
| `resource_type` | string | Yes      | The resource type to record                      |
| `resource_id`   | string | No       | Static resource ID (usually extracted dynamically)|

### Dynamic Resource ID

For endpoints where the resource ID is determined at runtime, the decorator extracts it from the response body if the response contains an `id` field, or from the URL parameters:

```python
@app.route("/dm-webmanager/api/custom-resource/<resource_id>", methods=["PUT"])
@audit_log(action="update", resource_type="custom_resource")
def update_custom_resource(resource_id):
    # resource_id is automatically captured from the URL
    resource = update_resource(resource_id, request.json)
    return jsonify(resource), 200
```

### Adding Extra Details

Include additional context in the audit entry by setting `audit_details` on the Flask `g` object:

```python
from flask import g

@app.route("/dm-webmanager/api/custom-resource/<resource_id>", methods=["DELETE"])
@audit_log(action="delete", resource_type="custom_resource")
def delete_custom_resource(resource_id):
    resource = get_resource(resource_id)
    g.audit_details = {"resource_name": resource.name, "reason": request.args.get("reason")}
    remove_resource(resource_id)
    return "", 204
```

---

## Immutability

The audit log is designed to be **immutable and tamper-evident**:

- There is **no DELETE endpoint** for audit entries. Once written, entries cannot be removed through the API.
- There is **no UPDATE endpoint** for audit entries. Entries cannot be modified after creation.
- Audit entries are written synchronously within the same transaction as the action they record, ensuring consistency.
- Database-level protections prevent direct modification of audit records even outside the API.

This immutability is a fundamental design principle for compliance. If your organization requires audit log exports for archival, use the GET endpoint with date range filters and export the data to your SIEM or log management system.

### Exporting Audit Data

```bash
# Export all entries for a specific month as JSON
curl -s -X GET \
  "http://localhost:5000/dm-webmanager/api/audit?from=2026-03-01T00:00:00Z&to=2026-03-31T23:59:59Z&per_page=200" \
  -H "Authorization: Bearer $TOKEN" \
  | jq '.entries' > audit-march-2026.json
```

---

## Access Control

Audit log access is **restricted to administrators only**. Non-administrator users who attempt to access the audit log endpoint receive a 403 Forbidden response.

### Access Requirements

| Role          | Can View Audit Log | Can Generate Audit Entries |
|---------------|--------------------|-----------------------------|
| Administrator | Yes                | Yes (all actions are logged)|
| Operator      | No                 | Yes (their actions are logged but they cannot view the log) |
| Viewer        | No                 | Yes (read-only actions on sensitive resources are logged)   |

### Forbidden Response

```bash
# Non-admin user attempting to access the audit log
curl -X GET http://localhost:5000/dm-webmanager/api/audit \
  -H "Authorization: Bearer $NON_ADMIN_TOKEN"
```

```json
{
  "error": "Forbidden",
  "message": "Administrator access required to view the audit log"
}
```

> **Note:** The act of attempting to access a restricted resource is itself audit-logged, including the denied request.

---

## Configuration Reference

| Setting                  | Default   | Description                                       |
|--------------------------|-----------|---------------------------------------------------|
| Audit log retention      | Unlimited | Entries are never automatically deleted            |
| Max per_page             | 200       | Maximum entries returned in a single API call     |
| Default per_page         | 50        | Default page size when not specified              |
| Write mode               | Synchronous | Entries written within the same transaction     |
| Sensitive actions logged | All       | Login, CRUD, execution, admin actions             |

### Best Practices

1. **Regular exports:** Periodically export audit data to your SIEM or log management platform for long-term retention and cross-system correlation.
2. **Monitor failed logins:** Set up alerts (via [webhooks](12-webhooks.md) or external tools) when `login.failed` events spike.
3. **Review admin actions:** Regularly review actions taken by administrator accounts.
4. **Compliance reporting:** Use date-range filters to generate periodic compliance reports.

---

## Related Features

- [Tutorial 12: Webhooks](12-webhooks.md) -- Webhook CRUD operations are recorded in the audit log; combine with webhooks to alert on suspicious audit events
- [Tutorial 13: Scheduled Orchestrations](13-scheduled-orchestrations.md) -- Scheduled executions are audit-logged with the scheduler identified as the initiating user
- [Tutorial 14: Orchestration Versioning](14-orchestration-versioning.md) -- Version changes and rollbacks are recorded in the audit log
