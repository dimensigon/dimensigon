# Scheduled Orchestrations (Cron)

- **Priority:** 13
- **Category:** New Feature
- **Effort:** 3-4 days
- **Dependencies:** #1 (SQLAlchemy 2.x Migration), #5 (Authentication Flow Rework)

## Context

Operators frequently need to run orchestrations on a recurring schedule (health checks, backups,
log rotation, compliance scans). Currently this requires external cron jobs calling the API,
which is fragile and hard to manage. Built-in scheduling centralizes this and provides
visibility into upcoming and past scheduled runs.

## Scope

- Define schedule entity linking an orchestration to a cron expression.
- Standard cron syntax (5 fields) plus predefined shortcuts (@hourly, @daily, @weekly).
- Dashboard UI: list of schedules, next run time, last result, enable/disable toggle.
- Create/edit schedule form with cron expression builder (visual picker).
- Missed-run policy: `skip` (default) or `run_once` (catch up with a single execution).
- Timezone support per schedule (default UTC).

## Files to Modify

- `dimensigon/domain/entities/schedule.py` (new: Schedule model)
- `dimensigon/use_cases/scheduler.py` (new: scheduler loop, cron parsing)
- `dimensigon/web/api_2_0/schedules.py` (new: CRUD API for schedules)
- `dimensigon/web/admin/routes.py` (schedule management UI routes)
- `dimensigon/web/__init__.py` (start scheduler background thread)
- DB migration for schedule table.

## Implementation Steps

1. Define `Schedule` entity: id, orchestration_id, cron_expr, timezone, enabled, last_run,
   next_run, missed_policy, created_by.
2. Create DB migration.
3. Implement cron parser using the `croniter` library (add to requirements).
4. Build scheduler loop: runs as a background thread, checks for due schedules every 30 seconds.
5. On trigger: launch the orchestration with stored parameters, update last_run and next_run.
6. Handle missed runs: if next_run is in the past, apply missed_policy.
7. Build CRUD API: `GET/POST/PUT/DELETE /api/v2.0/schedules`.
8. Build dashboard UI: schedule list with columns (orchestration, cron, next run, last status).
9. Add cron expression builder: clickable dropdowns for minute/hour/day/month/weekday.
10. Add enable/disable toggle that PATCHes the schedule's `enabled` field.

## Verification

- Create a schedule with `*/5 * * * *` (every 5 minutes): orchestration runs on time.
- Disable the schedule: runs stop. Re-enable: next run calculated correctly.
- Set timezone to a non-UTC zone: runs fire at the correct local time.
- Dashboard shows accurate next-run times and last execution status.

## Breaking Changes

- None. New entity and endpoints. Adds `croniter` as a dependency.
