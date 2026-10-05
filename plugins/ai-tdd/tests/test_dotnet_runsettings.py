"""Existing repository settings remain unchanged and cannot hide test cases."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest
from unittest import mock

import test_dotnet_runner as fixtures


COVERAGE = '''<?xml version="1.0" encoding="utf-8"?>
<RunSettings><RunConfiguration><MaxCpuCount>0</MaxCpuCount>
<EnvironmentVariables><DEMO_MODE>local</DEMO_MODE></EnvironmentVariables></RunConfiguration>
<DataCollectionRunSettings><DataCollectors><DataCollector friendlyName="XPlat Code Coverage">
<Configuration><Format>cobertura</Format><Exclude>[*.Tests]*</Exclude>
<ExcludeByFile>**/Generated/*.cs</ExcludeByFile><IncludeTestAssembly>false</IncludeTestAssembly>
</Configuration></DataCollector></DataCollectors></DataCollectionRunSettings>
<xUnit><ParallelizeTestCollections>false</ParallelizeTestCollections></xUnit>
</RunSettings>'''


class RepositoryRunsettingsTests(unittest.TestCase):
    setUp = fixtures.DotnetSetupTests.setUp
    metadata = fixtures.DotnetSetupTests.metadata

    def configured(self, text=COVERAGE, *, filename="coverage.runsettings", properties=None):
        path = self.root / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        original = self.metadata

        def metadata(project, tfm=None, *, root=None):
            value = original(project, tfm, root=root)
            value["Properties"].update(properties or {"RunSettingsFilePath": str(path)})
            return value

        with mock.patch.object(self.setup, "evaluate", side_effect=metadata), mock.patch.object(
                self.setup, "sdk_identity", return_value={"executable": "fixture", "sha256": "a" * 64, "version": "10.0.301"}):
            return self.setup.configure(self.root), path

    def test_inherited_coverage_is_bound_and_does_not_edit_repository(self):
        before = {str(path): path.read_bytes() for path in self.root.rglob("*") if path.is_file()}
        config, path = self.configured()
        self.assertEqual(config["dotnet"]["modules"][0]["runsettings"], {
            "path": "coverage.runsettings", "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        self.assertIn("coverage.runsettings", config["protected_paths"])
        self.assertEqual(path.read_text(encoding="utf-8"), COVERAGE)
        self.assertEqual(before, {name: Path(name).read_bytes() for name in before})

    def test_bare_imported_path_is_project_relative_and_effective_vstest_setting_wins(self):
        (self.root / "coverage.runsettings").write_text("<RunSettings><RunConfiguration><TestCaseFilter>bad</TestCaseFilter></RunConfiguration></RunSettings>", encoding="utf-8")
        config, _ = self.configured(filename="tests/Demo.Tests/coverage.runsettings",
                                    properties={"RunSettingsFilePath": "coverage.runsettings"})
        self.assertEqual(config["dotnet"]["modules"][0]["runsettings"]["path"], "tests/Demo.Tests/coverage.runsettings")
        config, _ = self.configured(properties={"RunSettingsFilePath": "missing.runsettings",
                                              "VSTestSetting": str(self.root / "coverage.runsettings")})
        self.assertEqual(config["dotnet"]["modules"][0]["runsettings"]["path"], "coverage.runsettings")
        self.assertIn("VSTestSetting", self.setup.PROPERTIES)

    def test_settings_hash_changes_even_when_xml_semantics_do_not(self):
        config, _ = self.configured()
        changed, _ = self.configured(COVERAGE + "\n")
        self.assertNotEqual(config["dotnet"], changed["dotnet"])

    def test_selection_early_stop_and_unknown_adapter_controls_are_actionable(self):
        bad = [("RunConfiguration", "TestCaseFilter", "Category=Smoke"),
               ("xUnit", "StopOnFail", "true"), ("xUnit", "Explicit", "only"),
               ("xUnit", "PreEnumerateTheories", "unknown"), ("NUnit", "Where", "cat == Smoke"),
               ("NUnit", "StopOnError", "true"), ("NUnit", "ExplicitMode", "None"),
               ("xUnit", "UnreviewedSelectionExtension", "true")]
        for section, node, value in bad:
            with self.subTest(node=node), self.assertRaisesRegex(self.setup.DotnetError, node):
                self.configured(f"<RunSettings><{section}><{node}>{value}</{node}></{section}></RunSettings>")
        self.configured("<RunSettings><xUnit><StopOnFail>false</StopOnFail><PreEnumerateTheories>true</PreEnumerateTheories></xUnit></RunSettings>")

    def test_existing_deferred_theory_setting_is_preserved_under_runtime_row_policy(self):
        text = COVERAGE.replace("<xUnit>", "<xUnit><PreEnumerateTheories>false</PreEnumerateTheories>")
        config, path = self.configured(text)
        self.assertEqual(path.read_text(encoding="utf-8"), text)
        self.assertEqual(config["dotnet"]["theory_mode"], "runtime-parent-rows-v1")
        self.assertEqual(config["dotnet"]["modules"][0]["runsettings"]["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())

    def test_malformed_ambiguous_and_external_settings_do_not_pass(self):
        values = ["<RunSettings>", "<Other/>",
                  '<RunSettings xmlns="urn:custom"/>',
                  '<!DOCTYPE RunSettings [<!ENTITY x "x">]><RunSettings/>',
                  '<RunSettings><xUnit/><xUnit/></RunSettings>',
                  '<RunSettings><xUnit><StopOnFail>false</StopOnFail><StopOnFail>true</StopOnFail></xUnit></RunSettings>']
        for text in values:
            with self.subTest(text=text), self.assertRaises(self.setup.DotnetError):
                self.configured(text)
        for name in (str(self.root.parent / "outside.runsettings"), str(self.root / "missing.runsettings")):
            with self.subTest(path=name), self.assertRaises(self.setup.DotnetError):
                self.configured(properties={"RunSettingsFilePath": name})

    def test_discovery_and_execution_use_same_absolute_existing_settings(self):
        config, path = self.configured()
        folder = self.root / ".ai-tdd"
        folder.mkdir()
        (folder / "config.json").write_text(json.dumps(config), encoding="utf-8")
        loader = importlib.util.spec_from_file_location("settings_runner", fixtures.SCRIPTS / "dotnet_runner.py")
        runner = importlib.util.module_from_spec(loader)
        loader.loader.exec_module(runner)
        source = self.root / "tests/Demo.Tests/bin/Debug/net8.0/Demo.Tests.dll"
        case = {"source": str(source)}
        calls = []

        def process(argv, root, stdout, stderr, timeout):
            calls.append(argv)
            if "--list-tests" in argv:
                Path(argv[argv.index("--diag") + 1]).write_text("synthetic", encoding="utf-8")
            else:
                (stdout.parent / "result.trx").write_text("synthetic", encoding="utf-8")
            return 0, "synthetic"

        evidence = {"schema": 1, "collected": ["one"], "results": [{"id": "one", "status": "passed"}]}
        with mock.patch.object(runner.SETUP, "configure", return_value=config), mock.patch.object(
                runner, "_process", side_effect=process), mock.patch.object(runner, "discovery_cases", return_value={"case": case}), mock.patch.object(
                runner, "reconcile", return_value=evidence):
            self.assertEqual(runner.run(self.root, folder / "fresh.json"), 0)
        self.assertEqual(len(calls), 2)
        for argv in calls:
            self.assertIn("--settings", argv)
            self.assertEqual(argv[argv.index("--settings") + 1], str(path))
        changed = copy.deepcopy(config)
        changed["dotnet"]["modules"][0]["runsettings"]["sha256"] = "b" * 64
        with mock.patch.object(runner.SETUP, "configure", return_value=changed), mock.patch.object(
                runner, "_process") as execute, self.assertRaises(runner.DotnetError):
            runner.run(self.root, folder / "drift.json")
        execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
