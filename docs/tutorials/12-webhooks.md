# Tutorial 12: Webhooks

Integrate Dimensigon with external tools by configuring webhooks that deliver real-time event notifications to any HTTP endpoint. This tutorial covers the full webhook lifecycle: creating, testing, monitoring, and managing webhook subscriptions.

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Creating a Webhook](#creating-a-webhook)
4. [Supported Event Types](#supported-event-types)
5. [Webhook Payload Format](#webhook-payload-format)
6. [Testing a Webhook](#testing-a-webhook)
7. [Viewing Delivery Logs](#viewing-delivery-logs)
8. [Retry Logic](#retry-logic)
9. [Updating a Webhook](#updating-a-webhook)
10. [Deleting a Webhook](#deleting-a-webhook)
11. [Integration Examples](#integration-examples)
12. [Configuration Reference](#configuration-reference)
13. [Related Features](#related-features)

---

## Overview

Webhooks allow Dimensigon to push event notifications to external services whenever significant actions occur, such as an orchestration completing, a step failing, or a node going offline. Instead of polling the API for status changes, your external tools receive HTTP POST requests in real time.

Common use cases:

- Send Slack messages when orchestrations fail
- Trigger PagerDuty incidents when nodes go offline
- Feed orchestration metrics into monitoring dashboards
- Relay failure alerts to email distribution lists
- Update CMDB records when node status changes

---

## Prerequisites

- A running Dimensigon 3.0 cluster
- An administrator account with API access
- A valid JWT token (see the [API Reference](../api/API_REFERENCE.md) for authentication)
- An external HTTP endpoint to receive webhook deliveries (or a tool like [webhook.site](https://webhook.site) for testing)

### Obtain a JWT Token

```bash
# Authenticate and store the token
TOKEN=$(curl -s -X POST http://localhost:5000/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "your_password"
  }' | jq -r '.access_token')

echo $TOKEN
```

All subsequent `curl` examples assume the `$TOKEN` variable is set.

---

## Creating a Webhook

Register a new webhook subscription by specifying a target URL and the event types you want to receive.

**POST** `/dm-webmanager/api/webhooks`

### Request

```bash
curl -X POST http://localhost:5000/dm-webmanager/api/webhooks \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Slack Failure Alerts",
    "url": "https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXX",
    "events": [
      "orchestration.failed",
      "step.failed",
      "node.offline"
    ],
    "secret": "my-webhook-secret-key",
    "enabled": true
  }'
```

### Request Body Schema

| Field     | Type     | Required | Description                                         |
|-----------|----------|----------|-----------------------------------------------------|
| `name`    | string   | Yes      | Human-readable name for the webhook                 |
| `url`     | string   | Yes      | The HTTPS endpoint that will receive POST requests  |
| `events`  | string[] | Yes      | List of event types to subscribe to                 |
| `secret`  | string   | No       | Shared secret used to sign payloads (HMAC-SHA256)   |
| `enabled` | boolean  | No       | Whether the webhook is active (default: `true`)     |
| `headers` | object   | No       | Custom HTTP headers to include in deliveries        |

### Response (201 Created)

```json
{
  "id": "wh-a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "name": "Slack Failure Alerts",
  "url": "https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXX",
  "events": [
    "orchestration.failed",
    "step.failed",
    "node.offline"
  ],
  "secret": "****",
  "enabled": true,
  "headers": {},
  "created_at": "2026-04-07T10:30:00Z",
  "updated_at": "2026-04-07T10:30:00Z"
}
```

---

## Supported Event Types

Dimensigon emits webhooks for the following events:

| Event Type                  | Trigger                                              |
|-----------------------------|------------------------------------------------------|
| `orchestration.started`     | An orchestration execution begins                    |
| `orchestration.completed`   | An orchestration execution finishes successfully     |
| `orchestration.failed`      | An orchestration execution finishes with errors      |
| `step.failed`               | An individual step within an orchestration fails     |
| `node.offline`              | A node in the cluster becomes unreachable            |
| `node.online`               | A previously offline node rejoins the cluster        |

You can subscribe a single webhook to multiple events by listing them in the `events` array.

### Subscribe to All Events

```bash
curl -X POST http://localhost:5000/dm-webmanager/api/webhooks \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "All Events Monitor",
    "url": "https://monitor.example.com/dimensigon/events",
    "events": [
      "orchestration.started",
      "orchestration.completed",
      "orchestration.failed",
      "step.failed",
      "node.offline",
      "node.online"
    ],
    "secret": "monitor-secret-2026"
  }'
```

---

## Webhook Payload Format

Every webhook delivery is an HTTP POST request with a JSON body. The payload structure is consistent across all event types.

### Headers

| Header                        | Description                                         |
|-------------------------------|-----------------------------------------------------|
| `Content-Type`                | Always `application/json`                           |
| `X-Dimensigon-Event`         | The event type (e.g., `orchestration.failed`)       |
| `X-Dimensigon-Delivery`      | Unique delivery ID (UUID)                           |
| `X-Dimensigon-Signature-256` | HMAC-SHA256 signature of the body (if secret is set)|
| `X-Dimensigon-Timestamp`     | Unix timestamp of when the event was emitted        |

### Payload Body

```json
{
  "id": "evt-f1e2d3c4-b5a6-7890-1234-567890abcdef",
  "event": "orchestration.failed",
  "timestamp": "2026-04-07T14:22:33Z",
  "data": {
    "orchestration_id": "orch-12345678-abcd-ef01-2345-6789abcdef01",
    "orchestration_name": "Deploy Web Servers",
    "execution_id": "exec-aabbccdd-1122-3344-5566-778899001122",
    "status": "FAILED",
    "error": "Step 'Install Packages' failed on node web-02",
    "node": "web-02",
    "started_at": "2026-04-07T14:20:00Z",
    "finished_at": "2026-04-07T14:22:33Z",
    "duration_seconds": 153
  }
}
```

### Verifying the Signature

If you configured a `secret`, verify the delivery using HMAC-SHA256:

```python
import hmac
import hashlib

def verify_signature(payload_body, secret, signature_header):
    expected = hmac.new(
        secret.encode("utf-8"),
        payload_body,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature_header)
```

---

## Testing a Webhook

Before relying on a webhook in production, send a test delivery to verify connectivity and payload handling.

**POST** `/dm-webmanager/api/webhooks/<id>/test`

```bash
curl -X POST http://localhost:5000/dm-webmanager/api/webhooks/wh-a1b2c3d4-e5f6-7890-abcd-ef1234567890/test \
  -H "Authorization: Bearer $TOKEN"
```

### Response (200 OK)

```json
{
  "delivery_id": "del-99887766-5544-3322-1100-ffeeddccbbaa",
  "status": "delivered",
  "response_code": 200,
  "response_time_ms": 142,
  "message": "Test delivery sent successfully"
}
```

### Response (422 Unprocessable Entity)

If the target endpoint is unreachable or returns an error:

```json
{
  "delivery_id": "del-aabbccdd-eeff-0011-2233-445566778899",
  "status": "failed",
  "response_code": 502,
  "response_time_ms": 5023,
  "message": "Target endpoint returned HTTP 502"
}
```

---

## Viewing Delivery Logs

Inspect the history of deliveries for a specific webhook to troubleshoot failures.

**GET** `/dm-webmanager/api/webhooks/<id>/logs`

```bash
curl -X GET "http://localhost:5000/dm-webmanager/api/webhooks/wh-a1b2c3d4-e5f6-7890-abcd-ef1234567890/logs?page=1&per_page=20" \
  -H "Authorization: Bearer $TOKEN"
```

### Response (200 OK)

```json
{
  "webhook_id": "wh-a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "total": 47,
  "page": 1,
  "per_page": 20,
  "logs": [
    {
      "delivery_id": "del-11223344-5566-7788-99aa-bbccddeeff00",
      "event": "orchestration.failed",
      "status": "delivered",
      "response_code": 200,
      "response_time_ms": 89,
      "attempt": 1,
      "timestamp": "2026-04-07T14:22:34Z"
    },
    {
      "delivery_id": "del-ffeeddcc-bbaa-9988-7766-554433221100",
      "event": "node.offline",
      "status": "failed",
      "response_code": 503,
      "response_time_ms": 30012,
      "attempt": 5,
      "timestamp": "2026-04-07T13:10:05Z",
      "error": "Max retries exceeded"
    }
  ]
}
```

### Filter by Status

```bash
# Show only failed deliveries
curl -X GET "http://localhost:5000/dm-webmanager/api/webhooks/wh-a1b2c3d4-e5f6-7890-abcd-ef1234567890/logs?status=failed" \
  -H "Authorization: Bearer $TOKEN"
```

---

## Retry Logic

When a webhook delivery fails (non-2xx response or network timeout), Dimensigon retries using exponential backoff:

| Attempt | Delay After Failure |
|---------|---------------------|
| 1       | Immediate           |
| 2       | 1 second            |
| 3       | 2 seconds           |
| 4       | 4 seconds           |
| 5       | 8 seconds           |
| 6 (max) | 16 seconds          |

- **Maximum retries:** 5 (6 total attempts including the first)
- **Backoff formula:** `delay = 2^(attempt - 2)` seconds (starting from retry 2)
- **Timeout per attempt:** 30 seconds
- **Failure status:** If all retries are exhausted, the delivery is marked as `failed` in the logs

A delivery is considered successful if the target endpoint returns any HTTP 2xx status code.

---

## Updating a Webhook

Modify an existing webhook's properties, such as the target URL, subscribed events, or enabled status.

**PUT** `/dm-webmanager/api/webhooks/<id>`

```bash
curl -X PUT http://localhost:5000/dm-webmanager/api/webhooks/wh-a1b2c3d4-e5f6-7890-abcd-ef1234567890 \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Slack All Alerts",
    "url": "https://hooks.slack.com/services/T00000000/B00000000/YYYYYYYY",
    "events": [
      "orchestration.failed",
      "orchestration.completed",
      "step.failed",
      "node.offline",
      "node.online"
    ],
    "enabled": true
  }'
```

### Response (200 OK)

```json
{
  "id": "wh-a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "name": "Slack All Alerts",
  "url": "https://hooks.slack.com/services/T00000000/B00000000/YYYYYYYY",
  "events": [
    "orchestration.failed",
    "orchestration.completed",
    "step.failed",
    "node.offline",
    "node.online"
  ],
  "enabled": true,
  "updated_at": "2026-04-07T15:00:00Z"
}
```

### Disable a Webhook Without Deleting

```bash
curl -X PUT http://localhost:5000/dm-webmanager/api/webhooks/wh-a1b2c3d4-e5f6-7890-abcd-ef1234567890 \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "enabled": false
  }'
```

---

## Deleting a Webhook

Permanently remove a webhook subscription and all its delivery logs.

**DELETE** `/dm-webmanager/api/webhooks/<id>`

```bash
curl -X DELETE http://localhost:5000/dm-webmanager/api/webhooks/wh-a1b2c3d4-e5f6-7890-abcd-ef1234567890 \
  -H "Authorization: Bearer $TOKEN"
```

### Response (204 No Content)

No response body is returned on successful deletion.

### List All Webhooks

To see all registered webhooks before deleting:

```bash
curl -X GET http://localhost:5000/dm-webmanager/api/webhooks \
  -H "Authorization: Bearer $TOKEN"
```

---

## Integration Examples

### Slack Integration

Send orchestration failure alerts to a Slack channel:

```bash
curl -X POST http://localhost:5000/dm-webmanager/api/webhooks \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Slack #ops-alerts",
    "url": "https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXX",
    "events": [
      "orchestration.failed",
      "step.failed",
      "node.offline"
    ],
    "secret": "slack-webhook-secret"
  }'
```

On the receiving end, Slack will display the raw JSON payload. For formatted messages, place a lightweight relay service between Dimensigon and Slack that transforms the payload into Slack Block Kit format:

```python
# Example relay (Flask)
from flask import Flask, request, jsonify
import requests

app = Flask(__name__)
SLACK_WEBHOOK = "https://hooks.slack.com/services/T.../B.../XXX"

@app.route("/relay", methods=["POST"])
def relay():
    event = request.json
    slack_msg = {
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{event['event']}*\n{event['data'].get('error', 'No details')}"
                }
            }
        ]
    }
    requests.post(SLACK_WEBHOOK, json=slack_msg)
    return jsonify({"ok": True}), 200
```

### PagerDuty Integration

Trigger PagerDuty incidents when nodes go offline:

```bash
curl -X POST http://localhost:5000/dm-webmanager/api/webhooks \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "PagerDuty Node Alerts",
    "url": "https://events.pagerduty.com/v2/enqueue",
    "events": [
      "node.offline",
      "orchestration.failed"
    ],
    "headers": {
      "X-Routing-Key": "your-pagerduty-integration-key"
    },
    "secret": "pagerduty-secret"
  }'
```

> **Note:** PagerDuty expects a specific payload format. Use a relay service to transform the Dimensigon event payload into the PagerDuty Events API v2 schema.

### Email Relay Integration

Forward events to an email distribution list via an SMTP relay endpoint:

```bash
curl -X POST http://localhost:5000/dm-webmanager/api/webhooks \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Email Relay - Critical Failures",
    "url": "https://your-relay.example.com/email-notify",
    "events": [
      "orchestration.failed",
      "node.offline"
    ],
    "headers": {
      "X-Email-To": "ops-team@example.com",
      "X-Email-Subject-Prefix": "[Dimensigon Alert]"
    },
    "secret": "email-relay-secret"
  }'
```

---

## Configuration Reference

### Webhook Limits

| Setting                   | Default | Description                              |
|---------------------------|---------|------------------------------------------|
| Max webhooks per instance | 50      | Maximum number of registered webhooks    |
| Max events per webhook    | 10      | Maximum event subscriptions per webhook  |
| Delivery timeout          | 30s     | HTTP timeout for each delivery attempt   |
| Max retries               | 5       | Maximum retry attempts after failure     |
| Log retention             | 30 days | How long delivery logs are retained      |

### Security Recommendations

- Always use HTTPS URLs for webhook endpoints
- Configure a `secret` on every webhook and verify signatures on the receiving end
- Rotate webhook secrets periodically
- Monitor delivery logs for repeated failures
- Use the test endpoint to verify connectivity before going live

---

## Related Features

- [Tutorial 13: Scheduled Orchestrations](13-scheduled-orchestrations.md) -- Combine webhooks with schedules for automated alerting on recurring jobs
- [Tutorial 16: Audit Log](16-audit-log.md) -- Webhook creation, updates, and deletions are recorded in the audit log
- [Tutorial 14: Orchestration Versioning](14-orchestration-versioning.md) -- Track which version of an orchestration triggered a webhook event
