# Orchestration Templates / Marketplace

- **Priority:** 11
- **Category:** New Feature
- **Effort:** 4-5 days
- **Dependencies:** #5 (Authentication Flow Rework), #7 (Visual Orchestration Builder)

## Context

The project includes 6,302 training examples for AI orchestration generation, but these are
only accessible programmatically. Exposing them as a browsable, searchable template library
lets operators bootstrap new orchestrations from proven patterns instead of starting from
scratch. This also creates a feedback loop for community-contributed templates.

## Scope

- Browsable template library UI within the WebManager dashboard.
- Categories: deployment, monitoring, maintenance, security, networking, custom.
- Search by name, description, tags, and action types used.
- One-click "Use Template" that loads the template into the orchestration builder.
- User ratings: thumbs up/down per template with aggregate score display.
- Share across dimensions: export as a portable JSON bundle, import from URL.
- Pagination and lazy loading for the full 6,302+ template catalog.

## Files to Modify

- `dimensigon/web/api_2_0/templates.py` (new: template CRUD and search API)
- `dimensigon/domain/entities/template.py` (new: Template model with rating)
- `templates/admin/dashboard.html` (template browser UI section)
- `dimensigon/web/admin/routes.py` (template browser page routes)
- DB migration for the templates and ratings tables.

## Implementation Steps

1. Define the `Template` entity: id, name, description, category, tags, json_content, rating.
2. Create DB migration for the templates table and ratings table.
3. Write an import script that loads the 6,302 training examples as seed templates.
4. Build `GET /api/v2.0/templates` with search, filter, and pagination parameters.
5. Build `POST /api/v2.0/templates/<id>/rate` for user ratings.
6. Build the template browser UI: card grid with search bar, category filters, sort by rating.
7. Implement "Use Template" button that populates the orchestration builder canvas.
8. Implement export (download as JSON) and import (upload or paste URL).
9. Write tests: search returns relevant results, rating updates correctly, import/export round-trips.

## Verification

- Browse templates page shows categorized cards with search working.
- Search for "nginx deploy" returns relevant templates.
- Click "Use Template": orchestration builder opens with the template pre-loaded.
- Rate a template, refresh page: rating persists and aggregate updates.

## Breaking Changes

- None. New tables and endpoints; no modification to existing orchestration schema.
