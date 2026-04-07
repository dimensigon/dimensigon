# Auto-Complete for Orchestration Parameters

- **Priority:** 22
- **Category:** DShell
- **Effort:** 2-3 days
- **Dependencies:** None

## Context

DShell users must remember exact orchestration names, parameter keys, and target server names.
Typos cause cryptic errors, and discoverability is poor. Tab completion for orchestration
names, parameters, and target mappings dramatically improves the operator experience and
reduces errors.

## Scope

- Tab-complete orchestration names from the registered catalog.
- Auto-suggest target mappings: when typing a target field, suggest server names and
  granule-based groups (e.g., "web_servers", "db_servers").
- Show required parameters from the orchestration's input schema when tab is pressed
  after the orchestration name.
- Fuzzy matching: "hlt_chk" matches "health_check" in suggestions.
- Context-aware: completions change based on the current command (run vs. describe vs. edit).
- Inline documentation: show parameter descriptions alongside suggestions.

## Files to Modify

- `dimensigon/dshell/completer.py` (extend or rewrite completion logic)
- `dimensigon/dshell/interactive.py` (wire completer into the prompt session)
- `dimensigon/dshell/catalog.py` (new or existing: cache of orchestration metadata)

## Implementation Steps

1. Build orchestration catalog cache: on DShell startup, fetch all orchestration names,
   descriptions, and parameter schemas. Refresh on demand.
2. Implement orchestration name completer: match input prefix against catalog names.
3. Add fuzzy matching using a simple algorithm (subsequence match with scoring).
4. Implement parameter completer: after orchestration name is resolved, suggest parameter
   keys from its input schema with types and descriptions.
5. Implement target completer: suggest server names and granule groups for target fields.
6. Make completion context-aware: `run <tab>` shows orchestrations, `run orch_name --<tab>`
   shows parameters.
7. Add inline documentation: show parameter descriptions in a dimmed style next to suggestions.
8. Wire the completer into the prompt_toolkit session in `interactive.py`.
9. Handle stale cache: auto-refresh after 5 minutes or on explicit `refresh` command.
10. Write tests: verify completions for orchestration names, parameters, and targets.

## Verification

- Type `run hea<tab>`: completes to `run health_check`.
- Type `run health_check --<tab>`: shows `--target`, `--timeout`, `--verbose` with descriptions.
- Type `run health_check --target=web<tab>`: shows `web_server_1`, `web_server_2`, `web_servers`.
- Fuzzy: `run hlth<tab>` suggests `health_check`.

## Breaking Changes

- None. Tab completion is additive and does not change existing command behavior.
