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

from collections import defaultdict

from datetime import datetime, timedelta, timezone

from dimensigon.domain.entities import User, Orchestration, Step, ActionTemplate, ActionType, Server, Route, Gate
from dimensigon.domain.entities import OrchExecution
from sqlalchemy import select, func
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


# --- Real-time execution monitoring ---

@admin_routes_bp.route('/executions/<execution_id>/cancel', methods=['POST'])
@require_role('operator')
def cancel_execution(execution_id):
    """Cancel a running execution."""
    from dimensigon.domain.entities import OrchExecution
    from dimensigon.web.admin.ws import request_cancel

    execution = db.session.get(OrchExecution, execution_id)
    if not execution:
        return jsonify({'error': 'Execution not found'}), 404
    if execution.end_time is not None:
        return jsonify({'error': 'Execution already completed'}), 409

    request_cancel(execution_id)
    return jsonify({'message': 'Cancellation requested', 'execution_id': execution_id}), 200


# --- Orchestration Builder API ---

@admin_routes_bp.route('/api/builder/action-templates', methods=['GET'])
@webmanager_auth_required
def builder_action_templates():
    """Return list of available action templates for the node palette."""
    templates = db.session.execute(select(ActionTemplate)).scalars().all()
    result = []
    for at in templates:
        result.append({
            'id': str(at.id),
            'name': at.name,
            'version': at.version,
            'action_type': at.action_type.name,
            'description': at.description,
            'schema': at.schema or {},
        })
    return jsonify(result), 200


@admin_routes_bp.route('/api/builder/orchestrations/<orchestration_id>', methods=['GET'])
@webmanager_auth_required
def builder_load_orchestration(orchestration_id):
    """Load an existing orchestration with its steps and dependencies for editing."""
    orchestration = db.session.get(Orchestration, orchestration_id)
    if not orchestration:
        return jsonify({'error': 'Orchestration not found'}), 404

    steps_data = []
    for step in orchestration.steps:
        steps_data.append({
            'id': str(step.id),
            'name': step.name,
            'description': step.description,
            'undo': step.undo,
            'action_template_id': str(step.action_template_id) if step.action_template_id else None,
            'action_template': step.action_template.to_json() if step.action_template else None,
            'action_type': step.action_type.name if step.action_type else None,
            'target': step.target,
            'parent_step_ids': [str(p.id) for p in step.parent_steps],
            'children_step_ids': [str(c.id) for c in step.children_steps],
            'stop_on_error': step.step_stop_on_error,
            'undo_on_error': step.step_undo_on_error,
            'schema': step.step_schema or {},
        })

    data = {
        'id': str(orchestration.id),
        'name': orchestration.name,
        'version': orchestration.version,
        'description': orchestration.description,
        'stop_on_error': orchestration.stop_on_error,
        'stop_undo_on_error': orchestration.stop_undo_on_error,
        'undo_on_error': orchestration.undo_on_error,
        'steps': steps_data,
    }
    return jsonify(data), 200


@admin_routes_bp.route('/api/builder/validate', methods=['POST'])
@webmanager_auth_required
def builder_validate():
    """Validate a DAG JSON structure for cycles, disconnected nodes, and required fields."""
    data = request.get_json(silent=True) or {}
    steps = data.get('steps', [])
    errors = []

    if not steps:
        return jsonify({'valid': False, 'errors': ['No steps provided']}), 200

    # Check required fields on each step
    step_ids = set()
    for i, step in enumerate(steps):
        step_id = step.get('id')
        if not step_id:
            errors.append(f'Step at index {i} is missing an id')
        else:
            step_ids.add(step_id)
        if not step.get('action_template_id'):
            errors.append(f'Step "{step_id or i}" is missing action_template_id')

    # Validate parent/children references exist
    for step in steps:
        step_id = step.get('id', '?')
        for parent_id in step.get('parents', []):
            if parent_id not in step_ids:
                errors.append(f'Step "{step_id}" references unknown parent "{parent_id}"')
        for child_id in step.get('children', []):
            if child_id not in step_ids:
                errors.append(f'Step "{step_id}" references unknown child "{child_id}"')

    if errors:
        return jsonify({'valid': False, 'errors': errors}), 200

    # Cycle detection using Kahn's algorithm (topological sort)
    adj = defaultdict(set)      # parent -> children
    in_degree = defaultdict(int)

    for step_id in step_ids:
        in_degree[step_id] = in_degree.get(step_id, 0)

    for step in steps:
        step_id = step.get('id')
        for child_id in step.get('children', []):
            adj[step_id].add(child_id)
            in_degree[child_id] = in_degree.get(child_id, 0) + 1
        for parent_id in step.get('parents', []):
            adj[parent_id].add(step_id)
            in_degree[step_id] = in_degree.get(step_id, 0) + 1

    # Deduplicate edges: the same edge may appear in both parents and children lists
    # Rebuild in_degree from the final adjacency set
    in_degree = {sid: 0 for sid in step_ids}
    for parent, children in adj.items():
        for child in children:
            in_degree[child] += 1

    queue = [sid for sid in step_ids if in_degree[sid] == 0]
    sorted_count = 0
    while queue:
        node = queue.pop(0)
        sorted_count += 1
        for child in adj[node]:
            in_degree[child] -= 1
            if in_degree[child] == 0:
                queue.append(child)

    if sorted_count != len(step_ids):
        errors.append('DAG contains a cycle')

    # Check for disconnected nodes
    if step_ids and not errors:
        connected = set()
        start = next(iter(step_ids))
        visit_queue = [start]
        while visit_queue:
            node = visit_queue.pop(0)
            if node in connected:
                continue
            connected.add(node)
            for child in adj.get(node, set()):
                visit_queue.append(child)
            # Also traverse reverse edges
            for parent, children in adj.items():
                if node in children and parent not in connected:
                    visit_queue.append(parent)

        disconnected = step_ids - connected
        if disconnected:
            errors.append(f'Disconnected nodes detected: {", ".join(sorted(disconnected))}')

    return jsonify({'valid': len(errors) == 0, 'errors': errors}), 200


@admin_routes_bp.route('/api/builder/save', methods=['POST'])
@webmanager_auth_required
def builder_save():
    """Save an orchestration from the builder. Creates orchestration + steps + step dependencies."""
    data = request.get_json(silent=True) or {}

    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'Orchestration name is required'}), 400

    description = data.get('description')
    steps_data = data.get('steps', [])

    if not steps_data:
        return jsonify({'error': 'At least one step is required'}), 400

    # Determine next version for this orchestration name
    existing = db.session.execute(
        select(Orchestration).filter_by(name=name).order_by(Orchestration.version.desc())
    ).scalars().first()
    version = (existing.version + 1) if existing else 1

    try:
        orchestration = Orchestration(
            name=name,
            version=version,
            description=description,
        )
        db.session.add(orchestration)

        # First pass: create all Step objects and map temp IDs to them
        temp_id_to_step = {}
        for step_data in steps_data:
            temp_id = step_data.get('id')
            at_id = step_data.get('action_template_id')
            undo = step_data.get('undo', False)
            target = step_data.get('target')

            action_template = db.session.get(ActionTemplate, at_id) if at_id else None
            if at_id and not action_template:
                return jsonify({'error': f'ActionTemplate not found: {at_id}'}), 400

            step = Step(
                orchestration=None,
                undo=undo,
                action_template=action_template,
                target=target if not undo else None,
            )
            step.orchestration = orchestration
            db.session.add(step)
            temp_id_to_step[temp_id] = step

        # Second pass: wire up parent/children dependencies
        for step_data in steps_data:
            temp_id = step_data.get('id')
            step = temp_id_to_step[temp_id]

            for parent_temp_id in step_data.get('parents', []):
                parent_step = temp_id_to_step.get(parent_temp_id)
                if parent_step and parent_step not in step.parent_steps:
                    step.parent_steps.append(parent_step)

            for child_temp_id in step_data.get('children', []):
                child_step = temp_id_to_step.get(child_temp_id)
                if child_step and child_step not in step.children_steps:
                    step.children_steps.append(child_step)

        db.session.commit()

        return jsonify({
            'message': 'Orchestration saved successfully',
            'orchestration': {
                'id': str(orchestration.id),
                'name': orchestration.name,
                'version': orchestration.version,
            },
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to save orchestration: {str(e)}'}), 500


# --- Server Topology API ---

@admin_routes_bp.route('/api/topology', methods=['GET'])
@webmanager_auth_required
def topology():
    """Return server topology as nodes and edges for visualization."""
    servers = db.session.execute(select(Server)).scalars().all()
    routes = db.session.execute(select(Route)).scalars().all()

    nodes = []
    for srv in servers:
        gates_list = []
        for g in srv.gates:
            gates_list.append({
                'id': str(g.id),
                'dns': g.dns,
                'ip': str(g.ip) if g.ip else None,
                'port': g.port,
            })
        nodes.append({
            'id': str(srv.id),
            'name': srv.name,
            'me': srv._me or False,
            'gates': gates_list,
        })

    edges = []
    for r in routes:
        edges.append({
            'destination_id': str(r.destination_id),
            'proxy_server_id': str(r.proxy_server_id) if r.proxy_server_id else None,
            'gate_id': str(r.gate_id) if r.gate_id else None,
            'cost': r.cost,
        })

    return jsonify({'nodes': nodes, 'edges': edges}), 200


# --- Dashboard Widget endpoints ---

@admin_routes_bp.route('/api/widgets/success-rate', methods=['GET'])
@webmanager_auth_required
def widget_success_rate():
    """Return daily success rate for the last 7 days."""
    now = datetime.now(timezone.utc)
    seven_days_ago = now - timedelta(days=7)

    executions = db.session.execute(
        select(OrchExecution).where(OrchExecution.start_time >= seven_days_ago)
    ).scalars().all()

    # Group by date
    from collections import defaultdict as _dd
    by_day = _dd(lambda: {'total': 0, 'success': 0})
    for ex in executions:
        day_str = ex.start_time.strftime('%Y-%m-%d')
        by_day[day_str]['total'] += 1
        if ex.success is True:
            by_day[day_str]['success'] += 1

    days = []
    for i in range(7):
        d = (now - timedelta(days=6 - i)).strftime('%Y-%m-%d')
        info = by_day.get(d, {'total': 0, 'success': 0})
        total = info['total']
        success = info['success']
        rate = round((success / total) * 100, 1) if total > 0 else 0
        days.append({'date': d, 'total': total, 'success': success, 'rate': rate})

    return jsonify({'days': days}), 200


@admin_routes_bp.route('/api/widgets/top-failures', methods=['GET'])
@webmanager_auth_required
def widget_top_failures():
    """Return top 5 failing orchestrations."""
    results = db.session.execute(
        select(Orchestration.name, func.count(OrchExecution.id).label('cnt'))
        .join(OrchExecution, OrchExecution.orchestration_id == Orchestration.id)
        .where(OrchExecution.success == False)  # noqa: E712
        .group_by(Orchestration.name)
        .order_by(func.count(OrchExecution.id).desc())
        .limit(5)
    ).all()

    failures = [{'name': row[0], 'count': row[1]} for row in results]
    return jsonify({'failures': failures}), 200


@admin_routes_bp.route('/api/widgets/recent-activity', methods=['GET'])
@webmanager_auth_required
def widget_recent_activity():
    """Return the 20 most recent executions."""
    executions = db.session.execute(
        select(OrchExecution).order_by(OrchExecution.start_time.desc()).limit(20)
    ).scalars().all()

    events = []
    for ex in executions:
        if ex.success is True:
            status = 'success'
        elif ex.success is False:
            status = 'failed'
        elif ex.end_time is None:
            status = 'running'
        else:
            status = 'unknown'

        events.append({
            'id': str(ex.id),
            'orchestration_name': ex.orchestration.name if ex.orchestration else 'Unknown',
            'status': status,
            'start_time': ex.start_time.strftime('%Y-%m-%dT%H:%M:%SZ') if ex.start_time else None,
            'server_name': ex.server.name if ex.server else None,
        })

    return jsonify({'events': events}), 200
