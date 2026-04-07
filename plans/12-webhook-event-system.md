# Webhook / Event System

- **Priority:** 12
- **Category:** New Feature
- **Effort:** 3-4 days
- **Dependencies:** #1 (SQLAlchemy 2.x Migration)

## Context

There is no way to receive notifications when orchestrations complete or fail. Operators
must actively poll or watch the dashboard. Webhooks enable integration with Slack, PagerDuty,
email, and custom tools, bringing dimensigon into existing operational workflows without
requiring operators to change their habits.

## Scope

- Define webhook entity with: URL, event types, headers, retry policy, active flag.
- Supported events: `orchestration.started`, `orchestration.completed`, `orchestration.failed`,
  `step.failed`, `node.offline`, `node.online`.
- Per-orchestration webhook configuration (optional; global webhooks also supported).
- Built-in integrations: Slack (block kit), email (SMTP), PagerDuty (Events API v2), generic HTTP.
- Retry logic: exponential backoff, max 5 retries, dead-letter logging after exhaustion.
- Webhook management UI in the dashboard.

## Files to Modify

- `dimensigon/domain/entities/webhook.py` (new: Webhook model)
- `dimensigon/use_cases/webhooks.py` (new: dispatch logic, retry, integrations)
- `dimensigon/web/api_2_0/webhooks.py` (new: CRUD API for webhooks)
- `dimensigon/web/admin/routes.py` (webhook management UI routes)
- DB migration for webhook and webhook_log tables.

## Implementation Steps

1. Define `Webhook` entity: id, url, event_types (JSON array), headers, retry_policy, active.
2. Define `WebhookLog` entity: id, webhook_id, event, status_code, response, attempt, timestamp.
3. Create DB migration for both tables.
4. Build webhook dispatcher: receives an event, finds matching webhooks, sends HTTP POST.
5. Implement retry with exponential backoff (1s, 2s, 4s, 8s, 16s) using a background task.
6. Build Slack integration: format payload as Slack Block Kit message.
7. Build email integration: send via configured SMTP.
8. Build PagerDuty integration: format as PD Events API v2 payload.
9. Build CRUD API: `GET/POST/PUT/DELETE /api/v2.0/webhooks`.
10. Build dashboard UI: webhook list, create/edit form, test button, log viewer.
11. Wire events: instrument execution engine to emit events to the dispatcher.

## Verification

- Create a webhook for `orchestration.failed` pointing to a request bin.
- Run an orchestration that fails: webhook fires, payload appears in the bin.
- Simulate target down: retries occur with backoff, logged in webhook_log.
- Test Slack integration: message appears in configured channel.

## Breaking Changes

- None. New tables and endpoints only. Existing behavior is unchanged unless webhooks are configured.
