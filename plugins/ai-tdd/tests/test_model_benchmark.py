"""Independent synthetic contracts and benchmark accounting; no model calls."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

KIT = Path(__file__).resolve().parents[3]


def helper(name):
    sys.path.insert(0, str(KIT / "scripts"))
    try:
        spec = importlib.util.spec_from_file_location(name, KIT / "scripts" / (name + ".py"))
        value = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(value)
        return value
    finally:
        sys.path.pop(0)


class FrozenCaseTests(unittest.TestCase):
    def test_three_correct_contracts_and_twelve_distinct_faults(self):
        cases = helper("model_benchmark_cases")
        self.assertEqual(set(cases.CASES), {"fee", "authorization", "ledger"})
        for name, case in cases.CASES.items():
            with self.subTest(case=name):
                correct = cases.execute_fixture(case, case["correct_source"], case["oracle_tests"])
                self.assertEqual(correct["outcome"], "passed", correct)
                self.assertGreaterEqual(len(case["mutants"]), 4)
                self.assertEqual(len(set(case["mutants"].values())), len(case["mutants"]))
                for mutant, source in case["mutants"].items():
                    with self.subTest(mutant=mutant):
                        result = cases.execute_fixture(case, source, case["oracle_tests"])
                        self.assertEqual(result["outcome"], "assertion_failure", result)
                        self.assertTrue(result["witnesses"])

    def test_initial_regression_is_valid_but_does_not_prove_new_contract(self):
        cases = helper("model_benchmark_cases")
        for name, case in cases.CASES.items():
            with self.subTest(case=name):
                initial = cases.execute_fixture(case, case["initial_source"], case["initial_test"])
                self.assertEqual(initial["outcome"], "passed", initial)
                self.assertEqual(initial["executed_count"], 1)
                complete = cases.execute_fixture(case, case["initial_source"], case["oracle_tests"])
                self.assertEqual(complete["outcome"], "assertion_failure", complete)

    def test_errors_and_skips_never_become_detected_mutants(self):
        cases = helper("model_benchmark_cases")
        case = cases.CASES["fee"]
        tests = "import unittest\nfrom src.fee import fee\nclass Broken(unittest.TestCase):\n    def test_error(self):\n        raise RuntimeError('setup failure')\n"
        error = cases.execute_fixture(case, case["correct_source"], tests)
        self.assertEqual(error["outcome"], "unusable")
        skipped = tests.replace("raise RuntimeError('setup failure')", "self.skipTest('not executed')")
        self.assertEqual(cases.execute_fixture(case, case["correct_source"], skipped)["outcome"], "unusable")
        self.assertEqual(cases.execute_fixture(case, "invalid python !\n", tests)["outcome"], "unusable")

    def test_strength_uses_fresh_source_copies_and_keeps_real_project_bytes(self):
        cases = helper("model_benchmark_cases")
        case = cases.CASES["fee"]
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "src").mkdir()
            (root / "tests").mkdir()
            source = root / case["source_path"]
            source.write_text(case["correct_source"], encoding="utf-8")
            (root / "tests/test_generated.py").write_text(case["oracle_tests"], encoding="utf-8")
            before = source.read_bytes()
            strength = cases.inspect_test_strength(case, root)
            self.assertTrue(strength["available"])
            self.assertEqual((strength["detected"], strength["survived"], strength["unusable"]), (4, 0, 0))
            self.assertEqual(source.read_bytes(), before)
            self.assertFalse((root / "runner-report.json").exists())

    def inspect_incidental_suite(self, candidate, statement):
        cases = helper("model_benchmark_cases")
        case = cases.CASES["fee"]
        tests = case["initial_test"] + "\nimport inspect\n\nclass IncidentalTests(unittest.TestCase):\n    def test_source_identity(self):\n        " + statement + "\n"
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "src").mkdir()
            (root / "tests").mkdir()
            (root / case["source_path"]).write_text(candidate, encoding="utf-8")
            (root / case["test_path"]).write_text(tests, encoding="utf-8")
            self.assertTrue(cases.inspect_behavior(case, root)["passed"])
            result = cases.inspect_test_strength(case, root)
            self.assertEqual((root / case["source_path"]).read_text(encoding="utf-8"), candidate)
            return result

    def test_source_spelling_does_not_get_four_incidental_fault_credits(self):
        candidate = "def fee(cents: int) -> int:\n    if cents >= 10000:\n        return 0\n    return 799\n"
        result = self.inspect_incidental_suite(candidate, 'self.assertIn("if cents >= 10000:", inspect.getsource(fee))')
        self.assertFalse(result["available"], "Source spelling was credited as four behavioral detections")
        self.assertEqual(result["mutants"], [])
        failing_controls = [row for row in result["correct_controls"] if row["generated_tests"]["outcome"] != "passed"]
        self.assertTrue(failing_controls)
        self.assertTrue(all(row["oracle"]["outcome"] == "passed" for row in failing_controls))
        self.assertTrue(failing_controls[0]["generated_tests"]["witnesses"])

    def test_identical_candidate_and_fault_reference_need_distinct_correct_control(self):
        cases = helper("model_benchmark_cases")
        candidate = cases.CASES["fee"]["correct_source"]
        result = self.inspect_incidental_suite(candidate, "self.assertEqual(inspect.getsource(fee), " + repr(candidate) + ")")
        self.assertFalse(result["available"], "An identical reference cannot control implementation identity")
        controls = {row["id"]: row for row in result["correct_controls"]}
        self.assertEqual(controls["fault_reference"]["generated_tests"]["outcome"], "passed")
        self.assertEqual(controls["structural_alternative"]["oracle"]["outcome"], "passed")
        self.assertEqual(controls["structural_alternative"]["generated_tests"]["outcome"], "assertion_failure")
        self.assertEqual(result["mutants"], [])

    def test_correct_alternatives_preserve_behavioral_suites_for_all_three_cases(self):
        cases = helper("model_benchmark_cases")
        for name, case in cases.CASES.items():
            with self.subTest(case=name), tempfile.TemporaryDirectory() as folder:
                self.assertNotEqual(case["correct_controls"]["structural_alternative"], case["correct_source"])
                root = Path(folder)
                (root / "src").mkdir()
                (root / "tests").mkdir()
                (root / case["source_path"]).write_text(case["correct_source"], encoding="utf-8")
                (root / case["test_path"]).write_text(case["oracle_tests"], encoding="utf-8")
                result = cases.inspect_test_strength(case, root)
                self.assertTrue(result["available"], result)
                self.assertEqual((result["detected"], result["survived"], result["unusable"]), (4, 0, 0))
                for control in result["correct_controls"]:
                    self.assertEqual(control["oracle"]["executed_count"], case["oracle_cases"])
                    self.assertEqual(control["generated_tests"]["test_ids"], result["baseline"]["test_ids"])

    def test_capsule_contains_only_synthetic_python_and_does_not_overwrite(self):
        cases = helper("model_benchmark_cases")
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name in ("src", "tests", ".ai-tdd"):
                (root / name).mkdir()
            (root / "src/fee.py").write_text("def fee(cents):\n    return 799\n", encoding="utf-8")
            (root / "tests/test_fee.py").write_text("# synthetic test\n", encoding="utf-8")
            for name in (".env", "CLAUDE.md", "claude-output.jsonl", ".ai-tdd/state.json", "tests/.env"):
                (root / name).write_text("excluded synthetic marker", encoding="utf-8")
            target = root / "capsule.zip"
            result = cases.write_project_artifact(root, target)
            self.assertTrue(result["saved"])
            self.assertEqual(result["file_count"], 2)
            with zipfile.ZipFile(target) as archive:
                self.assertEqual(set(archive.namelist()), {"src/fee.py", "tests/test_fee.py"})
            before = target.read_bytes()
            with self.assertRaises(FileExistsError):
                cases.write_project_artifact(root, target)
            self.assertEqual(target.read_bytes(), before)

    def test_behavior_oracle_allows_valid_source_helper_modules(self):
        cases = helper("model_benchmark_cases")
        case = cases.CASES["fee"]
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "src").mkdir()
            (root / "src/fee.py").write_text("from src.policy import amount\ndef fee(cents: int) -> int:\n    return amount(cents)\n", encoding="utf-8")
            (root / "src/policy.py").write_text("def amount(cents: int) -> int:\n    return 0 if cents >= 10000 else 799\n", encoding="utf-8")
            result = cases.inspect_behavior(case, root)
            self.assertTrue(result["passed"], "A correct source helper was lost by the isolated oracle")


class PairedProtocolTests(unittest.TestCase):
    def test_plan_is_complete_reproducible_and_blocked(self):
        benchmark = helper("benchmark_models")
        plan = benchmark.trial_plan()
        self.assertEqual(plan, benchmark.trial_plan())
        self.assertEqual(len(plan), 18)
        self.assertEqual(len({(row["case"], row["model"], row["repetition"]) for row in plan}), 18)
        for start in range(0, 18, 3):
            block = plan[start:start + 3]
            self.assertEqual(len({(row["case"], row["repetition"]) for row in block}), 1)
            self.assertEqual({row["model"] for row in block}, set(benchmark.MODELS))

    def test_failed_trials_keep_their_cost_and_missing_cost_stays_unknown(self):
        benchmark = helper("benchmark_models")
        model = benchmark.MODELS[0]
        rows = [{"model": model, "summary": {"passed": passed, "usage": {"estimated_cost_usd": cost}}}
                for passed, cost in [(True, 0.4), (False, 1.7), (False, None)]]
        result = benchmark.aggregate(rows)[model]
        self.assertEqual((result["trials"], result["passed"]), (3, 1))
        self.assertAlmostEqual(result["reported_cost_usd_observed"], 2.1)
        self.assertIsNone(result["reported_cost_usd_total"])
        self.assertEqual(result["cost_reports_missing"], 1)

    def test_mixed_profile_is_separate_six_trial_preregistered_plan(self):
        benchmark = helper("benchmark_models")
        plan = benchmark.trial_plan("mixed-haiku")
        self.assertEqual(len(plan), 6)
        self.assertEqual({row["model"] for row in plan}, {"claude-sonnet-5-5"})
        self.assertEqual(len({(row["case"], row["repetition"]) for row in plan}), 6)
        self.assertTrue(all(row["profile"] == "mixed-haiku" for row in plan))
        self.assertFalse({row["trial_id"] for row in plan} & {row["trial_id"] for row in benchmark.trial_plan()})

    def test_mixed_policy_requires_exact_frozen_routing_and_observed_roles(self):
        evaluator = helper("evaluate_claude")
        policy = {"test-author": "inherit", "implementer": "haiku", "verifier": "inherit"}
        value = {
            "requested_model": "claude-sonnet-5-5", "requested_worker_models": policy.copy(),
            "observed_worker_models": policy.copy(),
            "observed_coordinator_models": ["claude-sonnet-5-5"],
            "observed_response_models": ["claude-sonnet-5-5", "claude-haiku-4-5-20251001"],
            "observed_role_models": {"ai-tdd:test-author": ["claude-sonnet-5-5"],
                                     "ai-tdd:implementer": ["claude-haiku-4-5-20251001"],
                                     "ai-tdd:verifier": ["claude-sonnet-5-5"]},
        }
        self.assertTrue(evaluator.model_policy_passed(value))
        import copy
        for path, replacement in [
            (("observed_worker_models", "implementer"), "inherit"),
            (("observed_role_models", "ai-tdd:verifier"), ["claude-haiku-4-5-20251001"]),
            (("observed_coordinator_models",), ["claude-haiku-4-5-20251001"]),
            (("observed_role_models", "ai-tdd:implementer"), []),
        ]:
            candidate = copy.deepcopy(value)
            target = candidate
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = replacement
            self.assertFalse(evaluator.model_policy_passed(candidate), path)

    def test_success_requires_usage_and_all_quality_evidence(self):
        evaluator = helper("evaluate_claude")
        value = {
            "phase": "DONE", "timed_out": False, "exit_code": 0,
            "result": {"is_error": False, "subtype": "success"},
            "independent_behavior_checks": {"passed": True},
            "initial_test_file_preserved": True, "final_evidence_current": True,
            "quality": {"status": "passed", "checks": [
                {"kind": kind, "exit_code": 0, "error": None} for kind in ("lint", "format", "typecheck")
            ], "test_assessment_count": 2, "repository_profile_present": True},
            "agent_types": ["ai-tdd:test-author", "ai-tdd:implementer", "ai-tdd:verifier"],
            "observed_role_models": {role: ["claude-haiku-4-5"] for role in
                                     ("ai-tdd:test-author", "ai-tdd:implementer", "ai-tdd:verifier")},
            "observed_response_models": ["claude-haiku-4-5"],
            "requested_model": "claude-haiku-4-5",
            "usage": {"available": True, "estimated_cost_usd": 0.2},
        }
        self.assertTrue(evaluator.trial_passed(value, require_usage=True, require_same_model=True))
        import copy
        for path, replacement in [
            (("usage", "available"), False), (("usage", "estimated_cost_usd"), None),
            (("usage", "estimated_cost_usd"), float("nan")),
            (("result", "is_error"), True), (("timed_out",), True),
            (("result", "subtype"), "error_max_budget_usd"),
            (("final_evidence_current",), False),
            (("quality", "repository_profile_present"), False),
            (("observed_role_models", "ai-tdd:verifier"), ["claude-opus-5-5"]),
        ]:
            candidate = copy.deepcopy(value)
            target = candidate
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = replacement
            self.assertFalse(evaluator.trial_passed(candidate, require_usage=True, require_same_model=True), path)


if __name__ == "__main__":
    unittest.main()
