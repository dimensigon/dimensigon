# Natural Language Orchestration Runner

- **Priority:** 19
- **Category:** AI
- **Effort:** 3-4 days
- **Dependencies:** #17 (Context-Aware AI in WebManager)

## Context

Running an orchestration today requires knowing its exact name, the target mapping syntax,
and the parameter format. Natural language execution ("Run health check on all web servers")
removes this barrier, making dimensigon accessible to operators who may not be familiar with
the orchestration catalog or the target mapping conventions.

## Scope

- Natural language input field in the dashboard and DShell.
- AI resolves the intent: identifies the orchestration by name (fuzzy matching against catalog).
- AI builds the target mapping: resolves "all web servers" to actual node names/granules.
- Confirmation step: shows the resolved orchestration, target mapping, and parameters
  before executing. User must confirm.
- Disambiguation: if multiple orchestrations match, show a selection list.
- Parameter extraction: "Run backup with retention=30 days" extracts parameters from the text.

## Files to Modify

- `dimensigon/ai/handler.py` (natural language intent resolution, target mapping)
- `dimensigon/ai/prompts.py` (NL runner prompt templates)
- `dimensigon/dshell/prompts/` (DShell integration for NL commands)
- `templates/admin/dashboard.html` (NL input field, confirmation dialog)
- `dimensigon/web/admin/routes.py` (NL execution endpoint)

## Implementation Steps

1. Build orchestration catalog index: name, description, tags, parameter schema for all
   registered orchestrations.
2. Build node/granule index: node names, granule types, granule values for target resolution.
3. Create NL parsing prompt: given user input + catalog + node index, return structured intent.
4. Implement intent resolution in `handler.py`: returns orchestration_id, target_mapping, params.
5. Handle ambiguity: if confidence < threshold or multiple matches, return options list.
6. Build confirmation dialog UI: shows resolved orchestration name, target servers,
   parameters in a clear format. Requires explicit "Confirm & Run" click.
7. On confirmation: dispatch execution via standard API.
8. Integrate with DShell: `run "health check on web servers"` triggers the same NL flow.
9. Add usage logging for NL queries to improve resolution over time.
10. Write tests: known orchestration names resolve correctly, ambiguous input triggers selection.

## Verification

- Type "Run health check on web servers": AI resolves to correct orchestration and nodes.
- Confirmation dialog shows accurate resolution. Click confirm: execution starts.
- Ambiguous input "Run deploy": disambiguation list shows matching orchestrations.
- DShell command `run "backup all databases"` works identically.

## Breaking Changes

- None. Natural language is an alternative input method; existing execution methods unchanged.
