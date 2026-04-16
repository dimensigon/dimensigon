# Interactive Step Debugger

- **Priority:** 21
- **Category:** DShell
- **Effort:** 4-5 days
- **Dependencies:** None

## Context

When a step fails in DShell, the operator sees the error output and has to manually
reconstruct what happened: what command ran, on which server, with what environment. Then
they must fix the command, rebuild the orchestration, and re-run from scratch. An interactive
debugger lets operators inspect the failure in context, modify the command, and re-run just
the failed step, cutting troubleshooting time significantly.

## Scope

- When a step fails during DShell execution, offer to drop into debug mode.
- Debug mode shows: the exact command that ran, target server, environment variables,
  working directory, stdout/stderr, exit code.
- Allow re-running the failed step with modifications (edit command inline).
- Step-through mode: advance through the DAG one step at a time, inspecting results.
- Breakpoints: set breakpoints on specific steps before execution starts.
- Variable inspection: show current variable values (from previous step outputs).
- Continue/abort/skip controls for navigating the execution.

## Files to Modify

- `dimensigon/dshell/debugger.py` (new: debugger engine, breakpoint manager)
- `dimensigon/dshell/interactive.py` (integrate debugger into the interactive loop)
- `dimensigon/dshell/execution.py` (hook into step execution for breakpoint checks)
- `dimensigon/dshell/completer.py` (debug command auto-completion)

## Implementation Steps

1. Create `debugger.py` with `StepDebugger` class managing debug state and breakpoints.
2. Add debug mode prompt: `(debug) >` with commands: `inspect`, `modify`, `rerun`, `continue`,
   `skip`, `abort`, `vars`, `breakpoint`.
3. Implement `inspect`: display full step context (command, target, env, working dir).
4. Implement `modify`: open inline editor for the step command, save changes in memory.
5. Implement `rerun`: re-execute the current step with modifications.
6. Implement step-through: `--debug` flag on execution command enables step-by-step mode.
7. Implement breakpoints: `breakpoint add <step_name>` before execution, pause when reached.
8. Implement `vars`: display all variables from previous step outputs.
9. Add `continue` (run to next breakpoint/failure), `skip` (skip current step), `abort` (stop).
10. Integrate with interactive.py: on step failure, prompt "Drop into debug mode? [Y/n]".
11. Write tests: simulate failure, enter debug mode, modify command, rerun, verify success.

## Verification

- Run an orchestration with a deliberate error in step 3: DShell offers debug mode.
- In debug mode, `inspect` shows the full step context.
- `modify` and `rerun`: step succeeds with the fixed command, execution continues.
- `--debug` flag: execution pauses at each step, allowing inspection before proceeding.

## Breaking Changes

- None. Debug mode is opt-in and only activates on failure or with the `--debug` flag.
