# Tutorial 09: Execution History and Diff

## Overview

Dimensigon 3.0 lets operators compare two executions of the same orchestration
side by side, highlighting differences in step status, parameters, and duration.
A duration trend chart shows how execution times change over multiple runs.
These features help operators diagnose regressions, verify fixes, and track
performance trends.

## Prerequisites

- A running Dimensigon 3.0 instance with at least two completed executions of
  the same orchestration.
- An operator or administrator account.
- Access to DM-WebManager at `http://<host>:5000/dm-webmanager/dashboard`.
- For API examples: `curl` and `jq`.

## 1. Viewing Execution History

1. Log in to DM-WebManager.
2. Navigate to **Executions** in the left-hand menu.
3. The execution list displays all orchestration runs, sorted by start time
   (most recent first).

### Filtering the list

Use the filter controls at the top of the list:

| Filter           | Description                                    |
|------------------|------------------------------------------------|
| **Status**       | Filter by `success`, `failed`, or `running`.   |
| **Orchestration**| Show only executions of a specific orchestration. |
| **Date range**   | Restrict to a start/end date window.           |
| **Search**       | Full-text search in orchestration names.       |

### Execution row details

Each row shows:

- Execution ID (abbreviated).
- Orchestration name and version.
- Start time and duration.
- Status badge (green for success, red for failed, yellow for running).
- Number of steps completed vs total.

## 2. Selecting Two Executions for Comparison

1. In the execution list, check the checkbox on the left side of two execution
   rows you want to compare.
2. Once two rows are selected, the **Compare** button appears in the toolbar.
3. Click **Compare** to open the side-by-side comparison view.

Alternatively, open an execution detail view and click **Compare with...** to
select a second execution from a dropdown filtered to the same orchestration.

## 3. Side-by-Side Comparison View

The comparison view displays two executions in parallel columns:

```
+---------------------------+---------------------------+
|      Execution A          |      Execution B          |
+---------------------------+---------------------------+
| ID: ...0001               | ID: ...0002               |
| Status: success           | Status: failed            |
| Duration: 30.0s           | Duration: 45.0s           |
| Params: env=staging       | Params: env=production    |
+---------------------------+---------------------------+
|         Step Comparison Table                         |
+-------------------------------------------------------+
| Step Name    | A Status | B Status | Duration A | B   |
+--------------+----------+----------+------------+-----+
| step-alpha   | success  | success  | 10.0s      |12.0s|
| step-beta    | success  | FAILED   | 15.0s      |28.0s|
+--------------+----------+----------+------------+-----+
```

### Header section

Each column header shows:

| Field                  | Description                           |
|------------------------|---------------------------------------|
| **ID**                 | Full execution UUID.                  |
| **Orchestration Name** | Name and version of the orchestration.|
| **Status**             | Overall execution result.             |
| **Start Time**         | When the execution started.           |
| **Duration**           | Total execution time in seconds.      |

## 4. Step Status Diff

The step comparison table highlights differences using color coding:

| Color       | Meaning                                                    |
|-------------|------------------------------------------------------------|
| **Green**   | Improved -- a step that failed in A now succeeds in B.     |
| **Red**     | Degraded -- a step that succeeded in A now fails in B.     |
| **No color**| Unchanged -- both executions have the same status for the step. |

Each row in the table shows:

| Column       | Description                                    |
|--------------|------------------------------------------------|
| `step_name`  | Name of the step.                              |
| `status_a`   | Step status in execution A.                    |
| `status_b`   | Step status in execution B.                    |
| `duration_a` | Step duration in execution A (seconds).        |
| `duration_b` | Step duration in execution B (seconds).        |
| `changed`    | Boolean indicating whether the status differs. |

## 5. Parameter Diff Between Runs

Below the step table, the comparison view shows a parameter diff section.
Parameters that differ between the two executions are displayed in a two-column
layout:

```
Parameter   | Execution A     | Execution B
------------|-----------------|----------------
env         | staging         | production
retries     | (same: 3)       | (same: 3)
```

Only parameters with differing values are highlighted. Parameters that are
identical in both executions are shown in a collapsed "Unchanged" section.

## 6. Duration Trend Chart

The trend chart shows how execution duration changes across multiple runs of
the same orchestration. It is accessible from:

1. The execution detail view -- click the **Trends** tab.
2. The orchestration list -- click the trend icon next to an orchestration name.

### Chart details

- **X-axis:** Execution start time (chronological, oldest to newest).
- **Y-axis:** Total duration in seconds.
- **Data points:** Each run is a dot. Green dots for successful runs, red for
  failed runs.
- **Trend line:** A dashed line showing the moving average.

Hover over a data point to see the execution ID, duration, and status.

## 7. API Reference

### Compare two executions

```
GET /dm-webmanager/api/executions/compare?a=<execution_id_a>&b=<execution_id_b>
```

**Authentication:** Requires a valid session.

**Query parameters:**

| Param | Required | Description                      |
|-------|----------|----------------------------------|
| `a`   | Yes      | UUID of the first execution.     |
| `b`   | Yes      | UUID of the second execution.    |

**curl example:**

```bash
curl -s -b cookies.txt \
  "http://localhost:5000/dm-webmanager/api/executions/compare?a=00000000-0000-0000-000d-000000000001&b=00000000-0000-0000-000d-000000000002" \
  | jq .
```

**Response (200 OK):**

```json
{
  "execution_a": {
    "id": "00000000-0000-0000-000d-000000000001",
    "orchestration_name": "TestOrch",
    "status": "success",
    "start_time": "2026-04-07T12:00:00Z",
    "duration": 30.0,
    "params": {"env": "staging", "retries": 3},
    "steps": [
      {
        "step_name": "step-alpha",
        "status": "success",
        "duration": 10.0,
        "rc": 0
      },
      {
        "step_name": "step-beta",
        "status": "success",
        "duration": 15.0,
        "rc": 0
      }
    ]
  },
  "execution_b": {
    "id": "00000000-0000-0000-000d-000000000002",
    "orchestration_name": "TestOrch",
    "status": "failed",
    "start_time": "2026-04-07T13:00:00Z",
    "duration": 45.0,
    "params": {"env": "production", "retries": 3},
    "steps": [
      {
        "step_name": "step-alpha",
        "status": "success",
        "duration": 12.0,
        "rc": 0
      },
      {
        "step_name": "step-beta",
        "status": "failed",
        "duration": 28.0,
        "rc": 1
      }
    ]
  },
  "diff": {
    "status_changed": true,
    "param_diff": {
      "env": {
        "a": "staging",
        "b": "production"
      }
    },
    "step_diffs": [
      {
        "step_name": "step-alpha",
        "status_a": "success",
        "status_b": "success",
        "duration_a": 10.0,
        "duration_b": 12.0,
        "changed": false
      },
      {
        "step_name": "step-beta",
        "status_a": "success",
        "status_b": "failed",
        "duration_a": 15.0,
        "duration_b": 28.0,
        "changed": true
      }
    ]
  }
}
```

**Error responses:**

| Status | Condition                                        |
|--------|--------------------------------------------------|
| 400    | Missing `a` or `b` query parameter.             |
| 404    | One or both execution IDs do not exist.          |

### Duration trends for an orchestration

```
GET /dm-webmanager/api/executions/trends/<orchestration_id>
```

**Authentication:** Requires a valid session.

**curl example:**

```bash
curl -s -b cookies.txt \
  http://localhost:5000/dm-webmanager/api/executions/trends/00000000-0000-0000-000b-000000000001 \
  | jq .
```

**Response (200 OK):**

```json
{
  "orchestration_id": "00000000-0000-0000-000b-000000000001",
  "orchestration_name": "TestOrch",
  "runs": [
    {
      "id": "00000000-0000-0000-000d-000000000001",
      "start_time": "2026-04-07T12:00:00Z",
      "duration": 30.0,
      "status": "success"
    },
    {
      "id": "00000000-0000-0000-000d-000000000002",
      "start_time": "2026-04-07T13:00:00Z",
      "duration": 45.0,
      "status": "failed"
    }
  ]
}
```

Runs are ordered chronologically (oldest first) so the trend chart can plot
them left to right.

**Error responses:**

| Status | Condition                                    |
|--------|----------------------------------------------|
| 404    | Orchestration ID does not exist.             |

## 8. Use Cases

### Diagnosing a regression

1. A deployment that previously succeeded now fails.
2. Select the last successful execution and the failed execution.
3. Open the comparison view.
4. Check the **Step Status Diff** to identify which step changed from success
   to failure.
5. Review the **Parameter Diff** to see if different parameters were used.
6. Investigate the failing step's stdout/stderr in the execution detail view.

### Verifying a fix

1. A step failed due to a known issue. A fix has been deployed.
2. Re-run the orchestration.
3. Compare the new execution with the previously failed one.
4. Confirm the failing step is now green (improved) in the diff.

### Tracking performance over time

1. Open the trend chart for a frequently executed orchestration.
2. Look for upward trends in duration, which may indicate resource contention
   or degradation.
3. Correlate red data points (failures) with deployment events.

## Related Features

- [Tutorial 06: Real-Time Monitoring](06-realtime-monitoring.md) -- watch executions in progress.
- [Tutorial 10: Dashboard Widgets](10-dashboard-widgets.md) -- see aggregated success rate trends.
- [Tutorial 24: Prometheus Metrics](24-prometheus-metrics.md) -- `dm_step_execution_duration_seconds` provides histogram data.
