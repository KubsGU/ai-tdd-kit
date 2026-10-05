"""Missing linked tooling inputs stay frozen throughout actual phase gates."""
import importlib.util
import json
from pathlib import Path
import unittest
from unittest import mock

from test_controller import Fixture, PLUGIN, tdd
import test_dotnet_runner as fixtures


class ExternalControllerGates(Fixture, unittest.TestCase):
    def bind_absent(self):
        self.external = self.root.parent / (self.root.name + "-absent.dockerignore")
        self.addCleanup(self.external.unlink, missing_ok=True)
        self.config["dotnet"] = {"schema": 1, "external_absent_inputs": [str(self.external)]}
        self.save(".ai-tdd/config.json", self.config)
        self.c = tdd.Controller(self.root)

    def test_creation_after_green_invalidates_freshness(self):
        self.bind_absent()
        self.ready_green()
        self.external.write_text("new build input", encoding="utf-8")
        with self.assertRaises(tdd.TddError):
            self.c.fresh()

    def test_creation_during_real_runner_cannot_issue_a_receipt(self):
        self.bind_absent()
        runner = self.root / "mutating-runner.py"
        runner.write_text(
            "import pathlib, subprocess, sys\n"
            "result = subprocess.run([sys.executable, '-B', "
            + repr(str(PLUGIN / "scripts/unittest_runner.py"))
            + ", '--start-dir', 'tests', '--report', sys.argv[1]])\n"
            + "pathlib.Path(" + repr(str(self.external)) + ").write_text('created', encoding='utf-8')\n"
            + "raise SystemExit(result.returncode)\n", encoding="utf-8")
        self.config["runner"]["argv"] = ["{python}", "-B", str(runner), "{report}"]
        self.save(".ai-tdd/config.json", self.config)
        self.c = tdd.Controller(self.root)
        with self.assertRaises(tdd.TddError):
            self.c.run("baseline-probe")
        self.assertTrue(self.external.is_file())
        self.assertEqual(list((self.root / ".ai-tdd/runs").glob("*.receipt.json")), [])

    def test_bound_external_path_does_not_grant_worker_write_access(self):
        self.bind_absent()
        self.ready_red()
        payload = {"cwd": str(self.root), "tool_name": "Write", "agent_type": "ai-tdd:implementer",
                   "agent_id": "implementation-worker", "tool_input": {"file_path": str(self.external)}}
        self.assertIsNotNone(tdd.guard(payload))
        self.assertFalse(self.external.exists())


class ExternalNativeRunnerGates(unittest.TestCase):
    setUp = fixtures.DotnetSetupTests.setUp

    def test_creation_during_native_run_cannot_emit_successful_evidence(self):
        external = self.root.parent / (self.root.name + "-absent.dockerignore")
        self.addCleanup(external.unlink, missing_ok=True)
        folder = self.root / ".ai-tdd"
        folder.mkdir()
        config = {"dotnet": {"schema": 1, "external_absent_inputs": [str(external)],
                             "modules": [{"project": "tests/Demo.Tests/Demo.Tests.csproj", "tfm": "net8.0", "framework": "xunit-vstest"}]},
                  "generated_roots": [], "timeout_seconds": 10}
        (folder / "config.json").write_text(json.dumps(config), encoding="utf-8")
        loader = importlib.util.spec_from_file_location("external_native_runner", fixtures.SCRIPTS / "dotnet_runner.py")
        runner = importlib.util.module_from_spec(loader)
        loader.loader.exec_module(runner)
        source = self.root / "tests/Demo.Tests/bin/Debug/net8.0/Demo.Tests.dll"

        def process(argv, root, stdout, stderr, timeout):
            if "--list-tests" in argv:
                Path(argv[argv.index("--diag") + 1]).write_text("synthetic", encoding="utf-8")
            else:
                (stdout.parent / "result.trx").write_text("synthetic", encoding="utf-8")
                external.write_text("changed during execution", encoding="utf-8")
            return 0, "synthetic"

        evidence = {"schema": 1, "collected": ["one"], "results": [{"id": "one", "status": "passed"}]}
        report = folder / "fresh.json"
        with mock.patch.object(runner.SETUP, "configure", return_value=config), mock.patch.object(
                runner, "_process", side_effect=process), mock.patch.object(
                runner, "discovery_cases", return_value={"case": {"source": str(source)}}), mock.patch.object(
                runner, "reconcile", return_value=evidence), self.assertRaises(runner.DotnetError):
            runner.run(self.root, report)
        progress = json.loads(report.read_text(encoding="utf-8"))
        self.assertEqual(progress["completion"], "incomplete")
        self.assertNotEqual(progress["native_modules"][0]["status"], "complete")


if __name__ == "__main__":
    unittest.main()
