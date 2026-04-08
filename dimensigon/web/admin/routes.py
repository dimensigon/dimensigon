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
from dimensigon.domain.entities import OrchExecution, StepExecution  # noqa: F401 - StepExecution used via relationship
from dimensigon.domain.entities.webhook import Webhook, WebhookLog
from dimensigon.domain.entities.orch_version import OrchestrationVersion
from dimensigon.domain.entities.template import OrchTemplate, TEMPLATE_CATEGORIES
from sqlalchemy import select, func
from dimensigon.web import db
from dimensigon.web.admin.auth import (
    webmanager_auth_required, require_role, token_blacklist
)
from dimensigon.web.decorators import audit_log

admin_routes_bp = Blueprint('admin_routes', __name__, url_prefix='/dm-webmanager')


def _build_orchestration_snapshot(orchestration):
    """Build a JSON-serializable snapshot of an orchestration and its steps."""
    steps_data = []
    for step in orchestration.steps:
        steps_data.append({
            'id': str(step.id),
            'undo': step.undo,
            'action_template_id': str(step.action_template_id) if step.action_template_id else None,
            'action_type': step.action_type.name if step.action_type else None,
            'target': step.target,
            'parent_step_ids': [str(p.id) for p in step.parent_steps],
            'children_step_ids': [str(c.id) for c in step.children_steps],
        })
    return {
        'id': str(orchestration.id),
        'name': orchestration.name,
        'version': orchestration.version,
        'description': orchestration.description,
        'stop_on_error': orchestration.stop_on_error,
        'stop_undo_on_error': orchestration.stop_undo_on_error,
        'undo_on_error': orchestration.undo_on_error,
        'steps': steps_data,
    }


def _create_orchestration_version(orchestration, author=None, message=None):
    """Create a new OrchestrationVersion snapshot for the given orchestration."""
    snapshot = _build_orchestration_snapshot(orchestration)
    # Determine next version number
    last = db.session.execute(
        select(OrchestrationVersion)
        .filter_by(orchestration_id=str(orchestration.id))
        .order_by(OrchestrationVersion.version_number.desc())
    ).scalars().first()
    next_num = (last.version_number + 1) if last else 1

    version = OrchestrationVersion(
        orchestration_id=str(orchestration.id),
        version_number=next_num,
        json_snapshot=snapshot,
        author=author,
        message=message,
    )
    db.session.add(version)
    db.session.commit()
    return version


# --- Authentication endpoints ---

@admin_routes_bp.route('/login', methods=['GET'])
def login_page():
    """Render the login page."""
    return render_template('admin/login.html')


@admin_routes_bp.route('/login', methods=['POST'])
@audit_log('login')
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

        # Auto-version: create an OrchestrationVersion snapshot
        try:
            _create_orchestration_version(
                orchestration,
                author=data.get('author'),
                message=data.get('message', 'Saved from builder'),
            )
        except Exception:
            pass  # versioning failure should not block the save response

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


# --- Orchestration Versioning API ---

@admin_routes_bp.route('/api/orchestrations/<orch_id>/versions', methods=['GET'])
@webmanager_auth_required
def list_orchestration_versions(orch_id):
    """List all versions for an orchestration."""
    orchestration = db.session.get(Orchestration, orch_id)
    if not orchestration:
        return jsonify({'error': 'Orchestration not found'}), 404

    versions = db.session.execute(
        select(OrchestrationVersion)
        .filter_by(orchestration_id=orch_id)
        .order_by(OrchestrationVersion.version_number.asc())
    ).scalars().all()

    result = []
    for v in versions:
        result.append({
            'id': str(v.id),
            'version_number': v.version_number,
            'author': v.author,
            'message': v.message,
            'created_at': v.created_at.strftime('%Y-%m-%dT%H:%M:%SZ') if v.created_at else None,
        })

    return jsonify({'versions': result}), 200


@admin_routes_bp.route('/api/orchestrations/<orch_id>/versions/<int:v1>/diff/<int:v2>', methods=['GET'])
@webmanager_auth_required
def diff_orchestration_versions(orch_id, v1, v2):
    """Compute diff between two version numbers of an orchestration."""
    ver1 = db.session.execute(
        select(OrchestrationVersion)
        .filter_by(orchestration_id=orch_id, version_number=v1)
    ).scalars().first()
    ver2 = db.session.execute(
        select(OrchestrationVersion)
        .filter_by(orchestration_id=orch_id, version_number=v2)
    ).scalars().first()

    if not ver1 or not ver2:
        return jsonify({'error': 'One or both versions not found'}), 404

    snap1 = ver1.json_snapshot or {}
    snap2 = ver2.json_snapshot or {}

    # Build step lookup by id
    steps1 = {s['id']: s for s in snap1.get('steps', [])}
    steps2 = {s['id']: s for s in snap2.get('steps', [])}

    ids1 = set(steps1.keys())
    ids2 = set(steps2.keys())

    added = [steps2[sid] for sid in (ids2 - ids1)]
    removed = [steps1[sid] for sid in (ids1 - ids2)]

    changed = []
    for sid in (ids1 & ids2):
        if steps1[sid] != steps2[sid]:
            changed.append({
                'step_id': sid,
                'from': steps1[sid],
                'to': steps2[sid],
            })

    # Also check top-level orchestration fields
    orch_changes = {}
    for key in ('name', 'version', 'description', 'stop_on_error', 'stop_undo_on_error', 'undo_on_error'):
        val1 = snap1.get(key)
        val2 = snap2.get(key)
        if val1 != val2:
            orch_changes[key] = {'from': val1, 'to': val2}

    return jsonify({
        'added': added,
        'removed': removed,
        'changed': changed,
        'orchestration_changes': orch_changes,
    }), 200


@admin_routes_bp.route('/api/orchestrations/<orch_id>/rollback/<int:version_number>', methods=['POST'])
@require_role('operator')
def rollback_orchestration(orch_id, version_number):
    """Rollback an orchestration to a specific version snapshot."""
    orchestration = db.session.get(Orchestration, orch_id)
    if not orchestration:
        return jsonify({'error': 'Orchestration not found'}), 404

    target_version = db.session.execute(
        select(OrchestrationVersion)
        .filter_by(orchestration_id=orch_id, version_number=version_number)
    ).scalars().first()

    if not target_version:
        return jsonify({'error': f'Version {version_number} not found'}), 404

    snapshot = target_version.json_snapshot
    if not snapshot:
        return jsonify({'error': 'Version snapshot is empty'}), 400

    try:
        # Apply snapshot fields to orchestration
        orchestration.description = snapshot.get('description')
        orchestration.stop_on_error = snapshot.get('stop_on_error', True)
        orchestration.stop_undo_on_error = snapshot.get('stop_undo_on_error', True)
        orchestration.undo_on_error = snapshot.get('undo_on_error', True)

        # Remove existing steps
        for step in list(orchestration.steps):
            db.session.delete(step)
        db.session.flush()

        # Recreate steps from snapshot
        snap_steps = snapshot.get('steps', [])
        id_to_step = {}
        for s in snap_steps:
            at_id = s.get('action_template_id')
            action_template = db.session.get(ActionTemplate, at_id) if at_id else None
            step = Step(
                orchestration=orchestration,
                undo=s.get('undo', False),
                action_template=action_template,
                target=s.get('target'),
            )
            db.session.add(step)
            id_to_step[s['id']] = step

        db.session.flush()

        # Wire dependencies
        for s in snap_steps:
            step = id_to_step[s['id']]
            for pid in s.get('parent_step_ids', []):
                parent = id_to_step.get(pid)
                if parent and parent not in step.parent_steps:
                    step.parent_steps.append(parent)

        db.session.commit()

        # Create a new version recording the rollback
        new_ver = _create_orchestration_version(
            orchestration,
            author=None,
            message=f'Rollback to version {version_number}',
        )

        return jsonify({
            'message': f'Rolled back to version {version_number}',
            'new_version_number': new_ver.version_number,
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Rollback failed: {str(e)}'}), 500


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


# --- Schedule CRUD API ---

@admin_routes_bp.route('/api/schedules', methods=['GET'])
@webmanager_auth_required
def list_schedules():
    """List all schedules with orchestration names."""
    from dimensigon.domain.entities.schedule import Schedule

    schedules = db.session.execute(select(Schedule)).scalars().all()
    result = []
    for s in schedules:
        result.append({
            'id': str(s.id),
            'orchestration_id': str(s.orchestration_id),
            'orchestration_name': s.orchestration.name if s.orchestration else None,
            'cron_expr': s.cron_expr,
            'timezone': s.timezone,
            'enabled': s.enabled,
            'last_run': s.last_run.strftime('%Y-%m-%dT%H:%M:%SZ') if s.last_run else None,
            'next_run': s.next_run.strftime('%Y-%m-%dT%H:%M:%SZ') if s.next_run else None,
            'missed_policy': s.missed_policy,
            'params': s.params,
            'created_by': s.created_by,
            'created_at': s.created_at.strftime('%Y-%m-%dT%H:%M:%SZ') if s.created_at else None,
        })
    return jsonify({'schedules': result}), 200


@admin_routes_bp.route('/api/schedules', methods=['POST'])
@webmanager_auth_required
def create_schedule():
    """Create a new schedule. Validates cron_expr with croniter."""
    from dimensigon.domain.entities.schedule import Schedule
    from dimensigon.use_cases.scheduler import compute_next_run
    from croniter import croniter

    data = request.get_json(silent=True) or {}

    orchestration_id = data.get('orchestration_id')
    cron_expr = data.get('cron_expr', '').strip()

    if not orchestration_id:
        return jsonify({'error': 'orchestration_id is required'}), 400
    if not cron_expr:
        return jsonify({'error': 'cron_expr is required'}), 400

    # Validate orchestration exists
    orch = db.session.get(Orchestration, orchestration_id)
    if not orch:
        return jsonify({'error': 'Orchestration not found'}), 404

    # Validate cron expression
    if not croniter.is_valid(cron_expr):
        return jsonify({'error': f'Invalid cron expression: {cron_expr}'}), 400

    tz = data.get('timezone', 'UTC')
    missed_policy = data.get('missed_policy', 'skip')
    if missed_policy not in ('skip', 'run_once'):
        return jsonify({'error': 'missed_policy must be "skip" or "run_once"'}), 400

    schedule = Schedule(
        orchestration_id=orchestration_id,
        cron_expr=cron_expr,
        timezone=tz,
        enabled=data.get('enabled', True),
        missed_policy=missed_policy,
        params=data.get('params'),
        created_by=data.get('created_by'),
    )
    schedule.next_run = compute_next_run(cron_expr, tz)

    db.session.add(schedule)
    db.session.commit()

    return jsonify({
        'message': 'Schedule created',
        'schedule': {
            'id': str(schedule.id),
            'orchestration_id': str(schedule.orchestration_id),
            'cron_expr': schedule.cron_expr,
            'next_run': schedule.next_run.strftime('%Y-%m-%dT%H:%M:%SZ') if schedule.next_run else None,
        },
    }), 201


@admin_routes_bp.route('/api/schedules/<schedule_id>', methods=['PUT'])
@webmanager_auth_required
def update_schedule(schedule_id):
    """Update an existing schedule."""
    from dimensigon.domain.entities.schedule import Schedule
    from dimensigon.use_cases.scheduler import compute_next_run
    from croniter import croniter

    schedule = db.session.get(Schedule, schedule_id)
    if not schedule:
        return jsonify({'error': 'Schedule not found'}), 404

    data = request.get_json(silent=True) or {}

    if 'orchestration_id' in data:
        orch = db.session.get(Orchestration, data['orchestration_id'])
        if not orch:
            return jsonify({'error': 'Orchestration not found'}), 404
        schedule.orchestration_id = data['orchestration_id']

    if 'cron_expr' in data:
        cron_expr = data['cron_expr'].strip()
        if not croniter.is_valid(cron_expr):
            return jsonify({'error': f'Invalid cron expression: {cron_expr}'}), 400
        schedule.cron_expr = cron_expr

    if 'timezone' in data:
        schedule.timezone = data['timezone']
    if 'enabled' in data:
        schedule.enabled = bool(data['enabled'])
    if 'missed_policy' in data:
        if data['missed_policy'] not in ('skip', 'run_once'):
            return jsonify({'error': 'missed_policy must be "skip" or "run_once"'}), 400
        schedule.missed_policy = data['missed_policy']
    if 'params' in data:
        schedule.params = data['params']

    # Recompute next_run
    schedule.next_run = compute_next_run(schedule.cron_expr, schedule.timezone)

    db.session.commit()

    return jsonify({
        'message': 'Schedule updated',
        'schedule': {
            'id': str(schedule.id),
            'orchestration_id': str(schedule.orchestration_id),
            'cron_expr': schedule.cron_expr,
            'enabled': schedule.enabled,
            'next_run': schedule.next_run.strftime('%Y-%m-%dT%H:%M:%SZ') if schedule.next_run else None,
        },
    }), 200


@admin_routes_bp.route('/api/schedules/<schedule_id>', methods=['DELETE'])
@webmanager_auth_required
def delete_schedule(schedule_id):
    """Delete a schedule."""
    from dimensigon.domain.entities.schedule import Schedule

    schedule = db.session.get(Schedule, schedule_id)
    if not schedule:
        return jsonify({'error': 'Schedule not found'}), 404

    db.session.delete(schedule)
    db.session.commit()
    return jsonify({'message': 'Schedule deleted'}), 200


@admin_routes_bp.route('/api/schedules/<schedule_id>/toggle', methods=['PATCH'])
@webmanager_auth_required
def toggle_schedule(schedule_id):
    """Toggle the enabled flag on a schedule."""
    from dimensigon.domain.entities.schedule import Schedule
    from dimensigon.use_cases.scheduler import compute_next_run

    schedule = db.session.get(Schedule, schedule_id)
    if not schedule:
        return jsonify({'error': 'Schedule not found'}), 404

    schedule.enabled = not schedule.enabled
    # Recompute next_run when re-enabling
    if schedule.enabled:
        schedule.next_run = compute_next_run(schedule.cron_expr, schedule.timezone)

    db.session.commit()

    return jsonify({
        'message': f'Schedule {"enabled" if schedule.enabled else "disabled"}',
        'schedule': {
            'id': str(schedule.id),
            'enabled': schedule.enabled,
            'next_run': schedule.next_run.strftime('%Y-%m-%dT%H:%M:%SZ') if schedule.next_run else None,
        },
    }), 200


# --- Audit Log API ---

@admin_routes_bp.route('/api/audit', methods=['GET'])
@require_role('administrator')
def audit_log_list():
    """Return paginated, filterable audit log entries."""
    from dimensigon.domain.entities.audit import AuditEntry

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    per_page = min(per_page, 200)  # cap max page size

    query = select(AuditEntry).order_by(AuditEntry.timestamp.desc())

    # Filters
    user_filter = request.args.get('user')
    if user_filter:
        query = query.where(AuditEntry.username == user_filter)

    action_filter = request.args.get('action')
    if action_filter:
        query = query.where(AuditEntry.action == action_filter)

    resource_type_filter = request.args.get('resource_type')
    if resource_type_filter:
        query = query.where(AuditEntry.resource_type == resource_type_filter)

    date_from = request.args.get('date_from')
    if date_from:
        try:
            dt_from = datetime.fromisoformat(date_from).replace(tzinfo=timezone.utc)
            query = query.where(AuditEntry.timestamp >= dt_from)
        except (ValueError, TypeError):
            pass

    date_to = request.args.get('date_to')
    if date_to:
        try:
            dt_to = datetime.fromisoformat(date_to).replace(tzinfo=timezone.utc)
            query = query.where(AuditEntry.timestamp <= dt_to)
        except (ValueError, TypeError):
            pass

    # Count total matching entries
    count_query = select(func.count()).select_from(query.subquery())
    total = db.session.execute(count_query).scalar() or 0

    # Paginate
    offset = (page - 1) * per_page
    entries = db.session.execute(query.offset(offset).limit(per_page)).scalars().all()

    return jsonify({
        'entries': [
            {
                'id': e.id,
                'timestamp': e.timestamp.strftime('%Y-%m-%dT%H:%M:%SZ') if e.timestamp else None,
                'username': e.username,
                'action': e.action,
                'resource_type': e.resource_type,
                'resource_id': e.resource_id,
                'ip_address': e.ip_address,
            }
            for e in entries
        ],
        'total': total,
        'page': page,
        'per_page': per_page,
    }), 200


# --- Webhook CRUD API ---

@admin_routes_bp.route('/api/webhooks', methods=['GET'])
@webmanager_auth_required
def list_webhooks():
    """List all webhooks."""
    webhooks = db.session.execute(select(Webhook)).scalars().all()
    return jsonify([wh.to_json() for wh in webhooks]), 200


@admin_routes_bp.route('/api/webhooks', methods=['POST'])
@webmanager_auth_required
def create_webhook():
    """Create a new webhook."""
    import uuid as _uuid
    data = request.get_json(silent=True) or {}

    url = data.get('url', '').strip()
    if not url:
        return jsonify({'error': 'url is required'}), 400

    webhook = Webhook(
        id=str(_uuid.uuid4()),
        name=data.get('name', '').strip() or None,
        url=url,
        event_types=data.get('event_types', []),
        headers=data.get('headers', {}),
        retry_max=data.get('retry_max', 5),
        active=data.get('active', True),
    )
    db.session.add(webhook)
    db.session.commit()
    return jsonify(webhook.to_json()), 201


@admin_routes_bp.route('/api/webhooks/<webhook_id>', methods=['PUT'])
@webmanager_auth_required
def update_webhook(webhook_id):
    """Update an existing webhook."""
    webhook = db.session.get(Webhook, webhook_id)
    if not webhook:
        return jsonify({'error': 'Webhook not found'}), 404

    data = request.get_json(silent=True) or {}

    if 'name' in data:
        webhook.name = data['name']
    if 'url' in data:
        webhook.url = data['url']
    if 'event_types' in data:
        webhook.event_types = data['event_types']
    if 'headers' in data:
        webhook.headers = data['headers']
    if 'retry_max' in data:
        webhook.retry_max = data['retry_max']
    if 'active' in data:
        webhook.active = data['active']

    db.session.commit()
    return jsonify(webhook.to_json()), 200


@admin_routes_bp.route('/api/webhooks/<webhook_id>', methods=['DELETE'])
@webmanager_auth_required
def delete_webhook(webhook_id):
    """Delete a webhook and its logs."""
    webhook = db.session.get(Webhook, webhook_id)
    if not webhook:
        return jsonify({'error': 'Webhook not found'}), 404

    db.session.delete(webhook)
    db.session.commit()
    return jsonify({'message': 'Webhook deleted'}), 200


@admin_routes_bp.route('/api/webhooks/<webhook_id>/test', methods=['POST'])
@webmanager_auth_required
def test_webhook(webhook_id):
    """Send a test event to a webhook."""
    webhook = db.session.get(Webhook, webhook_id)
    if not webhook:
        return jsonify({'error': 'Webhook not found'}), 404

    from dimensigon.use_cases.webhooks import dispatch_event
    dispatch_event('webhook.test', {
        'webhook_id': webhook.id,
        'message': 'This is a test event',
    })
    return jsonify({'message': 'Test event dispatched'}), 200


@admin_routes_bp.route('/api/webhooks/<webhook_id>/logs', methods=['GET'])
@webmanager_auth_required
def webhook_logs(webhook_id):
    """Get delivery logs for a webhook."""
    webhook = db.session.get(Webhook, webhook_id)
    if not webhook:
        return jsonify({'error': 'Webhook not found'}), 404

    logs = db.session.execute(
        select(WebhookLog)
        .where(WebhookLog.webhook_id == webhook_id)
        .order_by(WebhookLog.created_at.desc())
        .limit(100)
    ).scalars().all()
    return jsonify([log.to_json() for log in logs]), 200


# --- AI Troubleshooting API ---

@admin_routes_bp.route('/api/ai/troubleshoot', methods=['POST'])
@webmanager_auth_required
def ai_troubleshoot():
    """Analyze a failed step execution and return troubleshooting suggestions.

    Accepts either:
      - {step_execution_id: "..."} to look up the failure from the database
      - {command, stdout, stderr, rc} for ad-hoc analysis
    """
    from dimensigon.domain.entities import StepExecution
    from dimensigon.ai.troubleshoot import analyze_failure

    data = request.get_json(silent=True) or {}

    step_execution_id = data.get('step_execution_id')
    if step_execution_id:
        se = db.session.get(StepExecution, step_execution_id)
        if not se:
            return jsonify({'error': 'StepExecution not found'}), 404

        step_data = {
            'command': se.step.code if se.step else None,
            'stdout': se.stdout,
            'stderr': se.stderr,
            'rc': se.rc,
            'server_name': se.server.name if se.server else None,
            'step_name': se.step.name if se.step else None,
            'orchestration_name': (
                se.orch_execution.orchestration.name
                if se.orch_execution and se.orch_execution.orchestration else None
            ),
        }
    else:
        # Ad-hoc analysis from request body
        step_data = {
            'command': data.get('command'),
            'stdout': data.get('stdout'),
            'stderr': data.get('stderr'),
            'rc': data.get('rc'),
            'server_name': data.get('server_name'),
            'step_name': data.get('step_name'),
            'orchestration_name': data.get('orchestration_name'),
        }

    result = analyze_failure(step_data)
    return jsonify(result), 200


@admin_routes_bp.route('/api/ai/apply-fix', methods=['POST'])
@require_role('operator')
def ai_apply_fix():
    """Apply a suggested fix by updating a step's code.

    Accepts: {step_id, orchestration_id, new_command}
    """
    data = request.get_json(silent=True) or {}

    step_id = data.get('step_id')
    orchestration_id = data.get('orchestration_id')
    new_command = data.get('new_command')

    if not step_id:
        return jsonify({'error': 'step_id is required'}), 400
    if not orchestration_id:
        return jsonify({'error': 'orchestration_id is required'}), 400
    if not new_command:
        return jsonify({'error': 'new_command is required'}), 400

    orchestration = db.session.get(Orchestration, orchestration_id)
    if not orchestration:
        return jsonify({'error': 'Orchestration not found'}), 404

    step = db.session.get(Step, step_id)
    if not step:
        return jsonify({'error': 'Step not found'}), 404

    if str(step.orchestration_id) != str(orchestration_id):
        return jsonify({'error': 'Step does not belong to the specified orchestration'}), 400

    old_command = step.code
    step.code = new_command
    db.session.commit()

    # Auto-version the orchestration after the fix
    try:
        _create_orchestration_version(
            orchestration,
            author='ai-troubleshoot',
            message=f'AI fix applied to step {step_id}',
        )
    except Exception:
        pass  # versioning failure should not block the response

    return jsonify({
        'message': 'Step code updated successfully',
        'step_id': str(step.id),
        'old_command': old_command,
        'new_command': new_command,
    }), 200


# --- AI Chat API ---

# Rate limiting: track request timestamps per user identity
_ai_rate_limits = defaultdict(list)  # user_id -> [timestamp, ...]
_AI_RATE_LIMIT = 20   # max requests
_AI_RATE_WINDOW = 3600  # per hour (seconds)


def _check_ai_rate_limit(user_id):
    """Return True if the user is within the rate limit, False otherwise."""
    now = time.time()
    # Prune old entries outside the window
    _ai_rate_limits[user_id] = [
        ts for ts in _ai_rate_limits[user_id] if now - ts < _AI_RATE_WINDOW
    ]
    if len(_ai_rate_limits[user_id]) >= _AI_RATE_LIMIT:
        return False
    _ai_rate_limits[user_id].append(now)
    return True


@admin_routes_bp.route('/api/ai/chat', methods=['POST'])
@webmanager_auth_required
def ai_chat():
    """Context-aware AI chat endpoint for orchestration assistance.

    Accepts JSON body:
        message (str): User message / instruction.
        orchestration_context (dict|null): Current orchestration JSON for context.
        mode (str): 'modify' or 'review'.

    Returns AI-generated suggestions or modifications.
    When DM_AI_ENABLED is False, returns a helpful mock response.
    """
    from flask import current_app
    import json as _json

    user_id = get_jwt_identity()

    # Rate limiting
    if not _check_ai_rate_limit(user_id):
        return jsonify({
            'error': 'Rate limit exceeded. Maximum 20 requests per hour.',
        }), 429

    data = request.get_json(silent=True) or {}
    message = data.get('message', '').strip()
    orchestration_context = data.get('orchestration_context')
    mode = data.get('mode', 'review')

    if not message:
        return jsonify({'error': 'message is required'}), 400
    if mode not in ('modify', 'review'):
        return jsonify({'error': 'mode must be "modify" or "review"'}), 400

    ai_enabled = current_app.config.get('DM_AI_ENABLED', False)

    if ai_enabled:
        # Attempt to call the real AI handler
        try:
            from dimensigon.ai.handler import handle_ai_chat
            result = handle_ai_chat(
                message=message,
                orchestration_context=orchestration_context,
                mode=mode,
            )
            return jsonify(result), 200
        except ImportError:
            # AI handler module not available; fall through to mock response
            pass
        except Exception as e:
            return jsonify({
                'error': f'AI handler error: {str(e)}',
            }), 500

    # Mock response when AI is not configured
    if mode == 'modify':
        mock_response = {
            'type': 'modify',
            'message': (
                'AI-powered orchestration modification is not currently configured. '
                'To enable this feature, set the DM_AI_ENABLED environment variable '
                'to "true" and ensure an AI backend is available. '
                'Your instruction was: ' + message
            ),
            'modified_orchestration': orchestration_context,
        }
    else:
        mock_response = {
            'type': 'review',
            'message': (
                'AI-powered orchestration review is not currently configured. '
                'To enable this feature, set the DM_AI_ENABLED environment variable '
                'to "true" and ensure an AI backend is available. '
                'Your instruction was: ' + message
            ),
            'suggestions': [
                {
                    'category': 'info',
                    'severity': 'info',
                    'title': 'AI features not enabled',
                    'description': (
                        'Configure DM_AI_ENABLED=true to unlock AI-powered '
                        'orchestration review, modification suggestions, '
                        'error-handling analysis, and parallelization recommendations.'
                    ),
                    'affected_steps': [],
                }
            ],
            'summary': 'AI assistant is not configured. Enable it via DM_AI_ENABLED=true.',
        }

    return jsonify(mock_response), 200


# --- Orchestration Templates / Marketplace API ---

@admin_routes_bp.route('/api/templates', methods=['GET'])
@webmanager_auth_required
def list_templates():
    """List orchestration templates with search, category filter, pagination and sort by rating."""
    import uuid as _uuid

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    per_page = min(per_page, 100)  # cap max page size

    search = request.args.get('search', '').strip()
    category = request.args.get('category', '').strip()

    query = select(OrchTemplate)

    # Category filter
    if category and category in TEMPLATE_CATEGORIES:
        query = query.where(OrchTemplate.category == category)

    # Search filter (name, description, tags)
    if search:
        like_pattern = f'%{search}%'
        query = query.where(
            db.or_(
                OrchTemplate.name.ilike(like_pattern),
                OrchTemplate.description.ilike(like_pattern),
                OrchTemplate.tags.cast(db.String).ilike(like_pattern),
            )
        )

    # Count total matching
    count_query = select(func.count()).select_from(query.subquery())
    total = db.session.execute(count_query).scalar() or 0

    # Sort by rating (rating_sum / rating_count approximation: order by rating_sum desc)
    query = query.order_by(OrchTemplate.rating_sum.desc(), OrchTemplate.created_at.desc())

    # Paginate
    offset = (page - 1) * per_page
    templates = db.session.execute(query.offset(offset).limit(per_page)).scalars().all()

    return jsonify({
        'templates': [t.to_json(include_content=False) for t in templates],
        'total': total,
        'page': page,
        'per_page': per_page,
    }), 200


@admin_routes_bp.route('/api/templates/<template_id>', methods=['GET'])
@webmanager_auth_required
def get_template(template_id):
    """Get a single orchestration template with full json_content."""
    template = db.session.get(OrchTemplate, template_id)
    if not template:
        return jsonify({'error': 'Template not found'}), 404

    return jsonify(template.to_json(include_content=True)), 200


@admin_routes_bp.route('/api/templates', methods=['POST'])
@webmanager_auth_required
def create_template():
    """Create / share a new orchestration template."""
    import uuid as _uuid

    data = request.get_json(silent=True) or {}

    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400

    category = data.get('category', 'custom').strip()
    if category not in TEMPLATE_CATEGORIES:
        return jsonify({'error': f'Invalid category. Must be one of: {", ".join(TEMPLATE_CATEGORIES)}'}), 400

    json_content = data.get('json_content')
    if not json_content:
        return jsonify({'error': 'json_content is required'}), 400

    template = OrchTemplate(
        id=str(_uuid.uuid4()),
        name=name,
        description=data.get('description', '').strip() or None,
        category=category,
        tags=data.get('tags', []),
        json_content=json_content,
    )
    db.session.add(template)
    db.session.commit()

    return jsonify(template.to_json(include_content=True)), 201


@admin_routes_bp.route('/api/templates/<template_id>/rate', methods=['POST'])
@webmanager_auth_required
def rate_template(template_id):
    """Rate a template. Accepts {rating: 1} or {rating: -1}."""
    template = db.session.get(OrchTemplate, template_id)
    if not template:
        return jsonify({'error': 'Template not found'}), 404

    data = request.get_json(silent=True) or {}
    rating = data.get('rating')
    if rating not in (1, -1):
        return jsonify({'error': 'rating must be 1 or -1'}), 400

    template.rating_sum = (template.rating_sum or 0) + rating
    template.rating_count = (template.rating_count or 0) + 1
    db.session.commit()

    return jsonify({
        'message': 'Rating recorded',
        'rating': template.rating,
        'rating_sum': template.rating_sum,
        'rating_count': template.rating_count,
    }), 200


@admin_routes_bp.route('/api/templates/<template_id>/use', methods=['POST'])
@webmanager_auth_required
def use_template(template_id):
    """Return the template json_content ready for the orchestration builder."""
    template = db.session.get(OrchTemplate, template_id)
    if not template:
        return jsonify({'error': 'Template not found'}), 404

    return jsonify({
        'template_id': str(template.id),
        'name': template.name,
        'json_content': template.json_content,
    }), 200


# --- Execution Comparison & Trends API ---

def _build_execution_summary(execution):
    """Build a JSON-serializable summary of an OrchExecution with its step executions."""
    status = 'success' if execution.success is True else ('failed' if execution.success is False else 'running')
    duration = None
    if execution.start_time and execution.end_time:
        duration = (execution.end_time - execution.start_time).total_seconds()

    steps = []
    for se in execution.step_executions:
        step_duration = None
        if se.start_time and se.end_time:
            step_duration = (se.end_time - se.start_time).total_seconds()
        step_status = 'success' if se.success is True else ('failed' if se.success is False else 'running')
        step_name = se.step.step_name if se.step else None
        steps.append({
            'step_id': str(se.step_id),
            'step_name': step_name or str(se.step_id),
            'status': step_status,
            'duration': step_duration,
            'rc': se.rc,
        })

    return {
        'id': str(execution.id),
        'orchestration_name': execution.orchestration.name if execution.orchestration else None,
        'status': status,
        'start_time': execution.start_time.strftime('%Y-%m-%dT%H:%M:%SZ') if execution.start_time else None,
        'duration': duration,
        'params': execution.params,
        'steps': steps,
    }


@admin_routes_bp.route('/api/executions/compare', methods=['GET'])
@webmanager_auth_required
def compare_executions():
    """Compare two executions side-by-side and return a structured diff."""
    exec_id_a = request.args.get('a')
    exec_id_b = request.args.get('b')

    if not exec_id_a or not exec_id_b:
        return jsonify({'error': 'Both query params "a" and "b" (execution IDs) are required'}), 400

    execution_a = db.session.get(OrchExecution, exec_id_a)
    execution_b = db.session.get(OrchExecution, exec_id_b)

    if not execution_a:
        return jsonify({'error': f'Execution {exec_id_a} not found'}), 404
    if not execution_b:
        return jsonify({'error': f'Execution {exec_id_b} not found'}), 404

    summary_a = _build_execution_summary(execution_a)
    summary_b = _build_execution_summary(execution_b)

    # Compute diff
    status_changed = summary_a['status'] != summary_b['status']

    # Param diff
    params_a = summary_a['params'] or {}
    params_b = summary_b['params'] or {}
    all_keys = set(list(params_a.keys()) + list(params_b.keys()))
    param_diff = {}
    for key in all_keys:
        val_a = params_a.get(key)
        val_b = params_b.get(key)
        if val_a != val_b:
            param_diff[key] = {'a': val_a, 'b': val_b}

    # Step diffs -- match by step_id
    steps_a_map = {s['step_id']: s for s in summary_a['steps']}
    steps_b_map = {s['step_id']: s for s in summary_b['steps']}
    all_step_ids = list(dict.fromkeys(list(steps_a_map.keys()) + list(steps_b_map.keys())))

    step_diffs = []
    for sid in all_step_ids:
        sa = steps_a_map.get(sid, {})
        sb = steps_b_map.get(sid, {})
        step_name = sa.get('step_name') or sb.get('step_name') or sid
        status_a = sa.get('status')
        status_b = sb.get('status')
        duration_a = sa.get('duration')
        duration_b = sb.get('duration')
        changed = (status_a != status_b) or (duration_a != duration_b)
        step_diffs.append({
            'step_name': step_name,
            'status_a': status_a,
            'status_b': status_b,
            'duration_a': duration_a,
            'duration_b': duration_b,
            'changed': changed,
        })

    return jsonify({
        'execution_a': summary_a,
        'execution_b': summary_b,
        'diff': {
            'status_changed': status_changed,
            'param_diff': param_diff,
            'step_diffs': step_diffs,
        },
    }), 200


@admin_routes_bp.route('/api/executions/trends/<orchestration_id>', methods=['GET'])
@webmanager_auth_required
def execution_trends(orchestration_id):
    """Return duration trend for the last 20 runs of an orchestration."""
    orchestration = db.session.get(Orchestration, orchestration_id)
    if not orchestration:
        return jsonify({'error': 'Orchestration not found'}), 404

    executions = db.session.execute(
        select(OrchExecution)
        .where(OrchExecution.orchestration_id == orchestration_id)
        .order_by(OrchExecution.start_time.desc())
        .limit(20)
    ).scalars().all()

    runs = []
    for ex in reversed(executions):  # oldest first for charting
        duration = None
        if ex.start_time and ex.end_time:
            duration = (ex.end_time - ex.start_time).total_seconds()
        status = 'success' if ex.success is True else ('failed' if ex.success is False else 'running')
        runs.append({
            'id': str(ex.id),
            'start_time': ex.start_time.strftime('%Y-%m-%dT%H:%M:%SZ') if ex.start_time else None,
            'duration': duration,
            'status': status,
        })

    return jsonify({'runs': runs}), 200
