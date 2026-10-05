"""Native coverage proofs follow TRX attachments rather than unrelated copies."""
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET


KIT = Path(__file__).resolve().parents[3]
loader = importlib.util.spec_from_file_location("dotnet_demo_coverage", KIT / "scripts/dotnet_demo.py")
demo = importlib.util.module_from_spec(loader)
loader.loader.exec_module(demo)
TRX_NS = "http://microsoft.com/schemas/VisualStudio/TeamTest/2010"


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
