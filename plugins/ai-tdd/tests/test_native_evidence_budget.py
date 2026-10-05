"""Large native evidence remains complete without relaxing setup-input bounds."""
import importlib.util
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from test_controller import Fixture, PLUGIN, tdd
import test_runner_diagnostics as fixtures


LARGE = "synthetic native stack frame\n" * 200_000


class NativeEvidenceBudgetTests(Fixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        loader = importlib.util.spec_from_file_location("native_evidence_budget_runner", PLUGIN / "scripts/dotnet_runner.py")
        self.runner = importlib.util.module_from_spec(loader)
        loader.loader.exec_module(self.runner)

    def test_large_native_progress_preserves_all_failure_payloads_and_outcomes(self):
        payload = fixtures.native_report()
        payload["results"][0].update(status="error", exception="System.InvalidOperationException", native_stack_traces=[LARGE])
        path = self.root / ".ai-tdd/native.json"
        self.runner._write_progress(path, payload, initial=True)
        self.assertGreater(path.stat().st_size, 5_000_000)
        collected, results = tdd.parse_report(path, "json", native=True)
        self.assertEqual(collected, payload["collected"])
        self.assertEqual(results, payload["results"])
        with self.assertRaisesRegex(tdd.TddError, "oversized"):
            tdd.parse_report(path, "json")

    def test_large_native_baseline_state_reloads_with_compact_user_view(self):
        payload = fixtures.native_report()
        payload["results"][0]["display_name"] = LARGE
        data = self.root / "fixture-payload.json"
        data.write_text(json.dumps(payload), encoding="utf-8")
        self.write("fixture_runner.py", "import shutil, sys\nshutil.copyfile('fixture-payload.json', sys.argv[1])\n")
        self.config["dotnet"] = {"schema": 1, "theory_mode": "runtime-parent-rows-v1"}
        self.config["protected_paths"] += ["fixture_runner.py", "fixture-payload.json"]
        self.config["runner"]["argv"] = ["{python}", "-B", "fixture_runner.py", "{report}"]
        self.save(".ai-tdd/config.json", self.config)
        tdd.Controller(self.root).begin()
        self.assertGreater((self.root / ".ai-tdd/state.json").stat().st_size, 5_000_000)
        reloaded = tdd.Controller(self.root)
        self.assertEqual(reloaded.state["baseline_receipt"]["results"], payload["results"])
        self.assertLess(len(json.dumps(tdd.compact_state(reloaded.state))), 10_000)

    def test_large_configuration_is_still_rejected(self):
        self.config["padding"] = LARGE
        self.save(".ai-tdd/config.json", self.config)
        with self.assertRaisesRegex(tdd.TddError, "oversized"):
            tdd.Controller(self.root)

    def test_read_checks_actual_bytes_if_artifact_grows_after_stat(self):
        path = self.root / "growing.json"
        path.write_text(json.dumps({"value": "x" * 100}), encoding="utf-8")
        observed = SimpleNamespace(st_size=1, st_mode=path.stat().st_mode, st_file_attributes=0)
        with patch.object(type(path), "lstat", return_value=observed):
            with self.assertRaisesRegex(tdd.TddError, "oversized"):
                tdd.read_json(path, max_bytes=50)

    def test_oversized_state_write_keeps_previous_complete_state(self):
        controller = tdd.Controller(self.root)
        controller.begin()
        previous = controller.state_path.read_bytes()
        controller.state["padding"] = "x" * 200
        with patch.object(tdd, "STATE_MAX_BYTES", 100):
            with self.assertRaisesRegex(tdd.TddError, "bounded evidence budget"):
                controller.save("cannot-fit")
        self.assertEqual(controller.state_path.read_bytes(), previous)
        self.assertFalse(list(controller.folder.glob("state.json.*.tmp")))


if __name__ == "__main__":
    unittest.main()
