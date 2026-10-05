"""Incomplete native runs must retain useful errors without certifying a phase."""
import copy
import json
import unittest

from test_controller import Fixture, tdd


def native_report(complete=True, rows=None):
    rows = rows or [{"id": "tests/Demo.csproj|net8.0|xunit:parent|test:child",
                     "status": "passed", "exception": "", "native_case_id": "parent",
                     "native_test_id": "child", "vstest_id": "parent-guid"}]
    return {"schema": 1, "completion": "complete" if complete else "incomplete",
            "planned_module_count": 1, "collected": [row["id"] for row in rows], "results": rows,
            "native_modules": [{"project": "tests/Demo.csproj", "tfm": "net8.0",
                                "status": "complete" if complete else "error"}],
            "diagnostics": [] if complete else [{"code": "application_control_blocked",
                                                  "module_index": 0, "stage": "execution"}]}


class RunnerDiagnosticTests(Fixture, unittest.TestCase):
    def runner(self, payload=None, exit_code=0, sleep=0, mutate=False):
        script = "from pathlib import Path\nimport sys, time\n"
        if payload is not None:
            script += "Path(sys.argv[1]).write_text(" + repr(json.dumps(payload)) + ", encoding='utf-8')\n"
        if mutate:
            script += "Path('src/fee.py').write_text('def fee(cents): return 1\\n', encoding='utf-8')\n"
        if sleep:
            script += "time.sleep(" + repr(sleep) + ")\n"
        script += "sys.exit(" + repr(exit_code) + ")\n"
        self.write("fixture_runner.py", script)
        self.config["protected_paths"].append("fixture_runner.py")
        self.config["runner"]["argv"] = ["{python}", "-B", "fixture_runner.py", "{report}"]
        self.save(".ai-tdd/config.json", self.config)
        self.c = tdd.Controller(self.root)

    def no_receipt(self):
        self.assertEqual(list((self.root / ".ai-tdd/runs").glob("*.receipt.json")), [])

    def test_incomplete_json_cannot_certify_even_when_every_observed_test_passes(self):
        path = self.root / ".ai-tdd/incomplete.json"
        self.save(path, native_report(False))
        with self.assertRaisesRegex(tdd.TddError, "application_control_blocked"):
            tdd.parse_report(path, "json")

    def test_zero_exit_cannot_override_incomplete_module_diagnostics(self):
        self.runner(native_report(False))
        with self.assertRaisesRegex(tdd.TddError, "application_control_blocked"):
            self.c.run("baseline")
        self.no_receipt()

    def test_completed_label_cannot_hide_missing_planned_modules_or_diagnostics(self):
        missing = native_report()
        missing["planned_module_count"] = 2
        issues = native_report()
        issues["diagnostics"] = [{"code": "native_discovery_error"}]
        for payload in (missing, issues):
            with self.subTest(payload=payload):
                self.runner(payload)
                with self.assertRaisesRegex(tdd.TddError, "Incomplete native"):
                    self.c.run("baseline")
                self.no_receipt()

    def test_infrastructure_exit_reports_typed_cause_and_artifact_path(self):
        self.runner(native_report(False), exit_code=2)
        with self.assertRaisesRegex(tdd.TddError, "application_control_blocked.*ai-tdd/runs"):
            self.c.run("baseline")
        self.no_receipt()

    def test_missing_report_identifies_runner_logs_without_file_not_found_noise(self):
        self.runner(exit_code=2)
        with self.assertRaisesRegex(tdd.TddError, "Runner.*exit.*2.*stderr.log"):
            self.c.run("baseline")
        self.no_receipt()

    def test_timeout_keeps_partial_diagnostics_and_checks_source_mutation(self):
        self.config["timeout_seconds"] = 0.8
        self.runner(native_report(False), sleep=3)
        with self.assertRaisesRegex(tdd.TddError, "timeout.*application_control_blocked"):
            self.c.run("baseline")
        self.no_receipt()
        self.runner(native_report(False), sleep=3, mutate=True)
        with self.assertRaisesRegex(tdd.TddError, "modified source"):
            self.c.run("baseline")
        self.no_receipt()

    def test_complete_existing_runtime_error_is_retained_and_baseline_cannot_start(self):
        payload = native_report()
        payload["results"][0].update(status="error", exception="System.UriFormatException")
        self.runner(payload, exit_code=1)
        with self.assertRaisesRegex(tdd.TddError, "Baseline.*System.UriFormatException.*receipt.json"):
            self.c.begin()
        self.assertFalse((self.root / ".ai-tdd/state.json").exists())
        receipts = list((self.root / ".ai-tdd/runs").glob("*.receipt.json"))
        self.assertEqual(len(receipts), 1)
        self.assertEqual(json.loads(receipts[0].read_text())["results"][0]["status"], "error")

    def test_known_parent_cannot_silently_add_another_runtime_row(self):
        self.runner(native_report())
        self.c.begin()
        receipt = self.c.run("coverage")
        extra = copy.deepcopy(receipt["results"][0])
        extra.update(id=extra["id"].replace("test:child", "test:another"), native_test_id="another")
        receipt["results"].append(extra)
        receipt["collected"].append(extra["id"])
        with self.assertRaisesRegex(tdd.TddError, "runtime.*row.*inventory"):
            self.c.require_suite(receipt)

    def test_new_parent_can_introduce_a_selected_behavioral_red_row(self):
        self.runner(native_report())
        self.c.begin()
        receipt = self.c.run("red")
        extra = copy.deepcopy(receipt["results"][0])
        extra.update(id=extra["id"].replace("xunit:parent", "xunit:new-parent"),
                     native_case_id="new-parent", status="failed", exception="AssertionError")
        receipt["results"].append(extra)
        receipt["collected"].append(extra["id"])
        self.c.require_suite(receipt, [extra["id"]])


if __name__ == "__main__":
    unittest.main()
