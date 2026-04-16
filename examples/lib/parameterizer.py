"""Template expansion engine for generating example variations.

Takes a seed template with parameter pools and produces diverse
combinations through stratified sampling.
"""

import itertools
import random
from typing import Any, Dict, List


class Parameterizer:
    """Expands seed templates into multiple variations via parameter pools."""

    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)

    def expand(self, seed_template: Dict[str, Any], param_pools: Dict[str, List],
               prompt_templates: List[str], num_variations: int = 8) -> List[Dict[str, Any]]:
        """Generate variations of a seed template.

        Args:
            seed_template: Base template with {param} placeholders.
            param_pools: {"param_name": ["value1", "value2", ...]}
            prompt_templates: List of user prompt format strings.
            num_variations: Number of variations to generate.

        Returns:
            List of dicts with 'params', 'prompt', 'variant' keys.
        """
        # Generate param combinations — always produce num_variations
        if param_pools:
            combinations = self._stratified_sample(param_pools, num_variations)
        else:
            combinations = [{}] * num_variations

        results = []
        for i, params in enumerate(combinations):
            prompt_template = prompt_templates[i % len(prompt_templates)]
            try:
                prompt = prompt_template.format(**params)
            except (KeyError, ValueError, IndexError):
                for key, value in params.items():
                    prompt = prompt_template.replace('{' + key + '}', str(value))

            results.append({
                'params': params,
                'prompt': prompt,
                'variant': i,
            })

        return results

    def _stratified_sample(self, param_pools: Dict[str, List],
                           num_samples: int) -> List[Dict[str, Any]]:
        """Sample diverse parameter combinations.

        Uses round-robin cycling through each pool to maximize diversity
        rather than random sampling which can produce duplicates.
        """
        if not param_pools:
            return [{}] * num_samples

        pool_names = list(param_pools.keys())
        pool_values = [param_pools[k] for k in pool_names]

        # If pools are small enough, use all combinations
        total_combos = 1
        for v in pool_values:
            total_combos *= len(v)

        if total_combos <= num_samples:
            combos = list(itertools.product(*pool_values))
            self.rng.shuffle(combos)
            combos = combos[:num_samples]
        else:
            # Stratified: cycle through each pool independently
            combos = []
            shuffled_pools = [list(v) for v in pool_values]
            for p in shuffled_pools:
                self.rng.shuffle(p)

            for i in range(num_samples):
                combo = tuple(
                    shuffled_pools[j][i % len(shuffled_pools[j])]
                    for j in range(len(pool_names))
                )
                combos.append(combo)

        return [dict(zip(pool_names, combo)) for combo in combos]

    def render_code(self, code_template: str, params: Dict[str, Any]) -> str:
        """Render code template with generator-time parameters.

        Uses {param} for generator-time substitution.
        Preserves {{input.var}} for DM runtime Jinja2.
        """
        # Temporarily escape DM's {{...}} so .format() doesn't touch them
        code = code_template.replace('{{', '\x00\x00').replace('}}', '\x01\x01')
        try:
            code = code.format(**params)
        except (KeyError, ValueError, IndexError):
            # ValueError: stray braces from Python f-strings in code templates
            # Fall back to manual replacement
            for key, value in params.items():
                code = code.replace('{' + key + '}', str(value))
        code = code.replace('\x00\x00', '{{').replace('\x01\x01', '}}')
        return code

    def render_dict(self, template: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively render all string values in a dict template."""
        result = {}
        for key, value in template.items():
            if isinstance(value, str):
                result[key] = self.render_code(value, params)
            elif isinstance(value, dict):
                result[key] = self.render_dict(value, params)
            elif isinstance(value, list):
                result[key] = [
                    self.render_dict(item, params) if isinstance(item, dict)
                    else self.render_code(item, params) if isinstance(item, str)
                    else item
                    for item in value
                ]
            else:
                result[key] = value
        return result
