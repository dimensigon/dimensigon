# Lightweight Health Endpoint

- **Priority:** 4
- **Category:** Core
- **Effort:** 3-4 hours
- **Dependencies:** None

## Context

There is no unauthenticated health check endpoint. Container orchestrators (Docker, Kubernetes),
load balancers, and monitoring tools need a fast, no-auth endpoint to determine if a node is
alive and ready. This is also a prerequisite for the topology visualization and container-native
deployment features.

## Scope

- Add `GET /health` endpoint that bypasses all authentication and securizer logic.
- Return a JSON payload: `{"status":"ok","version":"X.Y.Z","node":"<name>","neighbours":<count>}`.
- Response time target: under 10ms (no DB queries in the hot path).
- Cache neighbour count with a short TTL (5 seconds) to avoid repeated lookups.
- Add optional `?detail=true` parameter for extended info (uptime, DB status, memory).

## Files to Modify

- `dimensigon/web/routes.py` (or new `dimensigon/web/health.py`)
- `dimensigon/web/__init__.py` (register blueprint)
- `dimensigon/web/decorators.py` (ensure health route is excluded from securizer)

## Implementation Steps

1. Create a new Flask blueprint `health_bp` with prefix `/health`.
2. Implement `GET /` returning the basic JSON payload.
3. Read version from package metadata or a `__version__` constant.
4. Cache neighbour count using a simple TTL dict or `functools.lru_cache` with expiry.
5. Add `?detail=true` branch with uptime, DB connectivity check, memory usage.
6. Register the blueprint before the securizer middleware in app factory.
7. Write tests: unauthenticated access returns 200, payload schema matches.

## Verification

- `curl http://localhost:5000/health` returns 200 with valid JSON, no auth required.
- `curl http://localhost:5000/health?detail=true` returns extended payload.
- Response time under 10ms confirmed with `time curl`.
- Container HEALTHCHECK directive works with this endpoint.

## Breaking Changes

- None. This is a purely additive endpoint.
