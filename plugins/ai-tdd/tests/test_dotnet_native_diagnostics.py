"""Partial native execution is useful diagnostics and never success evidence."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import unittest
from unittest import mock

import test_dotnet_runner as fixtures


class NativeDiagnosticsTests(unittest.TestCase):
    setUp = fixtures.DotnetSetupTests.setUp
    metadata = fixtures.DotnetSetupTests.metadata
    configure = fixtures.DotnetSetupTests.configure

    def prepare(self):
        loader = importlib.util.spec_from_file_location("diagnostic_runner", fixtures.SCRIPTS / "dotnet_runner.py")
        self.runner = importlib.util.module_from_spec(loader)
        loader.loader.exec_module(self.runner)
        self.config = self.configure()
        self.config["dotnet"]["theory_mode"] = "runtime-parent-rows-v1"
        original = self.config["dotnet"]["modules"][0]
        self.config["dotnet"]["modules"] = [{**copy.deepcopy(original), "tfm": "net" + str(index + 8) + ".0"} for index in range(3)]
        folder = self.root / ".ai-tdd"
        folder.mkdir()
        (folder / "config.json").write_text(json.dumps(self.config), encoding="utf-8")
        self.report_path = folder / "fresh.json"
        self.calls = []

    def process(self, argv, root, stdout, stderr, timeout):
        self.calls.append(argv)
        stdout.write_text("synthetic", encoding="utf-8")
        stderr.write_text("", encoding="utf-8")
        if "--list-tests" in argv:
            self.assertTrue(self.report_path.is_file(), "Progress report must exist before first native process")
            Path(argv[argv.index("--diag") + 1]).write_text("synthetic", encoding="utf-8")
        else:
            (stdout.parent / "result.trx").write_text("synthetic", encoding="utf-8")
        return 0, "synthetic"

    def run_native(self, process=None, evidence=None):
        source = self.root / "tests/Demo.Tests/bin/Debug/net8.0/Demo.Tests.dll"
        with mock.patch.object(self.runner.SETUP, "configure", return_value=self.config), mock.patch.object(
                self.runner, "_process", side_effect=process or self.process), mock.patch.object(
                self.runner, "discovery_cases", return_value={"case": {"source": str(source)}}), mock.patch.object(
                self.runner, "reconcile", side_effect=evidence or [{"schema": 1, "collected": [str(index)],
                                                                  "results": [{"id": str(index), "status": "passed"}]} for index in range(3)]):
            return self.runner.run(self.root, self.report_path)

    def test_failed_discovery_retains_complete_later_modules_and_noncertifying_report(self):
        self.prepare()

        def process(argv, *args):
            value = self.process(argv, *args)
            return (1, "build failed") if argv[argv.index("--framework") + 1] == "net8.0" else value

        code = self.run_native(process=process)
        report = json.loads(self.report_path.read_text(encoding="utf-8"))
        self.assertEqual(code, 2)
        self.assertEqual(report["completion"], "incomplete")
        self.assertEqual(report["planned_module_count"], 3)
        self.assertEqual([row["status"] for row in report["native_modules"]], ["incomplete", "complete", "complete"])
        self.assertEqual(len(report["results"]), 2)
        self.assertEqual(report["diagnostics"][0]["phase"], "discovery")
        self.assertTrue(report["diagnostics"][0]["logs"])
        self.assertEqual(len(self.calls), 5)

    def test_reconciliation_failure_keeps_progress_and_runs_next_module(self):
        self.prepare()
        evidence = [{"schema": 1, "collected": ["one"], "results": [{"id": "one", "status": "passed"}]},
                    self.runner.DotnetError("Native execution case/method differs from full discovery"),
                    {"schema": 1, "collected": ["three"], "results": [{"id": "three", "status": "passed"}]}]
        self.assertEqual(self.run_native(evidence=evidence), 2)
        report = json.loads(self.report_path.read_text(encoding="utf-8"))
        self.assertEqual(report["collected"], ["one", "three"])
        self.assertEqual(report["diagnostics"][0]["phase"], "reconciliation")
        self.assertEqual(len(self.calls), 6)

    def test_completed_real_failure_has_complete_receipt_shape_and_exit_one(self):
        self.prepare()
        evidence = [{"schema": 1, "collected": [str(index)], "results": [{"id": str(index), "status": "error"}]} for index in range(3)]

        def process(argv, *args):
            value = self.process(argv, *args)
            return (1, value[1]) if "--list-tests" not in argv else value

        self.assertEqual(self.run_native(process=process, evidence=evidence), 1)
        report = json.loads(self.report_path.read_text(encoding="utf-8"))
        self.assertEqual(report["completion"], "complete")
        self.assertEqual(report["diagnostics"], [])
        self.assertEqual(len(report["results"]), 3)

    def test_policy_diagnostic_uses_native_exception_and_hresult_not_localized_guess(self):
        self.prepare()
        events = fixtures.messages("test-failed", "System.IO.FileLoadException")
        events[3]["Messages"] = ["localized operating system reason (0x800711C7)"]
        diagnostic = self.runner._native_diagnostic(fixtures.console(events))
        self.assertEqual(diagnostic["kind"], "application-control")
        self.assertEqual(diagnostic["exception_type"], "System.IO.FileLoadException")
        self.assertEqual(diagnostic["hresult"], "0x800711C7")
        events[3]["ExceptionTypes"] = ["Xunit.Sdk.EqualException"]
        self.assertNotEqual(self.runner._native_diagnostic(fixtures.console(events)).get("kind"), "application-control")

    def test_discovery_and_execution_use_same_command_scoped_theory_setting(self):
        self.prepare()
        self.assertEqual(self.run_native(), 0)
        self.assertEqual(len(self.calls), 6)
        self.assertTrue(all("xUnit.PreEnumerateTheories=false" in argv[argv.index("--") + 1:] for argv in self.calls))

    def test_local_process_timeout_is_typed_and_does_not_skip_later_modules(self):
        self.prepare()

        def process(argv, *args):
            value = self.process(argv, *args)
            if argv[argv.index("--framework") + 1] == "net8.0":
                try:
                    raise subprocess.TimeoutExpired(argv, 10)
                except subprocess.TimeoutExpired as error:
                    raise self.runner.DotnetError("Native .NET execution failed: TimeoutExpired") from error
            return value

        self.assertEqual(self.run_native(process=process), 2)
        report = json.loads(self.report_path.read_text(encoding="utf-8"))
        self.assertEqual(report["diagnostics"][0]["kind"], "native-process-timeout")
        self.assertEqual([row["status"] for row in report["native_modules"]], ["incomplete", "complete", "complete"])

    def test_policy_is_primary_when_corrupted_discovery_also_breaks_inventory(self):
        self.prepare()
        events = fixtures.messages("test-failed", "System.IO.FileLoadException")
        events[3]["Messages"] = ["unrelated locale (0x800711C7)"]

        def process(argv, *args):
            value = self.process(argv, *args)
            return (1, fixtures.console(events)) if "--list-tests" not in argv else value

        evidence = [self.runner.DotnetError("Native execution case/method differs from full discovery") for _ in range(3)]
        self.assertEqual(self.run_native(process=process, evidence=evidence), 2)
        report = json.loads(self.report_path.read_text(encoding="utf-8"))
        self.assertEqual(report["diagnostics"][0]["kind"], "application-control")
        self.assertIn("Native execution case/method", report["diagnostics"][0]["reconciliation_error"])
        self.assertEqual(report["results"], [])

    def test_external_absence_drift_is_fatal_even_when_build_module_fails(self):
        self.prepare()
        external = self.root.parent / (self.root.name + "-missing-tooling.txt")
        self.addCleanup(external.unlink, missing_ok=True)
        self.config["dotnet"]["external_absent_inputs"] = [str(external)]
        (self.root / ".ai-tdd/config.json").write_text(json.dumps(self.config), encoding="utf-8")

        def process(argv, *args):
            self.process(argv, *args)
            external.write_text("new input", encoding="utf-8")
            return 1, "build failed"

        with self.assertRaises(self.runner.DotnetError):
            self.run_native(process=process)
        report = json.loads(self.report_path.read_text(encoding="utf-8"))
        self.assertEqual(report["completion"], "incomplete")
        self.assertEqual([row["status"] for row in report["native_modules"]], ["incomplete", "pending", "pending"])
        self.assertEqual(report["diagnostics"][-1]["kind"], "native-ownership-error")
        self.assertEqual(len(self.calls), 1)

    def test_unsafe_native_assembly_aborts_remaining_plan_without_execution(self):
        self.prepare()
        with mock.patch.object(self.runner.SETUP, "configure", return_value=self.config), mock.patch.object(
                self.runner, "_process", side_effect=self.process), mock.patch.object(
                self.runner, "discovery_cases", return_value={"case": {"source": str(self.root / "unowned.dll")}}):
            with self.assertRaises(self.runner.NativeOwnershipError):
                self.runner.run(self.root, self.report_path)
        report = json.loads(self.report_path.read_text(encoding="utf-8"))
        self.assertEqual(report["completion"], "incomplete")
        self.assertEqual(report["diagnostics"][0]["kind"], "native-ownership-error")
        self.assertEqual(len(self.calls), 1)

    def test_progress_preserves_completed_module_when_process_is_interrupted(self):
        self.prepare()

        def process(argv, *args):
            value = self.process(argv, *args)
            if argv[argv.index("--framework") + 1] == "net9.0":
                raise KeyboardInterrupt("synthetic whole-run interruption")
            return value

        with self.assertRaises(KeyboardInterrupt):
            self.run_native(process=process)
        report = json.loads(self.report_path.read_text(encoding="utf-8"))
        self.assertEqual(report["completion"], "incomplete")
        self.assertEqual([row["status"] for row in report["native_modules"]], ["complete", "running", "pending"])
        self.assertEqual(report["collected"], ["0"])

    def test_catastrophic_adapter_policy_error_before_json_has_explicit_advisory_source(self):
        self.prepare()
        stderr = "Catastrophic failure: System.IO.FileLoadException: localized reason (0x800711C7)\n   at Native.Adapter.Execute()"
        diagnostic = self.runner._native_diagnostic("No test is available", stderr)
        self.assertEqual(diagnostic["code"], "application_control_blocked")
        self.assertEqual(diagnostic["evidence_source"], "adapter-stderr")
        prefixed = "[xUnit.net 00:00:00.15] Demo.Tests: " + stderr
        self.assertEqual(self.runner._native_diagnostic("", prefixed)["code"], "application_control_blocked")
        for unsupported in (stderr.replace("FileLoadException", "InvalidOperationException"),
                            stderr.replace("0x800711C7", "0x80070002"),
                            stderr.replace("Catastrophic failure:", "captured application output:")):
            with self.subTest(stderr=unsupported):
                self.assertEqual(self.runner._native_diagnostic("", unsupported), {})

    def test_missing_reporter_after_catastrophic_policy_keeps_module_incomplete(self):
        self.prepare()

        def process(argv, *args):
            value = self.process(argv, *args)
            if "--list-tests" not in argv:
                args[2].write_text("Catastrophic failure: System.IO.FileLoadException: locale (0x800711C7)", encoding="utf-8")
                return 0, "No test is available"
            return value

        evidence = [self.runner.DotnetError("Missing typed xUnit JSONReporter output") for _ in range(3)]
        self.assertEqual(self.run_native(process=process, evidence=evidence), 2)
        report = json.loads(self.report_path.read_text(encoding="utf-8"))
        self.assertEqual(report["completion"], "incomplete")
        self.assertEqual(report["diagnostics"][0]["code"], "application_control_blocked")
        self.assertEqual(report["diagnostics"][0]["evidence_source"], "adapter-stderr")
        self.assertEqual(report["results"], [])


if __name__ == "__main__":
    unittest.main()
