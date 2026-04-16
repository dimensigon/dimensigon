"""Central registry that collects all generators and produces examples."""

import importlib
import logging
from typing import Dict, List, Optional, Type

from examples.lib.base import TrainingExample

logger = logging.getLogger('examples.registry')


class ExampleRegistry:
    """Collects generators and produces the full example catalog."""

    def __init__(self):
        self._generators = []
        self._examples: Optional[List[TrainingExample]] = None

    def register(self, generator):
        """Register a generator instance."""
        self._generators.append(generator)
        self._examples = None  # Invalidate cache

    def auto_discover(self):
        """Auto-discover and register all generators."""
        generator_modules = [
            # Shell generators
            'examples.generators.shell.service_mgmt',
            'examples.generators.shell.user_perms',
            'examples.generators.shell.packages',
            'examples.generators.shell.file_ops',
            'examples.generators.shell.log_mgmt',
            'examples.generators.shell.disk_storage',
            'examples.generators.shell.network_config',
            'examples.generators.shell.process_mgmt',
            'examples.generators.shell.backup_restore',
            'examples.generators.shell.security',
            'examples.generators.shell.containers',
            'examples.generators.shell.database_ops',
            'examples.generators.shell.health_checks',
            'examples.generators.shell.certificates',
            # Python generators
            'examples.generators.python.http_api',
            'examples.generators.python.notifications',
            'examples.generators.python.data_processing',
            'examples.generators.python.monitoring',
            'examples.generators.python.cloud_ops',
            'examples.generators.python.database',
            'examples.generators.python.security_crypto',
            'examples.generators.python.config_mgmt',
            # Orchestration generators
            'examples.generators.orchestration.single_server',
            'examples.generators.orchestration.multi_server',
            'examples.generators.orchestration.migration',
            # Ansible generators
            'examples.generators.ansible.packages',
            'examples.generators.ansible.services',
            'examples.generators.ansible.files_templates',
            'examples.generators.ansible.containers',
            'examples.generators.ansible.users_groups',
            'examples.generators.ansible.cloud',
            'examples.generators.ansible.network',
        ]

        for module_path in generator_modules:
            try:
                mod = importlib.import_module(module_path)
                if hasattr(mod, 'get_generators'):
                    for gen in mod.get_generators():
                        self.register(gen)
                elif hasattr(mod, 'Generator'):
                    self.register(mod.Generator())
            except ImportError as e:
                logger.warning(f"Could not load generator {module_path}: {e}")

    def generate_all(self) -> List[TrainingExample]:
        """Generate all examples from all registered generators."""
        if self._examples is not None:
            return self._examples

        self._examples = []
        for gen in self._generators:
            try:
                examples = gen.generate()
                self._examples.extend(examples)
                logger.info(f"{gen.category}.{gen.subcategory}: {len(examples)} examples")
            except Exception as e:
                logger.error(f"Generator {gen.__class__.__name__} failed: {e}")

        return self._examples

    def generate_category(self, category: str) -> List[TrainingExample]:
        """Generate examples for a specific category only."""
        examples = []
        for gen in self._generators:
            if gen.category == category or gen.category.startswith(category + '.'):
                examples.extend(gen.generate())
        return examples

    @property
    def stats(self) -> Dict:
        """Return statistics about generated examples."""
        examples = self.generate_all()
        by_category = {}
        by_type = {}
        by_topology = {}
        by_difficulty = {}

        for ex in examples:
            by_category[ex.category] = by_category.get(ex.category, 0) + 1
            by_type[ex.action_type] = by_type.get(ex.action_type, 0) + 1
            by_topology[ex.topology] = by_topology.get(ex.topology, 0) + 1
            by_difficulty[ex.difficulty] = by_difficulty.get(ex.difficulty, 0) + 1

        return {
            'total': len(examples),
            'generators': len(self._generators),
            'by_category': by_category,
            'by_type': by_type,
            'by_topology': by_topology,
            'by_difficulty': by_difficulty,
        }
