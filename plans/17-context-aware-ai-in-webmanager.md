# Context-Aware AI in WebManager

- **Priority:** 17
- **Category:** AI
- **Effort:** 4-5 days
- **Dependencies:** #5 (Authentication Flow Rework)

## Context

The existing AI handler can generate orchestrations from scratch, but it operates without
awareness of existing orchestrations or the current editing context. Integrating AI directly
into the WebManager with full context enables much more powerful interactions: modifying
existing orchestrations, adding error handling to current steps, and reviewing orchestrations
for potential improvements.

## Scope

- AI chat panel embedded in the WebManager sidebar.
- Context injection: current orchestration JSON is automatically fed to the AI when asking
  for modifications.
- Modification mode: "Add error handling to step 3" understands the current DAG.
- Review mode: AI analyzes an orchestration and suggests improvements (best practices,
  missing error handling, parallelization opportunities).
- Suggestion cards: AI improvements shown as accept/reject cards that apply changes on click.
- Prompt history: previous AI interactions saved per session for continuity.

## Files to Modify

- `dimensigon/ai/handler.py` (extend with context-aware prompt construction)
- `dimensigon/ai/prompts.py` (new prompts for modification and review modes)
- `templates/admin/dashboard.html` (AI sidebar chat panel, suggestion cards)
- `dimensigon/web/admin/routes.py` (AI chat endpoint)

## Implementation Steps

1. Build the AI chat sidebar component in the dashboard: text input, message history, loading state.
2. Create `/dm-webmanager/api/ai/chat` endpoint that accepts message + orchestration context.
3. Extend `handler.py` with a `modify_orchestration(current_json, instruction)` method.
4. Extend `handler.py` with a `review_orchestration(current_json)` method.
5. Build prompt templates for modification and review modes in `prompts.py`.
6. Implement suggestion cards UI: show proposed changes with diff preview, accept/reject buttons.
7. On accept: apply the AI-generated diff to the orchestration in the builder.
8. Save prompt history to session storage for conversation continuity.
9. Add rate limiting: max 20 AI requests per user per hour.
10. Write tests: send modification request, verify output is valid orchestration JSON.

## Verification

- Open an orchestration in the builder, type "Add retry logic to all steps": AI returns
  a modified orchestration with retry configuration added.
- Click "Review": AI identifies missing error handling and suggests parallelization.
- Accept a suggestion: orchestration JSON updates correctly in the builder.
- Rate limit triggers after 20 requests: user sees a friendly cooldown message.

## Breaking Changes

- None. This is additive UI and API functionality. Requires AI backend (OpenAI or equivalent)
  to be configured.
