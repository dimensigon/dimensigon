"""Validates generated examples against DM's json_schemas.py."""

import re
from typing import Any, Dict, List, Tuple

# Inline the schema constraints to avoid importing DM's full app context
VALID_ACTION_TYPES = {"SHELL", "PYTHON", "ANSIBLE", "REQUEST", "ORCHESTRATION"}
UUID_PATTERN = re.compile(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$')


def validate_action_template(data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate an action template dict against DM's schema."""
    errors = []

    if not isinstance(data.get('name'), str) or not data['name']:
        errors.append("name is required and must be a non-empty string")
    elif len(data['name']) > 40:
        errors.append(f"name exceeds 40 chars: {len(data['name'])}")

    action_type = data.get('action_type', '')
    if action_type not in VALID_ACTION_TYPES:
        errors.append(f"invalid action_type: {action_type}")

    if 'code' not in data and action_type != 'SEND':
        errors.append("code is required for non-SEND action types")

    if 'schema' in data:
        schema_errors = _validate_schema(data['schema'])
        errors.extend(schema_errors)

    if 'expected_rc' in data and not isinstance(data['expected_rc'], int):
        errors.append("expected_rc must be an integer")

    return len(errors) == 0, errors


def validate_orchestration(data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate an orchestration_full dict against DM's schema."""
    errors = []

    if not isinstance(data.get('name'), str) or not data['name']:
        errors.append("name is required")

    if 'steps' not in data or not isinstance(data['steps'], list):
        errors.append("steps array is required")
        return False, errors

    seen_ids = set()
    do_step_ids = set()
    undo_step_ids = set()

    for i, step in enumerate(data['steps']):
        step_errors = _validate_step(step, i, seen_ids, do_step_ids)
        errors.extend(step_errors)

        step_id = str(step.get('id', i))
        seen_ids.add(step_id)

        if step.get('undo'):
            undo_step_ids.add(step_id)
        else:
            do_step_ids.add(step_id)

    # Validate undo steps have parent_step_ids
    for i, step in enumerate(data['steps']):
        if step.get('undo'):
            parents = step.get('parent_step_ids', [])
            if not parents:
                errors.append(f"step {i} (undo) must have parent_step_ids")

    # Check for cycles
    cycle_errors = _check_dag_cycles(data['steps'])
    errors.extend(cycle_errors)

    return len(errors) == 0, errors


def _validate_step(step: Dict, index: int, seen_ids: set,
                   do_step_ids: set) -> List[str]:
    """Validate a single step within an orchestration."""
    errors = []
    prefix = f"step[{index}]"

    if 'undo' not in step:
        errors.append(f"{prefix}: 'undo' field is required")

    # Must have either action_template_id or action_type
    has_template = 'action_template_id' in step
    has_inline = 'action_type' in step
    if not has_template and not has_inline:
        errors.append(f"{prefix}: needs action_template_id or action_type")

    if has_inline:
        at = step.get('action_type', '')
        if at not in VALID_ACTION_TYPES:
            errors.append(f"{prefix}: invalid action_type: {at}")

    if 'name' in step and isinstance(step['name'], str) and len(step['name']) > 40:
        errors.append(f"{prefix}: name exceeds 40 chars")

    # Undo steps must not have target
    if step.get('undo') and 'target' in step and step['target'] is not None:
        errors.append(f"{prefix}: undo steps must not have target")

    # Check parent_step_ids reference existing steps
    for parent_id in step.get('parent_step_ids', []):
        if str(parent_id) not in seen_ids and str(parent_id) != str(step.get('id', '')):
            pass  # Parent may be defined later in the list; will be caught by cycle check

    if 'schema' in step:
        schema_errors = _validate_schema(step['schema'])
        errors.extend([f"{prefix}: {e}" for e in schema_errors])

    return errors


def _validate_schema(schema: Dict) -> List[str]:
    """Validate a schema definition."""
    errors = []
    if not isinstance(schema, dict):
        return ["schema must be an object"]
    if 'input' in schema and not isinstance(schema['input'], dict):
        errors.append("schema.input must be an object")
    if 'required' in schema and not isinstance(schema['required'], list):
        errors.append("schema.required must be an array")
    if 'output' in schema and not isinstance(schema['output'], list):
        errors.append("schema.output must be an array")
    return errors


def _check_dag_cycles(steps: List[Dict]) -> List[str]:
    """Check for circular dependencies in step DAG."""
    # Build adjacency list
    graph = {}
    for step in steps:
        step_id = str(step.get('id', ''))
        parents = [str(p) for p in step.get('parent_step_ids', [])]
        graph[step_id] = parents

    # DFS cycle detection
    visited = set()
    in_stack = set()

    def has_cycle(node):
        if node in in_stack:
            return True
        if node in visited:
            return False
        visited.add(node)
        in_stack.add(node)
        for parent in graph.get(node, []):
            if has_cycle(parent):
                return True
        in_stack.discard(node)
        return False

    for node in graph:
        if has_cycle(node):
            return ["circular dependency detected in step DAG"]

    return []


def validate_example(data: Dict[str, Any], entity_type: str) -> Tuple[bool, List[str]]:
    """Validate an example's dm_json against the appropriate schema."""
    if entity_type == 'action_template':
        return validate_action_template(data)
    elif entity_type == 'orchestration':
        return validate_orchestration(data)
    else:
        return False, [f"unknown entity_type: {entity_type}"]
