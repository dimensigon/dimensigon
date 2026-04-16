"""Interactive Step Debugger for DShell.

Provides breakpoint management, step inspection, and an interactive debug
command interface so operators can pause orchestration execution and
examine or modify steps on-the-fly.
"""


class StepDebugger:
    """Interactive debugger that can pause orchestration execution at
    specific steps, inspect context, and modify commands before they run."""

    def __init__(self):
        self.breakpoints = set()
        self.stepping = False
        self.debug_active = False

    # -- breakpoint management -----------------------------------------------

    def add_breakpoint(self, step_name):
        """Register *step_name* as a breakpoint."""
        self.breakpoints.add(step_name)

    def remove_breakpoint(self, step_name):
        """Remove *step_name* from the breakpoint set.

        Silently ignores names that are not present.
        """
        self.breakpoints.discard(step_name)

    def list_breakpoints(self):
        """Return a sorted list of current breakpoint names."""
        return sorted(self.breakpoints)

    # -- pause logic ---------------------------------------------------------

    def should_pause(self, step_name):
        """Return ``True`` if execution should pause at *step_name*.

        Pauses when single-stepping is active **or** the step is in the
        breakpoint set.
        """
        return self.stepping or step_name in self.breakpoints

    # -- inspection ----------------------------------------------------------

    def inspect_step(self, step_context):
        """Return a human-readable summary of *step_context*.

        Parameters
        ----------
        step_context : dict
            Expected keys (all optional): ``command``, ``target_server``,
            ``env_vars`` (dict), ``working_dir``, ``stdout``, ``stderr``,
            ``exit_code``.
        """
        lines = []
        lines.append("--- Step Inspection ---")
        lines.append(f"  Command:       {step_context.get('command', 'N/A')}")
        lines.append(f"  Target Server: {step_context.get('target_server', 'N/A')}")

        env_vars = step_context.get('env_vars', {})
        if env_vars:
            lines.append("  Env Vars:")
            for key in sorted(env_vars):
                lines.append(f"    {key}={env_vars[key]}")
        else:
            lines.append("  Env Vars:      (none)")

        lines.append(f"  Working Dir:   {step_context.get('working_dir', 'N/A')}")
        lines.append(f"  Stdout:        {step_context.get('stdout', 'N/A')}")
        lines.append(f"  Stderr:        {step_context.get('stderr', 'N/A')}")
        lines.append(f"  Exit Code:     {step_context.get('exit_code', 'N/A')}")
        lines.append("-----------------------")
        return "\n".join(lines)

    # -- modification --------------------------------------------------------

    def modify_command(self, step_context, new_command):
        """Return a *copy* of *step_context* with ``command`` replaced."""
        modified = dict(step_context)
        modified['command'] = new_command
        return modified

    # -- interactive debug prompt --------------------------------------------

    def get_debug_prompt(self):
        """Return the prompt string shown during a debug pause."""
        return "(debug) > "

    def parse_debug_command(self, cmd):
        """Parse a debug-mode command string.

        Returns a dict with at least a ``"action"`` key.  Recognised
        commands:

        * ``inspect``                       -- inspect the current step
        * ``modify <new_cmd>``              -- replace the step command
        * ``rerun``                         -- re-execute the current step
        * ``continue``                      -- resume normal execution
        * ``skip``                          -- skip the current step
        * ``abort``                         -- abort the orchestration
        * ``vars``                          -- show current variables
        * ``breakpoint add <name>``         -- add a breakpoint
        * ``breakpoint remove <name>``      -- remove a breakpoint
        * ``breakpoint list``               -- list breakpoints

        Unrecognised input yields ``{"action": "unknown", "raw": cmd}``.
        """
        parts = cmd.strip().split()
        if not parts:
            return {"action": "unknown", "raw": cmd}

        verb = parts[0]

        if verb == "inspect":
            return {"action": "inspect"}

        if verb == "modify":
            new_cmd = cmd.strip()[len("modify"):].strip()
            return {"action": "modify", "new_command": new_cmd}

        if verb in ("rerun", "continue", "skip", "abort", "vars"):
            return {"action": verb}

        if verb == "breakpoint":
            if len(parts) < 2:
                return {"action": "unknown", "raw": cmd}
            sub = parts[1]
            if sub == "list":
                return {"action": "breakpoint_list"}
            if sub == "add" and len(parts) >= 3:
                return {"action": "breakpoint_add", "name": parts[2]}
            if sub == "remove" and len(parts) >= 3:
                return {"action": "breakpoint_remove", "name": parts[2]}
            return {"action": "unknown", "raw": cmd}

        return {"action": "unknown", "raw": cmd}

    # -- variable formatting -------------------------------------------------

    def format_variables(self, var_context):
        """Return a formatted string displaying the variables in *var_context*.

        Parameters
        ----------
        var_context : dict
            Arbitrary key/value pairs representing the current variable state.
        """
        if not var_context:
            return "  (no variables)"

        lines = []
        for key in sorted(var_context):
            lines.append(f"  {key} = {var_context[key]!r}")
        return "\n".join(lines)
