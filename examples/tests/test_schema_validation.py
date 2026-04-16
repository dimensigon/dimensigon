"""Tier 1: Validate all generated examples against DM JSON schemas.

This test runs without Docker - pure schema validation.
Run: pytest examples/tests/test_schema_validation.py -v
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from examples.lib.validator import validate_example
from examples.lib.registry import ExampleRegistry


@pytest.fixture(scope='module')
def all_examples():
    """Generate all examples for validation."""
    registry = ExampleRegistry()
    registry.auto_discover()
    return registry.generate_all()


def test_total_count(all_examples):
    """Verify we have approximately 4000 examples."""
    assert len(all_examples) >= 3500, f"Expected ~4000 examples, got {len(all_examples)}"


def test_all_examples_valid(all_examples):
    """Every example must pass schema validation."""
    failures = []
    for ex in all_examples:
        valid, errors = validate_example(ex.dm_json, ex.entity_type)
        if not valid:
            failures.append((ex.id, errors))

    if failures:
        msg = f"{len(failures)} examples failed validation:\n"
        for ex_id, errors in failures[:20]:
            msg += f"  {ex_id}: {errors[0]}\n"
        pytest.fail(msg)


def test_action_templates_have_required_fields(all_examples):
    """All action templates must have name, action_type, code."""
    for ex in all_examples:
        if ex.entity_type != 'action_template':
            continue
        dm = ex.dm_json
        assert 'name' in dm, f"{ex.id}: missing name"
        assert 'action_type' in dm, f"{ex.id}: missing action_type"
        assert dm['action_type'] in {'SHELL', 'PYTHON', 'ANSIBLE', 'REQUEST', 'ORCHESTRATION'}, \
            f"{ex.id}: invalid action_type: {dm['action_type']}"


def test_orchestrations_have_steps(all_examples):
    """All orchestrations must have name and steps."""
    for ex in all_examples:
        if ex.entity_type != 'orchestration':
            continue
        dm = ex.dm_json
        assert 'name' in dm, f"{ex.id}: missing name"
        assert 'steps' in dm and isinstance(dm['steps'], list), f"{ex.id}: missing steps"
        assert len(dm['steps']) >= 2, f"{ex.id}: orchestration should have >=2 steps"


def test_step_names_max_40_chars(all_examples):
    """Step names must not exceed 40 characters."""
    for ex in all_examples:
        if ex.entity_type != 'orchestration':
            continue
        for step in ex.dm_json.get('steps', []):
            name = step.get('name', '')
            assert len(name) <= 40, f"{ex.id}: step name too long ({len(name)}): {name}"


def test_undo_steps_have_parents(all_examples):
    """Undo steps must reference parent step IDs."""
    for ex in all_examples:
        if ex.entity_type != 'orchestration':
            continue
        for i, step in enumerate(ex.dm_json.get('steps', [])):
            if step.get('undo'):
                parents = step.get('parent_step_ids', [])
                assert len(parents) > 0, \
                    f"{ex.id}: undo step[{i}] has no parent_step_ids"


def test_undo_steps_no_target(all_examples):
    """Undo steps must not have target field."""
    for ex in all_examples:
        if ex.entity_type != 'orchestration':
            continue
        for i, step in enumerate(ex.dm_json.get('steps', [])):
            if step.get('undo'):
                assert 'target' not in step or step['target'] is None, \
                    f"{ex.id}: undo step[{i}] should not have target"


def test_no_duplicate_step_ids(all_examples):
    """Step IDs must be unique within an orchestration."""
    for ex in all_examples:
        if ex.entity_type != 'orchestration':
            continue
        ids = [str(s.get('id', '')) for s in ex.dm_json.get('steps', [])]
        assert len(ids) == len(set(ids)), f"{ex.id}: duplicate step IDs"


def test_category_coverage(all_examples):
    """Ensure all major categories are represented."""
    categories = set(ex.category for ex in all_examples)
    expected_prefixes = ['shell.', 'python.', 'orchestration.', 'ansible.']
    for prefix in expected_prefixes:
        matching = [c for c in categories if c.startswith(prefix)]
        assert len(matching) > 0, f"No examples for category prefix: {prefix}"


def test_topology_distribution(all_examples):
    """Verify we have both single and multi-server examples."""
    topologies = set(ex.topology for ex in all_examples)
    assert 'single' in topologies, "Missing single-server examples"
    assert 'multi' in topologies or 'mesh' in topologies, "Missing multi-server examples"


def test_user_prompts_not_empty(all_examples):
    """Every example must have a non-empty user prompt."""
    for ex in all_examples:
        assert ex.user_prompt and len(ex.user_prompt) > 10, \
            f"{ex.id}: user_prompt too short: {ex.user_prompt!r}"


def test_explanations_not_empty(all_examples):
    """Every example must have a non-empty explanation."""
    for ex in all_examples:
        assert ex.explanation and len(ex.explanation) > 5, \
            f"{ex.id}: explanation too short"
