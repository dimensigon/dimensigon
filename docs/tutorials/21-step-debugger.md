# Tutorial 21: Interactive Step Debugger

Debug orchestration failures interactively in DShell without rebuilding or re-running from scratch.

---

## Overview

The Interactive Step Debugger lets you pause, inspect, modify, and re-run orchestration steps directly from the DShell command line. When a step fails, DShell offers to drop into debug mode where you can see exactly what went wrong -- the command that ran, the target server, environment variables, stdout, stderr, and exit code -- then fix the command in-place and re-run just that step. You can also set breakpoints and step through an orchestration one step at a time for proactive inspection.

## Prerequisites

- Dimensigon 3.0 installed and running
- DShell access (local terminal or web terminal)
- At least one orchestration defined in your dimension
- Familiarity with basic DShell commands (`run`, `list`, `show`)

---

## Entering Debug Mode

There are two ways to enter debug mode:

### 1. Automatic Entry on Failure

When a step fails during orchestration execution, DShell prompts you:

```
Step "install_packages" FAILED (exit code 1)
Drop into debug mode? [Y/n]: Y
(debug) >
```

Press `Y` (or Enter, since it defaults to yes) to enter the debug prompt.

### 2. Manual Entry with the --debug Flag

Add `--debug` to any `run` command to enable step-through mode. Execution pauses before every step, giving you a chance to inspect context and decide whether to proceed.

```
dm> run deploy_app --target web-01 --debug
[step-through] Pausing before step "check_disk_space"
(debug) >
```

---

## Debug Commands Reference

Once at the `(debug) >` prompt, the following commands are available:

### inspect

View the full context of the current step, including the command, target server, environment variables, working directory, stdout, stderr, and return code.

```
(debug) > inspect

Step: install_packages
  Command:    apt-get install -y nginx=1.18.0
  Target:     web-01 (192.168.1.10)
  Env:
    DEBIAN_FRONTEND=noninteractive
    PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin
  Working Dir: /root
  Stdout:     Reading package lists...
              E: Version '1.18.0' for 'nginx' was not found
  Stderr:     E: Version '1.18.0' for 'nginx' was not found
  Exit Code:  100
```

### modify \<new_command\>

Replace the current step's command with a new one. The change is in-memory only and does not alter the stored orchestration definition.

```
(debug) > modify apt-get install -y nginx

Step "install_packages" command updated:
  Old: apt-get install -y nginx=1.18.0
  New: apt-get install -y nginx
```

### rerun

Re-execute the current step. If you used `modify` beforehand, the updated command runs instead of the original.

```
(debug) > rerun

Re-running step "install_packages" on web-01...
  Stdout:     Reading package lists...
              Setting up nginx (1.24.0-1) ...
  Exit Code:  0
Step "install_packages" PASSED
(debug) >
```

### continue

Resume normal execution from the current point. Execution proceeds until the next breakpoint or the next failure.

```
(debug) > continue

Continuing execution...
[step 4/6] configure_nginx ... OK
[step 5/6] start_service ... OK
[step 6/6] verify_health ... OK

Orchestration "deploy_app" completed successfully.
dm>
```

### skip

Skip the current step entirely and move to the next one. The skipped step is marked as SKIPPED in the execution log.

```
(debug) > skip

Skipping step "install_packages" (marked SKIPPED)
[step-through] Pausing before step "configure_nginx"
(debug) >
```

### abort

Stop the orchestration immediately. No further steps are executed.

```
(debug) > abort

Orchestration "deploy_app" aborted at step "install_packages".
dm>
```

### vars

Display all variable values accumulated from previous step outputs. Variables are populated as steps complete, so earlier steps' outputs are available for inspection.

```
(debug) > vars

Variables:
  disk_free       = 15234 (from step "check_disk_space")
  app_version     = 3.1.0 (from step "detect_version")
  backup_path     = /var/backups/app-20260407.tar.gz (from step "backup_current")
```

### breakpoint add|remove|list \<step_name\>

Manage breakpoints. When execution reaches a step with a breakpoint, it pauses and enters debug mode.

```
(debug) > breakpoint add start_service
Breakpoint set on step "start_service"

(debug) > breakpoint add verify_health
Breakpoint set on step "verify_health"

(debug) > breakpoint list
Breakpoints:
  1. start_service
  2. verify_health

(debug) > breakpoint remove start_service
Breakpoint removed from step "start_service"
```

---

## Setting Breakpoints Before Execution

You can set breakpoints before starting an orchestration. Use the `--break` flag:

```
dm> run deploy_app --target web-01 --debug --break install_packages --break start_service

Breakpoints set: install_packages, start_service
[step 1/6] check_disk_space ... OK
[step 2/6] detect_version ... OK
[breakpoint] Pausing at step "install_packages"
(debug) >
```

You can also add or remove breakpoints while paused, and they take effect immediately for subsequent steps.

---

## Step-Through Mode

When you run with `--debug` and no breakpoints, execution pauses at every step:

```
dm> run deploy_app --target web-01 --debug

[step-through] Pausing before step "check_disk_space"
(debug) > inspect

Step: check_disk_space
  Command:    df -h / | awk 'NR==2 {print $4}'
  Target:     web-01 (192.168.1.10)
  ...

(debug) > continue

[step 1/6] check_disk_space ... OK
[step-through] Pausing before step "detect_version"
(debug) > continue

[step 2/6] detect_version ... OK
[step-through] Pausing before step "install_packages"
(debug) >
```

Use `continue` at each pause to advance one step at a time. To resume uninterrupted execution, remove all breakpoints and type `continue` -- it will run to completion (or the next failure).

---

## Workflow Example: Diagnosing and Fixing a Failure

This example walks through a realistic debugging session where a deployment fails and you fix it without restarting.

### Step 1: Run the Orchestration

```
dm> run deploy_app --target web-01

[step 1/6] check_disk_space ... OK
[step 2/6] detect_version ... OK
[step 3/6] install_packages ... FAILED (exit code 100)

Step "install_packages" FAILED (exit code 100)
Drop into debug mode? [Y/n]: Y
(debug) >
```

### Step 2: Inspect the Failure

```
(debug) > inspect

Step: install_packages
  Command:    apt-get install -y nginx=1.18.0
  Target:     web-01 (192.168.1.10)
  Env:
    DEBIAN_FRONTEND=noninteractive
  Stdout:     Reading package lists...
              E: Version '1.18.0' for 'nginx' was not found
  Stderr:     E: Version '1.18.0' for 'nginx' was not found
  Exit Code:  100
```

The problem is clear: version 1.18.0 is not available in the repository.

### Step 3: Check Variables from Prior Steps

```
(debug) > vars

Variables:
  disk_free       = 15234 (from step "check_disk_space")
  app_version     = 3.1.0 (from step "detect_version")
```

### Step 4: Modify the Command

```
(debug) > modify apt-get install -y nginx

Step "install_packages" command updated:
  Old: apt-get install -y nginx=1.18.0
  New: apt-get install -y nginx
```

### Step 5: Re-run the Step

```
(debug) > rerun

Re-running step "install_packages" on web-01...
  Stdout:     Reading package lists...
              Setting up nginx (1.24.0-1) ...
  Exit Code:  0
Step "install_packages" PASSED
(debug) >
```

### Step 6: Continue Execution

```
(debug) > continue

Continuing execution...
[step 4/6] configure_nginx ... OK
[step 5/6] start_service ... OK
[step 6/6] verify_health ... OK

Orchestration "deploy_app" completed successfully.
dm>
```

The orchestration completed without a full restart. Remember to update the orchestration definition to fix the version permanently.

---

## Tips

- **In-memory only**: `modify` changes are not persisted. Update the orchestration definition separately to make fixes permanent.
- **Combine with step-through**: Use `--debug` proactively on new or untested orchestrations to catch issues before they cascade.
- **Breakpoints are session-scoped**: They exist only for the current execution. Each new `run` starts with a clean slate unless you specify `--break` again.
- **Use `vars` liberally**: Checking variable state helps you understand what downstream steps will receive as input.
- **Abort safely**: `abort` stops execution cleanly. Any completed steps retain their results in the execution log.

---

## Next Steps

- [Tutorial 22: Auto-Complete for Orchestration Parameters](22-auto-complete.md) -- Faster command entry in DShell
- [Tutorial 23: Web Terminal](23-web-terminal.md) -- Use DShell (and the debugger) from your browser
