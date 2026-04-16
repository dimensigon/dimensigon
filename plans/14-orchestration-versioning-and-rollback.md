# Orchestration Versioning & Rollback

- **Priority:** 14
- **Category:** New Feature
- **Effort:** 3 days
- **Dependencies:** #5 (Authentication Flow Rework)

## Context

When an orchestration is modified and the new version breaks, there is no easy way to see
what changed or revert to the previous working version. Versioning provides an audit trail
of changes, and rollback provides a safety net that encourages operators to iterate faster
without fear of losing working configurations.

## Scope

- Store every save of an orchestration as a new version (immutable snapshots).
- Version history timeline in the dashboard: list of versions with timestamp and author.
- Diff view: show steps added, removed, or changed between any two versions.
- Rollback button: revert to a selected previous version (creates a new version, not destructive).
- Version metadata: author, timestamp, optional commit message.
- API support: `GET /orchestrations/<id>/versions`, `POST /orchestrations/<id>/rollback/<version>`.

## Files to Modify

- `dimensigon/web/api_1_0/resources/orchestration.py` (versioning on save, version list endpoint)
- `dimensigon/domain/entities/orchestration.py` (version tracking fields or separate version table)
- `templates/admin/dashboard.html` (version history timeline, diff viewer, rollback button)
- `dimensigon/web/admin/routes.py` (version history and rollback UI routes)
- DB migration for orchestration_version table.

## Implementation Steps

1. Create `OrchestrationVersion` entity: id, orchestration_id, version_number, json_snapshot,
   author, message, created_at.
2. Create DB migration.
3. Modify orchestration save logic: on every PUT, store current state as a new version.
4. Build `GET /api/v1.0/orchestrations/<id>/versions` returning version list.
5. Build `GET /api/v1.0/orchestrations/<id>/versions/<v>/diff/<v2>` returning JSON diff.
6. Build `POST /api/v1.0/orchestrations/<id>/rollback/<version>` that restores the snapshot.
7. Build version timeline UI: vertical list with version badges, author, and timestamp.
8. Build diff viewer: two-column layout highlighting additions (green) and removals (red).
9. Add rollback button with confirmation dialog showing what will change.
10. Write tests: save 3 versions, diff v1 vs v3, rollback to v1, verify state.

## Verification

- Edit an orchestration 3 times: version history shows versions 1, 2, and 3.
- Diff v1 vs v3: changes are highlighted correctly.
- Rollback to v1: orchestration content matches v1, version 4 is created.
- API returns correct version list and diff payloads.

## Breaking Changes

- Orchestration save now creates a version record. This increases DB writes slightly.
- Existing orchestrations will start with version 1 (no prior history available).
