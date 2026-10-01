"""Quality checks exercise real commands in isolated synthetic projects."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
import uuid


PLUGIN = Path(__file__).resolve().parents[1]
QUALITY_PATH = PLUGIN / "scripts/quality.py"


class QualityTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(QUALITY_PATH.is_file(), "Quality executor has not been implemented")
        loader = importlib.util.spec_from_file_location("quality", QUALITY_PATH)
        self.quality = importlib.util.module_from_spec(loader)
        loader.loader.exec_module(self.quality)
        self.temp = tempfile.TemporaryDirectory(prefix="ai-tdd-quality-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.folder = self.root / ".ai-tdd"
        self.folder.mkdir()
        (self.root / "src").mkdir()
        self.write("src/value.py", "VALUE = 1\n")
        self.write(".ai-tdd/config.json", '{"schema": 1}\n')
        self.fingerprints = []

    def write(self, relative, content):
        path = self.root / relative
        path.write_text(content, encoding="utf-8")
        return path

    def fingerprint(self):
        paths = [self.folder / "config.json", *sorted((self.root / "src").rglob("*"))]
        value = tuple((str(path.relative_to(self.root)), hashlib.sha256(path.read_bytes()).hexdigest())
                      for path in paths if path.is_file())
        self.fingerprints.append(value)
        return value

    def check(self, name="lint", code="print('ok')", **extra):
        value = {"name": name, "kind": "lint", "argv": ["{python}", "-c", code]}
        value.update(extra)
        return value

    def execute(self, checks):
        return self.quality.execute_checks(self.root, self.folder,
                                           self.quality.validate_checks(checks), self.fingerprint)

    def log(self, item, name):
        path = self.root / item[name]
        self.assertEqual(path.parent, self.folder / "runs")
        self.assertTrue(path.is_file())
        self.assertFalse(path.is_symlink())
        return path.read_text(encoding="utf-8")

    def test_validation_defaults_and_preserves_independent_config(self):
        original = [self.check(), self.check("typing", kind="typecheck", timeout_seconds=3600)]
        normalized = self.quality.validate_checks(original)
        self.assertEqual(normalized[0]["timeout_seconds"], 120)
        self.assertEqual(normalized[1]["timeout_seconds"], 3600)
        self.assertEqual([item["name"] for item in normalized], ["lint", "typing"])
        normalized[0]["argv"].append("changed")
        self.assertEqual(len(original[0]["argv"]), 3)
        self.assertNotIn("timeout_seconds", original[0])

    def test_validation_preserves_independent_quality_inputs(self):
        original = [self.check(inputs=["pyproject.toml", "typing-config"]), self.check("typing")]
        normalized = self.quality.validate_checks(original)
        self.assertEqual(normalized[0].get("inputs"), ["pyproject.toml", "typing-config"])
        self.assertEqual(normalized[1].get("inputs"), [])
        normalized[0]["inputs"].append("changed")
        self.assertEqual(original[0]["inputs"], ["pyproject.toml", "typing-config"])
        for inputs in (None, "pyproject.toml", [None], [""], [" "], ["bad\x00path"]):
            with self.subTest(inputs=inputs), self.assertRaises(ValueError):
                self.quality.validate_checks([self.check(inputs=inputs)])

    def test_validation_rejects_unsafe_names_and_commands(self):
        invalid = [
            self.check(name="../escape"), self.check(name="Upper"), self.check(name=""),
            self.check(name="a" * 65), self.check(name="con"), self.check(name="nul"),
            self.check(name="a--b"), self.check(kind="unknown"),
            self.check(argv="python -c print(1)"), self.check(argv=[]),
            self.check(argv=[""]), self.check(argv=[" "]), self.check(argv=[1]),
            self.check(argv=["python", "contains\x00nul"]),
            self.check(timeout_seconds=0), self.check(timeout_seconds=-1),
            self.check(timeout_seconds=3601), self.check(timeout_seconds=True),
            self.check(timeout_seconds="10"), self.check(timeout_seconds=float("nan")),
            self.check(timeout_seconds=float("inf")),
        ]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.quality.validate_checks([value])
        for value in ({}, "command", [None], [self.check(), self.check()],
                      [self.check("check-" + str(index)) for index in range(21)]):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.quality.validate_checks(value)

    def test_empty_config_is_not_configured_and_does_not_write_logs(self):
        self.assertEqual(self.quality.validate_checks(None), [])
        result = self.execute([])
        self.assertEqual(result["status"], "not_configured")
        self.assertEqual(result["checks"], [])
        uuid.UUID(result["id"])
        self.assertFalse((self.folder / "runs").exists())
        self.assertEqual(self.fingerprints, [])

    def test_success_stores_logs_without_exposing_output_in_receipt(self):
        result = self.execute([self.check(code="import sys; print('private-output'); print('private-error', file=sys.stderr)")])
        self.assertEqual(result["status"], "passed")
        uuid.UUID(result["id"])
        item = result["checks"][0]
        self.assertEqual((item["name"], item["kind"], item["exit_code"], item["timed_out"], item["error"]),
                         ("lint", "lint", 0, False, None))
        self.assertEqual(self.log(item, "stdout_path"), "private-output\n")
        self.assertEqual(self.log(item, "stderr_path"), "private-error\n")
        self.assertNotIn('"stdout":', json.dumps(result))
        self.assertNotIn('"stderr":', json.dumps(result))
        self.assertEqual(len(self.fingerprints), 2)

    def test_failure_stops_later_checks_and_preserves_order(self):
        result = self.execute([
            self.check("first", "print('first')"),
            self.check("second", "import sys; sys.exit(7)", kind="security"),
            self.check("third", "from pathlib import Path; Path('third-ran').touch()"),
        ])
        self.assertEqual(result["status"], "failed")
        self.assertEqual([item["name"] for item in result["checks"]], ["first", "second"])
        self.assertEqual(result["checks"][1]["exit_code"], 7)
        self.assertFalse(result["checks"][1]["timed_out"])
        self.assertEqual(result["unexecuted_checks"], ["third"])
        self.assertFalse((self.root / "third-ran").exists())
        self.assertEqual(len(self.fingerprints), 4)

    def test_timeout_cannot_pass_and_stores_partial_logs(self):
        result = self.execute([self.check(code="import time; print('started', flush=True); time.sleep(5)", timeout_seconds=0.2)])
        self.assertEqual(result["status"], "failed")
        item = result["checks"][0]
        self.assertTrue(item["timed_out"])
        self.assertIsNone(item["exit_code"])
        self.assertEqual(item["error"], "timeout")
        self.assertEqual(self.log(item, "stdout_path"), "started\n")
        self.assertEqual(len(self.fingerprints), 2)

    def test_unavailable_executable_cannot_pass_and_has_safe_error(self):
        result = self.execute([self.check(argv=[str(self.root / "missing-command")])])
        self.assertEqual(result["status"], "failed")
        item = result["checks"][0]
        self.assertIsNone(item["exit_code"])
        self.assertFalse(item["timed_out"])
        self.assertEqual(item["error"], "executable_unavailable")
        self.assertEqual(self.log(item, "stdout_path"), "")
        self.assertEqual(self.log(item, "stderr_path"), "")
        self.assertEqual(len(self.fingerprints), 2)

    def test_source_mutation_invalidates_successful_process(self):
        code = "from pathlib import Path; Path('src/value.py').write_text('VALUE = 2\\n')"
        with self.assertRaisesRegex(ValueError, "modified"):
            self.execute([self.check(code=code)])
        self.assertEqual((self.root / "src/value.py").read_text(encoding="utf-8"), "VALUE = 2\n")
        self.assertEqual(len(self.fingerprints), 2)

    def test_config_mutation_invalidates_successful_process(self):
        code = "from pathlib import Path; Path('.ai-tdd/config.json').write_text('{}')"
        with self.assertRaisesRegex(ValueError, "modified"):
            self.execute([self.check(code=code)])
        self.assertEqual(len(self.fingerprints), 2)

    def test_source_mutation_is_checked_after_timeout(self):
        code = "from pathlib import Path; import time; Path('src/value.py').write_text('changed'); time.sleep(5)"
        with self.assertRaisesRegex(ValueError, "modified"):
            self.execute([self.check(code=code, timeout_seconds=0.2)])
        self.assertEqual(len(self.fingerprints), 2)

    def test_config_mutation_is_checked_after_nonzero_exit(self):
        code = "from pathlib import Path; import sys; Path('.ai-tdd/config.json').write_text('{}'); sys.exit(3)"
        with self.assertRaisesRegex(ValueError, "modified"):
            self.execute([self.check(code=code)])
        self.assertEqual(len(self.fingerprints), 2)

    def test_placeholders_project_cwd_and_no_bytecode_are_scoped(self):
        script = self.write("check with spaces.py", "import os, sys\nfrom pathlib import Path\n"
                            "import src.value\n"
                            "print(Path.cwd())\nprint(sys.argv[1])\nprint(sys.argv[2])\n"
                            "print(os.environ.get('PYTHONDONTWRITEBYTECODE'))\nprint(sys.dont_write_bytecode)\n")
        result = self.execute([self.check(argv=["{python}", "{root}/check with spaces.py", "{root}", "{plugin}"])])
        item = result["checks"][0]
        self.assertEqual(result["status"], "passed")
        self.assertEqual(self.log(item, "stdout_path").splitlines(),
                         [str(self.root), str(self.root), str(PLUGIN), "1", "True"])
        self.assertEqual(item["argv"][0], sys.executable)
        self.assertEqual(Path(item["argv"][1]), script)
        self.assertEqual(item["argv"][2:], [str(self.root), str(PLUGIN)])
        self.assertFalse((self.root / "src/__pycache__").exists())

    def test_shell_metacharacters_remain_literal_arguments(self):
        literal = "; echo forbidden > should-not-exist"
        result = self.execute([self.check(argv=["{python}", "-c", "import sys; print(sys.argv[1])", literal])])
        self.assertEqual(result["status"], "passed")
        self.assertEqual(self.log(result["checks"][0], "stdout_path"), literal + "\n")
        self.assertFalse((self.root / "should-not-exist").exists())

    def test_repeat_runs_execute_fresh_and_use_unique_logs(self):
        checks = [self.check(code="from pathlib import Path; print(Path('src/value.py').read_text().strip())")]
        first = self.execute(checks)
        self.write("src/value.py", "VALUE = 2\n")
        second = self.execute(checks)
        self.assertEqual(self.log(first["checks"][0], "stdout_path"), "VALUE = 1\n")
        self.assertEqual(self.log(second["checks"][0], "stdout_path"), "VALUE = 2\n")
        self.assertNotEqual(first["id"], second["id"])
        self.assertNotEqual(first["checks"][0]["stdout_path"], second["checks"][0]["stdout_path"])
        self.assertEqual(len(list((self.folder / "runs").iterdir())), 4)
        self.assertEqual(len(self.fingerprints), 4)

    def test_log_folder_cannot_escape_root_by_parent_components(self):
        project = self.root / "project"
        project.mkdir()
        escaped = project / ".." / "escaped"
        with self.assertRaisesRegex(ValueError, "root"):
            self.quality.execute_checks(project, escaped, self.quality.validate_checks([self.check()]),
                                        self.fingerprint)
        self.assertFalse((self.root / "escaped").exists())
        self.assertEqual(self.fingerprints, [])

    def test_runs_directory_symlink_is_rejected_before_execution(self):
        external = self.root / "external"
        external.mkdir()
        try:
            os.symlink(external, self.folder / "runs", target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("Directory symlinks are unavailable on this platform")
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.execute([self.check(code="from pathlib import Path; Path('ran').touch()")])
        self.assertEqual(list(external.iterdir()), [])
        self.assertFalse((self.root / "ran").exists())
        self.assertEqual(self.fingerprints, [])


if __name__ == "__main__":
    unittest.main()
