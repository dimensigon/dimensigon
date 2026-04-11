# Authentication and Authorization Tutorial

## Overview

Dimensigon 3.0 provides two authentication layers:

1. **API authentication** (`/login`, `/refresh`) -- returns JWT tokens in the
   response body for programmatic clients.
2. **WebManager authentication** (`/dm-webmanager/login`, `/dm-webmanager/refresh`,
   `/dm-webmanager/logout`) -- sets JWT tokens as httpOnly cookies for the
   browser-based admin GUI.

Both layers use Flask-JWT-Extended and share the same token blacklist. This
tutorial covers the full login/refresh/logout cycle, role-based access control,
default users, and configuration options.

## Prerequisites

- A running Dimensigon node with default users initialized
- `curl` for the command-line examples
- Passwords set for the default users (see section 9)

## 1. Login Flow

### API login (for scripts and programmatic clients)

**Endpoint:** `POST /login`

```bash
curl -s -X POST http://localhost:5000/login \
  -H "Content-Type: application/json" \
  -d '{"username": "root", "password": "your-password"}' | python3 -m json.tool
```

**Response (200):**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIs..."
}
```

Use the `access_token` in the `Authorization` header for subsequent requests:

```bash
export TOKEN="eyJhbGciOiJIUzI1NiIs..."
curl -s http://localhost:5000/api/v1.0/servers \
  -H "Authorization: Bearer $TOKEN"
```

### WebManager login (for the browser GUI)

**Endpoint:** `POST /dm-webmanager/login`

```bash
curl -s -X POST http://localhost:5000/dm-webmanager/login \
  -H "Content-Type: application/json" \
  -d '{"username": "root", "password": "your-password"}' \
  -c cookies.txt | python3 -m json.tool
```

**Response (200):**

```json
{
  "message": "Login successful",
  "user": {
    "name": "root",
    "groups": ["administrator"]
  }
}
```

The response sets two httpOnly cookies:

| Cookie | Purpose |
|---|---|
| `access_token_cookie` | Short-lived JWT for request authentication |
| `refresh_token_cookie` | Long-lived JWT for obtaining new access tokens |

## 2. How JWT Cookies Work

When the WebManager login succeeds, Flask-JWT-Extended calls
`set_access_cookies(resp, access_token)` and
`set_refresh_cookies(resp, refresh_token)`, which set cookies with these
attributes:

| Attribute | Value | Purpose |
|---|---|---|
| `httpOnly` | `true` | Prevents JavaScript from reading the token (XSS protection) |
| `Secure` | configurable (`JWT_COOKIE_SECURE`) | If `true`, cookies are only sent over HTTPS |
| `SameSite` | `Lax` (default) | Prevents CSRF on cross-site requests |
| `Path` | `/` for access, `/dm-webmanager/refresh` for refresh | Limits where the cookie is sent |

The relevant configuration keys in `dimensigon/web/config.py`:

```python
JWT_TOKEN_LOCATION = ['headers', 'cookies']
JWT_COOKIE_SECURE = True        # Set to False for local HTTP development
JWT_COOKIE_CSRF_PROTECT = True  # Requires CSRF token in requests
JWT_COOKIE_SAMESITE = 'Lax'
```

## 3. Token Refresh

Access tokens expire after a configurable period (default: 8 hours). Use the
refresh endpoint to obtain a new access token without re-entering credentials.

### API refresh

**Endpoint:** `POST /refresh`

```bash
curl -s -X POST http://localhost:5000/refresh \
  -H "Authorization: Bearer $REFRESH_TOKEN" | python3 -m json.tool
```

**Response (200):**

```json
{
  "username": "root",
  "access_token": "eyJhbGciOiJIUzI1NiIs..."
}
```

### WebManager refresh

**Endpoint:** `POST /dm-webmanager/refresh`

```bash
curl -s -X POST http://localhost:5000/dm-webmanager/refresh \
  -b cookies.txt -c cookies.txt | python3 -m json.tool
```

**Response (200):**

```json
{
  "message": "Token refreshed",
  "user": {
    "name": "root",
    "groups": ["administrator"]
  }
}
```

The response sets a new `access_token_cookie`. The refresh token itself is not
rotated.

## 4. Logout (Token Blacklisting)

**Endpoint:** `POST /dm-webmanager/logout`

```bash
curl -s -X POST http://localhost:5000/dm-webmanager/logout \
  -b cookies.txt | python3 -m json.tool
```

**Response (200):**

```json
{
  "message": "Logged out"
}
```

What happens during logout:

1. The current JWT's `jti` (JWT ID) is added to the in-memory token blacklist
   along with its expiry timestamp.
2. `unset_jwt_cookies(resp)` clears the cookie from the browser.
3. Any subsequent request with the blacklisted token is rejected.

### Token blacklist implementation

The blacklist is an in-memory dictionary (not persisted to database) managed by
the `TokenBlacklist` class in `dimensigon/web/admin/auth.py`:

```python
class TokenBlacklist:
    def __init__(self):
        self._blacklist = {}  # jti -> expiry_timestamp
        self._lock = threading.Lock()

    def add(self, jti, expires_at):
        with self._lock:
            self._blacklist[jti] = expires_at

    def is_blacklisted(self, jti):
        self._cleanup()
        return jti in self._blacklist

    def _cleanup(self):
        # Automatically removes expired entries
        now = time.time()
        with self._lock:
            expired = [jti for jti, exp in self._blacklist.items() if exp < now]
            for jti in expired:
                del self._blacklist[jti]
```

The blacklist check is registered globally with Flask-JWT-Extended in
`dimensigon/web/__init__.py`:

```python
@jwt.token_in_blocklist_loader
def check_if_token_revoked(jwt_header, jwt_payload):
    return token_blacklist.is_blacklisted(jwt_payload.get('jti', ''))
```

Important: since the blacklist is in-memory, it is lost on process restart.
Tokens issued before the restart will still be valid until they expire
naturally. If this is a concern, reduce `JWT_ACCESS_TOKEN_EXPIRES`.

## 5. Role-Based Access Control

Dimensigon uses a simple role hierarchy:

| Role | Level | Description |
|---|---|---|
| `administrator` | 3 | Full access to all features |
| `operator` | 2 | Can execute orchestrations and manage deployments |
| `deployer` | 2 | Same level as operator (deployment-focused alias) |
| `readonly` | 1 | Read-only access to dashboards and data |

The hierarchy is defined in `dimensigon/web/admin/auth.py`:

```python
ROLE_HIERARCHY = {
    'administrator': 3,
    'operator': 2,
    'deployer': 2,
    'readonly': 1,
}
```

A user's effective role level is the highest level among all their groups. For
example, a user with `groups=['operator', 'readonly']` has level 2.

## 6. The `@require_role` Decorator

Use `@require_role` to protect custom endpoints with a minimum role level:

```python
from dimensigon.web.admin.auth import require_role

@app.route('/api/custom/deploy', methods=['POST'])
@require_role('operator')
def trigger_deploy():
    """Only operators and administrators can trigger deployments."""
    # ... deployment logic ...
    return jsonify({'status': 'started'}), 202
```

The decorator:

1. Verifies the JWT from cookies or headers.
2. Checks the token against the blacklist.
3. Loads the user from the database using `db.session.get(User, identity)`.
4. Compares the user's highest role level against the required minimum.
5. Returns 403 Forbidden if the user's level is too low.
6. Redirects to the login page if the JWT is missing or invalid.

## 7. The `@webmanager_auth_required` Middleware

This decorator is used on all WebManager pages. It is similar to
`@require_role` but does not enforce a minimum role -- it only checks that the
user is authenticated and not blacklisted:

```python
from dimensigon.web.admin.auth import webmanager_auth_required

@app.route('/dm-webmanager/settings')
@webmanager_auth_required
def settings_page():
    # g.current_user is set by the decorator
    return render_template('settings.html', user=g.current_user)
```

After successful authentication, `g.current_user` is set to the `User` object
so that templates and view functions can access user information.

## 8. Default Users

Dimensigon creates four default users during bootstrap (see
`dimensigon/domain/entities/user.py`):

| Username | UUID | Groups | Purpose |
|---|---|---|---|
| `root` | `00000000-0000-0000-0000-000000000001` | `['administrator']` | Superuser for administration |
| `ops` | `00000000-0000-0000-0000-000000000002` | `['operator', 'deployer']` | Operational deployments |
| `reporter` | `00000000-0000-0000-0000-000000000003` | `['readonly']` | Dashboard monitoring |
| `join` | `00000000-0000-0000-0000-000000000004` | `['']` | Internal use for node joining |

These users are created without passwords. You must set passwords before they
can log in.

## 9. Setting Passwords for Default Users

### Using the Dimensigon shell (dshell)

```bash
dshell> user set-password root
Enter new password: ********
```

### Using Python directly

```python
from dimensigon.web import create_app, db
from dimensigon.domain.entities import User

app = create_app('development')
with app.app_context():
    root = User.get_by_name('root')
    root.set_password('your-secure-password')

    ops = User.get_by_name('ops')
    ops.set_password('ops-secure-password')

    reporter = User.get_by_name('reporter')
    reporter.set_password('reporter-secure-password')

    db.session.commit()
```

### Using the API (once root has a password)

```bash
# First, log in as root to get a token
TOKEN=$(curl -s -X POST http://localhost:5000/login \
  -H "Content-Type: application/json" \
  -d '{"username": "root", "password": "initial-password"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Then use the user management API to update passwords
curl -s -X PATCH http://localhost:5000/api/v1.0/users/$USER_ID \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"password": "new-secure-password"}'
```

## 10. JWT Configuration

All JWT settings are in the `Config` class (`dimensigon/web/config.py`):

| Key | Default | Description |
|---|---|---|
| `JWT_ACCESS_TOKEN_EXPIRES` | `28800` (8 hours) | Access token lifetime in seconds |
| `JWT_REFRESH_TOKEN_EXPIRES` | `2592000` (30 days) | Refresh token lifetime in seconds |
| `JWT_TOKEN_LOCATION` | `['headers', 'cookies']` | Where to look for tokens |
| `JWT_COOKIE_SECURE` | `True` | Only send cookies over HTTPS |
| `JWT_COOKIE_CSRF_PROTECT` | `True` | Require CSRF double-submit token |
| `JWT_COOKIE_SAMESITE` | `'Lax'` | SameSite cookie attribute |
| `JWT_DECODE_LEEWAY` | `15` | Seconds of clock skew tolerance |
| `SECRET_KEY` | env `DM_SECRET_KEY` | Used to sign JWT tokens |

### Overriding for development

In `TestingConfig` or `DevelopmentConfig`, you may want to relax cookie
settings:

```python
class DevelopmentConfig(Config):
    JWT_COOKIE_SECURE = False         # Allow HTTP (no TLS)
    JWT_COOKIE_CSRF_PROTECT = False   # Disable CSRF for curl testing
```

### Overriding via environment

```bash
export DM_SECRET_KEY='your-production-secret-key'
```

Always set a strong, unique `SECRET_KEY` in production. The default value
(`'hard to guess string'`) is for development only.

## 11. Full Login/Refresh/Logout Cycle with curl

### Step 1: Login

```bash
# WebManager login (sets cookies)
curl -s -X POST http://localhost:5000/dm-webmanager/login \
  -H "Content-Type: application/json" \
  -d '{"username": "root", "password": "your-password"}' \
  -c cookies.txt | python3 -m json.tool
```

### Step 2: Access a protected page

```bash
curl -s http://localhost:5000/dm-webmanager/dashboard \
  -b cookies.txt -w "\nHTTP %{http_code}\n"
# Expected: 200 with HTML dashboard
```

### Step 3: Refresh the token

```bash
curl -s -X POST http://localhost:5000/dm-webmanager/refresh \
  -b cookies.txt -c cookies.txt | python3 -m json.tool
# Expected: 200 with "Token refreshed"
```

### Step 4: Logout

```bash
curl -s -X POST http://localhost:5000/dm-webmanager/logout \
  -b cookies.txt | python3 -m json.tool
# Expected: 200 with "Logged out"
```

### Step 5: Verify logout

```bash
curl -s http://localhost:5000/dm-webmanager/dashboard \
  -b cookies.txt -w "\nHTTP %{http_code}\n" -L
# Expected: redirect to login page (302 -> 200 on /dm-webmanager/login)
```

### API-only cycle (no cookies)

```bash
# Login
TOKENS=$(curl -s -X POST http://localhost:5000/login \
  -H "Content-Type: application/json" \
  -d '{"username": "root", "password": "your-password"}')

ACCESS=$(echo $TOKENS | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
REFRESH=$(echo $TOKENS | python3 -c "import sys,json; print(json.load(sys.stdin)['refresh_token'])")

# Use the access token
curl -s http://localhost:5000/api/v1.0/servers \
  -H "Authorization: Bearer $ACCESS" | python3 -m json.tool

# Refresh when the access token expires
NEW_ACCESS=$(curl -s -X POST http://localhost:5000/refresh \
  -H "Authorization: Bearer $REFRESH" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Use the new access token
curl -s http://localhost:5000/api/v1.0/orchestrations \
  -H "Authorization: Bearer $NEW_ACCESS" | python3 -m json.tool
```

## Troubleshooting

### "Bad username or password" (401)

- Verify the username exists: check the `D_user` table.
- Verify the password was set. Default users are created without passwords.
- Password hashing uses `sha256_crypt` from passlib. Ensure the stored hash
  is not empty.

### "Account is disabled" (403)

The WebManager login checks `user.active`. If the account was deactivated,
re-enable it:

```python
user = User.get_by_name('root')
user.active = True
db.session.commit()
```

### "Insufficient permissions" (403)

The user's role level is below the required minimum. Check the user's groups:

```python
user = User.get_by_name('ops')
print(user.groups)  # ['operator', 'deployer']
```

If the endpoint requires `administrator`, an `operator` user will get 403.

### Token is rejected after server restart

The in-memory blacklist is cleared on restart, but old tokens should still
work (they are validated by signature, not blacklist). If tokens fail after
restart, check that `SECRET_KEY` has not changed. A different key invalidates
all previously issued tokens.

### CSRF errors with cookie-based auth

If `JWT_COOKIE_CSRF_PROTECT = True`, the client must send the CSRF token in a
header. Flask-JWT-Extended provides the CSRF token as a non-httpOnly cookie
named `csrf_access_token`. JavaScript clients should read it and send it as the
`X-CSRF-TOKEN` header:

```javascript
const csrfToken = document.cookie
  .split('; ')
  .find(row => row.startsWith('csrf_access_token='))
  ?.split('=')[1];

fetch('/dm-webmanager/api/endpoint', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-CSRF-TOKEN': csrfToken,
  },
  body: JSON.stringify(data),
});
```

### Cookies not being sent over HTTP

Set `JWT_COOKIE_SECURE = False` in your development configuration. The
`Secure` flag prevents cookies from being sent over unencrypted connections.

## Related Features

- [Health Endpoint Tutorial](04-health-endpoint.md) -- unauthenticated endpoint
- [Security Layer Tutorial](02-security-layer.md) -- encryption layer
- [SQLAlchemy Migration](01-sqlalchemy-migration.md) -- how user lookups work
- Source code: `dimensigon/web/admin/auth.py` (TokenBlacklist, require_role,
  webmanager_auth_required)
- Source code: `dimensigon/web/admin/routes.py` (login, logout, refresh)
- Source code: `dimensigon/web/routes.py` (API login, refresh)
- Source code: `dimensigon/domain/entities/user.py` (User model, default users)
- Source code: `dimensigon/web/config.py` (JWT configuration)
