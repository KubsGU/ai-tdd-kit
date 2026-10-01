"""Managed state and log paths reject real directory redirection before I/O."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


PLUGIN = Path(__file__).resolve().parents[1]
loader = importlib.util.spec_from_file_location("tdd_log_paths", PLUGIN / "scripts/tdd.py")
tdd = importlib.util.module_from_spec(loader)
loader.loader.exec_module(tdd)


class DirectoryRedirectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ai-tdd-log-paths-")
        self.addCleanup(self.temp.cleanup)
        self.sandbox = Path(self.temp.name).resolve()
        self.root = self.sandbox / "project"
        self.external = self.sandbox / "external"
        self.root.mkdir()
        self.external.mkdir()
        self.folder = self.root / ".ai-tdd"

    def redirect(self, link):
        # Both junction endpoints belong to this test's temporary directory.
        for path in (link, self.external):
            self.assertIn(self.sandbox, path.absolute().parents)
        try:
            if os.name == "nt":
                result = subprocess.run(
                    ["cmd", "/d", "/c", "mklink", "/J", str(link), str(self.external)],
                    capture_output=True, text=True, check=False,
                )
                if result.returncode:
                    self.skipTest("Native Windows junction creation is unavailable")
            else:
                link.symlink_to(self.external, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("Directory link creation is unavailable")
        self.assertEqual(link.resolve(), self.external)
        if os.name == "nt":
            self.assertFalse(link.is_symlink(), "Exercise a native junction, not a symlink")

    def inventory(self):
        return {path.relative_to(self.external).as_posix(): path.read_bytes()
                for path in self.external.rglob("*") if path.is_file()}

    def test_init_rejects_redirected_state_before_writing_config(self):
        self.redirect(self.folder)
        error = None
        try:
            tdd.init(self.root)
        except tdd.TddError as caught:
            error = caught
        self.assertEqual(self.inventory(), {}, "init wrote config outside the project before rejecting the redirected directory")
        self.assertIsNotNone(error, "init must reject the redirected state directory")

    def test_lock_rejects_redirected_state_before_writing_lock(self):
        self.redirect(self.folder)
        entered = False
        external_lock_seen = False
        error = None
        try:
            with tdd.lock(self.root):
                entered = True
                external_lock_seen = (self.external / "controller.lock").is_file()
        except tdd.TddError as caught:
            error = caught
        self.assertFalse(external_lock_seen, "lock wrote controller.lock outside the project before rejecting the redirected directory")
        self.assertFalse(entered, "lock must reject before entering its protected operation")
        self.assertEqual(self.inventory(), {})
        self.assertIsNotNone(error, "lock must reject the redirected state directory")

    def test_controller_rejects_redirected_state_before_accepting_external_artifacts(self):
        config = {"schema": 1, "source_roots": ["src"], "test_roots": ["tests"],
                  "protected_paths": [], "runner": {"format": "json", "argv": ["runner", "{report}"]}}
        (self.external / "config.json").write_text(json.dumps(config), encoding="utf-8")
        (self.external / "state.json").write_text(json.dumps({"phase": "DONE", "probe_marker": "external-only"}), encoding="utf-8")
        before = self.inventory()
        self.redirect(self.folder)
        with self.assertRaises(tdd.TddError, msg="Controller accepted valid config/state from outside the project"):
            tdd.Controller(self.root)
        self.assertEqual(self.inventory(), before)

    def test_quality_rejects_redirected_runs_before_logs_or_command_execution(self):
        self.folder.mkdir()
        self.redirect(self.folder / "runs")
        fingerprints = []

        def fingerprint():
            fingerprints.append("called")
            return "unchanged"

        checks = [{"name": "lint", "kind": "lint", "argv": ["{python}", "-c",
                   "from pathlib import Path; Path('command-ran').touch()"]}]
        with self.assertRaises(ValueError):
            tdd.QUALITY.execute_checks(self.root, self.folder, checks, fingerprint)
        self.assertEqual(self.inventory(), {}, "Quality logs were written outside the project")
        self.assertFalse((self.root / "command-ran").exists())
        self.assertEqual(fingerprints, [], "Quality execution started before rejecting redirected logs")


if __name__ == "__main__":
    unittest.main()
