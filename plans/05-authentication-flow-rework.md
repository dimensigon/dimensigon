# Authentication Flow Rework

- **Priority:** 5
- **Category:** WebManager
- **Effort:** 3-4 days
- **Dependencies:** None

## Context

The current WebManager has minimal authentication -- no proper login page, no token refresh,
and no role-based access control. Every WebManager feature (execution monitoring, orchestration
builder, topology view) requires a solid auth foundation first. This is the gateway feature
for the entire WebManager category.

## Scope

- Build a dedicated login page at `/dm-webmanager/login` with username/password form.
- Implement JWT-based session tokens with configurable expiry (default 8 hours).
- Add automatic token refresh when token is within 15 minutes of expiry.
- Store session in httpOnly secure cookies (not localStorage).
- Implement role-based access: `admin`, `operator`, `viewer`.
- Add logout endpoint that invalidates the token server-side.
- Protect all `/dm-webmanager/*` routes behind the auth middleware.

## Files to Modify

- `templates/admin/dashboard.html` (add login page, auth state management)
- `dimensigon/web/admin/routes.py` (login/logout endpoints, auth middleware)
- `dimensigon/web/admin/auth.py` (new: JWT logic, role checks)
- `dimensigon/web/config.py` (JWT secret, expiry settings)

## Implementation Steps

1. Create `auth.py` with JWT encode/decode, role enum, and `@require_role` decorator.
2. Add `/dm-webmanager/login` POST endpoint that validates credentials and returns JWT.
3. Build login page HTML/CSS in dashboard SPA with form and error handling.
4. Add auth middleware that checks JWT on every `/dm-webmanager/*` request.
5. Implement token refresh logic: client-side timer + server-side `/refresh` endpoint.
6. Add `@require_role('admin')` to destructive actions, `@require_role('viewer')` to reads.
7. Add logout endpoint that adds token to a short-lived blacklist.
8. Write tests for login, refresh, role enforcement, and logout flows.

## Verification

- Unauthenticated access to `/dm-webmanager/` redirects to login page.
- Valid credentials produce a JWT and redirect to dashboard.
- Expired tokens trigger automatic refresh or redirect to login.
- `viewer` role cannot access admin-only endpoints (returns 403).
- Logout invalidates the session immediately.

## Breaking Changes

- All existing bookmarks to `/dm-webmanager/*` will now require login first.
- Any automation scripts hitting admin routes need to acquire a token.
