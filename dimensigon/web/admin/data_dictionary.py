"""
Data Dictionary Browser

Provides introspection and documentation for Dimensigon data models,
including Orchestrations, Actions, and their schemas.
"""
from flask import Blueprint, render_template, jsonify, request
from flask_jwt_extended import jwt_required
from sqlalchemy import inspect
from sqlalchemy.orm import class_mapper

from dimensigon.web import db
from dimensigon.domain.entities import (
    Orchestration, ActionTemplate, Step,
    OrchExecution, StepExecution, Server,
    User, Gate, Route, File
)

data_dict_bp = Blueprint('data_dictionary', __name__, url_prefix='/api/v2/data-dictionary')


# Entity registry for introspection
ENTITIES = {
    'orchestration': Orchestration,
    'action_template': ActionTemplate,
    'step': Step,
    'orch_execution': OrchExecution,
    'step_execution': StepExecution,
    'server': Server,
    'user': User,
    'gate': Gate,
    'route': Route,
    'file': File,
}


def get_model_schema(model_class):
    """
    Extract schema information from SQLAlchemy model

    Args:
        model_class: SQLAlchemy model class

    Returns:
        dict: Schema information including columns, relationships, and constraints
    """
    mapper = class_mapper(model_class)
    inspector = inspect(model_class)

    schema = {
        'table_name': model_class.__tablename__,
        'description': model_class.__doc__ or '',
        'columns': [],
        'relationships': [],
        'constraints': [],
        'methods': []
    }

    # Extract columns
    for column in mapper.columns:
        col_info = {
            'name': column.name,
            'type': str(column.type),
            'nullable': column.nullable,
            'primary_key': column.primary_key,
            'unique': column.unique,
            'default': str(column.default) if column.default else None,
            'foreign_keys': [str(fk.target_fullname) for fk in column.foreign_keys]
        }
        schema['columns'].append(col_info)

    # Extract relationships
    for relationship in mapper.relationships:
        rel_info = {
            'name': relationship.key,
            'target': relationship.mapper.class_.__name__,
            'uselist': relationship.uselist,
            'back_populates': relationship.back_populates,
            'cascade': str(relationship.cascade) if relationship.cascade else None
        }
        schema['relationships'].append(rel_info)

    # Extract custom methods
    for attr_name in dir(model_class):
        if not attr_name.startswith('_'):
            attr = getattr(model_class, attr_name)
            if callable(attr) and not attr_name in ['query', 'metadata']:
                try:
                    # Get method signature if possible
                    import inspect as py_inspect
                    sig = py_inspect.signature(attr)
                    schema['methods'].append({
                        'name': attr_name,
                        'signature': str(sig),
                        'doc': attr.__doc__ or ''
                    })
                except:
                    pass

    return schema


def get_orchestration_schema_details(orchestration_id):
    """
    Get detailed schema for a specific orchestration including all steps

    Args:
        orchestration_id: UUID of the orchestration

    Returns:
        dict: Detailed orchestration schema
    """
    orch = Orchestration.query.get(orchestration_id)
    if not orch:
        return None

    details = {
        'id': str(orch.id),
        'name': orch.name,
        'version': orch.version,
        'description': orch.description,
        'schema': orch.schema,
        'dependencies': orch.dependencies,
        'root_steps': [str(s.id) for s in orch.root],
        'steps': []
    }

    # Get all steps with their schemas
    for step in orch.steps:
        step_info = {
            'id': str(step.id),
            'name': step.name,
            'action_type': str(step.action_type) if step.action_type else None,
            'description': step.description,
            'schema': step.schema,
            'target': step.target,
            'undo': step.undo,
            'parents': [str(p.id) for p in step.parent_steps],
            'children': [str(c.id) for c in step.children_steps]
        }

        # Include action template schema if available
        if step.action_template:
            step_info['action_template'] = {
                'id': str(step.action_template.id),
                'name': step.action_template.name,
                'version': step.action_template.version,
                'schema': step.action_template.schema,
                'system_kwargs': step.action_template.system_kwargs
            }

        details['steps'].append(step_info)

    return details


def get_action_template_schema_details(action_id):
    """
    Get detailed schema for a specific action template

    Args:
        action_id: UUID of the action template

    Returns:
        dict: Detailed action template schema
    """
    action = ActionTemplate.query.get(action_id)
    if not action:
        return None

    details = {
        'id': str(action.id),
        'name': action.name,
        'version': action.version,
        'action_type': str(action.action_type),
        'description': action.description,
        'schema': action.schema,
        'system_kwargs': action.system_kwargs,
        'input_parameters': {},
        'output_parameters': {},
        'examples': []
    }

    # Parse schema for input/output parameters
    if action.schema:
        schema_obj = action.schema
        if isinstance(schema_obj, dict):
            details['input_parameters'] = schema_obj.get('properties', {})
            details['required_parameters'] = schema_obj.get('required', [])

    return details


@data_dict_bp.route('/entities', methods=['GET'])
@jwt_required()
def list_entities():
    """List all available entities in the data dictionary"""
    entities_list = []

    for key, model_class in ENTITIES.items():
        entities_list.append({
            'key': key,
            'name': model_class.__name__,
            'table': model_class.__tablename__,
            'description': model_class.__doc__ or '',
            'count': model_class.query.count()
        })

    return jsonify({
        'entities': entities_list,
        'total': len(entities_list)
    })


@data_dict_bp.route('/entities/<entity_key>', methods=['GET'])
@jwt_required()
def get_entity_schema(entity_key):
    """Get schema for a specific entity"""
    if entity_key not in ENTITIES:
        return jsonify({'error': 'Entity not found'}), 404

    model_class = ENTITIES[entity_key]
    schema = get_model_schema(model_class)

    return jsonify({
        'entity': entity_key,
        'schema': schema
    })


@data_dict_bp.route('/orchestrations', methods=['GET'])
@jwt_required()
def list_orchestrations():
    """List all orchestrations with basic schema info"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    search = request.args.get('search', '')

    query = Orchestration.query

    if search:
        query = query.filter(
            (Orchestration.name.contains(search)) |
            (Orchestration.description.contains(search))
        )

    paginated = query.order_by(Orchestration.name).paginate(
        page=page, per_page=per_page, error_out=False
    )

    orchestrations = []
    for orch in paginated.items:
        orchestrations.append({
            'id': str(orch.id),
            'name': orch.name,
            'version': orch.version,
            'description': orch.description,
            'step_count': len(orch.steps),
            'has_schema': bool(orch.schema)
        })

    return jsonify({
        'orchestrations': orchestrations,
        'total': paginated.total,
        'pages': paginated.pages,
        'page': page,
        'per_page': per_page
    })


@data_dict_bp.route('/orchestrations/<orchestration_id>', methods=['GET'])
@jwt_required()
def get_orchestration_details(orchestration_id):
    """Get detailed schema for a specific orchestration"""
    details = get_orchestration_schema_details(orchestration_id)

    if not details:
        return jsonify({'error': 'Orchestration not found'}), 404

    return jsonify(details)


@data_dict_bp.route('/action-templates', methods=['GET'])
@jwt_required()
def list_action_templates():
    """List all action templates with schema info"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    search = request.args.get('search', '')
    action_type = request.args.get('action_type', '')

    query = ActionTemplate.query

    if search:
        query = query.filter(
            (ActionTemplate.name.contains(search)) |
            (ActionTemplate.description.contains(search))
        )

    if action_type:
        query = query.filter(ActionTemplate.action_type == action_type)

    paginated = query.order_by(ActionTemplate.name).paginate(
        page=page, per_page=per_page, error_out=False
    )

    templates = []
    for template in paginated.items:
        templates.append({
            'id': str(template.id),
            'name': template.name,
            'version': template.version,
            'action_type': str(template.action_type),
            'description': template.description,
            'has_schema': bool(template.schema)
        })

    return jsonify({
        'action_templates': templates,
        'total': paginated.total,
        'pages': paginated.pages,
        'page': page,
        'per_page': per_page
    })


@data_dict_bp.route('/action-templates/<action_id>', methods=['GET'])
@jwt_required()
def get_action_template_details(action_id):
    """Get detailed schema for a specific action template"""
    details = get_action_template_schema_details(action_id)

    if not details:
        return jsonify({'error': 'Action template not found'}), 404

    return jsonify(details)


@data_dict_bp.route('/search', methods=['GET'])
@jwt_required()
def search_data_dictionary():
    """Search across orchestrations and action templates"""
    query_text = request.args.get('q', '')
    limit = request.args.get('limit', 20, type=int)

    if not query_text:
        return jsonify({'error': 'Search query required'}), 400

    results = {
        'orchestrations': [],
        'action_templates': [],
        'steps': []
    }

    # Search orchestrations
    orch_results = Orchestration.query.filter(
        (Orchestration.name.contains(query_text)) |
        (Orchestration.description.contains(query_text))
    ).limit(limit).all()

    for orch in orch_results:
        results['orchestrations'].append({
            'id': str(orch.id),
            'name': orch.name,
            'version': orch.version,
            'description': orch.description,
            'type': 'orchestration'
        })

    # Search action templates
    action_results = ActionTemplate.query.filter(
        (ActionTemplate.name.contains(query_text)) |
        (ActionTemplate.description.contains(query_text)) |
        (ActionTemplate.code.contains(query_text))
    ).limit(limit).all()

    for action in action_results:
        results['action_templates'].append({
            'id': str(action.id),
            'name': action.name,
            'version': action.version,
            'action_type': str(action.action_type),
            'description': action.description,
            'type': 'action_template'
        })

    results['total'] = len(results['orchestrations']) + len(results['action_templates'])

    return jsonify(results)
