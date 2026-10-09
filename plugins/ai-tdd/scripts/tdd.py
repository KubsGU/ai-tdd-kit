"""Deterministic AI TDD controller, Python 3.10+, standard library only.

Process safeguards, not a sandbox against hostile executable tests.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import shlex
import shutil
import stat
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET

PLUGIN = Path(__file__).resolve().parents[1]
_quality_loader = importlib.util.spec_from_file_location("ai_tdd_quality", PLUGIN / "scripts/quality.py")
QUALITY = importlib.util.module_from_spec(_quality_loader)
_quality_loader.loader.exec_module(QUALITY)
IGNORED = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", "node_modules", ".git", ".venv", "venv"}
READ_TOOLS = {"Read", "Glob", "Grep", "AskUserQuestion", "TodoWrite", "TaskCreate", "TaskUpdate", "TaskGet", "TaskList", "SendUserMessage"}
SELFTEST_REASON = "deny: AI TDD hook self-test"
CACHE_FLAGS = ("DISABLE_PROMPT_CACHING", "DISABLE_PROMPT_CACHING_OPUS", "DISABLE_PROMPT_CACHING_SONNET", "DISABLE_PROMPT_CACHING_HAIKU", "DISABLE_PROMPT_CACHING_FABLE")
JSON_INPUT_MAX_BYTES = 5_000_000
NATIVE_REPORT_MAX_BYTES = 64 * 1024 * 1024
STATE_MAX_BYTES = 64 * 1024 * 1024


class TddError(RuntimeError):
    pass


def worker_models(value):
    allowed = {'test-author': {'inherit', 'opus'}, 'implementer': {'inherit', 'sonnet', 'haiku', 'opus'},
               'verifier': {'inherit', 'opus'}}
    if not isinstance(value, dict) or set(value) - set(allowed):
        raise TddError('worker_models must map only test-author, implementer and verifier roles')
    result = {role: 'inherit' for role in allowed}
    for role, model in value.items():
        if not isinstance(model, str) or model not in allowed[role]:
            raise TddError('worker_models has an unsupported model for ' + role)
        result[role] = model
    return result


def managed_folder(root):
    folder = Path(root).resolve() / ".ai-tdd"
    if folder.is_symlink() or folder.resolve() != folder:
        raise TddError("Managed state directory cannot be a symlink or junction")
    return folder


def digest(path):
    if not path.exists():
        return None
    if not path.is_file() or path.is_symlink():
        raise TddError("Expected a regular file without symlinks")
    with path.open("rb") as stream:
        if hasattr(hashlib, "file_digest"):
            return hashlib.file_digest(stream, "sha256").hexdigest()
        return hashlib.sha256(stream.read()).hexdigest()


def read_json(path, *, max_bytes=JSON_INPUT_MAX_BYTES):
    try:
        info = path.lstat()
        if (info.st_size > max_bytes or not stat.S_ISREG(info.st_mode) or path.is_symlink()
                or getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)):
            raise TddError("Unsafe or oversized JSON artifact")
        with path.open("rb") as stream:
            raw = stream.read(max_bytes + 1)
        if len(raw) > max_bytes:
            raise TddError("Unsafe or oversized JSON artifact")
        return json.loads(raw.decode("utf-8"))
    except (OSError, ValueError) as error:
        raise TddError(f"Cannot read {path.name}: {type(error).__name__}") from error


def atomic_json(path, value, *, max_bytes=None):
    raw = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    if max_bytes is not None and len(raw.encode("utf-8")) > max_bytes:
        raise TddError("JSON artifact exceeds its bounded evidence budget; previous artifact is preserved")
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        temp.write_text(raw, encoding="utf-8")
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def inside(path, parent):
    return path == parent or parent in path.parents


def safe_path(root, value):
    if not isinstance(value, str) or not value.strip():
        raise TddError("A nonempty relative path is required")
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise TddError("Path traversal or absolute configuration path")
    path = root / relative
    resolved = path.resolve()
    if not inside(resolved, root) or resolved == root:
        raise TddError("Configured paths must stay below project root")
    cursor = path
    while cursor != root:
        if cursor.is_symlink():
            raise TddError("Symlinks are unsupported in managed paths")
        cursor = cursor.parent
    return resolved


def environment():
    names = ("PATH", "PYTHONPATH", "PYTEST_ADDOPTS", "PYTHONHASHSEED", "NODE_OPTIONS", "NODE_ENV", "CI", "TZ", "CLAUDE_CODE_DISABLE_BACKGROUND_TASKS",
             "CLAUDE_CODE_SUBAGENT_MODEL", "CLAUDE_CODE_SUBAGENT_MODEL_FORCE", "CLAUDE_CODE_EFFORT_LEVEL",
             "DOTNET_ROOT", "DOTNET_ROOT_X64", "DOTNET_ROLL_FORWARD", "DOTNET_ROLL_FORWARD_TO_PRERELEASE",
             "DOTNET_CLI_HOME", "DOTNET_MSBUILD_SDK_RESOLVER_CLI_DIR", "DOTNET_MSBUILD_SDK_RESOLVER_SDKS_DIR",
             "MSBuildSDKsPath", "MSBUILD_EXE_PATH", "NUGET_PACKAGES", "VSTEST_TESTCASEFILTER", "VSTEST_RUN_SETTINGS",
             "VSTEST_RUNSETTINGS", "AI_TDD_PYTHON") + CACHE_FLAGS
    executable = Path(sys.executable).resolve()
    value = {"python": sys.version, "executable": str(executable), "binary_sha256": digest(executable), "platform": platform.platform(),
             "options": {name: hashlib.sha256(os.environ.get(name, "").encode()).hexdigest() for name in names}}
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def generated_roots(root, config):
    """Explicit project build outputs, never a blanket bin/obj name exclusion."""
    values = config.get('generated_roots', [])
    if not isinstance(values, list) or any(not isinstance(value, str) for value in values) or len(set(values)) != len(values):
        raise TddError('generated_roots must be a unique list of project bin/obj directories')
    owned = {safe_path(root, value) for key in ('source_roots', 'test_roots') for value in config[key]}
    projects = {safe_path(root, value).parent for value in config['protected_paths']
                if Path(value).suffix.lower() == '.csproj' and safe_path(root, value).is_file()}
    result = []
    for value in values:
        try:
            path = safe_path(root, value)
        except TddError as error:
            raise TddError('Unsafe generated_roots path') from error
        expected = root / Path(value)
        if path != expected or path.name not in {'bin', 'obj'} or path.parent not in owned & projects or path.is_file():
            raise TddError('generated_roots may exclude only bin/obj below an owned, protected .csproj project')
        result.append(value)
    return sorted(result)


def hook_health():
    if os.environ.get("CLAUDECODE") and os.environ.get("CLAUDE_CODE_DISABLE_BACKGROUND_TASKS") != "1":
        raise TddError("Sequential AI TDD requires foreground workers; start Claude with CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1")
    if os.environ.get("CLAUDECODE"):
        if any(os.environ.get(name) == "1" for name in CACHE_FLAGS):
            raise TddError("Prompt caching is disabled in the environment; use the bundled launch_claude.py or unset DISABLE_PROMPT_CACHING flags before starting Claude")
        if os.environ.get("CLAUDE_CODE_SUBAGENT_MODEL_FORCE") == "1" and os.environ.get("CLAUDE_CODE_SUBAGENT_MODEL", "inherit") not in {"", "inherit"}:
            raise TddError("Forced worker model bypasses model inheritance; use launch_claude.py or remove the forced model override")
    node = shutil.which("node")
    if not node:
        raise TddError("AI TDD hook requires Node.js on PATH")
    try:
        payload = {"cwd": str(PLUGIN), "hook_event_name": "PreToolUse", "tool_name": "AI_TDD_SELFTEST", "tool_input": {}}
        result = subprocess.run([node, "--preserve-symlinks", "--preserve-symlinks-main", str(PLUGIN / "scripts/hook-launcher.cjs")], input=json.dumps(payload), capture_output=True, encoding="utf-8", timeout=15)
        decision = json.loads(result.stdout).get("hookSpecificOutput", {})
        if result.returncode or decision.get("permissionDecision") != "deny" or decision.get("permissionDecisionReason") != SELFTEST_REASON:
            raise TddError("AI TDD hook self-test failed; repair the runtime before begin")
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        raise TddError("AI TDD hook self-test failed: " + type(error).__name__) from error
    return {"hook_health": "pass", "python_version": platform.python_version()}


def native_report_problem(value):
    """A progress report is diagnostic evidence, never a passing receipt."""
    if not isinstance(value, dict):
        return "Runner JSON report must be an object"
    if (value.get("completion", "complete") != "complete" or value.get("complete", True) is not True
            or value.get("diagnostics")):
        codes = sorted({item["code"] for item in value.get("diagnostics", [])
                        if isinstance(item, dict) and isinstance(item.get("code"), str) and item["code"]}) if isinstance(value.get("diagnostics", []), list) else []
        return "Incomplete native .NET evidence: " + (", ".join(code[:120] for code in codes[:12]) or "module collection did not complete")
    if "planned_module_count" in value:
        count, modules = value["planned_module_count"], value.get("native_modules")
        if (type(count) is not int or count < 1 or not isinstance(modules, list) or len(modules) != count
                or any(not isinstance(module, dict) or module.get("status") != "complete" for module in modules)):
            return "Incomplete native .NET evidence: planned/completed module inventory differs"
    return None


def native_runtime_rows(results):
    """Bind the native framework's row inventory without interpreting names."""
    parents = {}
    for item in results:
        if "native_test_id" not in item:
            continue
        parent, child, test_id = item.get("native_case_id"), item["native_test_id"], item["id"]
        if (not isinstance(parent, str) or not parent or not isinstance(child, str) or not child
                or not test_id.endswith("|xunit:" + parent + "|test:" + child)):
            raise TddError("Invalid native runtime row identity")
        key = test_id[:-(len(child) + len("|test:"))]
        parents.setdefault(key, []).append(test_id)
    return {parent: sorted(rows) for parent, rows in sorted(parents.items())}


def parse_report(path, fmt, *, native=False):
    if fmt == "json":
        value = read_json(path, max_bytes=NATIVE_REPORT_MAX_BYTES if native else JSON_INPUT_MAX_BYTES)
        problem = native_report_problem(value)
        if problem:
            raise TddError(problem)
        if value.get("schema") != 1:
            raise TddError("Unsupported runner report schema")
        collected, results = value.get("collected"), value.get("results")
    elif fmt == "junit":
        try:
            if path.stat().st_size > 5_000_000 or path.is_symlink():
                raise TddError("Unsafe or oversized runner report")
            raw = path.read_bytes()
            if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
                raise TddError("DTD/entity declarations are unsupported")
            tree = ET.fromstring(raw)
        except (OSError, ET.ParseError) as error:
            raise TddError("Missing or invalid JUnit report") from error
        if tree.tag not in {"testsuite", "testsuites"}:
            raise TddError("JUnit root must be testsuite or testsuites")
        results = []
        for case in tree.iter("testcase"):
            name = case.get("name", "")
            if not name:
                raise TddError("JUnit testcase needs a name")
            test_id = ".".join(part for part in (case.get("classname", ""), name) if part)
            item = {"id": test_id, "status": "passed", "exception": "", "detail": ""}
            if sum(case.find(tag) is not None for tag in ("skipped", "failure", "error")) > 1:
                raise TddError("JUnit testcase has contradictory outcomes")
            for tag, status in (("skipped", "skipped"), ("failure", "failed"), ("error", "error")):
                child = case.find(tag)
                if child is not None:
                    item.update(status=status, exception=child.get("type", "UnknownFailure" if tag == "failure" else "RunnerError").split(".")[-1], detail=(child.get("message", "") + " " + (child.text or ""))[:1200])
            results.append(item)
        collected = [item["id"] for item in results]
        for suite in tree.iter():
            if suite.tag not in {"testsuite", "testsuites"}:
                continue
            cases = list(suite.iter("testcase"))
            actual_counts = {"tests": len(cases), **{name: sum(case.find(tag) is not None for case in cases)
                              for name, tag in (("failures", "failure"), ("errors", "error"), ("skipped", "skipped"))}}
            for name, actual in actual_counts.items():
                if name not in suite.attrib:
                    continue
                try:
                    declared = int(suite.attrib[name])
                except ValueError as error:
                    raise TddError("JUnit count must be a nonnegative integer: " + name) from error
                if declared < 0 or declared != actual:
                    raise TddError("JUnit declared " + name + " count differs from testcase inventory")
    else:
        raise TddError("Runner format must be json or junit")
    if not isinstance(collected, list) or not isinstance(results, list):
        raise TddError("Report needs collected IDs and executed results")
    ids = []
    for item in results:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not item["id"]:
            raise TddError("Invalid executed test ID")
        if item.get("status") not in {"passed", "failed", "error", "skipped"}:
            raise TddError("Invalid test status")
        ids.append(item["id"])
    if any(not isinstance(item, str) or not item for item in collected):
        raise TddError("Invalid collected test ID")
    if len(set(ids)) != len(ids) or len(set(collected)) != len(collected) or set(ids) != set(collected):
        raise TddError("Collected/executed ID mismatch or duplicate IDs")
    return collected, results


class Controller:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.folder = managed_folder(self.root)
        self.state_path = self.folder / "state.json"
        self.config = read_json(self.folder / "config.json")
        if self.config.get("schema") != 1:
            raise TddError("Unsupported config schema")
        self.worker_models = worker_models(self.config.get('worker_models', {}))
        for key in ("source_roots", "test_roots", "protected_paths"):
            paths = self.config.get(key)
            if not isinstance(paths, list) or (key != "protected_paths" and not paths):
                raise TddError(f"Config requires {key}")
            for path in paths:
                resolved = safe_path(self.root, path)
                if inside(resolved, self.folder) or ".git" in Path(path).parts or any(part.startswith(".env") for part in Path(path).parts):
                    raise TddError("Control, Git and secret paths cannot be feature artifacts")
        sources = [safe_path(self.root, path) for path in self.config["source_roots"]]
        tests = [safe_path(self.root, path) for path in self.config["test_roots"]]
        if any(inside(a, b) or inside(b, a) for a in sources for b in tests):
            raise TddError("source and test roots must not overlap")
        self.generated_roots = generated_roots(self.root, self.config)
        if not isinstance(self.config.get("max_attempts", 3), int) or not 1 <= self.config.get("max_attempts", 3) <= 20:
            raise TddError("max_attempts must be 1..20")
        budget = self.config.get("max_runner_runs", 100)
        if type(budget) is not int or not 1 <= budget <= 10000:
            raise TddError("max_runner_runs must be an integer in 1..10000")
        if not isinstance(self.config.get("timeout_seconds", 120), (int, float)) or not 0 < self.config.get("timeout_seconds", 120) <= 3600:
            raise TddError("timeout_seconds must be positive and at most 3600")
        runner = self.config.get("runner", {})
        argv = runner.get("argv", [])
        if not argv or not all(isinstance(arg, str) for arg in argv) or not any("{report}" in arg for arg in argv):
            raise TddError("Runner argv must contain {report}; shell command strings are unsupported")
        if runner.get("format") not in {"json", "junit"}:
            raise TddError("Unsupported runner format")
        try:
            self.quality_checks = QUALITY.validate_checks(self.config.get("quality_checks", []))
            self.project_python = QUALITY.project_python() if any('{python}' in arg for arg in
                [*argv, *(arg for check in self.quality_checks for arg in check['argv'])]) else None
        except ValueError as error:
            raise TddError(str(error)) from error
        quality_limit = self.config.get("max_quality_runs", 20)
        if type(quality_limit) is not int or not 1 <= quality_limit <= 10000:
            raise TddError("max_quality_runs must be an integer in 1..10000")
        self.quality_policy = {"checks": self.quality_checks, "run_limit": quality_limit}
        self.quality_inputs = sorted({path for check in self.quality_checks for path in check["inputs"]})
        for path in self.quality_inputs:
            resolved = safe_path(self.root, path)
            if inside(resolved, self.folder) or any(part == ".git" or part.startswith(".env") for part in Path(path).parts):
                raise TddError("Private/control paths cannot be quality inputs")
            if any(inside(resolved, owned) or inside(owned, resolved) for owned in sources + tests):
                raise TddError("Quality inputs are configuration; source/test roots are already fingerprinted")
        self.state = read_json(self.state_path, max_bytes=STATE_MAX_BYTES) if self.state_path.exists() else None
        if self.state and self.state.get("phase") != "DONE":
            if self.state.get('generated_roots', []) != self.generated_roots:
                raise TddError('Frozen generated_roots changed; setup repair cannot change excluded outputs')
            if "test_checkpoint" not in self.state:
                raise TddError("Active task lacks test_checkpoint; finish and archive with the previous plugin version, then update. Do not infer a checkpoint from current files")
            checkpoint = self.state["test_checkpoint"]
            if not isinstance(checkpoint, dict) or any(not isinstance(path, str) or not isinstance(value, str) or len(value) != 64 or any(char not in "0123456789abcdef" for char in value) for path, value in checkpoint.items()):
                raise TddError("Invalid test_checkpoint; restore reviewed task evidence before continuing")

    def spec(self):
        value = read_json(self.folder / "spec.json")
        if not isinstance(value.get("version"), int) or value["version"] < 1 or not value.get("goal"):
            raise TddError("Spec needs a positive version and goal")
        items = value.get("acceptance", [])
        if not items or any(not isinstance(item, dict) or not isinstance(item.get("id"), str) or not item["id"] or not item.get("description") for item in items):
            raise TddError("Spec needs acceptance IDs and descriptions")
        ids = [item["id"] for item in items]
        if len(set(ids)) != len(ids):
            raise TddError("Duplicate acceptance IDs")
        if value.get("open_questions", []):
            raise TddError("Unresolved behavior questions prevent implementation")
        return value

    def manifest(self, paths):
        result = {}
        outputs = [safe_path(self.root, value) for value in self.generated_roots]
        for relative in paths:
            path = safe_path(self.root, relative)
            if path.is_dir():
                result[relative.rstrip("/") + "/"] = "directory"
                for item in sorted(path.rglob("*")):
                    if any(inside(item, output) for output in outputs):
                        continue
                    if any(part in IGNORED for part in item.relative_to(path).parts):
                        continue
                    if item.is_symlink():
                        raise TddError("Symlinks are unsupported in managed artifacts")
                    if item.is_file():
                        result[item.relative_to(self.root).as_posix()] = digest(item)
            else:
                result[relative] = digest(path)
        return result

    def source(self):
        return self.manifest(self.config["source_roots"])

    def test_files(self):
        return {path: value for path, value in self.manifest(self.config["test_roots"]).items()
                if value not in {None, "directory"}}

    def protected(self, include_tests=True, include_spec=True):
        paths = self.config["protected_paths"] + self.quality_inputs + (self.config["test_roots"] if include_tests else [])
        result = self.manifest(paths)
        dotnet = self.config.get("dotnet", {})
        if isinstance(dotnet, dict) and "external_absent_inputs" in dotnet:
            module = dotnet_setup_module()
            try:
                absent = module.external_absent_snapshot(self.root, dotnet["external_absent_inputs"])
            except module.DotnetError as error:
                raise TddError(str(error)) from error
            result.update({"external-absent:" + path: marker for path, marker in absent.items()})
        names = ["config.json", "review-plan.json", "repo-profile.json"] + (["spec.json"] if include_spec else [])
        for name in names:
            result[".ai-tdd/" + name] = digest(self.folder / name)
        for name in ("scripts/tdd.py", "scripts/quality.py", "scripts/unittest_runner.py", "scripts/pytest_runner.py", "scripts/hook-launcher.cjs", "hooks/hooks.json",
                     "scripts/tdd-launcher.cjs", "scripts/runtime_entry.py", "scripts/dotnet_runner.py", "scripts/dotnet_setup.py", "runtime-manifest.json", "references/dotnet.md",
                     "agents/test-author.md", "agents/implementer.md", "agents/verifier.md",
                     "skills/feature/SKILL.md", "skills/resume/SKILL.md", "references/protocol.md", "references/efficiency.md", "references/quality.md",
                     "SKILL.md", "references/host-integration.md", ".claude-plugin/plugin.json", ".claude-plugin/marketplace.json"):
            result["plugin/" + name] = digest(PLUGIN / name)
        return result

    def save(self, event, **details):
        self.state["history"].append({"event": event, "utc": datetime.now(timezone.utc).isoformat(), **details})
        atomic_json(self.state_path, self.state, max_bytes=STATE_MAX_BYTES)
        return self.state

    def phase(self, *allowed):
        if not self.state or self.state["phase"] not in allowed:
            raise TddError("Expected phase " + "/".join(allowed))
        if self.state["environment"] != self.runtime_environment():
            raise TddError("Environment changed; start a fresh reviewed run")
        if self.state["phase"] != "DONE" and self.state.get("quality_policy") != self.quality_policy:
            raise TddError("Frozen quality definitions/budget changed; setup repair cannot drop or weaken quality checks")
        if self.state["phase"] != "DONE":
            self.fixed_worker_models()

    def fixed_worker_models(self):
        if self.state.get('worker_models', worker_models({})) != self.worker_models:
            raise TddError('Frozen worker model policy changed; finish and archive this task before selecting another policy')

    def runtime_environment(self):
        base = environment()
        if self.project_python and Path(self.project_python).resolve() != Path(sys.executable).resolve():
            value = {'controller': base, 'project_python': self.project_python, 'sha256': digest(Path(self.project_python))}
            return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()
        return base

    def fixed(self, include_tests=True, include_spec=True):
        expected = self.state["frozen"] if include_tests else self.state["fixed"]
        if self.protected(include_tests, include_spec) != expected:
            raise TddError("Changed protected artifacts; use explicit contract amendment")

    def run(self, kind):
        dotnet = self.config.get("dotnet")
        native = isinstance(dotnet, dict) and dotnet.get("schema") == 1
        if self.state:
            self.require_run_budget()
            self.state["runner_runs"] = self.state.get("runner_runs", 1) + 1
            self.save("runner-started", kind=kind, total_runner_runs=self.state["runner_runs"])
        before_protected, before_source = self.protected(), self.source()
        before_state = digest(self.state_path)
        run_id = uuid.uuid4().hex
        runs = self.folder / "runs"
        runs.mkdir(parents=True, exist_ok=True)
        if runs.is_symlink():
            raise TddError("Runner directory cannot be a symlink")
        report = runs / (run_id + (".xml" if self.config["runner"]["format"] == "junit" else ".json"))
        replacements = {"{python}": self.project_python or '', "{plugin}": PLUGIN.as_posix(), "{root}": self.root.as_posix(), "{report}": report.as_posix()}
        argv = []
        for arg in self.config["runner"]["argv"]:
            for key, value in replacements.items():
                arg = arg.replace(key, value)
            argv.append(arg)
        child_env = os.environ.copy()
        child_env["PYTHONDONTWRITEBYTECODE"] = "1"
        process_error = None
        try:
            with (runs / (run_id + ".stdout.log")).open("wb") as out, (runs / (run_id + ".stderr.log")).open("wb") as err:
                process = subprocess.run(argv, cwd=self.root, env=child_env, shell=False, stdout=out, stderr=err, timeout=self.config.get("timeout_seconds", 120))
        except subprocess.TimeoutExpired as error:
            process_error = error
        except OSError as error:
            process_error = error
        if self.protected() != before_protected or self.source() != before_source or digest(self.state_path) != before_state:
            raise TddError("Runner modified source or protected artifacts")
        log_path = (runs / (run_id + ".stderr.log")).relative_to(self.root).as_posix()
        if process_error:
            reason = "Runner timeout" if isinstance(process_error, subprocess.TimeoutExpired) else "Runner executable unavailable: " + type(process_error).__name__
            if self.config["runner"]["format"] == "json" and report.exists():
                try:
                    problem = native_report_problem(read_json(report, max_bytes=NATIVE_REPORT_MAX_BYTES if native else JSON_INPUT_MAX_BYTES))
                except TddError as error:
                    problem = str(error)
                if problem:
                    reason += "; " + problem
            raise TddError(reason + "; no RED/GREEN evidence; inspect " + log_path) from process_error
        if not report.exists():
            raise TddError("Runner exited with code " + str(process.returncode) + " without a fresh report; inspect " + log_path)
        try:
            collected, results = parse_report(report, self.config["runner"]["format"], native=native)
        except TddError as error:
            raise TddError(str(error) + "; inspect " + report.relative_to(self.root).as_posix() + " and " + log_path) from error
        failed = any(item["status"] in {"failed", "error"} for item in results)
        if process.returncode not in {0, 1} or (process.returncode == 0) == failed:
            raise TddError("Runner exit/report mismatch or infrastructure failure")
        if any(item["status"] == "skipped" for item in results):
            raise TddError("Skipped tests cannot certify this workflow")
        receipt = {"id": run_id, "kind": kind, "utc": datetime.now(timezone.utc).isoformat(), "environment": self.runtime_environment(), "protected": before_protected, "source": before_source, "collected": collected, "results": results, "exit_code": process.returncode}
        atomic_json(runs / (run_id + ".receipt.json"), receipt, max_bytes=STATE_MAX_BYTES)
        return receipt

    def require_run_budget(self):
        if self.state.get("runner_runs", 1) >= self.state.get("runner_run_limit", self.config.get("max_runner_runs", 100)):
            raise TddError("Task runner budget exhausted; no retry or setup repair grants more runs")

    def require_suite(self, receipt, failing=()):
        actual = {item["id"]: item for item in receipt["results"]}
        if not set(self.state["required_ids"]).issubset(actual):
            raise TddError("Missing previously executed required test IDs")
        if any(item["status"] != "passed" for test_id, item in actual.items() if test_id not in failing):
            raise TddError("Unexpected regression or runner error")
        rows = native_runtime_rows(receipt["results"])
        for parent, required in self.state.get("native_runtime_rows", {}).items():
            observed = rows.get(parent)
            if observed != required and self.state["phase"] != "AMEND":
                raise TddError("Existing runtime theory row inventory changed; diagnose data stability or use an explicit contract amendment")
        return actual

    def fresh(self):
        self.fixed()
        receipt = self.state["green_receipt"]
        if receipt["source"] != self.source() or receipt["environment"] != self.runtime_environment():
            raise TddError("Stale GREEN receipt; run green again before continuing")

    def run_quality(self, kind):
        if self.state and self.quality_checks:
            if self.state["quality_runs"] >= self.state["quality_run_limit"]:
                raise TddError("Task quality budget exhausted; no retry/setup repair grants more checks")
            self.state["quality_runs"] += 1
            self.save("quality-started", kind=kind, total_quality_runs=self.state["quality_runs"])
        source, protected = self.source(), self.protected()
        before_environment = self.runtime_environment()
        before_state = digest(self.state_path)
        before_review = digest(self.folder / "review.json")
        fingerprint = lambda: (self.source(), self.protected(), self.runtime_environment(), digest(self.state_path), digest(self.folder / "review.json"))
        try:
            receipt = QUALITY.execute_checks(self.root, self.folder, self.quality_checks, fingerprint, python_executable=self.project_python)
        except ValueError as error:
            if (self.state and self.source() != source and self.protected() == protected
                    and self.runtime_environment() == before_environment and digest(self.state_path) == before_state
                    and digest(self.folder / "review.json") == before_review):
                self.state["phase"] = "GREEN"
                self.state.pop("review", None)
                self.save("quality-rejected", kind=kind, reason="source modified by a check")
            raise TddError("quality check rejected: " + str(error)) from error
        receipt.update(kind=kind, utc=datetime.now(timezone.utc).isoformat(), source=source, protected=protected, environment=self.runtime_environment())
        for check in receipt["checks"]:
            check["log_hashes"] = {name: digest(safe_path(self.root, check[name])) for name in ("stdout_path", "stderr_path")}
        path = self.folder / "runs" / (receipt["id"] + ".quality.json")
        atomic_json(path, receipt)
        if self.state:
            self.state.update(quality_receipt=receipt, quality_hash=digest(path))
            if receipt["status"] == "failed":
                self.state["phase"] = "GREEN"
                self.state.pop("review", None)
            self.save("quality-checked", kind=kind, status=receipt["status"], receipt_id=receipt["id"])
        if receipt["status"] == "failed":
            raise TddError("quality checks failed; inspect .ai-tdd/runs/" + receipt["id"] + ".quality.json and its logs")
        return receipt

    def quality_current(self):
        receipt = (self.state or {}).get("quality_receipt")
        if not receipt or receipt["status"] not in {"passed", "not_configured"}:
            return False
        path = self.folder / "runs" / (receipt["id"] + ".quality.json")
        current = (receipt["source"] == self.source() and receipt["protected"] == self.protected()
                   and receipt["environment"] == self.runtime_environment() and digest(path) == self.state.get("quality_hash"))
        return current and all(digest(safe_path(self.root, check[name])) == check["log_hashes"][name]
                               for check in receipt["checks"] for name in ("stdout_path", "stderr_path"))

    def quality(self):
        self.phase("GREEN", "VERIFY")
        self.fresh()
        self.run_quality("pre-review")
        return self.state

    def begin(self, allow_empty=False):
        # Setup artifacts may have been completed after object construction.
        policy_upgrade = prepare_native_policy(self.root)
        self.__init__(self.root)
        if self.state:
            raise TddError("A task already exists; resume it or use a separate checkout")
        spec = self.spec()
        scenarios = read_json(self.folder / "review-plan.json").get("scenarios", [])
        valid_ac = {item["id"] for item in spec["acceptance"]}
        if not scenarios or any(not item.get("case") or item.get("ac") not in valid_ac for item in scenarios):
            raise TddError("Create an independent spec-based review plan before implementation")
        if {item["ac"] for item in scenarios} != valid_ac:
            raise TddError("Review plan must address every acceptance criterion")
        baseline = self.run("baseline")
        if baseline["exit_code"] or (not baseline["results"] and not allow_empty):
            types = sorted({str(item.get("exception") or item["status"])[:120] for item in baseline["results"] if item["status"] != "passed"})
            types = sorted(set(types) | {item["native_failure_code"] for item in baseline["results"]
                                        if item["status"] != "passed" and isinstance(item.get("native_failure_code"), str)})
            path = (self.folder / "runs" / (baseline["id"] + ".receipt.json")).relative_to(self.root).as_posix()
            raise TddError("Baseline must pass and execute tests" + (": " + ", ".join(types[:12]) if types else "; bootstrap needs --allow-empty") + "; inspect " + path)
        quality_baseline = self.run_quality("baseline")
        self.state = {"schema": 1, "task_id": uuid.uuid4().hex, "phase": "TEST", "spec_version": spec["version"], "environment": self.runtime_environment(), "baseline_receipt": baseline, "required_ids": baseline["collected"], "source_checkpoint": self.source(), "test_checkpoint": self.test_files(), "fixed": self.protected(False), "coverage": {}, "attempts": 0, "cycle": 1, "history": [], "empty_baseline_waiver": bool(not baseline["results"] and allow_empty)}
        self.state.update(runner_runs=1, runner_run_limit=self.config.get("max_runner_runs", 100))
        self.state.update(initial_required_ids=list(baseline["collected"]), quality_policy=self.quality_policy,
                          native_runtime_rows=native_runtime_rows(baseline["results"]),
                          native_policy_upgrade=policy_upgrade,
                          worker_models=dict(self.worker_models),
                          generated_roots=list(self.generated_roots),
                          quality_runs=int(bool(self.quality_checks)), quality_run_limit=self.quality_policy["run_limit"],
                          quality_receipt=quality_baseline, quality_hash=digest(self.folder / "runs" / (quality_baseline["id"] + ".quality.json")))
        return self.save("begin")

    def increment(self, tests, ac, because):
        self.phase("TEST", "AMEND")
        if not because or not tests or len(set(tests)) != len(tests) or not ac:
            raise TddError("Increment needs unique test IDs, acceptance IDs and oracle rationale")
        if self.source() != self.state["source_checkpoint"]:
            raise TddError("Changed source during test authoring")
        amendment = self.state["phase"] == "AMEND"
        if not amendment:
            current = self.test_files()
            if any(current.get(path) != value for path, value in self.state["test_checkpoint"].items()):
                raise TddError("Changed or deleted test checkpoint files; author a new test file or use explicit contract amendment")
        self.fixed(False, not amendment)
        spec = self.spec()
        valid_ac = {item["id"] for item in spec["acceptance"]}
        if not set(ac).issubset(valid_ac):
            raise TddError("Unknown acceptance ID")
        if amendment and spec["version"] != self.state["spec_version"] + 1:
            raise TddError("Contract amendment must increment spec version by one")
        if not amendment and set(tests) & set(self.state["required_ids"]):
            raise TddError("New increment must introduce new tests; existing test changes need amend")
        return spec

    def seal(self, receipt, tests, ac, spec, because):
        self.state["required_ids"] = sorted(set(self.state["required_ids"]) | set(receipt["collected"]))
        self.state["spec_version"] = spec["version"]
        self.state["fixed"], self.state["frozen"] = self.protected(False), self.protected()
        self.state["increment"] = {"tests": tests, "ac": ac, "because": because}
        self.state["attempts"] = 0
        self.state["native_runtime_rows"] = native_runtime_rows(receipt["results"])
        self.state.pop("review", None)

    def red(self, tests, ac, expect, because):
        spec = self.increment(tests, ac, because)
        if expect not in {"AssertionError", "NotImplementedError"}:
            raise TddError("RED accepts AssertionError or explicit interface-stub NotImplementedError only")
        receipt = self.run("red")
        actual = self.require_suite(receipt, tests)
        if set(tests) != {item["id"] for item in receipt["results"] if item["status"] != "passed"}:
            raise TddError("RED must fail exactly the selected target tests")
        if any(actual[test]["exception"] != expect for test in tests):
            raise TddError("RED exception differs from the expected behavior failure")
        self.seal(receipt, tests, ac, spec, because)
        self.state.update(phase="IMPLEMENT", red_receipt=receipt)
        return self.save("red-confirmed", tests=tests, ac=ac, oracle=because)

    def record_coverage(self, tests, ac):
        for criterion in ac:
            self.state["coverage"][criterion] = sorted(set(self.state["coverage"].get(criterion, [])) | set(tests))

    def cover(self, tests, ac, because):
        spec = self.increment(tests, ac, because)
        receipt = self.run("coverage")
        self.require_suite(receipt)
        if not receipt["results"] or not set(tests).issubset(receipt["collected"]):
            raise TddError("Coverage targets were not executed")
        self.seal(receipt, tests, ac, spec, because)
        self.record_coverage(tests, ac)
        self.state.update(phase="GREEN", green_receipt=receipt)
        return self.save("existing-behavior-covered", tests=tests, ac=ac)

    def green(self):
        self.phase("IMPLEMENT", "GREEN")
        self.fixed()
        if self.state["attempts"] >= self.config.get("max_attempts", 3):
            raise TddError("Repair budget exhausted")
        self.state["attempts"] += 1
        self.save("green-attempt", attempt=self.state["attempts"])
        try:
            receipt = self.run("green")
            self.require_suite(receipt)
            if not receipt["results"] or receipt["exit_code"]:
                raise TddError("GREEN requires a nonempty passing suite")
        except TddError as error:
            exhausted = self.state["runner_runs"] >= self.state["runner_run_limit"]
            self.state["phase"] = "BLOCKED" if exhausted or self.state["attempts"] >= self.config.get("max_attempts", 3) else "IMPLEMENT"
            self.save("green-failed", category=str(error))
            raise
        increment = self.state["increment"]
        self.record_coverage(increment["tests"], increment["ac"])
        self.state.update(phase="GREEN", green_receipt=receipt)
        return self.save("green-confirmed")

    def next(self):
        self.phase("GREEN", "VERIFY")
        self.fresh()
        self.state.update(phase="TEST", source_checkpoint=self.source(), test_checkpoint=self.test_files(), attempts=0, cycle=self.state["cycle"] + 1)
        self.state.pop("review", None)
        return self.save("next-increment")

    def amend(self, reason, ac):
        self.phase("IMPLEMENT", "GREEN", "VERIFY", "BLOCKED")
        self.fixed()
        valid_ac = {item["id"] for item in self.spec()["acceptance"]}
        if not reason.strip() or not ac or not set(ac).issubset(valid_ac):
            raise TddError("Amendment needs an independent justification and valid impacted AC IDs")
        self.state.update(phase="AMEND", source_checkpoint=self.source(), fixed=self.protected(False, False), cycle=self.state["cycle"] + 1, attempts=0)
        for criterion in ac:
            self.state["coverage"].pop(criterion, None)
        self.state.pop("review", None)
        return self.save("contract-amendment", reason=reason, impacted_ac=ac)

    def retry(self, reason):
        self.phase("BLOCKED")
        self.fixed()
        self.require_run_budget()
        if not reason.strip():
            raise TddError("Retry needs a new diagnosis")
        self.state.update(phase="IMPLEMENT", attempts=0)
        return self.save("budget-reset-after-diagnosis", reason=reason)

    def reconfigure(self, reason, paths):
        self.phase("IMPLEMENT", "GREEN", "VERIFY", "BLOCKED")
        self.fixed()
        if not reason.strip():
            raise TddError("Setup repair requires a concrete diagnosis")
        if any(path not in self.config["protected_paths"] for path in paths):
            raise TddError("Setup repair can unlock only explicitly protected existing file paths")
        for path in paths:
            item = safe_path(self.root, path)
            if item.is_dir() or path in {"CLAUDE.md", "AGENTS.md"} or ".claude" in Path(path).parts:
                raise TddError("Instructions, permissions and directories cannot be unlocked")
            if any(inside(item, safe_path(self.root, base)) for base in self.config["source_roots"] + self.config["test_roots"]):
                raise TddError("Feature source/tests cannot be unlocked as setup")
        stable = {key: value for key, value in self.protected().items() if key not in set(paths) | {".ai-tdd/config.json"}}
        self.state["reconfigure"] = {"paths": paths, "source": self.source(), "stable": stable,
                                      "ownership": {key: self.config[key] for key in ("source_roots", "test_roots", "protected_paths")}, "reason": reason}
        self.state["phase"] = "RECONFIGURE"
        self.state.pop("review", None)
        return self.save("setup-repair-opened", reason=reason, paths=paths)

    def rebase(self, expect="AssertionError"):
        self.__init__(self.root)
        self.phase("RECONFIGURE")
        repair = self.state["reconfigure"]
        if any(self.config[key] != value for key, value in repair["ownership"].items()):
            raise TddError("Setup repair cannot change path ownership or the protected inventory")
        if self.source() != repair["source"]:
            raise TddError("Setup repair changed feature source")
        stable = {key: value for key, value in self.protected().items() if key not in set(repair["paths"]) | {".ai-tdd/config.json"}}
        if stable != repair["stable"]:
            raise TddError("Setup repair changed other protected artifacts")
        if expect not in {"AssertionError", "NotImplementedError"}:
            raise TddError("Unsupported RED failure expectation")
        receipt = self.run("setup-revalidation")
        increment = self.state["increment"]
        actual = self.require_suite(receipt, increment["tests"])
        failures = {item["id"] for item in receipt["results"] if item["status"] != "passed"}
        if failures and (failures != set(increment["tests"]) or any(actual[test]["exception"] != expect for test in failures)):
            raise TddError("Reconfigured runner has unexpected failures")
        if not receipt["results"]:
            raise TddError("Reconfigured runner executed no tests")
        self.state["fixed"], self.state["frozen"] = self.protected(False), self.protected()
        self.state["attempts"] = 0
        self.state["required_ids"] = sorted(set(self.state["required_ids"]) | set(receipt["collected"]))
        if failures:
            for criterion in increment["ac"]:
                self.state["coverage"].pop(criterion, None)
            self.state.update(phase="IMPLEMENT", red_receipt=receipt)
        else:
            self.record_coverage(increment["tests"], increment["ac"])
            self.state.update(phase="GREEN", green_receipt=receipt)
        self.state.pop("reconfigure")
        return self.save("setup-revalidated", resulting_phase=self.state["phase"])

    def verify(self):
        self.phase("GREEN")
        self.fresh()
        ids = {item["id"] for item in self.spec()["acceptance"]}
        if ids != set(self.state["coverage"]):
            raise TddError("Every acceptance criterion needs mapped executed tests")
        if not self.quality_current():
            self.run_quality("pre-review")
        self.state["phase"] = "VERIFY"
        return self.save("independent-verification")

    def finish(self):
        self.phase("VERIFY")
        self.fresh()
        review = read_json(self.folder / "review.json")
        ids = {item["id"] for item in self.spec()["acceptance"]}
        if review.get("receipt_id") != self.state["green_receipt"]["id"] or set(review.get("checked_ac", [])) != ids:
            raise TddError("Review must reference current GREEN and every AC")
        if review.get("recommendation") != "accept" or review.get("findings") != [] or not isinstance(review.get("limitations"), list):
            raise TddError("Unresolved review findings prevent completion")
        assessed = review.get("test_assessment", [])
        required_assessment = set(self.state["required_ids"]) - set(self.state["initial_required_ids"])
        required_assessment.update(test for targets in self.state["coverage"].values() for test in targets)
        fields = ("test_id", "detects", "oracle", "why_needed")
        if (not isinstance(assessed, list) or any(not isinstance(item, dict) or any(not isinstance(item.get(field), str) or not item[field].strip() for field in fields) for item in assessed)):
            raise TddError("Test assessment needs IDs, concrete defects, independent oracles and distinct justification")
        assessed_ids = [item["test_id"] for item in assessed]
        if (len(set(assessed_ids)) != len(assessed_ids) or not required_assessment.issubset(assessed_ids)
                or not set(assessed_ids).issubset(self.state["required_ids"])):
            raise TddError("Test assessment must cover every new/changed behavior test with executed IDs")
        if not isinstance(review.get("repo_conventions"), str) or not review["repo_conventions"].strip():
            raise TddError("Review must assess repository conventions with concrete evidence")
        limitations = review.get("quality_limitations")
        if not isinstance(limitations, list) or any(not isinstance(item, str) or not item.strip() for item in limitations) or (not self.quality_checks and not limitations):
            raise TddError("Review needs explicit quality limitations when no tools are configured")
        if review.get("quality_receipt_id") != self.state["quality_receipt"]["id"]:
            raise TddError("Review must reference current quality evidence")
        review_hash = digest(self.folder / "review.json")
        self.run_quality("completion")
        receipt = self.run("completion")
        self.require_suite(receipt)
        if not receipt["results"] or receipt["exit_code"] or digest(self.folder / "review.json") != review_hash:
            raise TddError("Final verification failed or review changed during run")
        self.state.update(phase="DONE", completion_receipt=receipt, review=review, review_hash=review_hash)
        return self.save("complete")

    def archive(self):
        self.phase("DONE")
        task = self.state["task_id"]
        if len(task) != 32 or any(char not in "0123456789abcdef" for char in task):
            raise TddError("Invalid archived task identity")
        destination = safe_path(self.root, ".ai-tdd-history/" + task)
        if destination.exists():
            raise TddError("Archive already exists; nothing will be overwritten")
        destination.parent.mkdir(parents=True, exist_ok=True)
        self.save("archived", source_matches_completion=self.source() == self.state["completion_receipt"]["source"])
        os.replace(self.folder, destination)
        (destination / "controller.lock").unlink(missing_ok=True)
        return {"archive": str(destination), "next": "init for the next feature; all old evidence retained"}


def compact_state(state):
    """Project execution evidence into a small decision view, retaining disk proofs."""
    if not isinstance(state, dict) or "phase" not in state:
        return state
    fields = ("schema", "task_id", "phase", "spec_version", "cycle", "attempts", "increment", "coverage", "receipt_current", "quality_current", "empty_baseline_waiver", "review", "worker_models")
    result = {name: state[name] for name in fields if name in state}
    used, limit = state.get("runner_runs", 1), state.get("runner_run_limit", 100)
    result.update(view="compact", required_test_count=len(state["required_ids"]),
                  runner_budget={"used": used, "limit": limit, "remaining": max(0, limit-used)},
                  artifacts={"state": ".ai-tdd/state.json", "spec": ".ai-tdd/spec.json", "config": ".ai-tdd/config.json",
                             "review_plan": ".ai-tdd/review-plan.json", "review": ".ai-tdd/review.json"})
    for name in ("baseline_receipt", "red_receipt", "green_receipt", "completion_receipt"):
        if name not in state:
            continue
        receipt = state[name]
        result[name] = {"id": receipt["id"], "kind": receipt["kind"], "exit_code": receipt["exit_code"],
                        "executed_count": len(receipt["results"]), "path": ".ai-tdd/runs/" + receipt["id"] + ".receipt.json",
                        "nonpassing_tests": [item for item in receipt["results"] if item["status"] != "passed"]}
    if state.get("history"):
        result["last_event"] = state["history"][-1]
    if "reconfigure" in state:
        result["reconfigure"] = {name: state["reconfigure"][name] for name in ("paths", "reason")}
    if "quality_receipt" in state:
        receipt = state["quality_receipt"]
        result["quality_receipt"] = {"id": receipt["id"], "status": receipt["status"], "path": ".ai-tdd/runs/" + receipt["id"] + ".quality.json",
                                     "checks": [{key: check[key] for key in ("name", "kind", "exit_code", "error", "stdout_path", "stderr_path")} for check in receipt["checks"]]}
        result["quality_budget"] = {"used": state["quality_runs"], "limit": state["quality_run_limit"]}
    if "review" in result:
        result["review"] = {name: value for name, value in result["review"].items() if name != "test_assessment"}
        result["review"]["assessed_test_count"] = len(state["review"].get("test_assessment", []))
    return result


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--root", default=".")
    result.add_argument("--full", action="store_true", help="Emit full state instead of the default compact decision view")
    sub = result.add_subparsers(dest="command", required=True)
    sub.add_parser("init")
    sub.add_parser("status")
    sub.add_parser("doctor")
    sub.add_parser("quality")
    sub.add_parser("archive")
    begin = sub.add_parser("begin")
    begin.add_argument("--allow-empty", action="store_true")
    for name in ("red", "cover"):
        item = sub.add_parser(name)
        item.add_argument("--tests", nargs="+", required=True)
        item.add_argument("--ac", nargs="+", required=True)
        item.add_argument("--because", required=True)
        if name == "red":
            item.add_argument("--expect", default="AssertionError")
    for name in ("green", "next", "verify", "finish"):
        sub.add_parser(name)
    item = sub.add_parser("amend")
    item.add_argument("--reason", required=True)
    item.add_argument("--ac", nargs="+", required=True)
    item = sub.add_parser("retry")
    item.add_argument("--reason", required=True)
    item = sub.add_parser("reconfigure")
    item.add_argument("--reason", required=True)
    item.add_argument("--paths", nargs="*", default=[])
    item = sub.add_parser("rebase")
    item.add_argument("--expect", default="AssertionError")
    return result


def managed_root(cwd):
    path = Path(cwd).resolve()
    for candidate in (path, *path.parents):
        if (candidate / ".ai-tdd/state.json").exists():
            return candidate
    return None


def controller_command(command, root, plugin_root, cwd=None):
    if not isinstance(command, str) or any(char in command for char in ";&|><\n\r$`(){}"):
        return False
    try:
        parts = shlex.split(command)
        if len(parts) < 3:
            return False
        executable = Path(parts[0]).name.lower()
        if executable in {'node', 'node.exe'}:
            offset = 1
            while parts[offset] in {'--preserve-symlinks', '--preserve-symlinks-main'}:
                offset += 1
            script = 'scripts/tdd-launcher.cjs'
        elif executable in {'python', 'python3', 'python.exe', 'python3.exe'}:
            offset = 2 if parts[1] == '-B' else 1
            script = 'scripts/tdd.py'
        else:
            return False
        if Path(parts[offset]).resolve() != (Path(plugin_root) / script).resolve():
            return False
        args = parser().parse_args(parts[offset + 1:])
        path = Path(args.root)
        if not path.is_absolute():
            path = Path(cwd or root) / path
        return args.command != "init" and path.resolve() == Path(root).resolve()
    except (ValueError, IndexError, SystemExit):
        return False


def guard(payload, plugin_root=PLUGIN):
    if payload.get("tool_name") == "AI_TDD_SELFTEST":
        return SELFTEST_REASON
    root = managed_root(payload.get("cwd", os.getcwd()))
    if root is None:
        return None
    try:
        c = Controller(root)
        phase = c.state["phase"]
        if phase == "DONE":
            return None
        tool, inputs = payload.get("tool_name", ""), payload.get("tool_input", {})
        role = {"ai-tdd:test-author": "test-author", "ai-tdd:implementer": "implementer",
                "ai-tdd:verifier": "verifier"}.get(payload.get("agent_type", ""), "")
        worker = bool(payload.get("agent_id"))
        if tool == "Agent":
            c.fixed_worker_models()
            if worker or role:
                return "deny: workers cannot delegate managed work"
            if (root / ".ai-tdd/controller.lock").exists():
                return "deny: controller is executing; wait before dispatch"
            if any(inputs.get(key) for key in ("resume", "run_in_background", "isolation")):
                return "deny: managed workers need fresh contexts in the current checkout"
            requested = inputs.get("subagent_type")
            allowed = {"ai-tdd:verifier"}
            if phase in {"TEST", "AMEND"}:
                allowed.add("ai-tdd:test-author")
            if phase in {"IMPLEMENT", "GREEN"}:
                allowed.add("ai-tdd:implementer")
            if requested not in allowed:
                return "deny: dispatch the named agent that owns this phase"
            selected = c.worker_models[requested.removeprefix('ai-tdd:')]
            if inputs.get('model', 'inherit') != selected:
                return 'deny: worker dispatch must match frozen worker_models policy for ' + requested
            return None
        if tool in READ_TOOLS:
            return None
        if (root / ".ai-tdd/controller.lock").exists():
            return "deny: controller is executing; wait for its receipt"
        if tool == "Bash":
            if worker or role in {"test-author", "implementer", "verifier"}:
                return "deny: workers have no shell or runner authority"
            return None if controller_command(inputs.get("command"), root, plugin_root, payload.get("cwd")) else "deny: active AI TDD permits only a direct controller command in Bash"
        if tool not in {"Write", "Edit", "MultiEdit"}:
            return "deny: tool is outside the managed workflow allowlist"
        original = Path(inputs.get("file_path", ""))
        if not inputs.get("file_path") or ".." in original.parts:
            return "deny: missing path or unsupported traversal"
        cursor = original if original.is_absolute() else Path(payload.get("cwd", str(root))) / original
        path = cursor.resolve()
        if not inside(path, root) or inside(path, Path(plugin_root).resolve()):
            return "deny: mutation must stay within the feature workspace"
        relative = path.relative_to(root).as_posix()
        if phase == "RECONFIGURE":
            allowed = [".ai-tdd/config.json"] + c.state["reconfigure"]["paths"]
            if not worker and role not in {"test-author", "implementer", "verifier"} and relative in allowed:
                safe_path(root, relative)
                return None
            return "deny: setup repair is limited to coordinator-owned declared configuration files"
        if role == "verifier":
            return "deny: verifier is read-only"
        if path == root / ".ai-tdd/review.json" and phase == "VERIFY" and not worker:
            return None
        if path == root / ".ai-tdd/spec.json" and phase == "AMEND" and (role == "test-author" or (not worker and not role)):
            return None
        if role not in {"test-author", "implementer"}:
            return "deny: delegate feature edits to the role that owns the phase"
        protected = [safe_path(root, item) for item in c.config["protected_paths"] + c.quality_inputs]
        if any(inside(path, safe_path(root, item)) for item in c.generated_roots):
            return 'deny: generated build outputs are not worker write ownership'
        if inside(path, c.folder) or any(inside(path, item) for item in protected) or any(part.startswith(".env") or part == ".git" for part in Path(relative).parts):
            return "deny: controller, contracts, runner configuration and private paths are protected"
        roots = c.config["test_roots"] if phase in {"TEST", "AMEND"} else c.config["source_roots"] if phase in {"IMPLEMENT", "GREEN"} else []
        if (phase in {"TEST", "AMEND"} and role == "implementer") or (phase in {"IMPLEMENT", "GREEN"} and role == "test-author"):
            return "deny: role does not own the current phase"
        if not any(inside(path, safe_path(root, item)) for item in roots):
            return "deny: write is outside paths owned by the current phase"
        if phase == "TEST" and any(path == safe_path(root, item) for item in c.state["test_checkpoint"]):
            return "deny: test checkpoint files are frozen; author a new file or request an explicit contract amendment"
        safe_path(root, relative)
        while inside(cursor, root) and cursor != root:
            if cursor.is_symlink():
                return "deny: symlink mutation is unsupported"
            cursor = cursor.parent
        return None
    except (TddError, KeyError, TypeError, ValueError) as error:
        return "deny: invalid managed state; " + str(error)


@contextmanager
def lock(root):
    folder = managed_folder(root)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "controller.lock"
    try:
        with path.open("x", encoding="utf-8") as stream:
            stream.write(str(os.getpid()))
    except FileExistsError as error:
        raise TddError("Controller already running; investigate stale lock manually") from error
    try:
        yield
    finally:
        path.unlink(missing_ok=True)


def dotnet_setup_module():
    loader = importlib.util.spec_from_file_location('ai_tdd_dotnet_setup', PLUGIN / 'scripts/dotnet_setup.py')
    module = importlib.util.module_from_spec(loader)
    loader.loader.exec_module(module)
    return module


def dotnet_configuration(root):
    module = dotnet_setup_module()
    try:
        return module.configure(root)
    except module.DotnetError as error:
        raise TddError(str(error)) from error


def prepare_native_policy(root):
    """Upgrade only an unchanged inactive native preset's evidence policy."""
    folder = managed_folder(root)
    if (folder / "state.json").exists() or not (folder / "config.json").is_file():
        return None
    path = folder / "config.json"
    value = read_json(path)
    native = value.get("dotnet")
    if not isinstance(native, dict) or "theory_mode" in native:
        return None
    modules = native.get("modules", [])
    if not isinstance(modules, list) or not any(isinstance(module, dict) and module.get("framework") == "xunit-vstest" for module in modules):
        return None
    original = path.read_bytes()
    original_hash = hashlib.sha256(original).hexdigest()
    if value != json.loads(original):
        raise TddError("Native configuration changed during preparation; repeat reviewed setup before begin")
    current = dotnet_configuration(root)
    evaluated = dict(current["dotnet"])
    mode = evaluated.pop("theory_mode", None)
    ownership = ("source_roots", "test_roots", "protected_paths", "generated_roots")
    if (mode != "runtime-parent-rows-v1" or evaluated != native
            or any(current.get(key, []) != value.get(key, []) for key in ownership)
            or digest(path) != original_hash):
        raise TddError("Native setup changed beyond runtime-row policy; repeat reviewed setup before begin")
    directory = safe_path(root, ".ai-tdd/diagnostics")
    directory.mkdir(parents=True, exist_ok=True)
    backup = directory / ("config-before-runtime-rows-" + uuid.uuid4().hex + ".json")
    with backup.open("xb") as stream:
        stream.write(original)
    value["dotnet"]["theory_mode"] = mode
    atomic_json(path, value)
    return {"backup": backup.relative_to(root).as_posix(), "sha256": original_hash}


def init(root):
    folder = managed_folder(root)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "config.json"
    if path.exists():
        raise TddError("Config already exists; will not overwrite it")
    dotnet = False
    for current, directories, files in os.walk(root, followlinks=False):
        directories[:] = [name for name in directories if name not in IGNORED | {'bin', 'obj', '.ai-tdd', '.ai-tdd-history'}]
        if any(name.lower().endswith('.csproj') for name in files):
            dotnet = True
            break
    config = dotnet_configuration(root) if dotnet else read_json(PLUGIN / 'templates/config.unittest.json')
    atomic_json(path, config)
    return {'initialized': str(folder), 'next': ('.NET projects detected; review generated ownership and existing repo quality checks; '
            if dotnet else 'Adapt config; ') + 'write spec.json and independent review-plan.json; then begin'}


def main():
    if len(sys.argv) == 2 and sys.argv[1] == "hook":
        try:
            reason = guard(json.load(sys.stdin))
        except Exception as error:
            reason = "deny: hook input/state failure " + type(error).__name__
        if reason:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": reason}}))
        return 0
    values = vars(parser().parse_args()).copy()
    root, command = Path(values.pop("root")).resolve(), values.pop("command")
    full = values.pop("full")
    try:
        if command == "doctor":
            result = hook_health()
        elif command == "status":
            c = Controller(root)
            result = c.state
            if not result:
                raise TddError("Not started yet")
            if result["phase"] in {"GREEN", "VERIFY", "DONE"}:
                receipt = result["completion_receipt"] if result["phase"] == "DONE" else result["green_receipt"]
                current = receipt["source"] == c.source() and result["frozen"] == c.protected() and result["environment"] == c.runtime_environment()
                if result["phase"] == "DONE":
                    current = current and digest(c.folder / "review.json") == result["review_hash"] and c.quality_current()
                result = {**result, "receipt_current": current}
            result = {**result, "quality_current": c.quality_current()}
        else:
            with lock(root):
                if command == "begin":
                    hook_health()
                result = init(root) if command == "init" else getattr(Controller(root), command)(**values)
        print(json.dumps(result if full else compact_state(result), ensure_ascii=False, indent=2))
        return 0
    except (TddError, KeyError, TypeError, ValueError) as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
