"""Deterministic AI TDD controller, Python 3.10+, standard library only.

Process safeguards, not a sandbox against hostile executable tests.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import shlex
import shutil
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET

PLUGIN = Path(__file__).resolve().parents[1]
IGNORED = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", "node_modules", ".git", ".venv", "venv"}
READ_TOOLS = {"Read", "Glob", "Grep", "AskUserQuestion", "Agent", "TodoWrite", "TaskCreate", "TaskUpdate", "TaskGet", "TaskList", "SendUserMessage"}
SELFTEST_REASON = "deny: AI TDD hook self-test"


class TddError(RuntimeError):
    pass


def digest(path):
    if not path.exists():
        return None
    if not path.is_file() or path.is_symlink():
        raise TddError("Expected a regular file without symlinks")
    with path.open("rb") as stream:
        if hasattr(hashlib, "file_digest"):
            return hashlib.file_digest(stream, "sha256").hexdigest()
        return hashlib.sha256(stream.read()).hexdigest()


def read_json(path):
    try:
        if path.stat().st_size > 5_000_000 or path.is_symlink():
            raise TddError("Unsafe or oversized JSON artifact")
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise TddError(f"Cannot read {path.name}: {type(error).__name__}") from error


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
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
    names = ("PYTHONPATH", "PYTEST_ADDOPTS", "PYTHONHASHSEED", "NODE_OPTIONS", "NODE_ENV", "CI", "TZ")
    value = {"python": sys.version, "executable": str(Path(sys.executable).resolve()), "platform": platform.platform(),
             "options": {name: hashlib.sha256(os.environ.get(name, "").encode()).hexdigest() for name in names}}
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def hook_health():
    node = shutil.which("node")
    if not node:
        raise TddError("AI TDD hook requires Node.js on PATH")
    try:
        payload = {"cwd": str(PLUGIN), "hook_event_name": "PreToolUse", "tool_name": "AI_TDD_SELFTEST", "tool_input": {}}
        result = subprocess.run([node, "--preserve-symlinks-main", str(PLUGIN / "scripts/hook-launcher.cjs")], input=json.dumps(payload), capture_output=True, encoding="utf-8", timeout=15)
        decision = json.loads(result.stdout).get("hookSpecificOutput", {})
        if result.returncode or decision.get("permissionDecision") != "deny" or decision.get("permissionDecisionReason") != SELFTEST_REASON:
            raise TddError("AI TDD hook self-test failed; repair the runtime before begin")
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        raise TddError("AI TDD hook self-test failed: " + type(error).__name__) from error
    return {"hook_health": "pass", "python_version": platform.python_version()}


def parse_report(path, fmt):
    if fmt == "json":
        value = read_json(path)
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
            for tag, status in (("skipped", "skipped"), ("failure", "failed"), ("error", "error")):
                child = case.find(tag)
                if child is not None:
                    item.update(status=status, exception=child.get("type", "AssertionError" if tag == "failure" else "RunnerError").split(".")[-1], detail=(child.get("message", "") + " " + (child.text or ""))[:1200])
            results.append(item)
        collected = [item["id"] for item in results]
        for suite in tree.iter("testsuite"):
            if "tests" in suite.attrib and int(suite.attrib["tests"]) != len(list(suite.iter("testcase"))):
                raise TddError("JUnit declared test count differs from testcase inventory")
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
        self.folder = self.root / ".ai-tdd"
        self.state_path = self.folder / "state.json"
        if self.folder.is_symlink():
            raise TddError("Managed state directory cannot be a symlink")
        self.config = read_json(self.folder / "config.json")
        if self.config.get("schema") != 1:
            raise TddError("Unsupported config schema")
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
        if not isinstance(self.config.get("max_attempts", 3), int) or not 1 <= self.config.get("max_attempts", 3) <= 20:
            raise TddError("max_attempts must be 1..20")
        if not isinstance(self.config.get("timeout_seconds", 120), (int, float)) or not 0 < self.config.get("timeout_seconds", 120) <= 3600:
            raise TddError("timeout_seconds must be positive and at most 3600")
        runner = self.config.get("runner", {})
        argv = runner.get("argv", [])
        if not argv or not all(isinstance(arg, str) for arg in argv) or not any("{report}" in arg for arg in argv):
            raise TddError("Runner argv must contain {report}; shell command strings are unsupported")
        if runner.get("format") not in {"json", "junit"}:
            raise TddError("Unsupported runner format")
        self.state = read_json(self.state_path) if self.state_path.exists() else None

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
        for relative in paths:
            path = safe_path(self.root, relative)
            if path.is_dir():
                result[relative.rstrip("/") + "/"] = "directory"
                for item in sorted(path.rglob("*")):
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

    def protected(self, include_tests=True, include_spec=True):
        paths = self.config["protected_paths"] + (self.config["test_roots"] if include_tests else [])
        result = self.manifest(paths)
        names = ["config.json", "review-plan.json"] + (["spec.json"] if include_spec else [])
        for name in names:
            result[".ai-tdd/" + name] = digest(self.folder / name)
        for name in ("scripts/tdd.py", "scripts/unittest_runner.py", "scripts/hook-launcher.cjs", "hooks/hooks.json",
                     "agents/test-author.md", "agents/implementer.md", "agents/verifier.md",
                     "skills/feature/SKILL.md", "skills/resume/SKILL.md", "references/protocol.md"):
            result["plugin/" + name] = digest(PLUGIN / name)
        return result

    def save(self, event, **details):
        self.state["history"].append({"event": event, "utc": datetime.now(timezone.utc).isoformat(), **details})
        atomic_json(self.state_path, self.state)
        return self.state

    def phase(self, *allowed):
        if not self.state or self.state["phase"] not in allowed:
            raise TddError("Expected phase " + "/".join(allowed))
        if self.state["environment"] != environment():
            raise TddError("Environment changed; start a fresh reviewed run")

    def fixed(self, include_tests=True, include_spec=True):
        expected = self.state["frozen"] if include_tests else self.state["fixed"]
        if self.protected(include_tests, include_spec) != expected:
            raise TddError("Changed protected artifacts; use explicit contract amendment")

    def run(self, kind):
        before_protected, before_source = self.protected(), self.source()
        before_state = digest(self.state_path)
        run_id = uuid.uuid4().hex
        runs = self.folder / "runs"
        runs.mkdir(parents=True, exist_ok=True)
        if runs.is_symlink():
            raise TddError("Runner directory cannot be a symlink")
        report = runs / (run_id + (".xml" if self.config["runner"]["format"] == "junit" else ".json"))
        replacements = {"{python}": sys.executable, "{plugin}": PLUGIN.as_posix(), "{root}": self.root.as_posix(), "{report}": report.as_posix()}
        argv = []
        for arg in self.config["runner"]["argv"]:
            for key, value in replacements.items():
                arg = arg.replace(key, value)
            argv.append(arg)
        child_env = os.environ.copy()
        child_env["PYTHONDONTWRITEBYTECODE"] = "1"
        try:
            with (runs / (run_id + ".stdout.log")).open("wb") as out, (runs / (run_id + ".stderr.log")).open("wb") as err:
                process = subprocess.run(argv, cwd=self.root, env=child_env, shell=False, stdout=out, stderr=err, timeout=self.config.get("timeout_seconds", 120))
        except subprocess.TimeoutExpired as error:
            raise TddError("Runner timeout; no RED/GREEN evidence") from error
        except OSError as error:
            raise TddError("Runner executable unavailable: " + type(error).__name__) from error
        if self.protected() != before_protected or self.source() != before_source or digest(self.state_path) != before_state:
            raise TddError("Runner modified source or protected artifacts")
        collected, results = parse_report(report, self.config["runner"]["format"])
        failed = any(item["status"] in {"failed", "error"} for item in results)
        if process.returncode not in {0, 1} or (process.returncode == 0) == failed:
            raise TddError("Runner exit/report mismatch or infrastructure failure")
        if any(item["status"] == "skipped" for item in results):
            raise TddError("Skipped tests cannot certify this workflow")
        receipt = {"id": run_id, "kind": kind, "utc": datetime.now(timezone.utc).isoformat(), "environment": environment(), "protected": before_protected, "source": before_source, "collected": collected, "results": results, "exit_code": process.returncode}
        atomic_json(runs / (run_id + ".receipt.json"), receipt)
        return receipt

    def require_suite(self, receipt, failing=()):
        actual = {item["id"]: item for item in receipt["results"]}
        if not set(self.state["required_ids"]).issubset(actual):
            raise TddError("Missing previously executed required test IDs")
        if any(item["status"] != "passed" for test_id, item in actual.items() if test_id not in failing):
            raise TddError("Unexpected regression or runner error")
        return actual

    def fresh(self):
        self.fixed()
        receipt = self.state["green_receipt"]
        if receipt["source"] != self.source() or receipt["environment"] != environment():
            raise TddError("Stale GREEN receipt; run green again before continuing")

    def begin(self, allow_empty=False):
        # Setup artifacts may have been completed after object construction.
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
            raise TddError("Baseline must pass and execute tests; bootstrap needs --allow-empty")
        self.state = {"schema": 1, "task_id": uuid.uuid4().hex, "phase": "TEST", "spec_version": spec["version"], "environment": environment(), "baseline_receipt": baseline, "required_ids": baseline["collected"], "source_checkpoint": self.source(), "fixed": self.protected(False), "coverage": {}, "attempts": 0, "cycle": 1, "history": [], "empty_baseline_waiver": bool(not baseline["results"] and allow_empty)}
        return self.save("begin")

    def increment(self, tests, ac, because):
        self.phase("TEST", "AMEND")
        if not because or not tests or len(set(tests)) != len(tests) or not ac:
            raise TddError("Increment needs unique test IDs, acceptance IDs and oracle rationale")
        if self.source() != self.state["source_checkpoint"]:
            raise TddError("Changed source during test authoring")
        amendment = self.state["phase"] == "AMEND"
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
            self.state["phase"] = "BLOCKED" if self.state["attempts"] >= self.config.get("max_attempts", 3) else "IMPLEMENT"
            self.save("green-failed", category=str(error))
            raise
        increment = self.state["increment"]
        self.record_coverage(increment["tests"], increment["ac"])
        self.state.update(phase="GREEN", green_receipt=receipt)
        return self.save("green-confirmed")

    def next(self):
        self.phase("GREEN", "VERIFY")
        self.fresh()
        self.state.update(phase="TEST", source_checkpoint=self.source(), attempts=0, cycle=self.state["cycle"] + 1)
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
        review_hash = digest(self.folder / "review.json")
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


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--root", default=".")
    sub = result.add_subparsers(dest="command", required=True)
    sub.add_parser("init")
    sub.add_parser("status")
    sub.add_parser("doctor")
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
        if len(parts) < 3 or Path(parts[0]).name.lower() not in {"python", "python3", "python.exe", "python3.exe"}:
            return False
        offset = 2 if parts[1] == "-B" else 1
        if Path(parts[offset]).resolve() != (Path(plugin_root) / "scripts/tdd.py").resolve():
            return False
        args = parser().parse_args(parts[offset + 1:])
        path = Path(args.root)
        if not path.is_absolute():
            path = Path(cwd or root) / path
        return args.command != "init" and path.resolve() == root
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
        role = payload.get("agent_type", "").split(":")[-1]
        worker = bool(payload.get("agent_id"))
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
        if path == root / ".ai-tdd/spec.json" and phase == "AMEND" and role in {"", "test-author"}:
            return None
        if role not in {"test-author", "implementer"}:
            return "deny: delegate feature edits to the role that owns the phase"
        protected = [safe_path(root, item) for item in c.config["protected_paths"]]
        if inside(path, c.folder) or any(inside(path, item) for item in protected) or any(part.startswith(".env") or part == ".git" for part in Path(relative).parts):
            return "deny: controller, contracts, runner configuration and private paths are protected"
        roots = c.config["test_roots"] if phase in {"TEST", "AMEND"} else c.config["source_roots"] if phase in {"IMPLEMENT", "GREEN"} else []
        if (phase in {"TEST", "AMEND"} and role == "implementer") or (phase in {"IMPLEMENT", "GREEN"} and role == "test-author"):
            return "deny: role does not own the current phase"
        if not any(inside(path, safe_path(root, item)) for item in roots):
            return "deny: write is outside paths owned by the current phase"
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
    folder = root / ".ai-tdd"
    folder.mkdir(parents=True, exist_ok=True)
    if folder.is_symlink():
        raise TddError("State directory cannot be a symlink")
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


def init(root):
    folder = root / ".ai-tdd"
    folder.mkdir(parents=True, exist_ok=True)
    if folder.is_symlink():
        raise TddError("State directory cannot be a symlink")
    path = folder / "config.json"
    if path.exists():
        raise TddError("Config already exists; will not overwrite it")
    atomic_json(path, read_json(PLUGIN / "templates/config.unittest.json"))
    return {"initialized": str(folder), "next": "Adapt config; write spec.json and independent review-plan.json; then begin"}


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
    try:
        if command == "doctor":
            result = hook_health()
        elif command == "status":
            c = Controller(root)
            result = c.state
            if not result:
                raise TddError("Not started yet")
            if result["phase"] in {"GREEN", "VERIFY", "DONE"}:
                result = {**result, "receipt_current": result["green_receipt"]["source"] == c.source() and result["frozen"] == c.protected() and result["environment"] == environment()}
        else:
            with lock(root):
                if command == "begin":
                    hook_health()
                result = init(root) if command == "init" else getattr(Controller(root), command)(**values)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (TddError, KeyError, TypeError, ValueError) as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
