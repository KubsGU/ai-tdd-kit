"""Run explicitly configured local quality checks with the standard library.

Checks are project commands, not a sandbox for hostile executables. The caller
supplies a fingerprint of the artifacts that commands must not modify and owns
the final persisted receipt. This module never reads or imports the controller.
"""
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid


PLUGIN = Path(__file__).resolve().parents[1]
KINDS = {"lint", "format", "typecheck", "security", "custom"}
RESERVED_NAMES = {"con", "prn", "aux", "nul", *{"com" + str(i) for i in range(1, 10)},
                  *{"lpt" + str(i) for i in range(1, 10)}}


def validate_checks(checks):
    """Return an independent, bounded configuration or raise ``ValueError``."""
    if checks is None:
        return []
    if not isinstance(checks, list) or len(checks) > 20:
        raise ValueError("quality_checks must be a list of at most 20 checks")
    normalized = []
    names = set()
    for check in checks:
        if not isinstance(check, dict):
            raise ValueError("Each quality check must be an object")
        name = check.get("name")
        if (not isinstance(name, str) or len(name) > 64
                or not re.fullmatch(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*", name)
                or name in RESERVED_NAMES or name in names):
            raise ValueError("Quality check names must be unique, safe lowercase slugs of at most 64 characters")
        kind = check.get("kind")
        if not isinstance(kind, str) or kind not in KINDS:
            raise ValueError("Quality check kind must be lint, format, typecheck, security, or custom")
        argv = check.get("argv")
        if (not isinstance(argv, list) or not argv
                or any(not isinstance(arg, str) or not arg.strip() or "\x00" in arg for arg in argv)):
            raise ValueError("Quality check argv must be a nonempty list of nonempty strings")
        timeout = check.get("timeout_seconds", 120)
        if (isinstance(timeout, bool) or not isinstance(timeout, (int, float))
                or not 0 < timeout <= 3600 or not math.isfinite(timeout)):
            raise ValueError("Quality check timeout_seconds must be positive and at most 3600")
        inputs = check.get("inputs", [])
        if (not isinstance(inputs, list)
                or any(not isinstance(value, str) or not value.strip() or "\x00" in value for value in inputs)):
            raise ValueError("Quality check inputs must be a list of nonempty paths")
        normalized.append({"name": name, "kind": kind, "argv": list(argv),
                           "timeout_seconds": timeout, "inputs": list(inputs)})
        names.add(name)
    return normalized


def _runs_directory(root, folder):
    folder = Path(folder).absolute()
    if ".." in folder.parts or folder == root or root not in folder.parents:
        raise ValueError("Quality logs must stay below the project root")
    cursor = folder
    while cursor != root:
        if cursor.is_symlink() or cursor.resolve() != cursor:
            raise ValueError("Quality log directories cannot be symlinks or junctions")
        cursor = cursor.parent
    runs = folder / "runs"
    if runs.is_symlink() or runs.resolve() != runs:
        raise ValueError("Quality runs directory cannot be a symlink or junction")
    runs.mkdir(parents=True, exist_ok=True)
    return runs


def execute_checks(root, folder, checks, fingerprint):
    """Execute checks once in order, retaining logs and stopping on failure.

    Log paths are relative to ``root``. ``checks`` in the returned receipt records
    executed commands; ``unexecuted_checks`` lists names stopped by a failure.
    Fingerprint changes raise ValueError even after a timeout or launch error.
    """
    root = Path(root).resolve()
    checks = validate_checks(checks)
    receipt = {"id": str(uuid.uuid4()), "status": "not_configured", "checks": [], "unexecuted_checks": []}
    if not checks:
        return receipt
    runs = _runs_directory(root, folder)
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    replacements = {"{python}": sys.executable, "{root}": str(root), "{plugin}": str(PLUGIN)}
    receipt["status"] = "passed"
    for index, check in enumerate(checks):
        argv = []
        for argument in check["argv"]:
            for token, value in replacements.items():
                argument = argument.replace(token, value)
            argv.append(argument)
        stem = receipt["id"] + "-" + str(index) + "-" + check["name"]
        stdout_path, stderr_path = runs / (stem + ".stdout.log"), runs / (stem + ".stderr.log")
        result = {"name": check["name"], "kind": check["kind"], "argv": argv,
                  "exit_code": None, "timed_out": False, "error": None,
                  "stdout_path": stdout_path.relative_to(root).as_posix(),
                  "stderr_path": stderr_path.relative_to(root).as_posix()}
        with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
            before = fingerprint()
            try:
                process = subprocess.run(argv, cwd=root, env=env, shell=False,
                                         stdout=stdout, stderr=stderr, timeout=check["timeout_seconds"])
                result["exit_code"] = process.returncode
                if process.returncode:
                    result["error"] = "nonzero_exit"
            except subprocess.TimeoutExpired:
                result.update(timed_out=True, error="timeout")
            except FileNotFoundError:
                result["error"] = "executable_unavailable"
            except PermissionError:
                result["error"] = "permission_denied"
            except OSError:
                result["error"] = "process_error"
            finally:
                if fingerprint() != before:
                    raise ValueError("Quality check modified protected project artifacts: " + check["name"])
        receipt["checks"].append(result)
        if result["exit_code"] != 0 or result["timed_out"] or result["error"] is not None:
            receipt["status"] = "failed"
            receipt["unexecuted_checks"] = [item["name"] for item in checks[index + 1:]]
            break
    return receipt
