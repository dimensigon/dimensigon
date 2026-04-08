"""
Admin routes for DM-WebManager dashboard
"""
import time

from flask import Blueprint, render_template, redirect, url_for, request, jsonify, make_response
from flask_jwt_extended import (
    create_access_token, create_refresh_token, get_jwt_identity,
    get_jwt, set_access_cookies, set_refresh_cookies, unset_jwt_cookies,
    jwt_required
)

from dimensigon.domain.entities import User
from dimensigon.web import db
from dimensigon.web.admin.auth import (
    webmanager_auth_required, require_role, token_blacklist
)

admin_routes_bp = Blueprint('admin_routes', __name__, url_prefix='/dm-webmanager')


# --- Authentication endpoints ---

@admin_routes_bp.route('/login', methods=['GET'])
def login_page():
    """Render the login page."""
    return render_template('admin/login.html')


@admin_routes_bp.route('/login', methods=['POST'])
def login():
    """Authenticate user and set JWT cookies."""
    data = request.get_json(silent=True) or {}
    username = data.get('username', '')
    password = data.get('password', '')

    user = User.get_by_name(username)
    try:
        if not user or not user.verify_password(password):
            return jsonify({'error': 'Invalid username or password'}), 401
    except TypeError:
        return jsonify({'error': 'Invalid username or password'}), 401

    if not user.active:
        return jsonify({'error': 'Account is disabled'}), 403

    access_token = create_access_token(identity=str(user.id), fresh=True)
    refresh_token = create_refresh_token(identity=str(user.id))

    resp = make_response(jsonify({
        'message': 'Login successful',
        'user': {'name': user.name, 'groups': user.groups},
    }))
    set_access_cookies(resp, access_token)
    set_refresh_cookies(resp, refresh_token)
    return resp, 200


@admin_routes_bp.route('/logout', methods=['POST'])
@jwt_required(locations=['cookies', 'headers'], optional=True)
def logout():
    """Logout: blacklist current token and clear cookies."""
    try:
        jwt_data = get_jwt()
        jti = jwt_data.get('jti')
        exp = jwt_data.get('exp', time.time() + 28800)
        if jti:
            token_blacklist.add(jti, exp)
    except Exception:
        pass

    resp = make_response(jsonify({'message': 'Logged out'}))
    unset_jwt_cookies(resp)
    return resp, 200


@admin_routes_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True, locations=['cookies', 'headers'])
def refresh():
    """Refresh access token."""
    identity = get_jwt_identity()
    user = db.session.get(User, identity)
    if not user or not user.active:
        return jsonify({'error': 'Invalid session'}), 401

    access_token = create_access_token(identity=identity, fresh=False)
    resp = make_response(jsonify({
        'message': 'Token refreshed',
        'user': {'name': user.name, 'groups': user.groups},
    }))
    set_access_cookies(resp, access_token)
    return resp, 200


# --- Protected WebManager pages ---

@admin_routes_bp.route('/')
@admin_routes_bp.route('/dashboard')
@webmanager_auth_required
def dashboard():
    """Render the DM-WebManager dashboard"""
    return render_template('admin/dashboard.html')


@admin_routes_bp.route('/orchestrations')
@webmanager_auth_required
def orchestrations():
    """Render orchestrations management page"""
    return render_template('admin/dashboard.html')


@admin_routes_bp.route('/executions')
@webmanager_auth_required
def executions():
    """Render executions monitoring page"""
    return render_template('admin/dashboard.html')


@admin_routes_bp.route('/data-dictionary')
@webmanager_auth_required
def data_dictionary():
    """Render data dictionary browser"""
    return render_template('admin/dashboard.html')
