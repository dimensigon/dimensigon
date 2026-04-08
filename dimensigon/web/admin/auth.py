"""
Authentication and authorization for DM-WebManager.

Provides role-based access control, token blacklisting, and auth middleware.
"""
import functools
import threading
import time

from flask import redirect, url_for, request, g, jsonify
from flask_jwt_extended import (
    verify_jwt_in_request, get_jwt_identity, get_jwt,
    create_access_token, create_refresh_token, set_access_cookies,
    set_refresh_cookies, unset_jwt_cookies
)

from dimensigon.web import db

# Role hierarchy: administrator > operator > readonly
ROLE_HIERARCHY = {
    'administrator': 3,
    'operator': 2,
    'deployer': 2,
    'readonly': 1,
}


class TokenBlacklist:
    """In-memory token blacklist with TTL-based cleanup."""

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
        now = time.time()
        with self._lock:
            expired = [jti for jti, exp in self._blacklist.items() if exp < now]
            for jti in expired:
                del self._blacklist[jti]


token_blacklist = TokenBlacklist()


def get_user_role_level(user):
    """Get the highest role level for a user."""
    if not user or not user.groups:
        return 0
    return max((ROLE_HIERARCHY.get(g, 0) for g in user.groups), default=0)


def require_role(min_role):
    """Decorator to enforce minimum role level on a view.

    Usage:
        @require_role('operator')  # requires operator or administrator
        def my_view():
            ...
    """
    min_level = ROLE_HIERARCHY.get(min_role, 0)

    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            from dimensigon.domain.entities import User
            try:
                verify_jwt_in_request(locations=['cookies', 'headers'])
                jwt_data = get_jwt()
                if token_blacklist.is_blacklisted(jwt_data.get('jti', '')):
                    return redirect(url_for('admin_routes.login_page'))

                user = db.session.get(User, get_jwt_identity())
                if not user or get_user_role_level(user) < min_level:
                    return jsonify({'error': 'Insufficient permissions'}), 403
            except Exception:
                return redirect(url_for('admin_routes.login_page', next=request.url))
            return f(*args, **kwargs)
        return wrapper
    return decorator


def webmanager_auth_required(f):
    """Auth middleware for /dm-webmanager/* routes.

    Checks JWT from cookies (or headers as fallback).
    Redirects to login page if not authenticated.
    """
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        from dimensigon.domain.entities import User
        try:
            verify_jwt_in_request(locations=['cookies', 'headers'])
            jwt_data = get_jwt()
            if token_blacklist.is_blacklisted(jwt_data.get('jti', '')):
                return redirect(url_for('admin_routes.login_page'))

            user = db.session.get(User, get_jwt_identity())
            if not user:
                return redirect(url_for('admin_routes.login_page'))
            g.current_user = user
        except Exception:
            return redirect(url_for('admin_routes.login_page', next=request.url))
        return f(*args, **kwargs)
    return wrapper
