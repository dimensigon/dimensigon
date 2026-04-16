"""Training example dataclass and serialization."""

import json
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


@dataclass
class TrainingExample:
    """A single training example for the DimensigonAI SLM."""

    id: str
    category: str
    subcategory: str
    variant: int
    user_prompt: str
    dm_json: Dict[str, Any]
    explanation: str
    entity_type: str  # "action_template" | "orchestration"
    action_type: str  # SHELL | PYTHON | ANSIBLE | ORCHESTRATION
    topology: str = "single"  # "single" | "multi" | "mesh"
    features: List[str] = field(default_factory=list)
    difficulty: str = "basic"
    migration_source: Optional[str] = None

    def to_chatml(self, system_prompt: str) -> Dict:
        """Convert to ChatML conversation format for SLM training."""
        response = json.dumps({
            "fields": self.dm_json,
            "explanation": self.explanation,
        }, indent=2)
        return {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": self.user_prompt},
                {"role": "assistant", "content": response},
            ]
        }

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict) -> 'TrainingExample':
        return cls(**d)
