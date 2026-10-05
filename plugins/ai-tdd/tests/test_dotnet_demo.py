"""Native coverage proofs follow TRX attachments rather than unrelated copies."""
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import uuid
from unittest import mock
import xml.etree.ElementTree as ET


KIT = Path(__file__).resolve().parents[3]
loader = importlib.util.spec_from_file_location("dotnet_demo_coverage", KIT / "scripts/dotnet_demo.py")
demo = importlib.util.module_from_spec(loader)
loader.loader.exec_module(demo)
TRX_NS = "http://microsoft.com/schemas/VisualStudio/TeamTest/2010"


class RuntimeTheoryProofTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ai-tdd-runtime-theory-proof-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.directory = self.root / ".ai-tdd/native/0"
        self.directory.mkdir(parents=True)
        self.parents = {"objects": {"vstest_id": str(uuid.uuid4()), "source": str(self.root / "tests/bin/Demo.dll"),
                                  "executor_uri": "executor://xunit/VsTestRunner3/netcore/", "method": "Demo.DeferredTheories.Objects"},
                        "fact": {"vstest_id": str(uuid.uuid4()), "source": str(self.root / "tests/bin/Demo.dll"),
                                 "executor_uri": "executor://xunit/VsTestRunner3/netcore/", "method": "Demo.Checks.Baseline"}}
        cases = [{"Id": value["vstest_id"], "Source": value["source"], "ExecutorUri": value["executor_uri"],
                  "FullyQualifiedName": value["method"], "DisplayName": value["method"],
                  "Properties": [{"Key": {"Id": "XunitTestCaseUniqueID"}, "Value": parent}]}
                 for parent, value in self.parents.items()]
        payload = {"TotalTests": 2, "LastDiscoveredTests": cases, "IsAborted": False,
                   "FullyDiscoveredSources": [self.parents["objects"]["source"]], "PartiallyDiscoveredSources": [],
                   "NotDiscoveredSources": [], "SkippedDiscoverySources": []}
        event = {"Version": 7, "MessageType": "TestDiscovery.Completed", "Payload": payload}
        (self.directory / "discovery.diag.log").write_text(
            "TpTrace Verbose: 0 : 1, TestRequestSender.OnDiscoveryMessageReceived: Received message: " + json.dumps(event), encoding="utf-8")
        self.report = {"schema": 1, "collected": [], "results": [], "native_modules": [
            {"project": "tests/Demo.csproj", "tfm": "net8.0", "directory": ".ai-tdd/native/0"}]}
        for parent, children in (("objects", 3), ("fact", 1)):
            for index in range(children):
                child = parent + "-child-" + str(index)
                row = {"id": "tests/Demo.csproj|net8.0|xunit:" + parent + "|test:" + child,
                       "native_case_id": parent, "native_test_id": child, "vstest_id": self.parents[parent]["vstest_id"],
                       "display_name": "duplicate object" if parent == "objects" else "baseline", "status": "passed"}
                self.report["results"].append(row)
                self.report["collected"].append(row["id"])
        self.write_trx()

    def write_trx(self, corrupt_outcome=False, duplicate_execution=False):
        tree = ET.Element("TestRun", xmlns=TRX_NS)
        results, definitions = ET.SubElement(tree, "Results"), ET.SubElement(tree, "TestDefinitions")
        first_executions = {}
        for index, row in enumerate(self.report["results"]):
            execution = "00000000-0000-0000-0000-" + str(1 if duplicate_execution else index + 1).zfill(12)
            first_executions.setdefault(row["vstest_id"], execution)
            ET.SubElement(results, "UnitTestResult", testId=row["vstest_id"], executionId=execution,
                          testName="Deliberately unrelated display name", outcome="Failed" if corrupt_outcome and index == 0 else "Passed")
        for parent in self.parents.values():
            definition = ET.SubElement(definitions, "UnitTest", id=parent["vstest_id"])
            ET.SubElement(definition, "Execution", id=first_executions[parent["vstest_id"]])
            klass, method = parent["method"].rsplit(".", 1)
            ET.SubElement(definition, "TestMethod", className=klass, name=method,
                          codeBase=parent["source"], adapterTypeName=parent["executor_uri"])
        (self.directory / "result.trx").write_text(ET.tostring(tree, encoding="unicode"), encoding="utf-8")

    def test_proof_counts_parent_discovery_separately_from_runtime_rows_without_display_joins(self):
        proof = demo.native_identity_checks(self.root, self.report, previous=self.report)
        self.assertEqual(proof["discovered_parent_cases"], 2)
        self.assertEqual(proof["executed_native_rows"], 4)
        self.assertEqual(proof["expanded_parent_cases"], 1)
        self.assertTrue(proof["aggregate_trx_binding_proven"])
        self.assertTrue(proof["unchanged_run_child_ids_stable"])

    def test_proof_rejects_aggregate_trx_outcome_corruption_and_duplicate_execution_ids(self):
        for corrupt, duplicate in ((True, False), (False, True)):
            self.write_trx(corrupt, duplicate)
            with self.subTest(corrupt=corrupt, duplicate=duplicate), self.assertRaisesRegex(RuntimeError, "TRX"):
                demo.native_identity_checks(self.root, self.report)

    def test_proof_rejects_changed_child_identity_across_unchanged_runs(self):
        previous = json.loads(json.dumps(self.report))
        previous["results"][0]["native_test_id"] = "different-child"
        previous["results"][0]["id"] += "different-child"
        with self.assertRaisesRegex(RuntimeError, "child identities changed"):
            demo.native_identity_checks(self.root, self.report, previous=previous)

    def test_incomplete_native_envelope_preserves_diagnostic_before_coverage_proofs(self):
        def incomplete(root, path):
            path.write_text(json.dumps({"schema": 1, "completion": "incomplete", "planned_module_count": 1,
                "collected": [], "results": [], "native_modules": [{"directory": ".ai-tdd/native/0", "status": "incomplete"}],
                "diagnostics": [{"kind": "build-discovery", "message": "synthetic compiler failure"}]}), encoding="utf-8")
            return 2
        with mock.patch.object(demo.RUNNER, "run", side_effect=incomplete), mock.patch.object(demo, "setup_diagnostics"):
            with self.assertRaisesRegex(demo.RUNNER.DotnetError, "synthetic compiler failure"):
                demo.native(self.root)


class SyntheticFailureArtifactsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ai-tdd-artifact-tests-")
        self.addCleanup(self.temp.cleanup)
        self.artifacts = Path(self.temp.name).resolve() / "artifacts"

    def create_logs(self, root):
        logs = root / "nunit-workflow/.ai-tdd/runs"
        logs.mkdir(parents=True)
        (logs / "missing-receipt.stderr.log").write_text(
            "Native testhost could not start: synthetic assembly load failure\n", encoding="utf-8")
        (logs / "missing-receipt.stdout.log").write_text("synthetic runner stdout\n", encoding="utf-8")
        (root / "nunit-workflow/Secret.cs").write_text("source must not be uploaded", encoding="utf-8")
        (root / "nuget-packages").mkdir()
        (root / "nuget-packages/cache.log").write_text("cache must not be uploaded", encoding="utf-8")
        (logs / "not-a-diagnostic.dll").write_bytes(b"binary must not be uploaded")
        return logs

    def test_missing_receipt_failure_retains_runner_stderr_without_uploading_source_or_caches(self):
        original = RuntimeError("Cannot read completion.json: FileNotFoundError")
        with mock.patch.dict(os.environ, {"AI_TDD_DEMO_FAILURE_ARTIFACTS": str(self.artifacts)}):
            with mock.patch("sys.stderr", new_callable=io.StringIO), self.assertRaises(RuntimeError) as caught:
                with demo.fixture_directory() as root:
                    self.addCleanup(lambda: demo.shutil.rmtree(root, ignore_errors=True))
                    self.create_logs(root)
                    raise original
        self.assertIs(caught.exception, original)
        retained = self.artifacts / root.name
        log = retained / "nunit-workflow/.ai-tdd/runs/missing-receipt.stderr.log"
        self.assertIn("synthetic assembly load failure", log.read_text(encoding="utf-8"))
        manifest = json.loads((retained / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["scope"], "generated-public-dotnet-fixture")
        self.assertEqual(manifest["error_type"], "RuntimeError")
        self.assertEqual({item["path"] for item in manifest["files"]}, {
            "nunit-workflow/.ai-tdd/runs/missing-receipt.stderr.log",
            "nunit-workflow/.ai-tdd/runs/missing-receipt.stdout.log"})
        self.assertFalse((retained / "nunit-workflow/Secret.cs").exists())
        self.assertFalse((retained / "nuget-packages").exists())
        self.assertFalse((retained / "nunit-workflow/.ai-tdd/runs/not-a-diagnostic.dll").exists())
        self.assertTrue(root.is_dir(), "Original synthetic failure fixture remains available locally")

    def test_capture_failure_does_not_mask_the_native_failure(self):
        self.artifacts.parent.mkdir(parents=True, exist_ok=True)
        self.artifacts.write_text("blocked artifact directory", encoding="utf-8")
        original = RuntimeError("original native failure")
        with mock.patch.dict(os.environ, {"AI_TDD_DEMO_FAILURE_ARTIFACTS": str(self.artifacts)}):
            with mock.patch("sys.stderr", new_callable=io.StringIO) as stderr, self.assertRaises(RuntimeError) as caught:
                with demo.fixture_directory() as root:
                    self.addCleanup(lambda: demo.shutil.rmtree(root, ignore_errors=True))
                    self.create_logs(root)
                    raise original
        self.assertIs(caught.exception, original)
        self.assertIn("Could not collect synthetic failure artifacts", stderr.getvalue())

    def test_success_removes_fixture_and_produces_no_failure_upload(self):
        with mock.patch.dict(os.environ, {"AI_TDD_DEMO_FAILURE_ARTIFACTS": str(self.artifacts)}):
            with demo.fixture_directory() as root:
                self.create_logs(root)
        self.assertFalse(root.exists())
        self.assertFalse(self.artifacts.exists())

    def test_failure_capture_stays_local_when_ci_has_not_opted_in(self):
        with mock.patch.dict(os.environ, {"AI_TDD_DEMO_FAILURE_ARTIFACTS": ""}):
            with mock.patch("sys.stderr", new_callable=io.StringIO), self.assertRaisesRegex(RuntimeError, "synthetic"):
                with demo.fixture_directory() as root:
                    self.addCleanup(lambda: demo.shutil.rmtree(root, ignore_errors=True))
                    self.create_logs(root)
                    raise RuntimeError("synthetic")
        self.assertTrue(root.is_dir())
        self.assertFalse(self.artifacts.exists())

    def test_capture_is_opt_in_and_never_walks_an_arbitrary_repository(self):
        external = Path(self.temp.name) / "ordinary-repository"
        external.mkdir()
        self.create_logs(external)
        with self.assertRaisesRegex(RuntimeError, "created synthetic fixture"):
            demo.collect_failure_artifacts(external, self.artifacts, RuntimeError("failure"))
        self.assertFalse(self.artifacts.exists())

    def test_large_log_preserves_error_tail_with_explicit_truncation(self):
        with mock.patch.dict(os.environ, {"AI_TDD_DEMO_FAILURE_ARTIFACTS": str(self.artifacts)}):
            with mock.patch("sys.stderr", new_callable=io.StringIO), self.assertRaisesRegex(RuntimeError, "synthetic"):
                with demo.fixture_directory() as root:
                    self.addCleanup(lambda: demo.shutil.rmtree(root, ignore_errors=True))
                    logs = self.create_logs(root)
                    log = logs / "missing-receipt.stderr.log"
                    log.write_bytes(b"x" * (2 * 1024 * 1024) + b"\nFinal synthetic testhost error\n")
                    raise RuntimeError("synthetic")
        retained = self.artifacts / root.name
        copied = retained / "nunit-workflow/.ai-tdd/runs/missing-receipt.stderr.log"
        self.assertLessEqual(copied.stat().st_size, 1024 * 1024)
        self.assertTrue(copied.read_bytes().endswith(b"Final synthetic testhost error\n"))
        manifest = json.loads((retained / "manifest.json").read_text(encoding="utf-8"))
        entry = next(item for item in manifest["files"] if item["path"].endswith("stderr.log"))
        self.assertTrue(entry["truncated"])
        self.assertGreater(entry["original_bytes"], entry["copied_bytes"])

    def test_file_budget_keeps_subprocess_stderr_and_declares_incomplete_capture(self):
        with demo.fixture_directory() as root:
            logs = self.create_logs(root)
            for index in range(300):
                (logs / ("earlier-" + str(index) + ".stdout.log")).write_text("synthetic", encoding="utf-8")
            retained = demo.collect_failure_artifacts(root, self.artifacts, RuntimeError("failure"))
        manifest = json.loads((retained / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(len(manifest["files"]), 256)
        self.assertTrue(manifest["limit_reached"])
        self.assertTrue((retained / "nunit-workflow/.ai-tdd/runs/missing-receipt.stderr.log").is_file())

    def test_redirected_diagnostic_directory_never_copies_external_logs(self):
        with demo.fixture_directory() as root:
            logs = self.create_logs(root)
            external = Path(self.temp.name).resolve() / "outside"
            external.mkdir()
            (external / "private.stderr.log").write_text("external file must remain local", encoding="utf-8")
            link = logs / "redirected"
            try:
                if os.name == "nt":
                    result = subprocess.run(["cmd", "/d", "/c", "mklink", "/J", str(link), str(external)], capture_output=True, text=True)
                    if result.returncode:
                        self.skipTest("Native Windows junction creation is unavailable")
                else:
                    link.symlink_to(external, target_is_directory=True)
            except OSError:
                self.skipTest("Directory link creation is unavailable")
            retained = demo.collect_failure_artifacts(root, self.artifacts, RuntimeError("failure"))
            self.assertFalse((retained / "nunit-workflow/.ai-tdd/runs/redirected").exists())
            self.assertTrue((external / "private.stderr.log").is_file())


class AbsentExternalContentProofTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ai-tdd-absent-content-proof-")
        self.addCleanup(self.temp.cleanup)
        self.sandbox = Path(self.temp.name).resolve()
        self.root = self.sandbox / "project"
        (self.root / ".ai-tdd").mkdir(parents=True)
        self.external = self.sandbox / "absent-ancestor/.dockerignore"
        (self.root / ".ai-tdd/external-absent-input.json").write_text(
            json.dumps({"path": str(self.external)}), encoding="utf-8")
        self.write_config([str(self.external)])

    def write_config(self, paths):
        (self.root / ".ai-tdd/config.json").write_text(
            json.dumps({"dotnet": {"external_absent_inputs": paths}}), encoding="utf-8")

    def test_proof_requires_exactly_the_expected_bound_absent_path(self):
        proof = demo.verify_external_absent_input(self.root)
        self.assertEqual(proof["external_absent_input_count"], 1)
        self.assertTrue(proof["project_authored_absent_content_bound"])
        self.assertTrue(proof["external_absent_inputs_still_absent"])
        for paths in ([], [str(self.sandbox / "other")], [str(self.external), str(self.sandbox / "other")]):
            with self.subTest(paths=paths):
                self.write_config(paths)
                with self.assertRaisesRegex(RuntimeError, "exactly the expected absent external input"):
                    demo.verify_external_absent_input(self.root)

    def test_creating_the_bound_input_invalidates_final_absence_proof(self):
        demo.verify_external_absent_input(self.root)
        self.external.parent.mkdir()
        self.external.write_text("synthetic newly present external input\n", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "must remain absent"):
            demo.verify_external_absent_input(self.root)

    def test_only_fixture_setup_before_facade_init_can_defer_config_binding(self):
        (self.root / ".ai-tdd/config.json").unlink()
        proof = demo.verify_external_absent_input(self.root, require_config=False)
        self.assertTrue(proof["external_absent_inputs_still_absent"])
        self.assertFalse(proof["project_authored_absent_content_bound"])
        with self.assertRaisesRegex(RuntimeError, "evaluated native configuration"):
            demo.verify_external_absent_input(self.root)


class CoverageAttachmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ai-tdd-coverage-attachments-")
        self.addCleanup(self.temp.cleanup)
        self.sandbox = Path(self.temp.name).resolve()
        self.root = self.sandbox / "project"
        self.run = self.root / ".ai-tdd/native/0"
        self.run.mkdir(parents=True)
        self.attached = self.run / "native-run/In/agent/coverage.cobertura.xml"
        self.original = self.run / "collector-guid/coverage.cobertura.xml"
        self.write_coverage(self.attached, hits=2)
        self.write_coverage(self.original, hits=0)
        self.write_trx()

    def write_coverage(self, path, hits=1):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('<coverage><packages><package><classes><class name="Demo.Fee"><lines>'
                        '<line number="1" hits="' + str(hits) + '"/></lines></class></classes></package></packages></coverage>', encoding="utf-8")

    def write_trx(self, hrefs=("agent\\coverage.cobertura.xml",), deployment="native-run"):
        tree = ET.Element("TestRun", {"xmlns": TRX_NS})
        settings = ET.SubElement(tree, "TestSettings")
        ET.SubElement(settings, "Deployment", {"runDeploymentRoot": deployment})
        summary = ET.SubElement(tree, "ResultSummary")
        collectors = ET.SubElement(summary, "CollectorDataEntries")
        collector = ET.SubElement(collectors, "Collector", {
            "uri": "datacollector://microsoft/CoverletCodeCoverage/1.0", "agentName": "agent"})
        attachments = ET.SubElement(collector, "UriAttachments")
        for href in hrefs:
            attachment = ET.SubElement(attachments, "UriAttachment")
            ET.SubElement(attachment, "A", {"href": href})
        (self.run / "result.trx").write_text(ET.tostring(tree, encoding="unicode"), encoding="utf-8")

    def proof(self):
        return demo.coverage_checks(self.root, [self.run.relative_to(self.root).as_posix()])

    def test_two_physical_copies_validate_only_the_referenced_trx_attachment(self):
        proof = self.proof()
        self.assertEqual(proof["coverage_attached_runs"], 1)
        self.assertTrue(proof["coverage_feature_hit_proven"])
        self.assertEqual(proof["coverage_reports"][0]["coverage_attachment"], self.attached.relative_to(self.root).as_posix())

    def test_missing_referenced_report_cannot_use_unreferenced_original(self):
        self.attached.unlink()
        self.write_coverage(self.original, hits=2)
        with self.assertRaisesRegex(RuntimeError, "referenced coverage attachment"):
            self.proof()

    def test_attachment_and_deployment_paths_must_stay_inside_fresh_native_directory(self):
        external = self.sandbox / "external/coverage.cobertura.xml"
        self.write_coverage(external, hits=2)
        for href, deployment in ((str(external), "native-run"), ("../../../../external/coverage.cobertura.xml", "native-run"),
                                 ("agent/coverage.cobertura.xml", "../../outside"),
                                 ("https://example.com/coverage.cobertura.xml", "native-run")):
            with self.subTest(href=href, deployment=deployment):
                self.write_trx((href,), deployment)
                with self.assertRaisesRegex(RuntimeError, "Unsafe|relative"):
                    self.proof()

    def test_multiple_referenced_coverage_reports_are_ambiguous_even_if_identical(self):
        other = self.run / "native-run/In/other/coverage.cobertura.xml"
        self.write_coverage(other, hits=2)
        for hrefs in (("agent/coverage.cobertura.xml", "other/coverage.cobertura.xml"),
                      ("agent/coverage.cobertura.xml", "agent/coverage.cobertura.xml")):
            with self.subTest(hrefs=hrefs):
                self.write_trx(hrefs)
                with self.assertRaisesRegex(RuntimeError, "exactly one referenced coverage attachment"):
                    self.proof()

    def test_attached_report_must_prove_feature_execution_even_if_original_has_hits(self):
        self.write_coverage(self.attached, hits=0)
        self.write_coverage(self.original, hits=2)
        with self.assertRaisesRegex(RuntimeError, "witness execution"):
            self.proof()

    def test_redirected_attachment_directory_is_rejected(self):
        self.attached.unlink()
        link = self.attached.parent
        link.rmdir()
        external = self.sandbox / "external"
        self.write_coverage(external / "coverage.cobertura.xml", hits=2)
        self.assertIn(self.sandbox, link.absolute().parents)
        self.assertIn(self.sandbox, external.absolute().parents)
        try:
            if os.name == "nt":
                result = subprocess.run(["cmd", "/d", "/c", "mklink", "/J", str(link), str(external)], capture_output=True, text=True)
                if result.returncode:
                    self.skipTest("Native Windows junction creation is unavailable")
            else:
                link.symlink_to(external, target_is_directory=True)
        except OSError:
            self.skipTest("Directory link creation is unavailable")
        with self.assertRaisesRegex(RuntimeError, "Unsafe referenced coverage attachment"):
            self.proof()


if __name__ == "__main__":
    unittest.main()
