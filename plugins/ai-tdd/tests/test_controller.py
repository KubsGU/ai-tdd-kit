"""Behavioral tests use real subprocesses in isolated synthetic projects."""
import importlib.util
import json
from pathlib import Path
import subprocess
import shutil
import sys
import os
from unittest import mock
import tempfile
import unittest

PLUGIN = Path(__file__).resolve().parents[1]
loader = importlib.util.spec_from_file_location("tdd", PLUGIN / "scripts/tdd.py")
tdd = importlib.util.module_from_spec(loader)
loader.loader.exec_module(tdd)


class Fixture:
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ai-tdd-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / ".ai-tdd").mkdir()
        (self.root / "src").mkdir()
        (self.root / "tests").mkdir()
        self.write("src/fee.py", "def fee(cents):\n    return 799\n")
        self.write("tests/test_fee.py", "import unittest\nfrom src.fee import fee\n\nclass FeeTests(unittest.TestCase):\n    def test_regular(self):\n        self.assertEqual(fee(100), 799)\n")
        self.write("requirements.txt", "")
        self.config = {
            "schema": 1, "source_roots": ["src"], "test_roots": ["tests"],
            "protected_paths": ["requirements.txt"], "timeout_seconds": 10,
            "max_attempts": 3,
            "runner": {"format": "json", "argv": ["{python}", "-B", "{plugin}/scripts/unittest_runner.py", "--start-dir", "tests", "--report", "{report}"]}
        }
        self.save(".ai-tdd/config.json", self.config)
        self.spec = {"version": 1, "goal": "Free delivery at 10000 cents", "acceptance": [{"id": "AC1", "description": "fee is zero at 10000 cents"}], "open_questions": []}
        self.save(".ai-tdd/spec.json", self.spec)
        self.save(".ai-tdd/review-plan.json", {"scenarios": [{"ac": "AC1", "case": "9999, 10000, 10001 cents"}]})
        self.c = tdd.Controller(self.root)

    def write(self, path, content):
        (self.root / path).write_text(content, encoding="utf-8")

    def save(self, path, value):
        self.write(path, json.dumps(value))

    def state(self):
        return json.loads((self.root / ".ai-tdd/state.json").read_text(encoding="utf-8"))

    def new_test(self, assertion="self.assertEqual(fee(10000), 0)"):
        with (self.root / "tests/test_fee.py").open("a", encoding="utf-8") as stream:
            stream.write("\n    def test_threshold(self):\n        " + assertion + "\n")

    def ready_red(self):
        self.c.begin()
        self.new_test()
        self.c.red(tests=["test_fee.FeeTests.test_threshold"], ac=["AC1"], expect="AssertionError", because="AC1 literal expected zero")

    def ready_green(self):
        self.ready_red()
        self.write("src/fee.py", "def fee(cents):\n    return 0 if cents >= 10000 else 799\n")
        self.c.green()

    def review(self, **extra):
        value = {"receipt_id": self.state()["green_receipt"]["id"], "checked_ac": ["AC1"], "findings": [], "limitations": [], "recommendation": "accept"}
        value.update(extra)
        self.save(".ai-tdd/review.json", value)


class ControllerTests(Fixture, unittest.TestCase):
    def test_real_red_green_review_completion(self):
        self.ready_green()
        self.assertEqual(self.state()["phase"], "GREEN")
        self.c.verify()
        self.review()
        result = self.c.finish()
        self.assertEqual(result["phase"], "DONE")
        self.assertEqual(len(result["completion_receipt"]["results"]), 2)

    def test_green_without_red_is_rejected(self):
        self.c.begin()
        with self.assertRaises(tdd.TddError):
            self.c.green()

    def test_source_write_during_test_authoring_invalidates_red(self):
        self.c.begin()
        self.new_test()
        self.write("src/fee.py", "def fee(cents):\n    return 123\n")
        with self.assertRaisesRegex(tdd.TddError, "source"):
            self.c.red(tests=["test_fee.FeeTests.test_threshold"], ac=["AC1"], expect="AssertionError", because="AC1")

    def test_import_error_does_not_count_as_red(self):
        self.c.begin()
        self.new_test("import nonexistent_module")
        with self.assertRaises(tdd.TddError):
            self.c.red(tests=["test_fee.FeeTests.test_threshold"], ac=["AC1"], expect="AssertionError", because="AC1")

    def test_red_cannot_expect_infrastructure_exception(self):
        self.c.begin()
        self.new_test("import nonexistent_module")
        with self.assertRaises(tdd.TddError):
            self.c.red(tests=["test_fee.FeeTests.test_threshold"], ac=["AC1"], expect="ModuleNotFoundError", because="AC1")

    def test_frozen_test_edit_is_detected(self):
        self.ready_red()
        self.write("tests/test_fee.py", "# deleted assertions\n")
        with self.assertRaisesRegex(tdd.TddError, "protected"):
            self.c.green()

    def test_frozen_dependency_edit_is_detected(self):
        self.ready_red()
        self.write("src/fee.py", "def fee(cents): return 0 if cents >= 10000 else 799\n")
        self.write("requirements.txt", "changed\n")
        with self.assertRaisesRegex(tdd.TddError, "protected"):
            self.c.green()

    def test_new_dependency_file_is_detected_when_initially_absent(self):
        self.config["protected_paths"].append("pyproject.toml")
        self.save(".ai-tdd/config.json", self.config)
        self.ready_red()
        self.write("src/fee.py", "def fee(cents): return 0 if cents >= 10000 else 799\n")
        self.write("pyproject.toml", "[tool.pytest.ini_options]\n")
        with self.assertRaisesRegex(tdd.TddError, "protected"):
            self.c.green()

    def test_zero_tests_cannot_begin_without_explicit_bootstrap(self):
        self.write("tests/test_fee.py", "")
        with self.assertRaises(tdd.TddError):
            self.c.begin()
        result = self.c.begin(allow_empty=True)
        self.assertEqual(result["phase"], "TEST")
        self.assertTrue(result["empty_baseline_waiver"])

    def test_zero_tests_cannot_become_green(self):
        self.ready_red()
        self.write("src/fee.py", "import unittest\nunittest.TestLoader.getTestCaseNames = lambda *a: []\ndef fee(cents): return 0\n")
        with self.assertRaises(tdd.TddError):
            self.c.green()

    def test_missing_previously_executed_id_is_rejected(self):
        self.ready_red()
        self.write("src/fee.py", "import unittest\nold = unittest.TestLoader.getTestCaseNames\nunittest.TestLoader.getTestCaseNames = lambda s, c: [n for n in old(s, c) if n != 'test_regular']\ndef fee(cents): return 0\n")
        with self.assertRaises(tdd.TddError):
            self.c.green()

    def test_self_modifying_test_is_detected_during_runner(self):
        self.c.begin()
        self.new_test("from pathlib import Path; Path(__file__).write_text('# modified'); self.assertEqual(fee(10000), 0)")
        with self.assertRaises(tdd.TddError):
            self.c.red(tests=["test_fee.FeeTests.test_threshold"], ac=["AC1"], expect="AssertionError", because="AC1")

    def test_skipped_new_test_is_not_red(self):
        self.c.begin()
        self.new_test("self.skipTest('deadline')")
        with self.assertRaises(tdd.TddError):
            self.c.red(tests=["test_fee.FeeTests.test_threshold"], ac=["AC1"], expect="AssertionError", because="AC1")

    def test_repair_budget_is_bounded(self):
        self.ready_red()
        for _ in range(3):
            with self.assertRaises(tdd.TddError):
                self.c.green()
        self.assertEqual(self.state()["phase"], "BLOCKED")
        self.write("src/fee.py", "def fee(cents): return 0 if cents >= 10000 else 799\n")
        with self.assertRaises(tdd.TddError):
            self.c.green()

    def test_completion_requires_all_acceptance_criteria(self):
        self.spec["acceptance"].append({"id": "AC2", "description": "negative input raises ValueError"})
        self.save(".ai-tdd/spec.json", self.spec)
        self.save(".ai-tdd/review-plan.json", {"scenarios": [{"ac": "AC1", "case": "threshold"}, {"ac": "AC2", "case": "negative"}]})
        self.ready_green()
        with self.assertRaises(tdd.TddError):
            self.c.verify()

    def test_completion_requires_review(self):
        self.ready_green()
        self.c.verify()
        with self.assertRaises(tdd.TddError):
            self.c.finish()

    def test_unresolved_finding_blocks_completion(self):
        self.ready_green()
        self.c.verify()
        self.review(findings=[{"id": "R1", "ac": "AC1", "case": "10001", "expected": 0, "actual": 799}])
        with self.assertRaises(tdd.TddError):
            self.c.finish()

    def test_stale_review_receipt_blocks_completion(self):
        self.ready_green()
        self.c.verify()
        self.review(receipt_id="old")
        with self.assertRaises(tdd.TddError):
            self.c.finish()

    def test_source_changed_after_green_requires_rerun(self):
        self.ready_green()
        self.write("src/fee.py", "def fee(cents): return 799\n")
        with self.assertRaises(tdd.TddError):
            self.c.verify()

    def test_already_green_test_is_recorded_without_fake_red(self):
        self.c.begin()
        self.new_test("self.assertEqual(fee(9999), 799)")
        result = self.c.cover(tests=["test_fee.FeeTests.test_threshold"], ac=["AC1"], because="Existing behavior protection")
        self.assertEqual(result["phase"], "GREEN")
        self.assertEqual(result["green_receipt"]["kind"], "coverage")

    def test_next_cycle_and_resume_keep_previous_ids(self):
        self.ready_green()
        self.c = tdd.Controller(self.root)
        self.c.next()
        self.assertEqual(self.state()["phase"], "TEST")
        self.assertEqual(len(self.state()["required_ids"]), 2)

    def test_amend_requires_reason_and_versioned_contract(self):
        self.ready_green()
        with self.assertRaises(tdd.TddError):
            self.c.amend(reason="", ac=["AC1"])
        result = self.c.amend(reason="Independent example proves incorrect test", ac=["AC1"])
        self.assertEqual(result["phase"], "AMEND")
        with self.assertRaises(tdd.TddError):
            self.c.cover(tests=["test_fee.FeeTests.test_threshold"], ac=["AC1"], because="correction")

    def test_real_contract_correction_gets_new_red_for_existing_id(self):
        self.c.begin()
        self.new_test("self.assertEqual(fee(9999), 0)")
        target = "test_fee.FeeTests.test_threshold"
        self.c.red(tests=[target], ac=["AC1"], expect="AssertionError", because="Initially incorrect boundary example")
        self.write("src/fee.py", "def fee(cents): return 0 if cents >= 9999 else 799\n")
        self.c.green()
        self.c.amend(reason="Independent contract example requires 799 below 10000", ac=["AC1"])
        self.spec["version"] = 2
        self.spec["acceptance"][0]["examples"] = [{"input": 9999, "expected": 799}]
        self.save(".ai-tdd/spec.json", self.spec)
        path = self.root / "tests/test_fee.py"
        path.write_text(path.read_text().replace("fee(9999), 0", "fee(9999), 799"))
        self.c.red(tests=[target], ac=["AC1"], expect="AssertionError", because="Correct independent lower-boundary example")
        self.assertEqual(self.state()["spec_version"], 2)
        self.assertNotIn("AC1", self.state()["coverage"])
        self.write("src/fee.py", "def fee(cents): return 0 if cents >= 10000 else 799\n")
        self.c.green()
        self.assertEqual(len(self.state()["required_ids"]), 2)

    def test_fixture_setup_error_is_not_empty_baseline(self):
        self.write("tests/test_fee.py", "import unittest\nclass Broken(unittest.TestCase):\n    @classmethod\n    def setUpClass(cls): raise ValueError('setup')\n    def test_behavior(self): pass\n")
        with self.assertRaises(tdd.TddError):
            self.c.begin(allow_empty=True)

    def test_open_behavior_questions_prevent_begin(self):
        self.spec["open_questions"] = ["Do members pay?"]
        self.save(".ai-tdd/spec.json", self.spec)
        with self.assertRaises(tdd.TddError):
            self.c.begin()

    def test_path_traversal_configuration_rejected(self):
        self.config["source_roots"] = ["../outside"]
        self.save(".ai-tdd/config.json", self.config)
        with self.assertRaises(tdd.TddError):
            self.c.begin()

    def test_overlapping_source_test_roots_rejected(self):
        self.config["source_roots"] = ["tests"]
        self.save(".ai-tdd/config.json", self.config)
        with self.assertRaises(tdd.TddError):
            self.c.begin()

    def test_runner_timeout_is_not_red(self):
        self.config["timeout_seconds"] = 1
        self.config["runner"]["argv"] = ["{python}", "-c", "import time; time.sleep(3)", "{report}"]
        self.save(".ai-tdd/config.json", self.config)
        with self.assertRaises(tdd.TddError):
            self.c.begin()

    def test_reconfigure_preserves_required_inventory(self):
        self.ready_green()
        self.c.reconfigure(reason="Repair runner discovery", paths=[])
        self.config["runner"]["argv"][self.config["runner"]["argv"].index("--report"):self.config["runner"]["argv"].index("--report")] = ["--pattern", "absent*.py"]
        self.save(".ai-tdd/config.json", self.config)
        with self.assertRaisesRegex(tdd.TddError, "required"):
            self.c.rebase()
        self.config["runner"]["argv"].remove("--pattern")
        self.config["runner"]["argv"].remove("absent*.py")
        self.save(".ai-tdd/config.json", self.config)
        result = self.c.rebase()
        self.assertEqual(result["phase"], "GREEN")
        self.assertEqual(len(result["required_ids"]), 2)

    def test_reconfigure_dependency_requires_new_red_evidence(self):
        self.ready_red()
        old_receipt = self.state()["red_receipt"]["id"]
        self.c.reconfigure(reason="Dependency preparation", paths=["requirements.txt"])
        self.write("requirements.txt", "# dependency setup revised\n")
        result = self.c.rebase()
        self.assertEqual(result["phase"], "IMPLEMENT")
        self.assertNotEqual(result["red_receipt"]["id"], old_receipt)
        self.write("src/fee.py", "def fee(cents): return 0 if cents >= 10000 else 799\n")
        self.c.green()

    def test_reconfigure_cannot_change_feature_source(self):
        self.ready_green()
        self.c.reconfigure(reason="Repair discovery", paths=[])
        self.write("src/fee.py", "def fee(cents): return 42\n")
        with self.assertRaisesRegex(tdd.TddError, "source"):
            self.c.rebase()

    def test_reconfigure_cannot_widen_ownership(self):
        self.ready_green()
        self.c.reconfigure(reason="Repair discovery", paths=[])
        self.config["source_roots"].append("other")
        self.save(".ai-tdd/config.json", self.config)
        with self.assertRaisesRegex(tdd.TddError, "ownership"):
            self.c.rebase()

    def test_reconfigure_and_rebase_through_real_cli(self):
        self.ready_green()
        prefix = [sys.executable, "-B", str(PLUGIN / "scripts/tdd.py"), "--root", str(self.root)]
        result = subprocess.run(prefix + ["reconfigure", "--reason", "Repair discovery"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.state()["phase"], "RECONFIGURE")
        result = subprocess.run(prefix + ["rebase"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.state()["phase"], "GREEN")

    def test_archive_preserves_done_evidence_and_feature_files(self):
        self.ready_green()
        self.c.verify()
        self.review()
        self.c.finish()
        source = (self.root / "src/fee.py").read_bytes()
        tests = (self.root / "tests/test_fee.py").read_bytes()
        result = subprocess.run([sys.executable, "-B", str(PLUGIN / "scripts/tdd.py"), "--root", str(self.root), "archive"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        archive = Path(json.loads(result.stdout)["archive"])
        self.assertEqual(json.loads((archive / "state.json").read_text())["phase"], "DONE")
        self.assertFalse((archive / "controller.lock").exists())
        self.assertFalse((self.root / ".ai-tdd").exists())
        self.assertEqual((self.root / "src/fee.py").read_bytes(), source)
        self.assertEqual((self.root / "tests/test_fee.py").read_bytes(), tests)

    def test_active_task_cannot_be_archived(self):
        self.ready_red()
        with self.assertRaises(tdd.TddError):
            self.c.archive()

    def test_begin_cli_rejects_broken_hook_before_baseline(self):
        env = os.environ.copy()
        env["AI_TDD_PYTHON"] = str(self.root / "nonexistent-python")
        result = subprocess.run([sys.executable, "-B", str(PLUGIN / "scripts/tdd.py"), "--root", str(self.root), "begin"], env=env, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / ".ai-tdd/state.json").exists())
        self.assertIn("hook", result.stderr.lower())

    @unittest.skipUnless(importlib.util.find_spec("pytest"), "optional pytest integration")
    def test_real_pytest_json_red_green(self):
        self.config["runner"] = json.loads((PLUGIN / "templates/config.pytest.json").read_text())["runner"]
        self.save(".ai-tdd/config.json", self.config)
        baseline = self.c.begin()
        target = baseline["required_ids"][0].replace("test_regular", "test_threshold")
        self.new_test()
        self.c.red(tests=[target], ac=["AC1"], expect="AssertionError", because="Independent expected threshold")
        self.write("src/fee.py", "def fee(cents): return 0 if cents >= 10000 else 799\n")
        self.assertEqual(self.c.green()["phase"], "GREEN")


@unittest.skipUnless(importlib.util.find_spec("pytest"), "optional pytest integration")
class PytestEvidenceTests(Fixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.config["runner"] = json.loads((PLUGIN / "templates/config.pytest.json").read_text())["runner"]
        self.save(".ai-tdd/config.json", self.config)
        self.c = tdd.Controller(self.root)

    def test_missing_module_in_test_body_cannot_certify_red(self):
        baseline = self.c.begin()
        target = baseline["required_ids"][0].replace("test_regular", "test_threshold")
        self.new_test("import ai_tdd_missing_module_73ef")
        with self.assertRaisesRegex(tdd.TddError, "exception differs"):
            self.c.red(tests=[target], ac=["AC1"], expect="AssertionError", because="AC1 should fail on its assertion")
        self.assertEqual(self.state()["phase"], "TEST")

    def test_parameterized_ids_are_actual_pytest_node_ids(self):
        self.write("tests/test_fee.py", "import pytest\n@pytest.mark.parametrize('n', [1, 2])\ndef test_parameter(n):\n    assert n > 0\n")
        self.assertEqual(set(self.c.begin()["required_ids"]), {"tests/test_fee.py::test_parameter[1]", "tests/test_fee.py::test_parameter[2]"})

    def test_teardown_failure_cannot_be_hidden_by_passing_body(self):
        self.write("tests/test_fee.py", "import pytest\n@pytest.fixture\ndef resource():\n    yield\n    raise RuntimeError('broken teardown')\ndef test_resource(resource):\n    assert True\n")
        with self.assertRaises(tdd.TddError):
            self.c.begin()
        self.assertFalse(self.c.state_path.exists())

    def test_deselected_tests_cannot_certify_baseline(self):
        self.new_test("self.assertEqual(fee(1), 799)")
        self.config["runner"]["argv"].extend(["-k", "regular"])
        self.save(".ai-tdd/config.json", self.config)
        self.c = tdd.Controller(self.root)
        with self.assertRaisesRegex(tdd.TddError, "Skipped"):
            self.c.begin()

    def test_xpass_cannot_certify_baseline(self):
        self.write("tests/test_fee.py", "import pytest\n@pytest.mark.xfail(reason='known issue', strict=False)\ndef test_xpass():\n    assert True\n")
        with self.assertRaisesRegex(tdd.TddError, "Skipped"):
            self.c.begin()


class GuardTests(Fixture, unittest.TestCase):
    def payload(self, tool, inputs, agent=None):
        value = {"cwd": str(self.root), "tool_name": tool, "tool_input": inputs, "hook_event_name": "PreToolUse"}
        if agent:
            value["agent_id"] = "worker-1"
            value["agent_type"] = "ai-tdd:" + agent
        return value

    def test_inactive_project_is_untouched(self):
        self.assertIsNone(tdd.guard(self.payload("Bash", {"command": "echo hello"}), PLUGIN))

    def test_test_author_cannot_edit_source(self):
        self.c.begin()
        self.assertIn("deny", tdd.guard(self.payload("Edit", {"file_path": str(self.root / "src/fee.py")}, "test-author"), PLUGIN))

    def test_test_author_can_write_tests(self):
        self.c.begin()
        self.assertIsNone(tdd.guard(self.payload("Write", {"file_path": str(self.root / "tests/new.py")}, "test-author"), PLUGIN))

    def test_implementer_can_write_only_source(self):
        self.ready_red()
        self.assertIsNone(tdd.guard(self.payload("Edit", {"file_path": str(self.root / "src/fee.py")}, "implementer"), PLUGIN))
        self.assertIn("deny", tdd.guard(self.payload("Edit", {"file_path": str(self.root / "tests/test_fee.py")}, "implementer"), PLUGIN))

    def test_verifier_never_writes(self):
        self.ready_red()
        self.assertIn("deny", tdd.guard(self.payload("Write", {"file_path": str(self.root / "src/fee.py")}, "verifier"), PLUGIN))

    def test_worker_cannot_execute_shell(self):
        self.ready_red()
        self.assertIn("deny", tdd.guard(self.payload("Bash", {"command": "echo 0 > tests/test_fee.py"}, "implementer"), PLUGIN))

    def test_coordinator_shell_only_allows_exact_controller(self):
        self.ready_red()
        command = f'python -B "{(PLUGIN / "scripts/tdd.py").as_posix()}" --root "{self.root.as_posix()}" green'
        self.assertIsNone(tdd.guard(self.payload("Bash", {"command": command}), PLUGIN))
        self.assertIn("deny", tdd.guard(self.payload("Bash", {"command": command + " && echo hacked"}), PLUGIN))

    def test_controller_for_other_root_is_denied(self):
        self.ready_red()
        command = f'python -B "{(PLUGIN / "scripts/tdd.py").as_posix()}" --root "../other" green'
        self.assertIn("deny", tdd.guard(self.payload("Bash", {"command": command}), PLUGIN))

    def test_control_state_cannot_be_written_directly(self):
        self.ready_red()
        self.assertIn("deny", tdd.guard(self.payload("Write", {"file_path": str(self.root / ".ai-tdd/state.json")}), PLUGIN))

    def test_parent_traversal_write_is_denied(self):
        self.ready_red()
        self.assertIn("deny", tdd.guard(self.payload("Edit", {"file_path": "src/../../other.py"}), PLUGIN))

    def test_unknown_mutation_tool_is_denied(self):
        self.ready_red()
        self.assertIn("deny", tdd.guard(self.payload("mcp__unknown__execute", {"code": "..."}), PLUGIN))

    def test_reconfigure_only_coordinator_can_edit_declared_setup(self):
        self.ready_green()
        self.c.reconfigure(reason="Dependency preparation", paths=["requirements.txt"])
        self.assertIsNone(tdd.guard(self.payload("Edit", {"file_path": str(self.root / "requirements.txt")}), PLUGIN))
        self.assertIsNone(tdd.guard(self.payload("Edit", {"file_path": str(self.root / ".ai-tdd/config.json")}), PLUGIN))
        self.assertIn("deny", tdd.guard(self.payload("Edit", {"file_path": str(self.root / "requirements.txt")}, "implementer"), PLUGIN))
        self.assertIn("deny", tdd.guard(self.payload("Edit", {"file_path": str(self.root / "src/fee.py")}), PLUGIN))

    def test_real_node_hook_blocks_test_edit_by_implementer(self):
        self.ready_red()
        node = shutil.which("node")
        self.assertIsNotNone(node, "Node 18+ is a documented plugin dependency")
        payload = self.payload("Write", {"file_path": str(self.root / "tests/test_fee.py")}, "implementer")
        result = subprocess.run([node, "--preserve-symlinks-main", str(PLUGIN / "scripts/hook-launcher.cjs")], input=json.dumps(payload), capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"], "deny")


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ai-tdd-report-")
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "report"

    def test_duplicate_ids_rejected(self):
        self.path.write_text(json.dumps({"schema": 1, "collected": ["x", "x"], "results": [{"id": "x", "status": "passed"}, {"id": "x", "status": "passed"}]}))
        with self.assertRaises(tdd.TddError):
            tdd.parse_report(self.path, "json")

    def test_collected_but_unexecuted_test_rejected(self):
        self.path.write_text(json.dumps({"schema": 1, "collected": ["x"], "results": []}))
        with self.assertRaises(tdd.TddError):
            tdd.parse_report(self.path, "json")

    def test_junit_declared_count_mismatch_rejected(self):
        self.path.write_text('<testsuite tests="2"><testcase classname="C" name="x"/></testsuite>')
        with self.assertRaises(tdd.TddError):
            tdd.parse_report(self.path, "junit")

    def test_junit_dtd_rejected(self):
        self.path.write_text('<!DOCTYPE testsuite [<!ENTITY xx "unsafe">]><testsuite tests="0"/>')
        with self.assertRaises(tdd.TddError):
            tdd.parse_report(self.path, "junit")

    def test_doctor_checks_actual_hook_response(self):
        self.assertEqual(tdd.hook_health()["hook_health"], "pass")

    def test_doctor_rejects_missing_node(self):
        with mock.patch("shutil.which", return_value=None):
            with self.assertRaises(tdd.TddError):
                tdd.hook_health()


class JunitConsistencyTests(unittest.TestCase):
    setUp = ReportTests.setUp

    def test_declared_failure_cannot_become_a_passed_case(self):
        self.path.write_text('<testsuite tests="1" failures="1"><testcase name="x"/></testsuite>')
        with self.assertRaises(tdd.TddError):
            tdd.parse_report(self.path, "junit")

    def test_missing_exception_type_is_not_an_assertion(self):
        self.path.write_text('<testsuite tests="1"><testcase name="x"><failure message="ModuleNotFoundError"/></testcase></testsuite>')
        _, results = tdd.parse_report(self.path, "junit")
        self.assertEqual(results[0]["exception"], "UnknownFailure")

    def test_declared_error_cannot_become_a_passed_case(self):
        self.path.write_text('<testsuite tests="1" errors="1"><testcase name="x"/></testsuite>')
        with self.assertRaises(tdd.TddError):
            tdd.parse_report(self.path, "junit")

    def test_testsuites_root_inventory_must_match(self):
        self.path.write_text('<testsuites tests="2"><testsuite tests="1"><testcase name="x"/></testsuite></testsuites>')
        with self.assertRaises(tdd.TddError):
            tdd.parse_report(self.path, "junit")

    def test_aggregate_skips_cannot_be_hidden(self):
        self.path.write_text('<testsuites skipped="1"><testsuite><testcase name="x"/></testsuite></testsuites>')
        with self.assertRaises(tdd.TddError):
            tdd.parse_report(self.path, "junit")

    def test_inconsistent_case_outcomes_are_rejected(self):
        self.path.write_text('<testsuite><testcase name="x"><skipped/><failure/></testcase></testsuite>')
        with self.assertRaises(tdd.TddError):
            tdd.parse_report(self.path, "junit")

    def test_invalid_counts_raise_controlled_report_error(self):
        for count in ('-1', 'many', '1.5'):
            with self.subTest(count=count):
                self.path.write_text('<testsuite tests="' + count + '"><testcase name="x"/></testsuite>')
                with self.assertRaises(Exception) as caught:
                    tdd.parse_report(self.path, "junit")
                self.assertIsInstance(caught.exception, tdd.TddError)

    def test_nested_aggregate_reports_preserve_real_outcomes(self):
        self.path.write_text('<testsuites tests="2" failures="1" errors="0" skipped="0"><testsuite tests="2" failures="1"><testsuite tests="1"><testcase name="a"/></testsuite><testcase name="b"><failure type="AssertionError"/></testcase></testsuite></testsuites>')
        collected, results = tdd.parse_report(self.path, "junit")
        self.assertEqual(collected, ['a', 'b'])
        self.assertEqual([item['status'] for item in results], ['passed', 'failed'])


class DispatchBoundaryTests(Fixture, unittest.TestCase):
    def dispatch(self, role, **extra):
        return {"cwd": str(self.root), "tool_name": "Agent", "tool_input": {"subagent_type": role, "prompt": "One behavior increment", **extra}}

    def test_arbitrary_agent_cannot_inherit_managed_work(self):
        self.c.begin()
        self.assertIsNotNone(tdd.guard(self.dispatch('general-purpose')))

    def test_implementer_cannot_start_before_red(self):
        self.c.begin()
        self.assertIsNotNone(tdd.guard(self.dispatch('ai-tdd:implementer')))

    def test_workers_cannot_delegate_to_another_agent(self):
        self.c.begin()
        payload = self.dispatch('ai-tdd:verifier')
        payload.update(agent_id='author-1', agent_type='ai-tdd:test-author')
        self.assertIsNotNone(tdd.guard(payload))

    def test_resumed_or_explicit_background_workers_are_rejected(self):
        self.c.begin()
        for extra in ({'resume': 'previous-agent'}, {'run_in_background': True}, {'isolation': 'worktree'}):
            with self.subTest(extra=extra):
                self.assertIsNotNone(tdd.guard(self.dispatch('ai-tdd:test-author', **extra)))

    def test_agent_dispatch_waits_for_active_controller(self):
        self.c.begin()
        with tdd.lock(self.root):
            self.assertIsNotNone(tdd.guard(self.dispatch('ai-tdd:test-author')))

    def test_fresh_phase_owner_and_readonly_verifier_are_allowed(self):
        self.c.begin()
        self.assertIsNone(tdd.guard(self.dispatch('ai-tdd:test-author')))
        self.assertIsNone(tdd.guard(self.dispatch('ai-tdd:verifier')))
        self.new_test()
        self.c.red(tests=['test_fee.FeeTests.test_threshold'], ac=['AC1'], expect='AssertionError', because='AC1')
        self.assertIsNone(tdd.guard(self.dispatch('ai-tdd:implementer')))
        self.assertIsNotNone(tdd.guard(self.dispatch('ai-tdd:test-author')))

    def test_foreign_plugin_cannot_borrow_implementer_identity(self):
        self.ready_red()
        payload = {"cwd": str(self.root), "tool_name": "Edit", "tool_input": {"file_path": str(self.root/'src/fee.py')}, "agent_id": "foreign-1", "agent_type": "other-plugin:implementer"}
        self.assertIsNotNone(tdd.guard(payload))


class CompletionIntegrityTests(Fixture, unittest.TestCase):
    def status(self):
        p = subprocess.run([sys.executable, '-B', str(PLUGIN/'scripts/tdd.py'), '--root', str(self.root), 'status'], capture_output=True, encoding='utf-8')
        self.assertEqual(p.returncode, 0, p.stderr)
        return json.loads(p.stdout)

    def test_done_review_edit_invalidates_completion_freshness(self):
        self.ready_green()
        self.c.verify()
        self.review()
        self.c.finish()
        self.assertTrue(self.status()['receipt_current'])
        self.review(findings=[{'id': 'F1', 'impact': 'Unresolved wrong behavior'}])
        before = (self.root/'.ai-tdd/state.json').read_bytes()
        self.assertFalse(self.status()['receipt_current'])
        self.assertEqual((self.root/'.ai-tdd/state.json').read_bytes(), before)

    def test_missing_done_review_invalidates_completion_freshness(self):
        self.ready_green()
        self.c.verify()
        self.review()
        self.c.finish()
        (self.root/'.ai-tdd/review.json').unlink()
        self.assertFalse(self.status()['receipt_current'])


class TaskBudgetTests(Fixture, unittest.TestCase):
    def start_with_limit(self, limit):
        self.config['max_runner_runs'] = limit
        self.save('.ai-tdd/config.json', self.config)
        self.c = tdd.Controller(self.root)
        self.ready_red()

    def test_task_budget_survives_retry_and_prevents_another_execution(self):
        self.start_with_limit(3)
        with self.assertRaises(tdd.TddError):
            self.c.green()
        self.assertEqual(self.state()['phase'], 'BLOCKED')
        before = set((self.root/'.ai-tdd/runs').iterdir())
        with self.assertRaises(tdd.TddError):
            self.c.retry(reason='A different diagnosis cannot extend the task budget')
        with self.assertRaises(tdd.TddError):
            self.c.green()
        self.assertEqual(set((self.root/'.ai-tdd/runs').iterdir()), before)
        self.assertEqual(self.state()['runner_runs'], 3)

    def test_reconfiguration_cannot_increase_the_frozen_task_budget(self):
        self.start_with_limit(2)
        self.c.reconfigure(reason='Repair test runner configuration', paths=[])
        self.config['max_runner_runs'] = 500
        self.save('.ai-tdd/config.json', self.config)
        with self.assertRaises(tdd.TddError):
            self.c.rebase()
        self.assertEqual(self.state()['runner_runs'], 2)
        self.assertEqual(self.state()['runner_run_limit'], 2)

    def test_budget_includes_the_final_completion_check(self):
        self.start_with_limit(3)
        self.write('src/fee.py', 'def fee(cents): return 0 if cents >= 10000 else 799\n')
        self.c.green()
        self.c.verify()
        self.review()
        with self.assertRaises(tdd.TddError):
            self.c.finish()
        self.assertNotEqual(self.state()['phase'], 'DONE')

    def test_invalid_budget_cannot_create_a_task(self):
        for value in (0, -1, True, '100', 10001):
            with self.subTest(value=value):
                self.config['max_runner_runs'] = value
                self.save('.ai-tdd/config.json', self.config)
                with self.assertRaises(tdd.TddError):
                    tdd.Controller(self.root)


class ForegroundRuntimeTests(unittest.TestCase):
    def test_claude_without_serial_setting_is_rejected_before_task_work(self):
        with mock.patch.dict(os.environ, {'CLAUDECODE': '1', 'CLAUDE_CODE_DISABLE_BACKGROUND_TASKS': '0'}):
            with self.assertRaises(tdd.TddError):
                tdd.hook_health()

    def test_explicit_foreground_setting_passes_the_real_hook_health_check(self):
        with mock.patch.dict(os.environ, {'CLAUDECODE': '1', 'CLAUDE_CODE_DISABLE_BACKGROUND_TASKS': '1'}):
            self.assertEqual(tdd.hook_health()['hook_health'], 'pass')
