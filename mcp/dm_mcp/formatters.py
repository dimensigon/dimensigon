from __future__ import annotations

from typing import Any


def _val(v: Any) -> str:
    if isinstance(v, list):
        return "\n".join(v) if all(isinstance(i, str) for i in v) else str(v)
    return str(v) if v is not None else ""


def format_server_list(servers: list[dict]) -> str:
    if not servers:
        return "No servers found."
    lines = [f"Servers ({len(servers)}):"]
    for s in servers:
        name = s.get("name", s.get("id", "?"))
        sid = s.get("id", "")
        granules = ", ".join(s.get("granules", [])) or "none"
        line = f"  - {name}  (id: {sid}, granules: {granules})"
        gates = s.get("gates", [])
        if gates:
            gate_strs = [f"{g.get('dns') or g.get('ip')}:{g.get('port')}" for g in gates]
            line += f"  gates: {', '.join(gate_strs)}"
        lines.append(line)
    return "\n".join(lines)


def format_orchestration_list(orchs: list[dict]) -> str:
    if not orchs:
        return "No orchestrations found."
    lines = [f"Orchestrations ({len(orchs)}):"]
    for o in orchs:
        name = o.get("name", "?")
        ver = o.get("version", "?")
        oid = o.get("id", "")
        desc = o.get("description", "")
        target = o.get("target", [])
        line = f"  - {name} v{ver}  (id: {oid})"
        if desc:
            line += f"\n    Description: {desc}"
        if target:
            line += f"\n    Targets: {', '.join(target)}"
        steps = o.get("steps", [])
        if steps:
            line += f"\n    Steps: {len(steps)}"
        schema = o.get("schema")
        if schema:
            req = schema.get("required", [])
            if req:
                line += f"\n    Required inputs: {', '.join(req)}"
        lines.append(line)
    return "\n".join(lines)


def format_orchestration_detail(o: dict) -> str:
    lines = [
        f"Orchestration: {o.get('name', '?')} v{o.get('version', '?')}",
        f"ID: {o.get('id', '')}",
    ]
    if o.get("description"):
        lines.append(f"Description: {_val(o['description'])}")
    lines.append(f"Stop on error: {o.get('stop_on_error')}")
    lines.append(f"Undo on error: {o.get('undo_on_error')}")
    if o.get("target"):
        lines.append(f"Targets: {', '.join(o['target'])}")

    schema = o.get("schema")
    if schema:
        req = schema.get("required", [])
        if req:
            lines.append(f"Required inputs: {', '.join(req)}")
        inp = schema.get("input", {})
        if inp:
            lines.append("Input schema:")
            for k, v in inp.items():
                lines.append(f"  {k}: {v}")
        out = schema.get("output", [])
        if out:
            lines.append(f"Outputs: {', '.join(out)}")

    steps = o.get("steps", [])
    if steps:
        lines.append(f"\nSteps ({len(steps)}):")
        for s in steps:
            _format_step_inline(s, lines)
    return "\n".join(lines)


def _format_step_inline(s: dict, lines: list[str]) -> None:
    name = s.get("name") or s.get("id", "?")
    undo = " [UNDO]" if s.get("undo") else ""
    lines.append(f"  Step: {name}{undo}  (id: {s.get('id', '')})")
    at = s.get("action_template")
    if at:
        lines.append(f"    Action: {at.get('name', '?')} v{at.get('version', '?')} ({at.get('action_type', '?')})")
        if at.get("code"):
            lines.append(f"    Code: {_val(at['code'])[:200]}")
    elif s.get("action_type"):
        lines.append(f"    Action type: {s['action_type']}")
        if s.get("code"):
            lines.append(f"    Code: {_val(s['code'])[:200]}")
    parents = s.get("parent_step_ids", [])
    if parents:
        lines.append(f"    Parents: {', '.join(parents)}")
    if s.get("target"):
        lines.append(f"    Target: {s['target']}")


def format_action_template_list(templates: list[dict]) -> str:
    if not templates:
        return "No action templates found."
    lines = [f"Action Templates ({len(templates)}):"]
    for t in templates:
        name = t.get("name", "?")
        ver = t.get("version", "?")
        tid = t.get("id", "")
        atype = t.get("action_type", "?")
        lines.append(f"  - {name} v{ver}  ({atype})  id: {tid}")
        if t.get("description"):
            lines.append(f"    {_val(t['description'])[:120]}")
    return "\n".join(lines)


def format_action_template_detail(t: dict) -> str:
    lines = [
        f"Action Template: {t.get('name', '?')} v{t.get('version', '?')}",
        f"ID: {t.get('id', '')}",
        f"Type: {t.get('action_type', '?')}",
    ]
    if t.get("description"):
        lines.append(f"Description: {_val(t['description'])}")
    if t.get("code"):
        lines.append(f"Code:\n{_val(t['code'])}")
    if t.get("schema"):
        lines.append(f"Schema: {t['schema']}")
    if t.get("pre_process"):
        lines.append(f"Pre-process:\n{_val(t['pre_process'])}")
    if t.get("post_process"):
        lines.append(f"Post-process:\n{_val(t['post_process'])}")
    if t.get("expected_rc") is not None:
        lines.append(f"Expected RC: {t['expected_rc']}")
    if t.get("expected_stdout"):
        lines.append(f"Expected stdout: {_val(t['expected_stdout'])}")
    if t.get("system_kwargs"):
        lines.append(f"System kwargs: {t['system_kwargs']}")
    return "\n".join(lines)


def format_execution_list(execs: list[dict]) -> str:
    if not execs:
        return "No executions found."
    lines = [f"Executions ({len(execs)}):"]
    for e in execs:
        eid = e.get("id", "?")
        orch = e.get("orchestration", {})
        if isinstance(orch, dict):
            oname = f"{orch.get('name', '?')} v{orch.get('version', '?')}"
        else:
            oname = str(e.get("orchestration_id", "?"))
        success = e.get("success")
        status = "SUCCESS" if success is True else ("FAILED" if success is False else "RUNNING")
        start = e.get("start_time", "?")
        end = e.get("end_time", "")
        lines.append(f"  - [{status}] {oname}  (id: {eid})")
        lines.append(f"    Started: {start}" + (f"  Ended: {end}" if end else ""))
        if e.get("target"):
            lines.append(f"    Target: {e['target']}")
        if e.get("message"):
            lines.append(f"    Message: {e['message']}")
    return "\n".join(lines)


def format_execution_detail(e: dict) -> str:
    orch = e.get("orchestration", {})
    if isinstance(orch, dict):
        oname = f"{orch.get('name', '?')} v{orch.get('version', '?')}"
    else:
        oname = str(e.get("orchestration_id", "?"))
    success = e.get("success")
    status = "SUCCESS" if success is True else ("FAILED" if success is False else "RUNNING")

    lines = [
        f"Execution: {oname}  [{status}]",
        f"ID: {e.get('id', '')}",
        f"Started: {e.get('start_time', '?')}",
    ]
    if e.get("end_time"):
        lines.append(f"Ended: {e['end_time']}")
    if e.get("target"):
        lines.append(f"Target: {e['target']}")
    if e.get("params"):
        lines.append(f"Params: {e['params']}")
    if e.get("message"):
        lines.append(f"Message: {e['message']}")
    if e.get("undo_success") is not None:
        lines.append(f"Undo success: {e['undo_success']}")

    steps = e.get("steps", [])
    if steps:
        lines.append(f"\nStep Executions ({len(steps)}):")
        for se in steps:
            _format_step_execution(se, lines)
    return "\n".join(lines)


def _format_step_execution(se: dict, lines: list[str]) -> None:
    sid = se.get("step_id", "?")
    success = se.get("success")
    status = "OK" if success is True else ("FAIL" if success is False else "?")
    server = se.get("server") or se.get("server_id", "")
    lines.append(f"  [{status}] Step {sid}  server: {server}  rc: {se.get('rc', '?')}")
    if se.get("stdout"):
        lines.append(f"    stdout: {_val(se['stdout'])[:300]}")
    if se.get("stderr"):
        lines.append(f"    stderr: {_val(se['stderr'])[:300]}")
    timing = []
    if se.get("pre_process_elapsed_time") is not None:
        timing.append(f"pre={se['pre_process_elapsed_time']:.2f}s")
    if se.get("execution_elapsed_time") is not None:
        timing.append(f"exec={se['execution_elapsed_time']:.2f}s")
    if se.get("post_process_elapsed_time") is not None:
        timing.append(f"post={se['post_process_elapsed_time']:.2f}s")
    if timing:
        lines.append(f"    Timing: {', '.join(timing)}")
    # Nested orchestration execution
    if se.get("orch_execution"):
        lines.append("    Nested execution:")
        nested = format_execution_detail(se["orch_execution"])
        for nl in nested.split("\n"):
            lines.append(f"      {nl}")


def format_command_result(result: dict) -> str:
    if not result:
        return "No output."
    lines = ["Command Results:"]
    for server, data in result.items():
        lines.append(f"  Server: {server}")
        if isinstance(data, dict):
            lines.append(f"    RC: {data.get('rc', '?')}")
            if data.get("stdout"):
                lines.append(f"    stdout: {_val(data['stdout'])}")
            if data.get("stderr"):
                lines.append(f"    stderr: {_val(data['stderr'])}")
        else:
            lines.append(f"    {data}")
    return "\n".join(lines)


def format_vault_list(entries: list[dict] | dict) -> str:
    if isinstance(entries, dict):
        # scopes response
        lines = ["Vault Scopes:"]
        for k, v in entries.items():
            lines.append(f"  - {k}: {v}")
        return "\n".join(lines)
    if not entries:
        return "No vault entries found."
    lines = [f"Vault Entries ({len(entries)}):"]
    for e in entries:
        name = e.get("name", "?")
        scope = e.get("scope", "?")
        lines.append(f"  - {scope}/{name}: {e.get('value', '***')}")
    return "\n".join(lines)


def format_granules(granules: list) -> str:
    if not granules:
        return "No granules defined."
    lines = [f"Granules ({len(granules)}):"]
    for g in granules:
        lines.append(f"  - {g}")
    return "\n".join(lines)
