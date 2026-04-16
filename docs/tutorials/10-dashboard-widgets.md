# Tutorial 10: Dashboard Widgets

## Overview

The DM-WebManager dashboard includes a set of widgets that provide at-a-glance
operational insights: success rate trends, top failures, and recent activity.
Widgets aggregate execution data and auto-refresh to give operators a
continuously updated picture of cluster health.

This tutorial covers each widget type, the data aggregation logic, the backing
API endpoints, and customization options.

## Prerequisites

- A running Dimensigon 3.0 instance with execution history (at least a few
  days of orchestration runs).
- An operator or administrator account.
- Access to DM-WebManager at `http://<host>:5000/dm-webmanager/dashboard`.
- For API examples: `curl` and `jq`.

## 1. Widget Types

The dashboard displays three default widgets, arranged in a grid layout.

### 1.1 Success Rate Trend

**Location:** Top-left card on the dashboard.

This widget shows a 7-day bar chart of execution success rates.

**What it displays:**

- One bar per day for the last 7 days.
- Each bar is split into a green segment (successful executions) and a red
  segment (failed executions).
- A percentage label shows the daily success rate.
- A trend arrow indicates whether today's rate is above or below the 7-day
  average.

**Example data:**

| Date       | Total | Success | Failed | Rate   |
|------------|-------|---------|--------|--------|
| 2026-04-01 | 42    | 38      | 4      | 90.5%  |
| 2026-04-02 | 50    | 47      | 3      | 94.0%  |
| 2026-04-03 | 35    | 30      | 5      | 85.7%  |
| 2026-04-04 | 48    | 46      | 2      | 95.8%  |
| 2026-04-05 | 39    | 36      | 3      | 92.3%  |
| 2026-04-06 | 45    | 42      | 3      | 93.3%  |
| 2026-04-07 | 22    | 20      | 2      | 90.9%  |

### 1.2 Top Failures

**Location:** Top-right card on the dashboard.

This widget shows the 5 orchestrations with the most failures in the last 7
days, ranked by failure count.

**What it displays:**

- A ranked list of orchestration names with their failure counts.
- A horizontal bar for each entry, proportional to the failure count.
- The most-failed orchestration appears first.

**Example data:**

| Rank | Orchestration      | Failures |
|------|--------------------|----------|
| 1    | Restart Service    | 12       |
| 2    | Deploy App         | 7        |
| 3    | Backup Database    | 4        |
| 4    | Rotate Logs        | 2        |
| 5    | Sync Config        | 1        |

### 1.3 Recent Activity

**Location:** Bottom card spanning the full width.

This widget shows the 20 most recent execution events, providing a live feed of
cluster activity.

**What it displays:**

- A table with one row per execution.
- Columns: orchestration name, status, server, start time, duration.
- Rows are sorted by start time (newest first).
- Status is color-coded: green (success), red (failed), yellow (running).
- The table scrolls and new entries appear at the top as they occur.

## 2. Data Aggregation

### 7-day window

The success rate and top failures widgets use a rolling 7-day window. The window
is calculated server-side based on the current UTC time minus 7 days. Data
outside this window is excluded from the aggregation.

### Top 5

The top failures widget returns at most 5 entries, ordered by descending failure
count. If fewer than 5 orchestrations have failures, only the ones with
failures are shown.

### Last 20

The recent activity widget returns the 20 most recent executions regardless of
status. The count is configurable via the `WIDGET_RECENT_ACTIVITY_LIMIT`
setting (see Configuration section).

## 3. Widget API Endpoints

All widget endpoints require authentication (JWT cookie or Authorization
header).

### 3.1 Success Rate

```
GET /dm-webmanager/api/widgets/success-rate
```

**curl example:**

```bash
curl -s -b cookies.txt http://localhost:5000/dm-webmanager/api/widgets/success-rate | jq .
```

**Response (200 OK):**

```json
{
  "days": [
    {
      "date": "2026-04-01",
      "total": 42,
      "success": 38,
      "rate": 90.5
    },
    {
      "date": "2026-04-02",
      "total": 50,
      "success": 47,
      "rate": 94.0
    },
    {
      "date": "2026-04-03",
      "total": 35,
      "success": 30,
      "rate": 85.7
    },
    {
      "date": "2026-04-04",
      "total": 48,
      "success": 46,
      "rate": 95.8
    },
    {
      "date": "2026-04-05",
      "total": 39,
      "success": 36,
      "rate": 92.3
    },
    {
      "date": "2026-04-06",
      "total": 45,
      "success": 42,
      "rate": 93.3
    },
    {
      "date": "2026-04-07",
      "total": 22,
      "success": 20,
      "rate": 90.9
    }
  ]
}
```

**Response fields:**

| Field          | Type      | Description                                   |
|----------------|-----------|-----------------------------------------------|
| `days`         | `array`   | Array of 7 daily aggregations.                |
| `days[].date`  | `string`  | Date in `YYYY-MM-DD` format.                  |
| `days[].total` | `integer` | Total executions that day.                    |
| `days[].success`| `integer`| Successful executions that day.               |
| `days[].rate`  | `float`   | Success rate as a percentage (0.0 - 100.0).   |

### 3.2 Top Failures

```
GET /dm-webmanager/api/widgets/top-failures
```

**curl example:**

```bash
curl -s -b cookies.txt http://localhost:5000/dm-webmanager/api/widgets/top-failures | jq .
```

**Response (200 OK):**

```json
{
  "failures": [
    {
      "name": "Restart Service",
      "count": 12
    },
    {
      "name": "Deploy App",
      "count": 7
    },
    {
      "name": "Backup Database",
      "count": 4
    }
  ]
}
```

**Response fields:**

| Field               | Type      | Description                            |
|---------------------|-----------|----------------------------------------|
| `failures`          | `array`   | Array of up to 5 entries.              |
| `failures[].name`   | `string`  | Orchestration name.                    |
| `failures[].count`  | `integer` | Number of failures in the last 7 days. |

### 3.3 Recent Activity

```
GET /dm-webmanager/api/widgets/recent-activity
```

**curl example:**

```bash
curl -s -b cookies.txt http://localhost:5000/dm-webmanager/api/widgets/recent-activity | jq .
```

**Response (200 OK):**

```json
{
  "events": [
    {
      "id": "00000000-0000-0000-000d-000000000002",
      "orchestration_name": "Deploy App",
      "status": "failed",
      "start_time": "2026-04-07T13:45:00Z",
      "server_name": "web-server-01"
    },
    {
      "id": "00000000-0000-0000-000d-000000000001",
      "orchestration_name": "Deploy App",
      "status": "success",
      "start_time": "2026-04-07T12:30:00Z",
      "server_name": "web-server-01"
    }
  ]
}
```

**Response fields:**

| Field                       | Type     | Description                        |
|-----------------------------|----------|------------------------------------|
| `events`                    | `array`  | Array of up to 20 recent events.   |
| `events[].id`               | `string` | Execution UUID.                    |
| `events[].orchestration_name`| `string`| Orchestration name.                |
| `events[].status`           | `string` | `success`, `failed`, or `running`. |
| `events[].start_time`       | `string` | ISO-8601 timestamp.                |
| `events[].server_name`      | `string` | Server that ran the execution (may be null). |

## 4. Customizing the Dashboard Layout

### Reordering widgets

In the DM-WebManager settings (gear icon on the dashboard), you can reorder
widgets by dragging them within the layout editor. The layout is saved
per-user in the browser's localStorage.

### Collapsing widgets

Click the minimize icon on any widget card to collapse it. Collapsed widgets
show only the title bar and can be expanded again by clicking the same icon.

### Adjusting the refresh interval

Each widget has a small clock icon. Click it to set a custom refresh interval:

| Option       | Interval      |
|--------------|---------------|
| **Fast**     | 10 seconds    |
| **Normal**   | 30 seconds    |
| **Slow**     | 60 seconds    |
| **Paused**   | No auto-refresh |

The default refresh interval is 30 seconds for all widgets.

## 5. Auto-Refresh Behavior

All widgets auto-refresh independently. When auto-refresh fires:

1. The widget makes an API call to its endpoint.
2. A subtle loading animation appears on the widget card.
3. Data is updated in place without a full page reload.
4. The refresh timer resets.

If the API call fails (network error, timeout, auth expiry), the widget
displays a warning icon and retries on the next interval. After 3 consecutive
failures, auto-refresh is paused and a manual "Retry" button appears.

## 6. Configuration Options

| Setting                          | Default | Description                               |
|----------------------------------|---------|-------------------------------------------|
| `WIDGET_REFRESH_INTERVAL`        | `30`    | Default auto-refresh interval in seconds. |
| `WIDGET_SUCCESS_RATE_DAYS`       | `7`     | Number of days in the success rate window. |
| `WIDGET_TOP_FAILURES_LIMIT`      | `5`     | Maximum entries in the top failures list.  |
| `WIDGET_RECENT_ACTIVITY_LIMIT`   | `20`    | Maximum events in the recent activity feed.|

Set these in your Dimensigon configuration file or as environment variables.

## 7. Troubleshooting

**Widgets show "No data"**
- Ensure there are orchestration executions in the database. The widgets only
  display data from the configured time window.
- Verify the API endpoints are responding: `curl -b cookies.txt http://localhost:5000/dm-webmanager/api/widgets/success-rate`

**Auto-refresh stops working**
- Check for JavaScript errors in the browser console.
- If the JWT session has expired, the API returns 401/302 and auto-refresh
  pauses. Re-login to resume.

**Success rate shows 0% even with successful executions**
- Verify that execution records have the `success` field set properly.
- Check the date range: only the last 7 days are included by default.

## Related Features

- [Tutorial 06: Real-Time Monitoring](06-realtime-monitoring.md) -- watch individual executions in real time.
- [Tutorial 09: Execution History and Diff](09-execution-history-diff.md) -- detailed comparison of two runs.
- [Tutorial 24: Prometheus Metrics](24-prometheus-metrics.md) -- export `dm_orchestration_executions_total` for external dashboards.
