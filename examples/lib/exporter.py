"""Export training examples to ChatML JSONL for SLM fine-tuning."""

import json
import random
from typing import IO, List

from examples.lib.base import TrainingExample

SYSTEM_PROMPT = (
    "You are DimensigonAI, an assistant that helps create and modify "
    "orchestrations and action templates for the Dimensigon distributed "
    "orchestration platform. Always respond with a JSON object containing "
    '"fields" and "explanation".'
)


class ChatMLExporter:
    """Exports TrainingExample objects to ChatML JSONL format."""

    def __init__(self, system_prompt: str = SYSTEM_PROMPT):
        self.system_prompt = system_prompt

    def export(self, examples: List[TrainingExample], output_file: IO) -> int:
        """Write all examples as ChatML JSONL lines.

        Returns number of examples written.
        """
        count = 0
        for example in examples:
            chatml = example.to_chatml(self.system_prompt)
            output_file.write(json.dumps(chatml) + '\n')
            count += 1
        return count

    def export_to_file(self, examples: List[TrainingExample], path: str) -> int:
        with open(path, 'w') as f:
            return self.export(examples, f)

    def split_and_export(self, examples: List[TrainingExample],
                         train_path: str, val_path: str,
                         train_ratio: float = 0.9, seed: int = 42) -> dict:
        """Split examples by category (stratified) and export train/val sets."""
        rng = random.Random(seed)

        # Group by category
        by_category = {}
        for ex in examples:
            by_category.setdefault(ex.category, []).append(ex)

        train_examples = []
        val_examples = []

        for category, cat_examples in sorted(by_category.items()):
            rng.shuffle(cat_examples)
            split_idx = int(len(cat_examples) * train_ratio)
            train_examples.extend(cat_examples[:split_idx])
            val_examples.extend(cat_examples[split_idx:])

        rng.shuffle(train_examples)
        rng.shuffle(val_examples)

        train_count = self.export_to_file(train_examples, train_path)
        val_count = self.export_to_file(val_examples, val_path)

        return {
            'train': train_count,
            'val': val_count,
            'total': train_count + val_count,
            'categories': len(by_category),
        }
