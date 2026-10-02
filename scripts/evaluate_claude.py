"""Opt-in real Claude Code smoke test in a synthetic temporary project.

Uses normal Claude authentication and usage. No deployment or public publishing.
Only a sanitized summary is written to the requested output file.
"""
import argparse
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time

KIT = Path(__file__).resolve().parents[1]
MODEL_IDS = {"opus": "claude-opus-5-5", "sonnet": "claude-sonnet-5-5", "haiku": "claude-haiku-4-5"}


def summarize_usage(result):
    """Use final per-model totals, including subagents; never sum streamed deltas."""
    fields = {"input_tokens": "inputTokens", "output_tokens": "outputTokens", "cache_read_input_tokens": "cacheReadInputTokens", "cache_creation_input_tokens": "cacheCreationInputTokens"}
    models = {}
    for model, usage in (result.get("modelUsage") or {}).items():
        if not isinstance(usage, dict):
            continue
        models[model] = {name: value if type(value := usage.get(key)) is int and value >= 0 else None for name, key in fields.items()}
    complete = bool(models) and all(value is not None for usage in models.values() for value in usage.values())
    totals = {name: sum(usage[name] for usage in models.values()) for name in fields} if complete else None
    denominator = sum(totals[name] for name in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")) if totals else 0
    cost = result.get("total_cost_usd")
    if type(cost) not in (int, float) or not math.isfinite(cost) or cost < 0:
        cost = None
    return {"available": complete, "scope": "final modelUsage totals including subagents", "models": models,
            "totals": totals, "cache_read_fraction": round(totals["cache_read_input_tokens"] / denominator, 6) if denominator else None,
            "estimated_cost_usd": cost}


def matches_model(model, requested):
    """Accept an exact requested full model or its native date-pinned form."""
    expected = MODEL_IDS.get(requested, requested)
    return (isinstance(model, str) and isinstance(expected, str) and expected.startswith("claude-")
            and bool(re.fullmatch(re.escape(expected) + r"(?:-\d{8})?", model)))


def model_policy_passed(summary):
    """Audit frozen requested routing plus actual coordinator and worker metadata."""
    policy = summary.get("requested_worker_models")
    if not isinstance(policy, dict) or set(policy) != {"test-author", "implementer", "verifier"}:
        return False
    if summary.get("observed_worker_models") != policy:
        return False
    session = summary.get("requested_model", "")
    coordinator = summary.get("observed_coordinator_models", [])
    if not coordinator or not all(matches_model(model, session) for model in coordinator):
        return False
    expected = {}
    for role, selected in policy.items():
        if selected not in {"inherit", "opus", "sonnet", "haiku"}:
            return False
        expected["ai-tdd:" + role] = session if selected == "inherit" else MODEL_IDS[selected]
    roles = summary.get("observed_role_models", {})
    if not all(roles.get(role) and all(matches_model(model, target) for model in roles[role])
               for role, target in expected.items()):
        return False
    observed = summary.get("observed_response_models", [])
    return bool(observed) and all(any(matches_model(model, target) for target in [session, *expected.values()]) for model in observed)


def trial_passed(summary, require_usage=False, require_same_model=False, resume_check=False, require_model_policy=False):
    """Judge observed workflow evidence, independently of Claude's final prose."""
    quality = summary.get("quality", {})
    result = summary.get("result") or {}
    required_roles = {"ai-tdd:test-author", "ai-tdd:implementer", "ai-tdd:verifier"}
    checks = quality.get("checks", [])
    passed = (summary.get("phase") == "DONE" and summary.get("timed_out") is False
              and summary.get("exit_code") == 0 and result.get("is_error") is False
              and result.get("subtype") == "success"
              and summary.get("independent_behavior_checks", {}).get("passed") is True
              and summary.get("initial_test_file_preserved") is True
              and summary.get("final_evidence_current") is True
              and quality.get("status") == "passed"
              and {"lint", "format", "typecheck"}.issubset({check.get("kind") for check in checks})
              and all(check.get("exit_code") == 0 and not check.get("error") for check in checks)
              and quality.get("test_assessment_count", 0) > 0
              and quality.get("repository_profile_present") is True
              and required_roles.issubset(summary.get("agent_types", [])))
    if require_usage:
        usage = summary.get("usage", {})
        cost = usage.get("estimated_cost_usd")
        passed = (passed and usage.get("available") is True and type(cost) in (int, float)
                  and math.isfinite(cost) and cost >= 0)
    if require_same_model:
        requested = summary.get("requested_model", "")
        roles = summary.get("observed_role_models", {})
        observed = summary.get("observed_response_models", [])
        passed = (passed and requested.startswith("claude-") and bool(observed)
                  and all(matches_model(model, requested) for model in observed)
                  and all(roles.get(role) and all(matches_model(model, requested) for model in roles[role])
                          for role in required_roles))
    if require_model_policy:
        passed = passed and model_policy_passed(summary)
    if resume_check:
        resume = summary.get("resume", {})
        passed = (passed and resume.get("exit_code") == 0 and resume.get("is_error") is False
                  and resume.get("phase") == "DONE" and resume.get("state_preserved") is True)
    return bool(passed)


def stop_model_process(process):
    """Stop this evaluator's process tree when its pre-registered time expires."""
    if os.name == "nt":
        try:
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                           capture_output=True, timeout=15, check=False)
        except (OSError, subprocess.TimeoutExpired):
            process.kill()
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    try:
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        if os.name != "nt":
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        process.kill()
        process.wait(timeout=15)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--timeout", type=int, default=420)
    parser.add_argument("--resume-check", action="store_true")
    parser.add_argument("--model", default="opus")
    parser.add_argument("--effort", choices=["low", "medium", "high", "xhigh", "max"])
    parser.add_argument("--plugin-dir", help="Optional baseline plugin directory for a controlled comparison")
    parser.add_argument("--case", choices=["fee", "authorization", "ledger"], default="fee")
    parser.add_argument("--max-budget-usd", type=float, default=5)
    parser.add_argument("--max-turns", type=int, default=45)
    parser.add_argument("--test-strength", action="store_true", help="Execute frozen selected faults after final evidence inspection")
    parser.add_argument("--require-usage", action="store_true")
    parser.add_argument("--require-same-model", action="store_true")
    parser.add_argument("--require-model-policy", action="store_true", help="Audit exact frozen routing and actual coordinator/worker models")
    parser.add_argument("--implementer-model", choices=["haiku", "sonnet", "opus"], help="Explicit mixed-role experiment; default workers all inherit")
    parser.add_argument("--project-artifact", help="Optional local ZIP retaining only synthetic src/tests Python files")
    parser.add_argument("--quiet", action="store_true", help="Write the sanitized report without phase or summary stdout")
    args = parser.parse_args()
    if args.timeout <= 0 or args.max_turns <= 0 or not math.isfinite(args.max_budget_usd) or args.max_budget_usd <= 0:
        parser.error("Timeout, turns and model budget must be positive")
    if args.project_artifact and Path(args.project_artifact).exists():
        parser.error("Project artifact already exists; use a distinct trial target")
    if args.require_same_model and args.implementer_model:
        parser.error("A mixed implementer policy cannot require all roles to use the session model")
    executable = shutil.which("claude")
    if not executable:
        raise SystemExit("Claude Code not found")
    from launch_claude import launch_environment
    from model_benchmark_cases import CASES, case_fingerprint, inspect_behavior, inspect_test_strength, write_project_artifact
    case = CASES[args.case]
    requested_worker_models = {"test-author": "inherit", "implementer": args.implementer_model or "inherit", "verifier": "inherit"}
    plugin = Path(args.plugin_dir).resolve() if args.plugin_dir else KIT / "plugins/ai-tdd"
    with tempfile.TemporaryDirectory(prefix="ai-tdd-claude-") as folder:
        root = Path(folder)
        (root / "src").mkdir()
        (root / "tests").mkdir()
        (root / case["source_path"]).write_text(case["initial_source"], encoding="utf-8")
        (root / case["test_path"]).write_text(case["initial_test"], encoding="utf-8")
        original_test_bytes = (root / case["test_path"]).read_bytes()
        (root / "pyproject.toml").write_text('[tool.ruff]\ntarget-version = "py310"\n[tool.ruff.lint]\nselect = ["F"]\n[tool.mypy]\nstrict = true\n', encoding="utf-8")
        (root / "CLAUDE.md").write_text(case["style"] + " Repository quality commands: python -m ruff check .; python -m ruff format --check src; python -m mypy src. Configure these read-only commands in quality_checks before begin; pyproject.toml is their protected input. Do not disable rules, mask failures, remove types or introduce dependencies.\n", encoding="utf-8")
        routing = "For this controlled comparison configure worker_models with test-author, implementer and verifier all set to inherit; all roles must use the selected session model."
        if args.implementer_model:
            routing = ("For this controlled mixed-role comparison configure worker_models with test-author and verifier set to inherit and implementer set to "
                       + args.implementer_model + ". Dispatch test-author and verifier without a model override; dispatch implementer with model: "
                       + args.implementer_model + ". Preserve these exact routes throughout the task; no fallback or escalation.")
        prompt = "/ai-tdd:feature " + case["contract"] + " Use the complete AI TDD workflow through DONE, including real RED, repo conventions, its configured quality commands and independent test adequacy review. Work is authorized; ask no permission questions. Preserve the existing passing regression. " + routing + " Do not merely describe the workflow. Return a short result."
        argv = [executable, "-p", prompt, "--plugin-dir", str(plugin), "--model", args.model,
                "--output-format", "stream-json", "--verbose", "--max-turns", str(args.max_turns), "--max-budget-usd", str(args.max_budget_usd),
                "--no-session-persistence", "--setting-sources", "", "--strict-mcp-config",
                "--mcp-config", '{"mcpServers":{}}', "--permission-mode", "acceptEdits",
                "--allowedTools", "Read,Glob,Grep,Write,Edit,Agent,Bash(python *),Bash(python3 *),Bash(node *)"]
        if args.effort:
            argv += ["--effort", args.effort]
        env = launch_environment(os.environ)
        env.pop("CLAUDECODE", None)
        env["CLAUDE_CODE_DISABLE_BACKGROUND_TASKS"] = "1"
        started = time.monotonic()
        with (root / "claude-output.jsonl").open("wb") as output, (root / "claude-errors.log").open("wb") as errors:
            process = subprocess.Popen(argv, cwd=root, env=env, stdout=output, stderr=errors,
                                       start_new_session=os.name != "nt")
            seen = None
            while process.poll() is None and time.monotonic() - started < args.timeout:
                state_path = root / ".ai-tdd/state.json"
                if state_path.exists():
                    state = json.loads(state_path.read_text(encoding="utf-8"))
                    current = (state["phase"], state["cycle"])
                    if current != seen:
                        if not args.quiet:
                            print(json.dumps({"phase": current[0], "cycle": current[1]}), flush=True)
                        seen = current
                time.sleep(1)
            timed_out = process.poll() is None
            if timed_out:
                stop_model_process(process)
            else:
                process.wait(timeout=15)
        model_elapsed_seconds = round(time.monotonic() - started, 1)
        state_path = root / ".ai-tdd/state.json"
        state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
        agents = []
        loaded_commands = []
        final = None
        final_message = {}
        observed_models = set()
        coordinator_models = set()
        dispatch_roles = {}
        role_models = {}
        controller_calls = set()
        controller_output_bytes = 0
        for line in (root / "claude-output.jsonl").read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                item = json.loads(line)
            except ValueError:
                continue
            if item.get("type") == "assistant":
                message = item.get("message", {})
                if message.get("model"):
                    observed_models.add(message["model"])
                    if not item.get("parent_tool_use_id"):
                        coordinator_models.add(message["model"])
                    if item.get("parent_tool_use_id") in dispatch_roles:
                        role_models.setdefault(dispatch_roles[item["parent_tool_use_id"]], set()).add(message["model"])
                for content in item.get("message", {}).get("content", []):
                    if content.get("type") == "tool_use" and content.get("name") in {"Agent", "Task"}:
                        agents.append(content.get("input", {}).get("subagent_type", ""))
                        dispatch_roles[content["id"]] = content.get("input", {}).get("subagent_type", "")
                    if content.get("type") == "tool_use" and content.get("name") == "Bash" and any(entry in content.get("input", {}).get("command", "") for entry in ("scripts/tdd.py", "scripts/tdd-launcher.cjs")):
                        controller_calls.add(content["id"])
            if item.get("type") == "user":
                for content in item.get("message", {}).get("content", []):
                    if content.get("type") == "tool_result" and content.get("tool_use_id") in controller_calls:
                        value = content.get("content", "")
                        controller_output_bytes += len((value if isinstance(value, str) else json.dumps(value)).encode("utf-8"))
            if item.get("type") == "system" and item.get("subtype") == "init":
                loaded_commands = [name for name in item.get("slash_commands", []) if name.startswith("ai-tdd:")]
            if item.get("type") == "result":
                final_message = item
                final = {key: item.get(key) for key in ("subtype", "is_error", "num_turns")}
        summary = {"schema": 1, "claude_version": subprocess.check_output([executable, "--version"], encoding="utf-8").strip(),
                   "elapsed_seconds": round(time.monotonic() - started, 1), "exit_code": process.returncode,
                   "timed_out": timed_out, "phase": state.get("phase"), "agent_types": agents, "loaded_commands": loaded_commands,
                   "events": [item["event"] for item in state.get("history", [])],
                   "required_test_count": len(state.get("required_ids", [])), "result": final}
        summary.update(requested_model=args.model, requested_effort=args.effort,
                       observed_response_models=sorted(observed_models), observed_role_models={name: sorted(models) for name, models in role_models.items()},
                       usage=summarize_usage(final_message), controller_output_bytes=controller_output_bytes)
        summary.update(requested_worker_models=requested_worker_models, observed_worker_models=state.get("worker_models"),
                       observed_coordinator_models=sorted(coordinator_models))
        summary.update(case=args.case, case_fingerprint=case_fingerprint(), max_budget_usd=args.max_budget_usd,
                       max_turns=args.max_turns, model_timeout_seconds=args.timeout,
                       model_elapsed_seconds=model_elapsed_seconds,
                       runner_runs=state.get("runner_runs", state.get("runs")),
                       effort_policy="explicit" if args.effort else "model-native default; no --effort override")
        quality = state.get("quality_receipt", {})
        review = state.get("review", {})
        summary["quality"] = {"status": quality.get("status"), "runs": state.get("quality_runs"),
                              "checks": [{key: check.get(key) for key in ("kind", "exit_code", "error")} for check in quality.get("checks", [])],
                              "test_assessment_count": len(review.get("test_assessment", [])),
                              "test_assessment": [{key: item.get(key) for key in ("test_id", "detects", "oracle", "why_needed")} for item in review.get("test_assessment", [])],
                              "repository_profile_present": (root / ".ai-tdd/repo-profile.json").is_file(),
                              "limitations": review.get("quality_limitations")}
        original_test = root / case["test_path"]
        summary["initial_test_file_preserved"] = original_test.is_file() and original_test.read_bytes() == original_test_bytes
        if state:
            audit = subprocess.run([sys.executable, "-B", str(plugin / "scripts/tdd.py"), "--root", str(root), "status"],
                                   cwd=root, env=env, capture_output=True, encoding="utf-8", timeout=20)
            inspected = json.loads(audit.stdout) if audit.returncode == 0 else {}
            summary["final_evidence_current"] = inspected.get("receipt_current") is True and inspected.get("quality_current") is True
        else:
            summary["final_evidence_current"] = False
        if args.project_artifact:
            try:
                summary["project_artifact"] = write_project_artifact(root, args.project_artifact)
            except (OSError, ValueError):
                summary["project_artifact"] = {"saved": False, "diagnostic": "Synthetic artifact could not be retained safely"}
        # Never give the model the hidden oracle or mutate its managed project.
        summary["independent_behavior_checks"] = inspect_behavior(case, root)
        if args.test_strength:
            summary["test_strength"] = inspect_test_strength(case, root)
        if not state:
            summary["diagnostic"] = "No framework state or Claude result; inspect authentication/environment locally."
        if args.resume_check and state.get("phase") == "DONE":
            resume_argv = argv.copy()
            resume_argv[2] = "/ai-tdd:resume Report this existing task's phase and verify its current artifacts. Do not create or change any feature."
            resume_argv[resume_argv.index("--max-turns") + 1] = "8"
            resume_argv[resume_argv.index("--output-format") + 1] = "json"
            resume_argv.remove("--verbose")
            try:
                resumed = subprocess.run(resume_argv, cwd=root, env=env, capture_output=True,
                                         encoding="utf-8", errors="replace", timeout=120)
                item = json.loads(resumed.stdout)
                if isinstance(item, list):
                    item = next((value for value in reversed(item) if value.get("type") == "result"), {})
                after = json.loads(state_path.read_text(encoding="utf-8"))
                summary["resume"] = {"exit_code": resumed.returncode, "is_error": item.get("is_error"), "phase": after.get("phase"), "state_preserved": after == state, "usage": summarize_usage(item)}
            except (subprocess.TimeoutExpired, ValueError, TypeError):
                summary["resume"] = {"ok": False, "diagnostic": "Resume did not complete"}
        passed = trial_passed(summary, require_usage=args.require_usage, require_same_model=args.require_same_model,
                              resume_check=args.resume_check,
                              require_model_policy=args.require_model_policy or bool(args.implementer_model))
        summary["model_policy_passed"] = model_policy_passed(summary)
        summary["passed"] = passed
        target = Path(args.output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        if not args.quiet:
            print(json.dumps(summary, indent=2))
        return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
