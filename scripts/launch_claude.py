"""Launch Claude for AI TDD with foreground workers and native prompt caching.

Changes only the child process environment. Normal Claude permissions, provider,
authentication, settings and tools stay under Claude's usual control.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess

CACHE_FLAGS = ("DISABLE_PROMPT_CACHING", "DISABLE_PROMPT_CACHING_OPUS", "DISABLE_PROMPT_CACHING_SONNET", "DISABLE_PROMPT_CACHING_HAIKU", "DISABLE_PROMPT_CACHING_FABLE")


def launch_environment(parent):
    child = dict(parent)
    for name in (*CACHE_FLAGS, "CLAUDE_CODE_SUBAGENT_MODEL", "CLAUDE_CODE_SUBAGENT_MODEL_FORCE"):
        child.pop(name, None)
    child["CLAUDE_CODE_DISABLE_BACKGROUND_TASKS"] = "1"
    return child


def launch_argv(executable, model, effort, extra):
    argv = [executable, "--model", model]
    if effort:
        argv += ["--effort", effort]
    return argv + extra


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path.cwd(), help="Feature project directory; default current directory")
    parser.add_argument("--model", default="sonnet", help="Explicit session model; default sonnet. Workers follow the frozen task policy")
    parser.add_argument("--effort", choices=["low", "medium", "high", "xhigh", "max"], help="Optional stable effort; otherwise Claude keeps its normal configuration")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("claude_args", nargs=argparse.REMAINDER, help="Additional Claude options after --")
    args = parser.parse_args()
    project = args.project.resolve()
    if not project.is_dir():
        parser.error("The feature project must be an existing directory")
    extra = args.claude_args[1:] if args.claude_args[:1] == ["--"] else args.claude_args
    if any(value.split("=")[0] in {"--model", "--effort", "--fallback-model"} for value in extra):
        parser.error("Set model/effort through launcher options; an automatic fallback profile is not supplied")
    if args.dry_run:
        print(json.dumps({"project": str(project), "requested_model": args.model, "worker_model": "inherit", "effort": args.effort or "Claude configuration",
                          "foreground_workers": True, "native_prompt_caching": "not disabled by launch environment", "parent_settings_changed": False}))
        return 0
    executable = shutil.which("claude")
    if not executable:
        parser.error("Claude Code is not on PATH")
    try:
        return subprocess.call(launch_argv(executable, args.model, args.effort, extra), cwd=project, env=launch_environment(os.environ))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
