"""Run deliberately constructed weak/strong test examples with stdlib unittest.

Shipping contract: negative carts raise ValueError, including for members;
valid members and carts of at least 10000 cents ship free; other carts cost
799 cents. A quote totals the cart and its shipping fee.

These examples illustrate selected defects, not an LLM benchmark, a universal
mutation score, or a guarantee about other tests. No AI or network calls occur.
"""

import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from textwrap import dedent, indent


SHIPPING = dedent("""\
    def shipping_fee(cents, member=False):
        if cents < 0:
            raise ValueError("negative cart")
        return 0 if member or cents >= 10000 else 799
""")

QUOTE = dedent("""\

    def quote_total(cents, member=False, fee_calculator=shipping_fee):
        fee = fee_calculator(cents, member)
        return cents + fee
""")

CORRECT = SHIPPING + QUOTE

# The child reports unittest outcomes, rather than inferring kills from exit 1.
RUNNER = dedent("""\
    import json
    from pathlib import Path
    import sys
    import unittest

    sys.path.insert(0, str(Path(__file__).resolve().parent))

    class RecordedResult(unittest.TestResult):
        def __init__(self):
            super().__init__()
            self.records = []

        def record(self, test, status, error=None):
            record = {"test": test.id(), "status": status}
            if error is not None:
                record["exception"] = error[0].__name__
                record["message"] = str(error[1])
            self.records.append(record)

        def addSuccess(self, test):
            super().addSuccess(test)
            self.record(test, "passed")

        def addFailure(self, test, error):
            super().addFailure(test, error)
            self.record(test, "failed", error)

        def addError(self, test, error):
            super().addError(test, error)
            self.record(test, "error", error)

        def addSkip(self, test, reason):
            super().addSkip(test, reason)
            self.record(test, "skipped")

        def addExpectedFailure(self, test, error):
            super().addExpectedFailure(test, error)
            self.record(test, "expected_failure", error)

        def addUnexpectedSuccess(self, test):
            super().addUnexpectedSuccess(test)
            self.record(test, "unexpected_success")

    suite = unittest.defaultTestLoader.loadTestsFromName("test_cases")
    result = RecordedResult()
    suite.run(result)
    print(json.dumps({"tests_run": result.testsRun, "records": result.records}))
    raise SystemExit(0 if result.wasSuccessful() else 1)
""")


def suite_source(cases, call_spy=False):
    """Give every case one unittest test and one assertion of its own."""
    imports = "import unittest\n"
    if call_spy:
        imports += "from unittest.mock import Mock\n"
    imports += "from fee import quote_total, shipping_fee\n\n"
    body = "class ContractTests(unittest.TestCase):\n"
    for name, statement in cases:
        body += f"    def test_{name}(self):\n{indent(statement, '        ')}\n\n"
    return imports + body


def examples():
    return [
        {
            "id": "circular_assertions",
            "defect": "Shipping always costs 799, ignoring free shipping.",
            "weak_check": "Compare each fee to another call to that same fee.",
            "strong_check": "Compare the same inputs to literal contract amounts.",
            "faulty_source": "def shipping_fee(cents, member=False):\n    return 799\n" + QUOTE,
            "weak": suite_source([
                ("ordinary", "self.assertEqual(shipping_fee(0), shipping_fee(0))"),
                ("threshold", "self.assertEqual(shipping_fee(10000), shipping_fee(10000))"),
                ("member", "self.assertEqual(shipping_fee(0, True), shipping_fee(0, True))"),
            ]),
            "strong": suite_source([
                ("ordinary", "self.assertEqual(shipping_fee(0), 799)"),
                ("threshold", "self.assertEqual(shipping_fee(10000), 0)"),
                ("member", "self.assertEqual(shipping_fee(0, True), 0)"),
            ]),
        },
        {
            "id": "call_only_spy",
            "defect": "The quote calls the calculator but discards the returned fee.",
            "weak_check": "Assert only that the injected calculator was called.",
            "strong_check": "Assert literal total amounts with the real fee function.",
            "faulty_source": CORRECT.replace("return cents + fee", "return cents + fee * 0"),
            "weak": suite_source([
                (name, f"calculator = Mock(return_value={fee})\n"
                 f"quote_total({cart}, fee_calculator=calculator)\n"
                 f"calculator.assert_called_once_with({cart}, False)")
                for name, cart, fee in [
                    ("empty", 0, 799), ("ordinary", 8000, 799), ("threshold", 10000, 0)
                ]
            ], call_spy=True),
            "strong": suite_source([
                ("empty", "self.assertEqual(quote_total(0), 799)"),
                ("ordinary", "self.assertEqual(quote_total(8000), 8799)"),
                ("threshold", "self.assertEqual(quote_total(10000), 10000)"),
            ]),
        },
        {
            "id": "missing_threshold_boundary",
            "defect": "Free shipping starts above 10000 instead of at 10000.",
            "weak_check": "Assert ordinary inputs 0, 8000, and 20000.",
            "strong_check": "Assert 9999, 10000, and 10001 around the boundary.",
            "faulty_source": CORRECT.replace("cents >= 10000", "cents > 10000"),
            "weak": suite_source([
                ("empty", "self.assertEqual(shipping_fee(0), 799)"),
                ("ordinary", "self.assertEqual(shipping_fee(8000), 799)"),
                ("above_threshold", "self.assertEqual(shipping_fee(20000), 0)"),
            ]),
            "strong": suite_source([
                ("below_threshold", "self.assertEqual(shipping_fee(9999), 799)"),
                ("at_threshold", "self.assertEqual(shipping_fee(10000), 0)"),
                ("above_threshold", "self.assertEqual(shipping_fee(10001), 0)"),
            ]),
        },
        {
            "id": "missing_invalid_member_interaction",
            "defect": "Membership returns free shipping before validating a negative cart.",
            "weak_check": "Assert only valid carts, including a valid member.",
            "strong_check": "Require ValueError for negative carts with either membership flag.",
            "faulty_source": dedent("""\
                def shipping_fee(cents, member=False):
                    if member:
                        return 0
                    if cents < 0:
                        raise ValueError("negative cart")
                    return 0 if cents >= 10000 else 799
            """) + QUOTE,
            "weak": suite_source([
                ("ordinary", "self.assertEqual(shipping_fee(0), 799)"),
                ("member", "self.assertEqual(shipping_fee(0, True), 0)"),
                ("threshold", "self.assertEqual(shipping_fee(10000), 0)"),
            ]),
            "strong": suite_source([
                (name, f"with self.assertRaises(ValueError):\n    shipping_fee({cart}, {member})")
                for name, cart, member in [
                    ("negative_nonmember", -1, False),
                    ("negative_member", -1, True),
                    ("larger_negative_member", -10000, True),
                ]
            ]),
        },
    ]


def invalid_execution(reason, tests_run=0):
    return {"outcome": "invalid_execution", "tests_run": tests_run, "reason": reason}


def run_suite(source, tests, expected_count=3):
    """Execute isolated files; only completed assertion failures detect a defect."""
    try:
        with tempfile.TemporaryDirectory(prefix="ai-tdd-strength-") as folder:
            root = Path(folder)
            for name, content in [("fee.py", source), ("test_cases.py", tests), ("runner.py", RUNNER)]:
                (root / name).write_text(content, encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, "-I", "-S", "-B", "runner.py"],
                cwd=root,
                capture_output=True,
                encoding="utf-8",
                timeout=10,
                check=False,
            )
    except subprocess.TimeoutExpired:
        return invalid_execution("timeout; never counted as a detected defect")
    except OSError as error:
        return invalid_execution(f"execution failed: {type(error).__name__}")

    try:
        payload = json.loads(completed.stdout)
    except (json.JSONDecodeError, TypeError):
        return invalid_execution("runner produced no usable JSON outcome")
    if not isinstance(payload, dict):
        return invalid_execution("runner outcome is not an object")
    count = payload.get("tests_run")
    records = payload.get("records")
    if count != expected_count or not isinstance(records, list) or len(records) != count:
        return invalid_execution("the expected number of tests did not complete", count)
    if not all(isinstance(record, dict) for record in records):
        return invalid_execution("invalid unittest records", count)
    if len({record.get("test") for record in records}) != expected_count:
        return invalid_execution("tests did not produce distinct outcome records", count)
    errors = [record for record in records if record.get("status") not in {"passed", "failed"}]
    failures = [record for record in records if record.get("status") == "failed"]
    if errors or any(record.get("exception") != "AssertionError" for record in failures):
        value = invalid_execution("errors or non-assertion outcomes; never counted as a detected defect", count)
        value["evidence"] = errors + failures
        return value
    expected_exit = 1 if failures else 0
    if completed.returncode != expected_exit or completed.stderr:
        return invalid_execution("runner exit or stderr disagrees with unittest records", count)
    return {
        "outcome": "assertion_failure" if failures else "passed",
        "tests_run": count,
        "passed": count - len(failures),
        "failures": failures,
    }


def run_demo():
    results = []
    problems = []
    for example in examples():
        correct = {name: run_suite(CORRECT, example[name]) for name in ("weak", "strong")}
        faulty = {name: run_suite(example["faulty_source"], example[name]) for name in ("weak", "strong")}
        detected = faulty["strong"]["outcome"] == "assertion_failure"
        valid = (
            all(value["outcome"] == "passed" for value in correct.values())
            and faulty["weak"]["outcome"] == "passed"
            and detected
        )
        if not valid:
            problems.append(example["id"])
        results.append({
            "id": example["id"],
            "defect": example["defect"],
            "weak_check": example["weak_check"],
            "strong_check": example["strong_check"],
            "correct": correct,
            "faulty": faulty,
            "selected_defect_detected": detected,
            "comparison_valid": valid,
        })
    return {
        "demonstration": "deliberately_constructed_test_strength_examples",
        "status": "passed" if not problems else "failed",
        "execution": "stdlib unittest in fresh temporary projects; no AI or networking",
        "checks_per_suite": 3,
        "limits": [
            "Selected synthetic pure functions and deliberately constructed tests.",
            "Equal test counts do not imply equal input coverage or equal assertion quality.",
            "A call spy is meaningful when the contract requires that call; these quotes require correct totals.",
            "This is not an LLM benchmark, a universal mutation score, or a guarantee of fewer bugs.",
            "Import, compile, runtime, skipped-test, and timeout errors never count as detected defects.",
        ],
        "examples": results,
        "invalid_comparisons": problems,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="also save the JSON result to this file")
    args = parser.parse_args()
    result = run_demo()
    serialized = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized, encoding="utf-8")
    print(serialized, end="")
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
