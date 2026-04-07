# Audit Log

- **Priority:** 16
- **Category:** New Feature
- **Effort:** 3-4 days
- **Dependencies:** #1 (SQLAlchemy 2.x Migration)

## Context

There is no record of who did what and when. For compliance, security, and debugging purposes,
every significant action (create, modify, delete, execute, login) must be tracked with user
attribution. An audit log provides accountability and is often a hard requirement in
enterprise environments.

## Scope

- Audit log entity capturing: timestamp, user, action, resource_type, resource_id, details, IP.
- Actions tracked: CRUD on orchestrations, execution launches, login/logout, config changes,
  API key creation/revocation, node registration/removal.
- `@audit_log` decorator for easy annotation of any endpoint.
- Dashboard UI: searchable, filterable log viewer with export capability.
- Retention policy: configurable max age (default 90 days), automatic cleanup.
- Immutable records: audit entries cannot be modified or deleted via API.

## Files to Modify

- `dimensigon/domain/entities/audit.py` (new: AuditEntry model)
- `dimensigon/web/decorators.py` (new `@audit_log` decorator)
- `dimensigon/web/admin/routes.py` (audit log viewer endpoints)
- `dimensigon/web/api_1_0/resources/*.py` (apply `@audit_log` to key endpoints)
- `templates/admin/dashboard.html` (audit log viewer UI)
- DB migration for audit_log table.

## Implementation Steps

1. Define `AuditEntry` entity: id, timestamp, user_id, username, action, resource_type,
   resource_id, details (JSON), ip_address, user_agent.
2. Create DB migration with index on timestamp and user_id.
3. Build `@audit_log(action, resource_type)` decorator that captures request context.
4. Apply decorator to orchestration CRUD, execution launch, login, and config endpoints.
5. Build `GET /dm-webmanager/api/audit` with filters: user, action, resource, date range.
6. Build audit log viewer UI: table with column sorting, filter chips, date range picker.
7. Add CSV/JSON export button.
8. Implement retention cleanup: background task deletes entries older than configured max age.
9. Ensure audit table has no DELETE API endpoint (immutability).
10. Write tests: perform actions, verify audit entries created, test search and filters.

## Verification

- Create an orchestration: audit log shows "create" entry with user and orchestration ID.
- Login: audit log shows "login" entry with IP address.
- Search by user: returns only that user's actions.
- Export as CSV: file contains all filtered entries with correct formatting.

## Breaking Changes

- Adds a small write overhead to every audited endpoint (typically under 1ms).
- New database table will grow over time; retention policy must be configured appropriately.
