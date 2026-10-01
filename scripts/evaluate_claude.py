"""Opt-in real Claude Code smoke test in a synthetic temporary project.

Uses normal Claude authentication and usage. No deployment or public publishing.
Only a sanitized summary is written to the requested output file.
"""
import argparse
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

KIT = Path(__file__).resolve().parents[1]


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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--timeout", type=int, default=420)
    parser.add_argument("--resume-check", action="store_true")
    parser.add_argument("--model", default="opus")
    parser.add_argument("--effort", choices=["low", "medium", "high", "xhigh", "max"])
    parser.add_argument("--plugin-dir", help="Optional baseline plugin directory for a controlled comparison")
    args = parser.parse_args()
    executable = shutil.which("claude")
    if not executable:
        raise SystemExit("Claude Code not found")
    from launch_claude import launch_environment
    plugin = Path(args.plugin_dir).resolve() if args.plugin_dir else KIT / "plugins/ai-tdd"
    with tempfile.TemporaryDirectory(prefix="ai-tdd-claude-") as folder:
        root = Path(folder)
        (root / "src").mkdir()
        (root / "tests").mkdir()
        (root / "src/fee.py").write_text("def fee(cents):\n    return 799\n", encoding="utf-8")
        (root / "tests/test_fee.py").write_text("import unittest\nfrom src.fee import fee\n\nclass FeeTests(unittest.TestCase):\n    def test_regular(self):\n        self.assertEqual(fee(100), 799)\n", encoding="utf-8")
        prompt = "/ai-tdd:feature Change src/fee.py fee(cents) so nonnegative integer carts at or above 10000 cents have fee 0, while carts below 10000 retain fee 799. Public API stays fee(cents). Other input types and negative values are out of scope. Use the complete AI TDD workflow through DONE, including real RED and an independent review. Work is authorized; ask no permission questions. Preserve the existing passing regression. Do not merely describe the workflow. Return a short result."
        argv = [executable, "-p", prompt, "--plugin-dir", str(plugin), "--model", args.model,
                "--output-format", "stream-json", "--verbose", "--max-turns", "45", "--max-budget-usd", "5",
                "--no-session-persistence", "--setting-sources", "", "--strict-mcp-config",
                "--mcp-config", '{"mcpServers":{}}', "--permission-mode", "acceptEdits",
                "--allowedTools", "Read,Glob,Grep,Write,Edit,Agent,Bash(python *),Bash(python3 *)"]
        if args.effort:
            argv += ["--effort", args.effort]
        env = launch_environment(os.environ)
        env.pop("CLAUDECODE", None)
        env["CLAUDE_CODE_DISABLE_BACKGROUND_TASKS"] = "1"
        started = time.monotonic()
        with (root / "claude-output.jsonl").open("wb") as output, (root / "claude-errors.log").open("wb") as errors:
            process = subprocess.Popen(argv, cwd=root, env=env, stdout=output, stderr=errors)
            seen = None
            while process.poll() is None and time.monotonic() - started < args.timeout:
                state_path = root / ".ai-tdd/state.json"
                if state_path.exists():
                    state = json.loads(state_path.read_text(encoding="utf-8"))
                    current = (state["phase"], state["cycle"])
                    if current != seen:
                        print(json.dumps({"phase": current[0], "cycle": current[1]}), flush=True)
                        seen = current
                time.sleep(1)
            timed_out = process.poll() is None
            if timed_out:
                process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        state_path = root / ".ai-tdd/state.json"
        state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
        agents = []
        loaded_commands = []
        final = None
        final_message = {}
        observed_models = set()
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
                    if item.get("parent_tool_use_id") in dispatch_roles:
                        role_models.setdefault(dispatch_roles[item["parent_tool_use_id"]], set()).add(message["model"])
                for content in item.get("message", {}).get("content", []):
                    if content.get("type") == "tool_use" and content.get("name") in {"Agent", "Task"}:
                        agents.append(content.get("input", {}).get("subagent_type", ""))
                        dispatch_roles[content["id"]] = content.get("input", {}).get("subagent_type", "")
                    if content.get("type") == "tool_use" and content.get("name") == "Bash" and "scripts/tdd.py" in content.get("input", {}).get("command", ""):
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
        oracle = subprocess.run([sys.executable, "-B", "-c", "from src.fee import fee; cases=[(0,799),(1,799),(9999,799),(10000,0),(10001,0),(20000,0)]; assert all(fee(n)==expected for n,expected in cases)"], cwd=root, env=env, capture_output=True, timeout=10)
        summary["independent_behavior_checks"] = {"cases": 6, "passed": oracle.returncode == 0}
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
        passed = (state.get("phase") == "DONE" and not timed_out and process.returncode == 0
                  and final is not None and final.get("is_error") is False
                  and oracle.returncode == 0
                  and {"ai-tdd:test-author", "ai-tdd:implementer", "ai-tdd:verifier"}.issubset(agents))
        if args.resume_check:
            resume = summary.get("resume", {})
            passed = (passed and resume.get("exit_code") == 0 and resume.get("is_error") is False
                      and resume.get("phase") == "DONE" and resume.get("state_preserved") is True)
        summary["passed"] = passed
        target = Path(args.output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(summary, indent=2))
        return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
