"""
DM-WebManager - Dimensigon Administration GUI

This module provides a web-based administration interface for managing
Dimensigon orchestrations, actions, and executions.
"""
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from flask import redirect, url_for, request
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
from werkzeug.exceptions import Forbidden

from dimensigon.web import db
from dimensigon.domain.entities import (
    Orchestration, ActionTemplate, Step,
    OrchExecution, StepExecution, Server, User
)


class SecureModelView(ModelView):
    """Base view with JWT authentication"""

    def is_accessible(self):
        """Check if user is authenticated via JWT"""
        try:
            verify_jwt_in_request()
            # Get user identity and check if they exist
            identity = get_jwt_identity()
            user = User.query.get(identity)
            return user is not None
        except:
            return False

    def inaccessible_callback(self, name, **kwargs):
        """Redirect to login if not accessible"""
        return redirect(url_for('root.token', next=request.url))


class OrchestrationView(SecureModelView):
    """Admin view for Orchestrations with Data Dictionary Browser"""

    column_list = ['name', 'version', 'description', 'last_modified_at']
    column_searchable_list = ['name', 'description']
    column_filters = ['version', 'stop_on_error']  # Removed created_at - not a standard column
    column_default_sort = ('last_modified_at', True)

    # Enable export functionality
    can_export = True
    export_types = ['csv', 'json']

    # Display detailed info
    column_details_list = [
        'id', 'name', 'version', 'description',
        'stop_on_error', 'undo_on_error', 'stop_undo_on_error',
        'created_at', 'last_modified_at'
    ]

    # Form customization
    form_columns = [
        'name', 'version', 'description',
        'stop_on_error', 'undo_on_error', 'stop_undo_on_error'
    ]

    def __init__(self, session, **kwargs):
        super(OrchestrationView, self).__init__(Orchestration, session, **kwargs)


class ActionTemplateView(SecureModelView):
    """Admin view for Action Templates with schema browser"""

    column_list = ['name', 'version', 'action_type', 'description']
    column_searchable_list = ['name', 'description', 'code']
    column_filters = ['action_type', 'version']
    column_default_sort = 'name'

    can_export = True
    export_types = ['csv', 'json']

    column_details_list = [
        'id', 'name', 'version', 'action_type', 'description',
        'code', 'expected_stdout', 'expected_stderr', 'expected_rc',
        'pre_process', 'post_process', 'schema', 'system_kwargs'
    ]

    # Use text area for code fields
    form_widget_args = {
        'code': {'rows': 10},
        'pre_process': {'rows': 5},
        'post_process': {'rows': 5},
        'description': {'rows': 3},
    }

    def __init__(self, session, **kwargs):
        super(ActionTemplateView, self).__init__(ActionTemplate, session, **kwargs)


class StepView(SecureModelView):
    """Admin view for orchestration steps"""

    column_list = ['orchestration', 'action_template', 'undo', 'target']
    column_filters = ['undo', 'orchestration_id']

    column_details_list = [
        'id', 'orchestration_id', 'action_template_id', 'undo',
        'step_name', 'step_description', 'step_code', 'step_action_type',
        'target', 'created_on'
    ]

    def __init__(self, session, **kwargs):
        super(StepView, self).__init__(Step, session, **kwargs)


class OrchExecutionView(SecureModelView):
    """Admin view for orchestration executions"""

    # Read-only view for executions
    can_create = False
    can_edit = False
    can_delete = False
    can_export = True
    export_types = ['csv', 'json']

    column_list = [
        'orchestration', 'start_time', 'end_time',
        'success', 'executor', 'server'
    ]
    column_searchable_list = ['message']
    column_filters = [
        'success', 'undo_success',
        'orchestration_id', 'server_id'
    ]
    column_default_sort = ('start_time', True)

    # Enable pagination
    page_size = 50
    can_set_page_size = True

    column_details_list = [
        'id', 'orchestration_id', 'start_time', 'end_time',
        'target', 'params', 'executor_id', 'service_id', 'server_id',
        'success', 'undo_success', 'message'
    ]

    # Custom formatters for better display
    column_formatters = {
        'start_time': lambda v, c, m, p: m.start_time.strftime('%Y-%m-%d %H:%M:%S') if m.start_time else '',
        'end_time': lambda v, c, m, p: m.end_time.strftime('%Y-%m-%d %H:%M:%S') if m.end_time else 'Running...',
        'success': lambda v, c, m, p: '✅' if m.success else '❌' if m.success is False else '⏳',
    }

    def __init__(self, session, **kwargs):
        super(OrchExecutionView, self).__init__(OrchExecution, session, **kwargs)


class StepExecutionView(SecureModelView):
    """Admin view for step executions"""

    # Read-only view
    can_create = False
    can_edit = False
    can_delete = False
    can_export = True

    column_list = [
        'step', 'server', 'start_time', 'end_time',
        'success', 'rc'
    ]
    column_filters = [
        'success', 'rc',
        'orch_execution_id', 'server_id'
    ]
    column_default_sort = ('start_time', True)

    page_size = 50
    can_set_page_size = True

    column_details_list = [
        'id', 'step_id', 'server_id', 'orch_execution_id',
        'start_time', 'end_time', 'params', 'rc',
        'stdout', 'stderr', 'success',
        'pre_process_elapsed_time', 'execution_elapsed_time',
        'post_process_elapsed_time'
    ]

    column_formatters = {
        'start_time': lambda v, c, m, p: m.start_time.strftime('%Y-%m-%d %H:%M:%S') if m.start_time else '',
        'end_time': lambda v, c, m, p: m.end_time.strftime('%Y-%m-%d %H:%M:%S') if m.end_time else 'Running...',
        'success': lambda v, c, m, p: '✅' if m.success else '❌' if m.success is False else '⏳',
    }

    def __init__(self, session, **kwargs):
        super(StepExecutionView, self).__init__(StepExecution, session, **kwargs)


class ServerView(SecureModelView):
    """Admin view for servers"""

    column_list = ['name', 'granules', '_me', 'created_on']
    column_searchable_list = ['name']
    column_filters = ['_me']

    column_labels = {
        '_me': 'Current Server'
    }

    def __init__(self, session, **kwargs):
        super(ServerView, self).__init__(Server, session, **kwargs)


def init_admin(app):
    """
    Initialize Flask-Admin with DM-WebManager

    Args:
        app: Flask application instance

    Returns:
        Admin instance
    """
    admin = Admin(
        app,
        name='DM-WebManager',
        template_mode='bootstrap4',
        base_template='admin/custom_base.html',
        url='/admin'
    )

    # Add views in logical order
    admin.add_view(OrchestrationView(db.session, name='Orchestrations', category='Workflow'))
    admin.add_view(ActionTemplateView(db.session, name='Action Templates', category='Workflow'))
    admin.add_view(StepView(db.session, name='Steps', category='Workflow'))

    admin.add_view(OrchExecutionView(db.session, name='Executions', category='Monitoring'))
    admin.add_view(StepExecutionView(db.session, name='Step Executions', category='Monitoring'))

    admin.add_view(ServerView(db.session, name='Servers', category='Infrastructure'))

    return admin
