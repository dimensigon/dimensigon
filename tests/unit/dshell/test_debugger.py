"""Unit tests for the DShell interactive step debugger."""

from unittest import TestCase

from dimensigon.dshell.debugger import StepDebugger


class TestBreakpointManagement(TestCase):
    """Tests for add / remove / list breakpoint operations."""

    def test_add_breakpoint(self):
        dbg = StepDebugger()
        dbg.add_breakpoint("step_1")
        self.assertIn("step_1", dbg.breakpoints)

    def test_remove_breakpoint(self):
        dbg = StepDebugger()
        dbg.add_breakpoint("step_1")
        dbg.remove_breakpoint("step_1")
        self.assertNotIn("step_1", dbg.breakpoints)

    def test_remove_nonexistent_breakpoint_is_silent(self):
        dbg = StepDebugger()
        dbg.remove_breakpoint("does_not_exist")  # should not raise

    def test_list_breakpoints_sorted(self):
        dbg = StepDebugger()
        dbg.add_breakpoint("z_step")
        dbg.add_breakpoint("a_step")
        dbg.add_breakpoint("m_step")
        self.assertEqual(["a_step", "m_step", "z_step"], dbg.list_breakpoints())

    def test_list_breakpoints_empty(self):
        dbg = StepDebugger()
        self.assertEqual([], dbg.list_breakpoints())


class TestShouldPause(TestCase):
    """Tests for the pause decision logic."""

    def test_pause_when_stepping(self):
        dbg = StepDebugger()
        dbg.stepping = True
        self.assertTrue(dbg.should_pause("any_step"))

    def test_pause_on_breakpoint(self):
        dbg = StepDebugger()
        dbg.add_breakpoint("deploy")
        self.assertTrue(dbg.should_pause("deploy"))

    def test_no_pause_without_stepping_or_breakpoint(self):
        dbg = StepDebugger()
        self.assertFalse(dbg.should_pause("some_step"))


class TestInspectStep(TestCase):
    """Tests for inspect_step formatting."""

    def test_inspect_full_context(self):
        dbg = StepDebugger()
        ctx = {
            "command": "echo hello",
            "target_server": "web-01",
            "env_vars": {"HOME": "/root", "APP": "myapp"},
            "working_dir": "/opt/app",
            "stdout": "hello",
            "stderr": "",
            "exit_code": 0,
        }
        result = dbg.inspect_step(ctx)
        self.assertIn("echo hello", result)
        self.assertIn("web-01", result)
        self.assertIn("HOME=/root", result)
        self.assertIn("APP=myapp", result)
        self.assertIn("/opt/app", result)
        self.assertIn("hello", result)
        self.assertIn("Exit Code:     0", result)

    def test_inspect_missing_keys_shows_na(self):
        dbg = StepDebugger()
        result = dbg.inspect_step({})
        self.assertIn("N/A", result)
        self.assertIn("(none)", result)


class TestModifyCommand(TestCase):
    """Tests for modify_command."""

    def test_modify_command_returns_new_dict(self):
        dbg = StepDebugger()
        ctx = {"command": "old_cmd", "target_server": "srv"}
        modified = dbg.modify_command(ctx, "new_cmd")
        self.assertEqual("new_cmd", modified["command"])
        self.assertEqual("srv", modified["target_server"])
        # Original must be untouched.
        self.assertEqual("old_cmd", ctx["command"])


class TestParseDebugCommand(TestCase):
    """Tests for each recognised debug command."""

    def setUp(self):
        self.dbg = StepDebugger()

    def test_inspect(self):
        result = self.dbg.parse_debug_command("inspect")
        self.assertEqual("inspect", result["action"])

    def test_modify(self):
        result = self.dbg.parse_debug_command("modify ls -la /tmp")
        self.assertEqual("modify", result["action"])
        self.assertEqual("ls -la /tmp", result["new_command"])

    def test_rerun(self):
        result = self.dbg.parse_debug_command("rerun")
        self.assertEqual("rerun", result["action"])

    def test_continue(self):
        result = self.dbg.parse_debug_command("continue")
        self.assertEqual("continue", result["action"])

    def test_skip(self):
        result = self.dbg.parse_debug_command("skip")
        self.assertEqual("skip", result["action"])

    def test_abort(self):
        result = self.dbg.parse_debug_command("abort")
        self.assertEqual("abort", result["action"])

    def test_vars(self):
        result = self.dbg.parse_debug_command("vars")
        self.assertEqual("vars", result["action"])

    def test_breakpoint_add(self):
        result = self.dbg.parse_debug_command("breakpoint add step_x")
        self.assertEqual("breakpoint_add", result["action"])
        self.assertEqual("step_x", result["name"])

    def test_breakpoint_remove(self):
        result = self.dbg.parse_debug_command("breakpoint remove step_x")
        self.assertEqual("breakpoint_remove", result["action"])
        self.assertEqual("step_x", result["name"])

    def test_breakpoint_list(self):
        result = self.dbg.parse_debug_command("breakpoint list")
        self.assertEqual("breakpoint_list", result["action"])

    def test_unknown_command(self):
        result = self.dbg.parse_debug_command("foobar")
        self.assertEqual("unknown", result["action"])
        self.assertIn("foobar", result["raw"])

    def test_empty_command(self):
        result = self.dbg.parse_debug_command("  ")
        self.assertEqual("unknown", result["action"])


class TestFormatVariables(TestCase):
    """Tests for format_variables."""

    def test_format_with_values(self):
        dbg = StepDebugger()
        result = dbg.format_variables({"version": "1.0", "count": 42})
        self.assertIn("count = 42", result)
        self.assertIn("version = '1.0'", result)

    def test_format_empty(self):
        dbg = StepDebugger()
        result = dbg.format_variables({})
        self.assertIn("(no variables)", result)


class TestDebugPrompt(TestCase):
    """Test the debug prompt string."""

    def test_get_debug_prompt(self):
        dbg = StepDebugger()
        self.assertEqual("(debug) > ", dbg.get_debug_prompt())
