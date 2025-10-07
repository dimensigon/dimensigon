"""
Executions Viewer API

Real-time execution monitoring with filtering, pagination, and detailed views.
"""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from sqlalchemy import desc, func
from datetime import datetime, timedelta

from dimensigon.web import db
from dimensigon.domain.entities import (
    OrchExecution, StepExecution, Orchestration,
    ActionTemplate, Server, User
)

executions_bp = Blueprint('executions_viewer', __name__, url_prefix='/api/v2/executions')


def format_execution(execution):
    """Format execution object for JSON response"""
    duration = None
    if execution.start_time and execution.end_time:
        delta = execution.end_time - execution.start_time
        duration = delta.total_seconds()

    return {
        'id': str(execution.id),
        'orchestration': {
            'id': str(execution.orchestration.id),
            'name': execution.orchestration.name,
            'version': execution.orchestration.version
        } if execution.orchestration else None,
        'start_time': execution.start_time.isoformat() if execution.start_time else None,
        'end_time': execution.end_time.isoformat() if execution.end_time else None,
        'duration': duration,
        'status': 'running' if execution.end_time is None else ('success' if execution.success else 'failed'),
        'success': execution.success,
        'undo_success': execution.undo_success,
        'message': execution.message,
        'executor': execution.executor.name if execution.executor else None,
        'server': {
            'id': str(execution.server.id) if execution.server else None,
            'name': execution.server.name if execution.server else None
        },
        'params': execution.params,
        'step_count': len(execution.step_executions) if execution.step_executions else 0
    }


def format_step_execution(step_exec):
    """Format step execution object for JSON response"""
    duration = None
    if step_exec.start_time and step_exec.end_time:
        delta = step_exec.end_time - step_exec.start_time
        duration = delta.total_seconds()

    return {
        'id': str(step_exec.id),
        'step': {
            'id': str(step_exec.step.id) if step_exec.step else None,
            'name': step_exec.step.name if step_exec.step else None,
            'action_type': str(step_exec.step.action_type) if step_exec.step and step_exec.step.action_type else None
        },
        'server': {
            'id': str(step_exec.server.id) if step_exec.server else None,
            'name': step_exec.server.name if step_exec.server else None
        },
        'start_time': step_exec.start_time.isoformat() if step_exec.start_time else None,
        'end_time': step_exec.end_time.isoformat() if step_exec.end_time else None,
        'duration': duration,
        'status': 'running' if step_exec.end_time is None else ('success' if step_exec.success else 'failed'),
        'success': step_exec.success,
        'rc': step_exec.rc,
        'stdout': step_exec.stdout,
        'stderr': step_exec.stderr,
        'params': step_exec.params,
        'timings': {
            'pre_process': step_exec.pre_process_elapsed_time,
            'execution': step_exec.execution_elapsed_time,
            'post_process': step_exec.post_process_elapsed_time
        }
    }


@executions_bp.route('/', methods=['GET'])
@jwt_required()
def list_executions():
    """
    List orchestration executions with filtering and pagination

    Query Parameters:
        - page: Page number (default: 1)
        - per_page: Items per page (default: 50, max: 200)
        - status: Filter by status (running, success, failed)
        - orchestration_id: Filter by orchestration
        - server_id: Filter by server
        - start_date: Filter executions after this date (ISO format)
        - end_date: Filter executions before this date (ISO format)
        - search: Search in orchestration name or message
    """
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 50, type=int), 200)

    query = OrchExecution.query

    # Apply filters
    status = request.args.get('status')
    if status == 'running':
        query = query.filter(OrchExecution.end_time == None)
    elif status == 'success':
        query = query.filter(OrchExecution.success == True)
    elif status == 'failed':
        query = query.filter(OrchExecution.success == False, OrchExecution.end_time != None)

    orchestration_id = request.args.get('orchestration_id')
    if orchestration_id:
        query = query.filter(OrchExecution.orchestration_id == orchestration_id)

    server_id = request.args.get('server_id')
    if server_id:
        query = query.filter(OrchExecution.server_id == server_id)

    start_date = request.args.get('start_date')
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date)
            query = query.filter(OrchExecution.start_time >= start_dt)
        except ValueError:
            pass

    end_date = request.args.get('end_date')
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date)
            query = query.filter(OrchExecution.start_time <= end_dt)
        except ValueError:
            pass

    search = request.args.get('search')
    if search:
        query = query.join(Orchestration).filter(
            (Orchestration.name.contains(search)) |
            (OrchExecution.message.contains(search))
        )

    # Order by start time (newest first)
    query = query.order_by(desc(OrchExecution.start_time))

    # Paginate
    paginated = query.paginate(page=page, per_page=per_page, error_out=False)

    executions = [format_execution(exec) for exec in paginated.items]

    return jsonify({
        'executions': executions,
        'total': paginated.total,
        'pages': paginated.pages,
        'page': page,
        'per_page': per_page
    })


@executions_bp.route('/<execution_id>', methods=['GET'])
@jwt_required()
def get_execution_details(execution_id):
    """Get detailed information about a specific execution"""
    execution = OrchExecution.query.get(execution_id)

    if not execution:
        return jsonify({'error': 'Execution not found'}), 404

    details = format_execution(execution)

    # Add step executions
    details['step_executions'] = [
        format_step_execution(step_exec)
        for step_exec in execution.step_executions
    ]

    return jsonify(details)


@executions_bp.route('/<execution_id>/steps', methods=['GET'])
@jwt_required()
def get_execution_steps(execution_id):
    """Get all step executions for a specific orchestration execution"""
    execution = OrchExecution.query.get(execution_id)

    if not execution:
        return jsonify({'error': 'Execution not found'}), 404

    steps = [format_step_execution(step_exec) for step_exec in execution.step_executions]

    return jsonify({
        'execution_id': str(execution_id),
        'steps': steps,
        'total': len(steps)
    })


@executions_bp.route('/stats', methods=['GET'])
@jwt_required()
def get_execution_stats():
    """Get execution statistics and metrics"""
    # Time range for stats (default: last 24 hours)
    hours = request.args.get('hours', 24, type=int)
    since = datetime.utcnow() - timedelta(hours=hours)

    # Total executions
    total = OrchExecution.query.filter(OrchExecution.start_time >= since).count()

    # Running executions
    running = OrchExecution.query.filter(
        OrchExecution.start_time >= since,
        OrchExecution.end_time == None
    ).count()

    # Successful executions
    success = OrchExecution.query.filter(
        OrchExecution.start_time >= since,
        OrchExecution.success == True
    ).count()

    # Failed executions
    failed = OrchExecution.query.filter(
        OrchExecution.start_time >= since,
        OrchExecution.success == False,
        OrchExecution.end_time != None
    ).count()

    # Success rate
    completed = success + failed
    success_rate = (success / completed * 100) if completed > 0 else 0

    # Most executed orchestrations
    top_orchestrations = db.session.query(
        Orchestration.name,
        Orchestration.version,
        func.count(OrchExecution.id).label('count')
    ).join(OrchExecution).filter(
        OrchExecution.start_time >= since
    ).group_by(
        Orchestration.name, Orchestration.version
    ).order_by(
        desc('count')
    ).limit(10).all()

    top_orch_list = [
        {'name': name, 'version': version, 'count': count}
        for name, version, count in top_orchestrations
    ]

    # Recent failures
    recent_failures = OrchExecution.query.filter(
        OrchExecution.start_time >= since,
        OrchExecution.success == False,
        OrchExecution.end_time != None
    ).order_by(desc(OrchExecution.start_time)).limit(5).all()

    failures_list = [
        {
            'id': str(exec.id),
            'orchestration': exec.orchestration.name if exec.orchestration else None,
            'start_time': exec.start_time.isoformat(),
            'message': exec.message
        }
        for exec in recent_failures
    ]

    return jsonify({
        'time_range': f'Last {hours} hours',
        'total_executions': total,
        'running': running,
        'successful': success,
        'failed': failed,
        'success_rate': round(success_rate, 2),
        'top_orchestrations': top_orch_list,
        'recent_failures': failures_list
    })


@executions_bp.route('/running', methods=['GET'])
@jwt_required()
def get_running_executions():
    """Get all currently running executions"""
    running = OrchExecution.query.filter(
        OrchExecution.end_time == None
    ).order_by(OrchExecution.start_time).all()

    executions = [format_execution(exec) for exec in running]

    return jsonify({
        'executions': executions,
        'total': len(executions)
    })


@executions_bp.route('/recent', methods=['GET'])
@jwt_required()
def get_recent_executions():
    """Get most recent executions (completed or running)"""
    limit = min(request.args.get('limit', 20, type=int), 100)

    recent = OrchExecution.query.order_by(
        desc(OrchExecution.start_time)
    ).limit(limit).all()

    executions = [format_execution(exec) for exec in recent]

    return jsonify({
        'executions': executions,
        'total': len(executions)
    })


@executions_bp.route('/step-executions/<step_execution_id>', methods=['GET'])
@jwt_required()
def get_step_execution_details(step_execution_id):
    """Get detailed information about a specific step execution"""
    step_exec = StepExecution.query.get(step_execution_id)

    if not step_exec:
        return jsonify({'error': 'Step execution not found'}), 404

    details = format_step_execution(step_exec)

    # Add parent orchestration execution info
    details['orchestration_execution'] = {
        'id': str(step_exec.orch_execution.id),
        'orchestration': {
            'id': str(step_exec.orch_execution.orchestration.id),
            'name': step_exec.orch_execution.orchestration.name
        } if step_exec.orch_execution.orchestration else None
    } if step_exec.orch_execution else None

    return jsonify(details)
