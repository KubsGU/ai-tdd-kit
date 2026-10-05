"""An inactive legacy native preset can adopt row evidence without manual edits."""
import copy
import json
import unittest
from unittest import mock

from test_controller import Fixture, tdd


class NativePolicyUpgradeTests(Fixture, unittest.TestCase):
    def legacy(self):
        self.config["dotnet"] = {"schema": 1, "sdk": {"version": "10.0.301"},
                                 "projects": ["tests/Demo.csproj"],
                                 "modules": [{"project": "tests/Demo.csproj", "tfm": "net8.0", "framework": "xunit-vstest"}]}
        self.config["max_runner_runs"] = 17
        self.config["worker_models"] = {"implementer": "sonnet"}
        self.save(".ai-tdd/config.json", self.config)
        self.c = tdd.Controller(self.root)
        expected = copy.deepcopy(self.config)
        expected["dotnet"]["theory_mode"] = "runtime-parent-rows-v1"
        return expected

    def test_begin_upgrades_only_proven_legacy_policy_and_keeps_original_backup(self):
        expected = self.legacy()
        original = (self.root / ".ai-tdd/config.json").read_bytes()
        with mock.patch.object(tdd, "dotnet_configuration", return_value=expected):
            self.c.begin()
        config = json.loads((self.root / ".ai-tdd/config.json").read_text())
        self.assertEqual(config, expected)
        backups = list((self.root / ".ai-tdd/diagnostics").glob("config-before-runtime-rows-*.json"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), original)
        self.assertEqual(self.state()["fixed"][".ai-tdd/config.json"], tdd.digest(self.root / ".ai-tdd/config.json"))

    def test_upgrade_does_not_overwrite_changed_sdk_settings_or_ownership(self):
        expected = self.legacy()
        for mode in ("sdk", "modules", "ownership"):
            changed = copy.deepcopy(expected)
            if mode == "sdk":
                changed["dotnet"]["sdk"]["version"] = "8.0.100"
            elif mode == "modules":
                changed["dotnet"]["modules"][0]["runsettings"] = {"path": "different.runsettings", "sha256": "a" * 64}
            else:
                changed["source_roots"] = ["elsewhere"]
            before = (self.root / ".ai-tdd/config.json").read_bytes()
            with self.subTest(mode=mode), mock.patch.object(tdd, "dotnet_configuration", return_value=changed):
                with self.assertRaisesRegex(tdd.TddError, "reviewed setup"):
                    self.c.begin()
            self.assertEqual((self.root / ".ai-tdd/config.json").read_bytes(), before)
            self.assertFalse((self.root / ".ai-tdd/state.json").exists())

    def test_active_task_cannot_migrate_its_frozen_policy(self):
        self.c.begin()
        self.config["dotnet"] = {"schema": 1, "modules": [{"framework": "xunit-vstest"}]}
        self.save(".ai-tdd/config.json", self.config)
        before = (self.root / ".ai-tdd/config.json").read_bytes()
        with mock.patch.object(tdd, "dotnet_configuration") as evaluate:
            with self.assertRaises(tdd.TddError):
                self.c.begin()
        evaluate.assert_not_called()
        self.assertEqual((self.root / ".ai-tdd/config.json").read_bytes(), before)

    def test_configuration_changed_during_evaluation_is_preserved(self):
        expected = self.legacy()
        changed = copy.deepcopy(self.config)
        changed["timeout_seconds"] = 25

        def evaluate(root):
            self.save(".ai-tdd/config.json", changed)
            return expected

        with mock.patch.object(tdd, "dotnet_configuration", side_effect=evaluate):
            with self.assertRaisesRegex(tdd.TddError, "reviewed setup"):
                self.c.begin()
        self.assertEqual(json.loads((self.root / ".ai-tdd/config.json").read_text()), changed)
        self.assertFalse((self.root / ".ai-tdd/state.json").exists())


if __name__ == "__main__":
    unittest.main()
