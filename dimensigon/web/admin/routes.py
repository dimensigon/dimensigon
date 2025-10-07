"""
Admin routes for DM-WebManager dashboard
"""
from flask import Blueprint, render_template, redirect, url_for
from flask_jwt_extended import jwt_required, get_jwt_identity

admin_routes_bp = Blueprint('admin_routes', __name__, url_prefix='/dm-webmanager')


@admin_routes_bp.route('/')
@admin_routes_bp.route('/dashboard')
def dashboard():
    """Render the DM-WebManager dashboard"""
    return render_template('admin/dashboard.html')


@admin_routes_bp.route('/orchestrations')
def orchestrations():
    """Render orchestrations management page"""
    return render_template('admin/dashboard.html')


@admin_routes_bp.route('/executions')
def executions():
    """Render executions monitoring page"""
    return render_template('admin/dashboard.html')


@admin_routes_bp.route('/data-dictionary')
def data_dictionary():
    """Render data dictionary browser"""
    return render_template('admin/dashboard.html')
