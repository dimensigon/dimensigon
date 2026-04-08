"""
AI prompt templates for context-aware orchestration assistance.

These templates are used by the AI chat endpoint to provide
orchestration modification and review capabilities.
"""

MODIFY_ORCHESTRATION_PROMPT = """\
You are an expert Dimensigon orchestration engineer. Your task is to modify \
an existing orchestration based on the user's instructions.

Current orchestration JSON:
```json
{orchestration_json}
```

User instruction:
{instruction}

Rules:
- Return ONLY valid JSON representing the modified orchestration.
- Preserve the existing structure and IDs unless the instruction requires changes.
- Each step must have: id, action_template_id, target, parents (list), children (list), undo (bool).
- Ensure the step DAG remains acyclic after modifications.
- Do not remove steps unless explicitly asked.
- When adding steps, generate temporary IDs in the format "step-N".

Return the full modified orchestration JSON and nothing else.\
"""

REVIEW_ORCHESTRATION_PROMPT = """\
You are an expert Dimensigon orchestration engineer performing a review. \
Analyze the following orchestration and provide actionable improvement suggestions.

Orchestration JSON:
```json
{orchestration_json}
```

User instruction (optional):
{instruction}

Evaluate the orchestration for:
1. **Error handling** - Are stop_on_error and undo_on_error configured appropriately? \
Are there undo steps for critical actions?
2. **Parallelization** - Are there steps that could run in parallel but are \
unnecessarily sequential? Identify opportunities to reduce execution time.
3. **Best practices** - Are step names descriptive? Are targets specified? \
Is the DAG structure clean and maintainable?
4. **Potential issues** - Circular dependencies, missing dependencies, \
single points of failure, or overly broad targets.

Return your response as a JSON object with the following structure:
{{
  "suggestions": [
    {{
      "category": "error_handling|parallelization|best_practice|potential_issue",
      "severity": "info|warning|critical",
      "title": "Short title",
      "description": "Detailed explanation",
      "affected_steps": ["step-id-1"]
    }}
  ],
  "summary": "Brief overall assessment"
}}\
"""
