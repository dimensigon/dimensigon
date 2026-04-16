# Tutorial 14: Orchestration Versioning

Track every change to your orchestrations with automatic versioning. This tutorial covers viewing version history, comparing versions, rolling back to previous configurations, and understanding the immutable snapshot model.

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [How Versioning Works](#how-versioning-works)
4. [Viewing Version History](#viewing-version-history)
5. [Comparing Versions](#comparing-versions)
6. [Rolling Back to a Previous Version](#rolling-back-to-a-previous-version)
7. [Auto-Versioning on Save](#auto-versioning-on-save)
8. [Configuration Reference](#configuration-reference)
9. [Related Features](#related-features)

---

## Overview

Orchestration versioning in Dimensigon 3.0 provides a complete history of every change made to an orchestration definition. Each time an orchestration is saved -- whether through the API or the visual builder -- an immutable snapshot is created. This enables:

- **Full audit trail:** See exactly what changed, when, and by whom
- **Safe rollbacks:** Restore any previous version without losing history
- **Change comparison:** Diff any two versions to understand what was modified
- **Execution traceability:** Link each execution to the exact version that ran

Versioning is automatic and requires no additional configuration. Every orchestration starts at version 1, and each subsequent save increments the version number.

---

## Prerequisites

- A running Dimensigon 3.0 cluster
- An administrator or operator account with API access
- A valid JWT token
- At least one orchestration already created

### Obtain a JWT Token

```bash
TOKEN=$(curl -s -X POST http://localhost:5000/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "your_password"
  }' | jq -r '.access_token')
```

### Create a Sample Orchestration

If you do not have an orchestration to work with, create one:

```bash
curl -X POST http://localhost:5000/dm-webmanager/api/orchestrations \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Deploy Application",
    "description": "Deploy the application to web servers",
    "steps": [
      {
        "name": "Stop Service",
        "action": "shell",
        "command": "systemctl stop myapp",
        "target": "web-servers"
      },
      {
        "name": "Deploy Code",
        "action": "shell",
        "command": "rsync -az /releases/latest/ /opt/myapp/",
        "target": "web-servers"
      },
      {
        "name": "Start Service",
        "action": "shell",
        "command": "systemctl start myapp",
        "target": "web-servers"
      }
    ]
  }'
```

Note the `orchestration_id` from the response for use in subsequent examples. The examples below use `orch-12345678-abcd-ef01-2345-6789abcdef01` as a placeholder.

---

## How Versioning Works

### The Immutable Snapshot Model

Every time an orchestration is saved, Dimensigon creates an **immutable snapshot** of the entire orchestration definition at that point in time. This snapshot includes:

- All step definitions (names, actions, commands, targets, ordering)
- Step dependencies and flow control logic
- Parameters and variable definitions
- Description and metadata

Key principles:

1. **Snapshots are immutable.** Once a version is created, it cannot be modified or deleted.
2. **Versions are sequential.** Each save increments the version number by 1.
3. **The current version is always the latest.** When you view or execute an orchestration, it uses the most recent version by default.
4. **Rollbacks create new versions.** Rolling back to version 3 does not delete versions 4 and above; instead, it creates a new version that is a copy of version 3.

### Version Lifecycle Example

```
v1 -- Initial creation (3 steps)
v2 -- Added monitoring step (4 steps)
v3 -- Changed deployment path (4 steps)
v4 -- Removed monitoring step (3 steps)
v5 -- Rollback to v2 (4 steps, copy of v2's snapshot)
```

All five versions remain in history permanently.

---

## Viewing Version History

Retrieve the complete version history for an orchestration.

**GET** `/dm-webmanager/api/orchestrations/<id>/versions`

### Request

```bash
curl -X GET http://localhost:5000/dm-webmanager/api/orchestrations/orch-12345678-abcd-ef01-2345-6789abcdef01/versions \
  -H "Authorization: Bearer $TOKEN"
```

### Response (200 OK)

```json
{
  "orchestration_id": "orch-12345678-abcd-ef01-2345-6789abcdef01",
  "orchestration_name": "Deploy Application",
  "current_version": 4,
  "total_versions": 4,
  "versions": [
    {
      "version": 4,
      "created_at": "2026-04-07T16:00:00Z",
      "created_by": "admin",
      "description": "Removed health check step",
      "step_count": 3,
      "is_current": true
    },
    {
      "version": 3,
      "created_at": "2026-04-07T14:30:00Z",
      "created_by": "admin",
      "description": "Updated deployment path to /opt/myapp/v2",
      "step_count": 4,
      "is_current": false
    },
    {
      "version": 2,
      "created_at": "2026-04-07T12:00:00Z",
      "created_by": "operator1",
      "description": "Added health check step",
      "step_count": 4,
      "is_current": false
    },
    {
      "version": 1,
      "created_at": "2026-04-07T10:00:00Z",
      "created_by": "admin",
      "description": "Initial creation",
      "step_count": 3,
      "is_current": false
    }
  ]
}
```

Versions are returned in reverse chronological order (newest first).

### View a Specific Version's Full Definition

```bash
curl -X GET http://localhost:5000/dm-webmanager/api/orchestrations/orch-12345678-abcd-ef01-2345-6789abcdef01/versions/2 \
  -H "Authorization: Bearer $TOKEN"
```

### Response (200 OK)

```json
{
  "orchestration_id": "orch-12345678-abcd-ef01-2345-6789abcdef01",
  "version": 2,
  "created_at": "2026-04-07T12:00:00Z",
  "created_by": "operator1",
  "description": "Added health check step",
  "definition": {
    "name": "Deploy Application",
    "description": "Deploy the application to web servers",
    "steps": [
      {
        "name": "Stop Service",
        "action": "shell",
        "command": "systemctl stop myapp",
        "target": "web-servers"
      },
      {
        "name": "Deploy Code",
        "action": "shell",
        "command": "rsync -az /releases/latest/ /opt/myapp/",
        "target": "web-servers"
      },
      {
        "name": "Health Check",
        "action": "shell",
        "command": "curl -f http://localhost:8080/health",
        "target": "web-servers"
      },
      {
        "name": "Start Service",
        "action": "shell",
        "command": "systemctl start myapp",
        "target": "web-servers"
      }
    ]
  }
}
```

---

## Comparing Versions

Compare any two versions to see exactly what changed between them.

**GET** `/dm-webmanager/api/orchestrations/<id>/versions/<v1>/diff/<v2>`

### Request

```bash
curl -X GET http://localhost:5000/dm-webmanager/api/orchestrations/orch-12345678-abcd-ef01-2345-6789abcdef01/versions/1/diff/2 \
  -H "Authorization: Bearer $TOKEN"
```

### Response (200 OK)

```json
{
  "orchestration_id": "orch-12345678-abcd-ef01-2345-6789abcdef01",
  "from_version": 1,
  "to_version": 2,
  "summary": {
    "added": 1,
    "removed": 0,
    "changed": 0
  },
  "changes": {
    "steps": {
      "added": [
        {
          "name": "Health Check",
          "action": "shell",
          "command": "curl -f http://localhost:8080/health",
          "target": "web-servers",
          "position": 3
        }
      ],
      "removed": [],
      "changed": []
    },
    "metadata": {}
  }
}
```

### Diff Format

The diff response organizes changes into three categories:

| Category  | Description                                                    |
|-----------|----------------------------------------------------------------|
| `added`   | Steps or properties that exist in `to_version` but not in `from_version` |
| `removed` | Steps or properties that exist in `from_version` but not in `to_version` |
| `changed` | Steps or properties that exist in both but have been modified  |

### Comparing Non-Adjacent Versions

You can compare any two versions, not just adjacent ones:

```bash
# Compare version 1 to version 4 (skipping 2 and 3)
curl -X GET http://localhost:5000/dm-webmanager/api/orchestrations/orch-12345678-abcd-ef01-2345-6789abcdef01/versions/1/diff/4 \
  -H "Authorization: Bearer $TOKEN"
```

### Response with Changed Steps

When a step is modified between versions, the diff shows both old and new values:

```json
{
  "orchestration_id": "orch-12345678-abcd-ef01-2345-6789abcdef01",
  "from_version": 2,
  "to_version": 3,
  "summary": {
    "added": 0,
    "removed": 0,
    "changed": 1
  },
  "changes": {
    "steps": {
      "added": [],
      "removed": [],
      "changed": [
        {
          "name": "Deploy Code",
          "field": "command",
          "from": "rsync -az /releases/latest/ /opt/myapp/",
          "to": "rsync -az /releases/latest/ /opt/myapp/v2/"
        }
      ]
    },
    "metadata": {}
  }
}
```

---

## Rolling Back to a Previous Version

Restore an orchestration to a previous version's configuration. This is a non-destructive operation that creates a new version.

**POST** `/dm-webmanager/api/orchestrations/<id>/rollback/<version>`

### Request

```bash
curl -X POST http://localhost:5000/dm-webmanager/api/orchestrations/orch-12345678-abcd-ef01-2345-6789abcdef01/rollback/2 \
  -H "Authorization: Bearer $TOKEN"
```

### Response (201 Created)

```json
{
  "orchestration_id": "orch-12345678-abcd-ef01-2345-6789abcdef01",
  "previous_version": 4,
  "rolled_back_to": 2,
  "new_version": 5,
  "message": "Orchestration rolled back to version 2. New version 5 created.",
  "created_at": "2026-04-07T17:00:00Z",
  "created_by": "admin"
}
```

### How Rollback Works

1. The system reads the immutable snapshot of the target version (version 2 in this example).
2. A **new version** (version 5) is created with the same definition as version 2.
3. The new version becomes the current version.
4. All previous versions remain intact in the history.

This means rolling back is always safe. You can always roll back the rollback by targeting any other version.

### Verify the Rollback

After rolling back, confirm the current state:

```bash
# Check the version history
curl -X GET http://localhost:5000/dm-webmanager/api/orchestrations/orch-12345678-abcd-ef01-2345-6789abcdef01/versions \
  -H "Authorization: Bearer $TOKEN"
```

```json
{
  "current_version": 5,
  "total_versions": 5,
  "versions": [
    {
      "version": 5,
      "created_at": "2026-04-07T17:00:00Z",
      "created_by": "admin",
      "description": "Rollback to version 2",
      "step_count": 4,
      "is_current": true
    },
    {
      "version": 4,
      "created_at": "2026-04-07T16:00:00Z",
      "created_by": "admin",
      "description": "Removed health check step",
      "step_count": 3,
      "is_current": false
    }
  ]
}
```

### Confirm Rollback Content Matches Target

```bash
# Diff the rollback result (v5) against the target (v2) -- should show zero changes
curl -X GET http://localhost:5000/dm-webmanager/api/orchestrations/orch-12345678-abcd-ef01-2345-6789abcdef01/versions/2/diff/5 \
  -H "Authorization: Bearer $TOKEN"
```

```json
{
  "from_version": 2,
  "to_version": 5,
  "summary": {
    "added": 0,
    "removed": 0,
    "changed": 0
  },
  "changes": {
    "steps": {
      "added": [],
      "removed": [],
      "changed": []
    },
    "metadata": {}
  }
}
```

---

## Auto-Versioning on Save

### API Saves

Every `PUT` request to update an orchestration automatically creates a new version:

```bash
curl -X PUT http://localhost:5000/dm-webmanager/api/orchestrations/orch-12345678-abcd-ef01-2345-6789abcdef01 \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Deploy Application",
    "description": "Deploy the application to web servers (with rollback step)",
    "steps": [
      {
        "name": "Create Backup",
        "action": "shell",
        "command": "cp -r /opt/myapp /opt/myapp.bak",
        "target": "web-servers"
      },
      {
        "name": "Stop Service",
        "action": "shell",
        "command": "systemctl stop myapp",
        "target": "web-servers"
      },
      {
        "name": "Deploy Code",
        "action": "shell",
        "command": "rsync -az /releases/latest/ /opt/myapp/",
        "target": "web-servers"
      },
      {
        "name": "Start Service",
        "action": "shell",
        "command": "systemctl start myapp",
        "target": "web-servers"
      }
    ]
  }'
```

This creates a new version automatically. The response includes the new version number:

```json
{
  "id": "orch-12345678-abcd-ef01-2345-6789abcdef01",
  "name": "Deploy Application",
  "version": 6,
  "updated_at": "2026-04-07T18:00:00Z"
}
```

### Visual Builder Saves

When using the Dimensigon web UI and visual builder, clicking **Save** triggers the same versioning mechanism. Every save from the builder creates a new version, ensuring that GUI-based changes are tracked with the same fidelity as API changes.

### No-Op Saves

If you save an orchestration without making any changes, Dimensigon detects that the definition is identical to the current version and skips version creation. This prevents unnecessary version accumulation.

---

## Configuration Reference

| Setting                     | Default   | Description                                          |
|-----------------------------|-----------|------------------------------------------------------|
| Version retention           | Unlimited | All versions are kept indefinitely                   |
| Max versions per orchestration | Unlimited | No limit on the number of versions               |
| Auto-version on save        | Enabled   | Cannot be disabled (core design principle)           |
| No-op detection             | Enabled   | Skips version creation if definition is unchanged    |

### Best Practices

1. **Use meaningful descriptions:** When updating orchestrations via the API, include a `description` field that explains what changed and why.
2. **Review before rollback:** Always compare the target version against the current version using the diff endpoint before rolling back.
3. **Tag important versions:** Use descriptive names in the version description (e.g., "Production release 2.1") so they are easy to identify later.
4. **Periodic review:** Periodically review version history for orchestrations to understand how they have evolved.

---

## Related Features

- [Tutorial 12: Webhooks](12-webhooks.md) -- Webhook event payloads include the orchestration version that was executed
- [Tutorial 13: Scheduled Orchestrations](13-scheduled-orchestrations.md) -- Schedules always execute the latest version of the associated orchestration
- [Tutorial 16: Audit Log](16-audit-log.md) -- All version changes and rollbacks are recorded in the audit log
- [Tutorial 25: Container Deployment](25-container-deployment.md) -- Version history persists across container restarts when database storage is properly configured
