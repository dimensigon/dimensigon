# AI-Powered Troubleshooting

- **Priority:** 18
- **Category:** AI
- **Effort:** 3-4 days
- **Dependencies:** #6 (Real-time Execution Monitoring), #17 (Context-Aware AI in WebManager)

## Context

When an orchestration step fails, operators must manually read stdout/stderr, identify the
error, determine the fix, and apply it. This process is slow and requires deep domain knowledge.
AI-powered troubleshooting automates the analysis, suggests concrete fixes, and can apply them
with one click, dramatically reducing mean-time-to-resolution.

## Scope

- Automatic error analysis when a step fails during monitored execution.
- AI receives: the failed step's command, stdout, stderr, exit code, target server info,
  and the orchestration context.
- AI produces: root cause analysis, suggested fix (modified command or configuration),
  confidence level.
- One-click "Apply Fix": modifies the step and optionally re-runs the failed step.
- Fix history: track which AI suggestions were applied and whether they resolved the issue.
- Learn from fixes: successful fixes feed back into the AI context for future suggestions.

## Files to Modify

- `dimensigon/ai/troubleshoot.py` (new: error analysis, fix suggestion, fix application)
- `dimensigon/ai/prompts.py` (troubleshooting prompt templates)
- `templates/admin/dashboard.html` (troubleshooting panel in execution monitor)
- `dimensigon/web/admin/routes.py` (troubleshoot API endpoint, apply-fix endpoint)

## Implementation Steps

1. Create `troubleshoot.py` with `analyze_failure(step_execution)` function.
2. Build prompt template that includes: command, stdout, stderr, exit code, OS info, step context.
3. Parse AI response into structured format: root_cause, suggestion, confidence, modified_command.
4. Build troubleshooting panel UI: appears automatically when a step fails during monitoring.
5. Display: error summary, AI analysis, suggested fix with diff view, confidence badge.
6. Implement "Apply Fix" button: PATCH the step command and optionally trigger re-execution.
7. Implement "Apply & Re-run" button: apply fix and immediately re-run the failed step.
8. Log fix attempts: track suggestion, applied fix, and outcome in a fix_history table.
9. Feed successful fixes back into prompt context for similar future errors.
10. Write tests: simulate a failed step, verify AI analysis returns valid suggestion.

## Verification

- Orchestration fails on a step: troubleshooting panel appears with AI analysis.
- AI correctly identifies a common error (e.g., "file not found" -> suggests correct path).
- Click "Apply Fix": step command is updated in the orchestration.
- Click "Apply & Re-run": step is patched and re-executed, succeeding this time.

## Breaking Changes

- None. Troubleshooting is an optional overlay on the execution monitoring UI.
