# Tutorial 13: Scheduled Orchestrations

Automate recurring tasks by scheduling orchestrations to run on a cron-based timetable. This tutorial covers creating schedules, cron syntax, timezone handling, missed-run policies, and the full management lifecycle.

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Creating a Schedule](#creating-a-schedule)
4. [Cron Expression Syntax](#cron-expression-syntax)
5. [Predefined Shortcuts](#predefined-shortcuts)
6. [Timezone Support](#timezone-support)
7. [Missed-Run Policies](#missed-run-policies)
8. [Enabling and Disabling Schedules](#enabling-and-disabling-schedules)
9. [Viewing Schedules](#viewing-schedules)
10. [Updating a Schedule](#updating-a-schedule)
11. [Deleting a Schedule](#deleting-a-schedule)
12. [The Scheduler Service](#the-scheduler-service)
13. [Configuration Reference](#configuration-reference)
14. [Related Features](#related-features)

---

## Overview

The scheduling system in Dimensigon 3.0 allows you to define cron-based schedules that automatically launch orchestration executions at specified times. This is useful for:

- Periodic health checks across your node fleet
- Nightly backup orchestrations
- Recurring deployment pipelines
- Scheduled compliance scans
- Regular log rotation or cleanup tasks

Schedules are evaluated by a background scheduler service that polls every 30 seconds, so the effective resolution for scheduled runs is approximately 30 seconds.

---

## Prerequisites

- A running Dimensigon 3.0 cluster
- An administrator account with API access
- A valid JWT token
- At least one orchestration already created (see the Getting Started guide)

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

## Creating a Schedule

Define a new schedule that associates a cron expression with an orchestration.

**POST** `/dm-webmanager/api/schedules`

### Request

```bash
curl -X POST http://localhost:5000/dm-webmanager/api/schedules \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Nightly Backup",
    "orchestration_id": "orch-12345678-abcd-ef01-2345-6789abcdef01",
    "cron": "0 2 * * *",
    "timezone": "UTC",
    "enabled": true,
    "missed_policy": "run_once",
    "parameters": {
      "target_nodes": ["db-01", "db-02"],
      "backup_path": "/var/backups/dimensigon"
    }
  }'
```

### Request Body Schema

| Field              | Type    | Required | Description                                                   |
|--------------------|---------|----------|---------------------------------------------------------------|
| `name`             | string  | Yes      | Human-readable name for the schedule                          |
| `orchestration_id` | string  | Yes      | ID of the orchestration to execute                            |
| `cron`             | string  | Yes      | Cron expression (5 fields)                                    |
| `timezone`         | string  | No       | IANA timezone (default: `UTC`)                                |
| `enabled`          | boolean | No       | Whether the schedule is active (default: `true`)              |
| `missed_policy`    | string  | No       | What to do if a run is missed: `skip` or `run_once` (default: `skip`) |
| `parameters`       | object  | No       | Parameters to pass to the orchestration on each execution     |

### Response (201 Created)

```json
{
  "id": "sched-aabb1122-ccdd-3344-eeff-556677889900",
  "name": "Nightly Backup",
  "orchestration_id": "orch-12345678-abcd-ef01-2345-6789abcdef01",
  "cron": "0 2 * * *",
  "timezone": "UTC",
  "enabled": true,
  "missed_policy": "run_once",
  "parameters": {
    "target_nodes": ["db-01", "db-02"],
    "backup_path": "/var/backups/dimensigon"
  },
  "next_run_at": "2026-04-08T02:00:00Z",
  "last_run_at": null,
  "created_at": "2026-04-07T10:00:00Z",
  "updated_at": "2026-04-07T10:00:00Z"
}
```

---

## Cron Expression Syntax

Dimensigon uses standard 5-field cron expressions:

```
 +------------ minute (0-59)
 | +---------- hour (0-23)
 | | +-------- day of month (1-31)
 | | | +------ month (1-12)
 | | | | +---- day of week (0-6, Sunday=0)
 | | | | |
 * * * * *
```

### Special Characters

| Character | Description                           | Example              |
|-----------|---------------------------------------|----------------------|
| `*`       | Any value                             | `* * * * *` (every minute) |
| `,`       | Value list separator                  | `1,15 * * * *` (minute 1 and 15) |
| `-`       | Range of values                       | `0 9-17 * * *` (hours 9 through 17) |
| `/`       | Step values                           | `*/10 * * * *` (every 10 minutes) |

### Examples

| Expression       | Meaning                                    |
|------------------|--------------------------------------------|
| `*/5 * * * *`    | Every 5 minutes                            |
| `0 * * * *`      | Every hour, on the hour                    |
| `0 0 * * *`      | Daily at midnight                          |
| `0 2 * * *`      | Daily at 2:00 AM                           |
| `0 0 * * 0`      | Every Sunday at midnight                   |
| `0 0 1 * *`      | First day of every month at midnight       |
| `30 6 * * 1-5`   | Weekdays at 6:30 AM                        |
| `0 9,12,18 * * *`| At 9:00 AM, 12:00 PM, and 6:00 PM daily   |
| `0 0 1,15 * *`   | 1st and 15th of each month at midnight     |

---

## Predefined Shortcuts

For convenience, here are common patterns ready to use:

### Every 5 Minutes

```bash
curl -X POST http://localhost:5000/dm-webmanager/api/schedules \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Health Check - Every 5 Min",
    "orchestration_id": "orch-healthcheck-0001",
    "cron": "*/5 * * * *",
    "missed_policy": "skip"
  }'
```

### Hourly

```bash
curl -X POST http://localhost:5000/dm-webmanager/api/schedules \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Hourly Log Rotation",
    "orchestration_id": "orch-logrotate-0001",
    "cron": "0 * * * *",
    "missed_policy": "skip"
  }'
```

### Daily at Midnight

```bash
curl -X POST http://localhost:5000/dm-webmanager/api/schedules \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Daily Compliance Scan",
    "orchestration_id": "orch-compliance-0001",
    "cron": "0 0 * * *",
    "missed_policy": "run_once"
  }'
```

---

## Timezone Support

By default, all cron expressions are evaluated in **UTC**. You can specify any IANA timezone string to adjust evaluation.

```bash
curl -X POST http://localhost:5000/dm-webmanager/api/schedules \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "End-of-Business Report (US Eastern)",
    "orchestration_id": "orch-report-0001",
    "cron": "0 17 * * 1-5",
    "timezone": "America/New_York",
    "missed_policy": "run_once"
  }'
```

### Common Timezone Values

| Timezone               | UTC Offset | Description          |
|------------------------|------------|----------------------|
| `UTC`                  | +00:00     | Default              |
| `America/New_York`     | -05:00     | US Eastern           |
| `America/Chicago`      | -06:00     | US Central           |
| `America/Los_Angeles`  | -08:00     | US Pacific           |
| `Europe/London`        | +00:00     | UK                   |
| `Europe/Berlin`        | +01:00     | Central Europe       |
| `Asia/Tokyo`           | +09:00     | Japan                |
| `Australia/Sydney`     | +11:00     | Australia Eastern    |

> **Note:** Dimensigon handles daylight saving time transitions automatically when IANA timezone names are used. Avoid specifying raw UTC offsets.

---

## Missed-Run Policies

If the scheduler service is temporarily down or a scheduled time is missed (for example, during a cluster restart), the missed-run policy determines what happens when the service comes back online.

| Policy     | Behavior                                                                  |
|------------|---------------------------------------------------------------------------|
| `skip`     | Silently skip all missed runs. Only future runs are executed.             |
| `run_once` | Execute the orchestration exactly once to catch up, then resume normally. |

### When to Use Each Policy

- **`skip`** -- Suitable for high-frequency checks (every 5 minutes) where missing one cycle is acceptable and running stale checks would be wasteful.
- **`run_once`** -- Suitable for critical daily or weekly tasks (backups, reports) where you want to ensure the job runs at least once even if the exact window was missed.

---

## Enabling and Disabling Schedules

Toggle a schedule on or off without deleting it.

**PATCH** `/dm-webmanager/api/schedules/<id>/toggle`

### Disable a Schedule

```bash
curl -X PATCH http://localhost:5000/dm-webmanager/api/schedules/sched-aabb1122-ccdd-3344-eeff-556677889900/toggle \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "enabled": false
  }'
```

### Response (200 OK)

```json
{
  "id": "sched-aabb1122-ccdd-3344-eeff-556677889900",
  "name": "Nightly Backup",
  "enabled": false,
  "next_run_at": null,
  "message": "Schedule disabled"
}
```

### Re-enable a Schedule

```bash
curl -X PATCH http://localhost:5000/dm-webmanager/api/schedules/sched-aabb1122-ccdd-3344-eeff-556677889900/toggle \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "enabled": true
  }'
```

### Response (200 OK)

```json
{
  "id": "sched-aabb1122-ccdd-3344-eeff-556677889900",
  "name": "Nightly Backup",
  "enabled": true,
  "next_run_at": "2026-04-08T02:00:00Z",
  "message": "Schedule enabled"
}
```

---

## Viewing Schedules

### List All Schedules

**GET** `/dm-webmanager/api/schedules`

```bash
curl -X GET http://localhost:5000/dm-webmanager/api/schedules \
  -H "Authorization: Bearer $TOKEN"
```

### Response (200 OK)

```json
{
  "total": 3,
  "schedules": [
    {
      "id": "sched-aabb1122-ccdd-3344-eeff-556677889900",
      "name": "Nightly Backup",
      "orchestration_id": "orch-12345678-abcd-ef01-2345-6789abcdef01",
      "cron": "0 2 * * *",
      "timezone": "UTC",
      "enabled": true,
      "missed_policy": "run_once",
      "next_run_at": "2026-04-08T02:00:00Z",
      "last_run_at": "2026-04-07T02:00:00Z",
      "last_status": "completed"
    },
    {
      "id": "sched-11223344-5566-7788-99aa-bbccddeeff00",
      "name": "Health Check - Every 5 Min",
      "orchestration_id": "orch-healthcheck-0001",
      "cron": "*/5 * * * *",
      "timezone": "UTC",
      "enabled": true,
      "missed_policy": "skip",
      "next_run_at": "2026-04-07T10:35:00Z",
      "last_run_at": "2026-04-07T10:30:00Z",
      "last_status": "completed"
    },
    {
      "id": "sched-ffeeddcc-bbaa-9988-7766-554433221100",
      "name": "Daily Compliance Scan",
      "orchestration_id": "orch-compliance-0001",
      "cron": "0 0 * * *",
      "timezone": "UTC",
      "enabled": false,
      "missed_policy": "run_once",
      "next_run_at": null,
      "last_run_at": "2026-04-06T00:00:00Z",
      "last_status": "failed"
    }
  ]
}
```

### Filter by Enabled Status

```bash
# Show only active schedules
curl -X GET "http://localhost:5000/dm-webmanager/api/schedules?enabled=true" \
  -H "Authorization: Bearer $TOKEN"
```

### Get a Single Schedule

```bash
curl -X GET http://localhost:5000/dm-webmanager/api/schedules/sched-aabb1122-ccdd-3344-eeff-556677889900 \
  -H "Authorization: Bearer $TOKEN"
```

---

## Updating a Schedule

Modify an existing schedule's cron expression, parameters, or other properties.

**PUT** `/dm-webmanager/api/schedules/<id>`

```bash
curl -X PUT http://localhost:5000/dm-webmanager/api/schedules/sched-aabb1122-ccdd-3344-eeff-556677889900 \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Nightly Backup (Updated)",
    "cron": "0 3 * * *",
    "timezone": "Europe/London",
    "missed_policy": "run_once",
    "parameters": {
      "target_nodes": ["db-01", "db-02", "db-03"],
      "backup_path": "/var/backups/dimensigon",
      "compression": true
    }
  }'
```

### Response (200 OK)

```json
{
  "id": "sched-aabb1122-ccdd-3344-eeff-556677889900",
  "name": "Nightly Backup (Updated)",
  "orchestration_id": "orch-12345678-abcd-ef01-2345-6789abcdef01",
  "cron": "0 3 * * *",
  "timezone": "Europe/London",
  "enabled": true,
  "missed_policy": "run_once",
  "parameters": {
    "target_nodes": ["db-01", "db-02", "db-03"],
    "backup_path": "/var/backups/dimensigon",
    "compression": true
  },
  "next_run_at": "2026-04-08T03:00:00+01:00",
  "updated_at": "2026-04-07T11:00:00Z"
}
```

---

## Deleting a Schedule

Permanently remove a schedule.

**DELETE** `/dm-webmanager/api/schedules/<id>`

```bash
curl -X DELETE http://localhost:5000/dm-webmanager/api/schedules/sched-ffeeddcc-bbaa-9988-7766-554433221100 \
  -H "Authorization: Bearer $TOKEN"
```

### Response (204 No Content)

No response body is returned on successful deletion.

---

## The Scheduler Service

The scheduler runs as a background service within the Dimensigon process. Understanding its behavior helps with operational planning.

### How It Works

1. The scheduler service runs a **polling loop every 30 seconds**.
2. On each tick, it queries all enabled schedules.
3. For each schedule, it compares the current time against the cron expression.
4. If the current time matches (within the 30-second window), it launches the associated orchestration.
5. After launching, it updates `last_run_at` and computes the `next_run_at`.

### Implications

- **Resolution:** The effective minimum interval is approximately 30 seconds. A `* * * * *` (every minute) cron will trigger once per minute, not more frequently.
- **Overlap prevention:** If a previous execution is still running when the next scheduled time arrives, the scheduler will skip that tick to prevent overlap. The skip is logged.
- **Cluster awareness:** In a multi-node cluster, only the leader node runs the scheduler to prevent duplicate executions.

### Monitoring the Scheduler

Check the scheduler's status in the application logs:

```bash
# View scheduler activity
grep "scheduler" /var/log/dimensigon/dimensigon.log | tail -20
```

---

## Configuration Reference

| Setting                   | Default   | Description                                      |
|---------------------------|-----------|--------------------------------------------------|
| Polling interval          | 30s       | How often the scheduler checks for due schedules |
| Max concurrent scheduled  | 10        | Maximum simultaneous scheduled executions        |
| Default timezone          | UTC       | Used when no timezone is specified               |
| Default missed policy     | skip      | Used when no missed_policy is specified          |
| Schedule history retention| 90 days   | How long execution records are kept              |

---

## Related Features

- [Tutorial 12: Webhooks](12-webhooks.md) -- Receive notifications when scheduled orchestrations complete or fail
- [Tutorial 14: Orchestration Versioning](14-orchestration-versioning.md) -- Schedules always run the latest version of the referenced orchestration
- [Tutorial 16: Audit Log](16-audit-log.md) -- All schedule creation, modification, and execution events are audit-logged
