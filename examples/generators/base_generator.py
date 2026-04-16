"""Base class for all example generators.

Each generator produces TrainingExample objects for a specific subcategory
by expanding seed templates with parameterized variations.
"""

import copy
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from examples.lib.base import TrainingExample
from examples.lib.parameterizer import Parameterizer
from examples.lib.validator import validate_example


class BaseGenerator(ABC):
    """Abstract base for example generators."""

    category: str = ""          # e.g., "shell.service_mgmt"
    subcategory: str = ""       # e.g., "restart_service"
    entity_type: str = ""       # "action_template" or "orchestration"
    action_type: str = ""       # "SHELL", "PYTHON", "ANSIBLE", "ORCHESTRATION"
    default_topology: str = "single"
    default_difficulty: str = "basic"
    num_variations: int = 72

    def __init__(self, seed: int = 42):
        self.parameterizer = Parameterizer(seed=seed)

    @abstractmethod
    def seeds(self) -> List[Dict[str, Any]]:
        """Return seed templates.

        Each seed dict must contain:
        - 'name': seed name (used for example ID)
        - 'template': the DM JSON template with {param} placeholders
        - 'params': dict of parameter pools {"param": ["val1", "val2", ...]}
        - 'prompts': list of user prompt templates
        - 'explanation': explanation template string

        Optional:
        - 'features': list of features demonstrated
        - 'difficulty': override default difficulty
        - 'topology': override default topology
        """
        ...

    def generate(self) -> List[TrainingExample]:
        """Generate all examples from all seeds."""
        examples = []
        for seed in self.seeds():
            seed_examples = self._expand_seed(seed)
            examples.extend(seed_examples)
        return examples

    def _expand_seed(self, seed: Dict[str, Any]) -> List[TrainingExample]:
        """Expand a single seed into multiple variations."""
        variations = self.parameterizer.expand(
            seed_template=seed['template'],
            param_pools=seed.get('params', {}),
            prompt_templates=seed['prompts'],
            num_variations=self.num_variations,
        )

        examples = []
        for var in variations:
            params = var['params']
            variant_idx = var['variant']

            # Render the DM JSON template
            dm_json = self.parameterizer.render_dict(
                copy.deepcopy(seed['template']), params
            )

            # Render explanation
            try:
                explanation = seed['explanation'].format(**params)
            except KeyError:
                explanation = seed['explanation']

            # Truncate name to 40 chars
            if 'name' in dm_json and len(dm_json['name']) > 40:
                dm_json['name'] = dm_json['name'][:40]

            # Validate
            valid, errors = validate_example(dm_json, self.entity_type)
            if not valid:
                # Try to auto-fix common issues
                dm_json = self._auto_fix(dm_json, errors)

            example_id = f"{self.category}.{seed['name']}.v{variant_idx}"
            example = TrainingExample(
                id=example_id,
                category=self.category,
                subcategory=seed['name'],
                variant=variant_idx,
                user_prompt=var['prompt'],
                dm_json=dm_json,
                explanation=explanation,
                entity_type=self.entity_type,
                action_type=self.action_type,
                topology=seed.get('topology', self.default_topology),
                features=seed.get('features', []),
                difficulty=seed.get('difficulty', self.default_difficulty),
                migration_source=seed.get('migration_source'),
            )
            examples.append(example)

        return examples

    def _auto_fix(self, dm_json: Dict, errors: List[str]) -> Dict:
        """Attempt to auto-fix common validation issues."""
        # Truncate names
        if 'name' in dm_json and isinstance(dm_json['name'], str):
            dm_json['name'] = dm_json['name'][:40]

        # Fix steps
        if 'steps' in dm_json:
            for step in dm_json['steps']:
                if 'name' in step and isinstance(step['name'], str):
                    step['name'] = step['name'][:40]
                # Remove target from undo steps
                if step.get('undo') and 'target' in step:
                    del step['target']
                # Ensure parent_step_ids exists
                if 'parent_step_ids' not in step:
                    step['parent_step_ids'] = []

        return dm_json


class ShellActionGenerator(BaseGenerator):
    """Base for SHELL action template generators."""
    entity_type = "action_template"
    action_type = "SHELL"


class PythonActionGenerator(BaseGenerator):
    """Base for PYTHON action template generators."""
    entity_type = "action_template"
    action_type = "PYTHON"


class AnsibleActionGenerator(BaseGenerator):
    """Base for ANSIBLE action template generators."""
    entity_type = "action_template"
    action_type = "ANSIBLE"


class OrchestrationGenerator(BaseGenerator):
    """Base for orchestration generators."""
    entity_type = "orchestration"
    action_type = "ORCHESTRATION"
