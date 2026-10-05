"""Deferred xUnit rows retain native identity and independent TRX counts."""
from collections import Counter
import copy
import importlib.util
import unittest
import xml.etree.ElementTree as ET

import test_dotnet_runner as fixtures


NS = "{http://microsoft.com/schemas/VisualStudio/TeamTest/2010}"


def theory_events(outcomes=("test-passed", "test-failed", "test-skipped")):
    original = fixtures.messages()
    events = copy.deepcopy(original[:2])
    for index, outcome in enumerate(outcomes):
        row = fixtures.messages(outcome)[2:5]
        for event in row:
            event["TestUniqueID"] = "native-row-" + str(index)
            if "TestDisplayName" in event:
                event["TestDisplayName"] = "same truncated row display"
        events.extend(row)
    counts = Counter(outcomes)
    for event in copy.deepcopy(original[5:]):
        event.update(TestsTotal=len(outcomes), TestsFailed=counts["test-failed"],
                     TestsSkipped=counts["test-skipped"], TestsNotRun=counts["test-not-run"])
        events.append(event)
    return events


def theory_trx(outcomes=("Passed", "Failed", "NotExecuted")):
    tree = ET.fromstring(fixtures.xunit_trx())
    results = tree.find(NS + "Results")
    template = copy.deepcopy(results[0])
    results.clear()
    for index, outcome in enumerate(outcomes):
        row = copy.deepcopy(template)
        row.set("executionId", f"00000000-0000-0000-0000-{index + 1:012d}")
        row.set("outcome", outcome)
        results.append(row)
    counters = tree.find(NS + "ResultSummary/" + NS + "Counters")
    counters.set("total", str(len(outcomes)))
    counters.set("executed", str(sum(row != "NotExecuted" for row in outcomes)))
    counters.set("passed", str(outcomes.count("Passed")))
    counters.set("failed", str(outcomes.count("Failed")))
    return ET.tostring(tree, encoding="unicode")


class RuntimeTheoryEvidenceTests(unittest.TestCase):
    def setUp(self):
        loader = importlib.util.spec_from_file_location("runtime_theory_runner", fixtures.SCRIPTS / "dotnet_runner.py")
        self.runner = importlib.util.module_from_spec(loader)
        loader.loader.exec_module(self.runner)
        self.inventory = self.runner.discovery_cases(fixtures.discovery_trace())

    def report(self, events=None, xml=None):
        return self.runner.reconcile("tests/Demo.csproj", "net8.0", self.inventory,
                                     fixtures.console(events or theory_events()), xml or theory_trx(), runtime_theories=True)

    def test_runtime_rows_keep_native_parent_child_ids_and_typed_outcomes(self):
        report = self.report()
        expected = ["tests/Demo.csproj|net8.0|xunit:case|test:native-row-" + str(index) for index in range(3)]
        self.assertEqual(report["collected"], expected)
        self.assertEqual([row["id"] for row in report["results"]], expected)
        self.assertEqual([row["native_test_id"] for row in report["results"]], ["native-row-0", "native-row-1", "native-row-2"])
        self.assertEqual([row["status"] for row in report["results"]], ["passed", "failed", "skipped"])
        self.assertEqual(report["results"][1]["exception"], "AssertionError")
        self.assertEqual({row["native_case_id"] for row in report["results"]}, {"case"})
        self.assertEqual({row["vstest_id"] for row in report["results"]}, {fixtures.VS_ID})
        self.assertTrue(all("trx_execution_id" not in row for row in report["results"]), "Native adapter has no child to TRX row linkage")

    def test_parent_outcome_multiset_is_independent_of_trx_row_order_or_names(self):
        report = self.report(xml=theory_trx(("NotExecuted", "Passed", "Failed")))
        self.assertEqual(len(report["results"]), 3)
        with self.assertRaises(self.runner.DotnetError):
            self.report(xml=theory_trx(("Passed", "Passed", "Failed")))

    def test_unknown_parent_missing_row_and_duplicate_child_cannot_be_accepted(self):
        unknown, duplicate, missing = theory_events(), theory_events(), theory_events()
        unknown[1]["TestCaseUniqueID"] = "unknown-parent"
        for event in duplicate[5:8]:
            event["TestUniqueID"] = "native-row-0"
        missing.pop(7)
        for events in (unknown, duplicate, missing):
            with self.subTest(events=events), self.assertRaises(self.runner.DotnetError):
                self.report(events)

    def test_wrong_source_method_parent_execution_and_duplicate_trx_execution_fail(self):
        for transform in (
            lambda raw: raw.replace('name="Total"', 'name="Other"'),
            lambda raw: raw.replace('codeBase="', 'codeBase="other'),
            lambda raw: raw.replace('000000000001', '000000000002'),
            lambda raw: raw.replace('id="00000000-0000-0000-0000-000000000001"', 'id="00000000-0000-0000-0000-000000000009"'),
        ):
            with self.subTest(transform=transform), self.assertRaises(self.runner.DotnetError):
                self.report(xml=transform(theory_trx()))

    def test_each_parent_and_whole_assembly_counts_must_cover_every_row(self):
        for index in (-2, -1):
            events = theory_events()
            events[index]["TestsTotal"] -= 1
            with self.subTest(index=index), self.assertRaises(self.runner.DotnetError):
                self.report(events)

    def test_ordinary_legacy_reconcile_does_not_silently_change_inventory_ids(self):
        legacy = self.runner.reconcile("tests/Demo.csproj", "net8.0", self.inventory,
                                       fixtures.console(fixtures.messages()), fixtures.xunit_trx())
        self.assertEqual(legacy["collected"], ["tests/Demo.csproj|net8.0|xunit:case"])

    def test_children_and_case_finish_keep_their_observed_native_ancestry(self):
        for index in (2, 3, 4, -2):
            for field in ("TestCollectionUniqueID", "TestClassUniqueID", "TestMethodUniqueID"):
                events = theory_events()
                events[index][field] = "different-parent"
                with self.subTest(index=index, field=field), self.assertRaises(self.runner.DotnetError):
                    self.report(events)

    def test_global_counts_cannot_hide_outcomes_transferred_between_parents(self):
        other_id = "00000000-0000-0000-0000-000000000009"
        self.inventory = self.runner.discovery_cases(fixtures.discovery_trace([
            fixtures.discovered(), fixtures.discovered("second-case", other_id)]))
        second = theory_events(("test-passed",) * 3)
        for event in second:
            if "TestCaseUniqueID" in event:
                event["TestCaseUniqueID"] = "second-case"
            if "TestUniqueID" in event:
                event["TestUniqueID"] = "second-" + event["TestUniqueID"]
        events = theory_events()[:-1] + second[1:]
        events[-1].update(TestsTotal=6, TestsFailed=1, TestsSkipped=1)
        tree, second_tree = ET.fromstring(theory_trx()), ET.fromstring(theory_trx(("Passed",) * 3))
        for node in second_tree.iter():
            for key in ("testId", "id"):
                if node.get(key) == fixtures.VS_ID:
                    node.set(key, other_id)
            for key in ("executionId", "id") if node.tag == NS + "Execution" else ("executionId",):
                if node.get(key, "").startswith("00000000-0000-0000-0000-00000000000"):
                    node.set(key, node.get(key)[:-2] + str(int(node.get(key)[-2:]) + 10))
        for name in ("Results", "TestDefinitions"):
            tree.find(NS + name).extend(second_tree.find(NS + name))
        counters = tree.find(NS + "ResultSummary/" + NS + "Counters")
        counters.set("total", "6")
        counters.set("executed", "5")
        counters.set("passed", "4")
        self.assertEqual(len(self.report(events, ET.tostring(tree, encoding="unicode"))["results"]), 6)
        rows = tree.find(NS + "Results")
        rows[1].set("outcome", "Passed")
        rows[3].set("outcome", "Failed")
        with self.assertRaises(self.runner.DotnetError):
            self.report(events, ET.tostring(tree, encoding="unicode"))

    def test_trx_hidden_nested_rows_and_unsupported_result_kinds_are_rejected(self):
        for mutation in ("nested", "other-kind", "extra-container"):
            tree = ET.fromstring(theory_trx())
            results = tree.find(NS + "Results")
            if mutation == "nested":
                inner = ET.SubElement(results[0], NS + "InnerResults")
                inner.append(copy.deepcopy(results[0]))
            elif mutation == "other-kind":
                ET.SubElement(results, NS + "GenericTestResult", outcome="Passed")
            else:
                ET.SubElement(tree, NS + "Results")
            with self.subTest(mutation=mutation), self.assertRaises(self.runner.DotnetError):
                self.report(xml=ET.tostring(tree, encoding="unicode"))

    def test_fully_reconciled_policy_failure_stays_error_and_has_machine_code(self):
        events = theory_events(("test-failed",))
        failure = events[3]
        # An assertion wrapper cannot turn an OS policy failure into RED.
        failure.update(ExceptionTypes=["Xunit.Sdk.ThrowsException", "System.IO.FileLoadException"],
                       ExceptionParentIndices=[-1, 0], Messages=["assertion wrapper", "localized text (0x800711C7)"],
                       StackTraces=["at Demo.Checks.Total()", "at Demo.Checks.Total()"])
        result = self.report(events, theory_trx(("Failed",)))["results"][0]
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["exception"], "System.IO.FileLoadException")
        self.assertEqual(result["native_failure_code"], "application_control_blocked")
        self.assertEqual(result["native_hresult"], "0x800711C7")


if __name__ == "__main__":
    unittest.main()
