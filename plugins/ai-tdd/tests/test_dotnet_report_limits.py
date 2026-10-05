"""Real native XML payloads can grow without weakening inventory evidence."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
from types import SimpleNamespace
import unittest
from unittest import mock
import uuid
import xml.etree.ElementTree as ET

import test_dotnet_runner as fixtures


NS = "{http://microsoft.com/schemas/VisualStudio/TeamTest/2010}"
LARGE_OUTPUT = "synthetic captured output " * 210_000


class NativeReportLimitTests(unittest.TestCase):
    metadata = fixtures.DotnetSetupTests.metadata
    configure = fixtures.DotnetSetupTests.configure

    def setUp(self):
        fixtures.DotnetSetupTests.setUp(self)
        loader = importlib.util.spec_from_file_location("large_xml_runner", fixtures.SCRIPTS / "dotnet_runner.py")
        self.runner = importlib.util.module_from_spec(loader)
        loader.loader.exec_module(self.runner)
        self.config = self.configure()
        self.folder = self.root / ".ai-tdd"
        self.folder.mkdir()
        self.source = self.root / "tests/Demo.Tests/bin/Debug/net8.0/Demo.Tests.dll"
        self.native_ids = ["case-" + str(index) for index in range(3)]
        self.rows = [fixtures.discovered(case_id=case, vs_id=str(uuid.UUID(int=index + 1)))
                     for index, case in enumerate(self.native_ids)]
        for row in self.rows:
            row["Source"] = str(self.source)
        events = [{"$type": "test-assembly-starting", "AssemblyUniqueID": "assembly"}]
        for index, case in enumerate(self.native_ids):
            for event in copy.deepcopy(fixtures.messages()[1:-1]):
                event["TestCaseUniqueID"] = case
                if "TestUniqueID" in event:
                    event["TestUniqueID"] = "test-" + str(index)
                events.append(event)
        events.append({"$type": "test-assembly-finished", "AssemblyUniqueID": "assembly",
                       "TestsTotal": 3, "TestsFailed": 0, "TestsSkipped": 0, "TestsNotRun": 0})
        self.execution = fixtures.console(events)
        cases = [(row["DisplayName"], row["Id"], "Passed") for row in self.rows]
        tree = ET.fromstring(fixtures.xunit_trx(total=3, cases=cases))
        for method in tree.findall(NS + "TestDefinitions/" + NS + "UnitTest/" + NS + "TestMethod"):
            method.set("codeBase", str(self.source))
        output = ET.SubElement(tree.find(NS + "Results/" + NS + "UnitTestResult"), NS + "Output")
        ET.SubElement(output, NS + "StdOut").text = LARGE_OUTPUT
        self.native_trx = ET.tostring(tree, encoding="unicode")
        self.calls = []

    def process(self, argv, root, stdout, stderr, timeout):
        self.calls.append(argv)
        if "--list-tests" in argv:
            trace = fixtures.discovery_trace(self.rows, FullyDiscoveredSources=[str(self.source)])
            Path(argv[argv.index("--diag") + 1]).write_text(trace, encoding="utf-8")
            return 0, "synthetic full discovery"
        (stdout.parent / "result.trx").write_text(self.native_trx, encoding="utf-8")
        return 0, self.execution

    def run_native(self, *, process=None):
        (self.folder / "config.json").write_text(json.dumps(self.config), encoding="utf-8")
        report = self.folder / ("report-" + uuid.uuid4().hex + ".json")
        with mock.patch.object(self.runner.SETUP, "configure", return_value=self.config), mock.patch.object(
                self.runner.shutil, "which", return_value="fixture-dotnet"), mock.patch.object(
                self.runner, "_process", side_effect=process or self.process):
            code = self.runner.run(self.root, report)
        return code, json.loads(report.read_text(encoding="utf-8"))

    def test_full_runner_accepts_large_trx_and_reconciles_every_native_id(self):
        self.assertGreater(len(self.native_trx.encode("utf-8")), 5_000_000)
        code, report = self.run_native()
        expected = ["tests/Demo.Tests/Demo.Tests.csproj|net8.0|xunit:" + case for case in self.native_ids]
        self.assertEqual(code, 0)
        self.assertEqual(report["collected"], expected)
        self.assertEqual([item["id"] for item in report["results"]], expected)
        self.assertEqual([item["vstest_id"] for item in report["results"]], [row["Id"] for row in self.rows])
        self.assertEqual([item["status"] for item in report["results"]], ["passed"] * 3)
        self.assertEqual(len(self.calls), 2)
        self.assertTrue(all("--filter" not in argv for argv in self.calls))
        self.assertLess(len(json.dumps(report)), 5_000_000)

    def test_large_trx_still_rejects_native_inventory_and_outcome_drift(self):
        original = self.native_trx
        for changed in (original.replace(self.rows[0]["Id"], str(uuid.UUID(int=99))),
                        original.replace('outcome="Passed"', 'outcome="Failed"', 1)):
            self.native_trx = changed
            with self.subTest(xml=changed[:80]), self.assertRaisesRegex(self.runner.DotnetError, "identity|inventory/outcomes"):
                self.run_native()

    def test_large_nunit_discovery_and_execution_xml_preserve_all_full_names(self):
        self.config["dotnet"]["modules"][0]["framework"] = "nunit-vstest"
        names = ["Demo.Checks.Total(" + str(index) + ")" for index in range(3)]
        leaf = lambda name: ET.Element("test-case", id=name, fullname=name, classname="Demo.Checks",
                                       methodname="Total", runstate="Runnable", result="Passed")
        discovery = ET.Element("NUnitXml")
        discovered = ET.SubElement(discovery, "test-run", testcasecount="3")
        discovered.extend(leaf(name) for name in names)
        ET.SubElement(discovery, "output").text = LARGE_OUTPUT
        results = ET.Element("test-run", testcasecount="3", total="3", passed="3", failed="0",
                             skipped="0", inconclusive="0", warnings="0", result="Passed")
        results.extend(leaf(name) for name in names)
        ET.SubElement(results, "output").text = LARGE_OUTPUT
        native_discovery, native_results = (ET.tostring(tree, encoding="unicode") for tree in (discovery, results))
        trx = ET.fromstring(fixtures.trx(total=3))
        trx_results = trx.find(NS + "Results")
        trx_results.clear()
        for name in names:
            ET.SubElement(trx_results, NS + "UnitTestResult", testName=name, outcome="Passed")
        counters = trx.find(NS + "ResultSummary/" + NS + "Counters")
        counters.set("executed", "3")
        counters.set("passed", "3")
        native_trx = ET.tostring(trx, encoding="unicode")
        dump = self.source.parent / "Dump/D_Demo.Tests.dll.dump"

        def process(argv, root, stdout, stderr, timeout):
            if "--list-tests" in argv:
                dump.parent.mkdir(parents=True)
                dump.write_text(native_discovery, encoding="utf-8")
            else:
                (stdout.parent / "result.trx").write_text(native_trx, encoding="utf-8")
                (stdout.parent / "Demo.Tests.xml").write_text(native_results, encoding="utf-8")
            return 0, "synthetic NUnit output"

        self.assertGreater(len(native_discovery), 5_000_000)
        self.assertGreater(len(native_results), 5_000_000)
        with mock.patch.object(self.runner, "_nunit_target", return_value=(dump, "Demo.Tests.xml")):
            code, report = self.run_native(process=process)
        self.assertEqual(code, 0)
        expected = ["tests/Demo.Tests/Demo.Tests.csproj|net8.0|" + name for name in names]
        self.assertEqual(report["collected"], expected)
        self.assertEqual([item["id"] for item in report["results"]], expected)

    def test_reader_checks_byte_size_before_opening_and_detects_growth_during_read(self):
        path = self.folder / "large.trx"
        path.write_text("<TestRun />", encoding="utf-8")
        oversized = SimpleNamespace(st_mode=stat.S_IFREG, st_file_attributes=0, st_size=64 * 1024 * 1024 + 1)
        with mock.patch.object(Path, "lstat", return_value=oversized), mock.patch.object(
                Path, "open", side_effect=AssertionError("Oversized input must not be read")):
            with self.assertRaisesRegex(self.runner.DotnetError, "Oversized TRX.*64 MiB"):
                self.runner._read_native_xml(path, "TRX")
        # A stat/read race still cannot return evidence past the native bound.
        limit = self.runner.NATIVE_XML_MAX_BYTES
        before_growth = SimpleNamespace(st_mode=stat.S_IFREG, st_file_attributes=0, st_size=8)
        with mock.patch.object(self.runner, "NATIVE_XML_MAX_BYTES", 8), mock.patch.object(
                Path, "lstat", return_value=before_growth):
            with self.assertRaisesRegex(self.runner.DotnetError, "Oversized TRX"):
                self.runner._read_native_xml(path, "TRX")
        self.assertEqual(limit, 64 * 1024 * 1024)

    def test_reader_distinguishes_missing_unsafe_and_oversized_xml(self):
        with self.assertRaisesRegex(self.runner.DotnetError, "Missing fresh TRX"):
            self.runner._read_native_xml(self.folder / "missing.trx", "TRX")
        with self.assertRaisesRegex(self.runner.DotnetError, "Unsafe TRX"):
            self.runner._read_native_xml(self.folder, "TRX")
        with mock.patch.object(Path, "lstat", side_effect=PermissionError("synthetic inaccessible file")):
            with self.assertRaisesRegex(self.runner.DotnetError, "Unsafe TRX"):
                self.runner._read_native_xml(self.folder / "blocked.trx", "TRX")

    def test_xml_reader_rejects_symlink_or_junction_ancestors(self):
        target = self.folder / "target"
        target.mkdir()
        (target / "result.trx").write_text("<TestRun />", encoding="utf-8")
        alias = self.folder / "alias"
        try:
            alias.symlink_to(target, target_is_directory=True)
        except OSError:
            if os.name != "nt":
                self.skipTest("Directory link privilege unavailable")
            result = subprocess.run(["cmd", "/c", "mklink", "/J", str(alias), str(target)], capture_output=True)
            if result.returncode:
                self.skipTest("Directory junction privilege unavailable")
        with self.assertRaisesRegex(self.runner.DotnetError, "Unsafe TRX"):
            self.runner._read_native_xml(alias / "result.trx", "TRX")


if __name__ == "__main__":
    unittest.main()
