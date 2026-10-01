"""Run an actual deterministic TDD demonstration without an LLM or dependencies."""
import argparse
import importlib.util
import json
from pathlib import Path
import tempfile

KIT = Path(__file__).resolve().parents[1]
PLUGIN = KIT / "plugins/ai-tdd"
loader = importlib.util.spec_from_file_location("ai_tdd", PLUGIN / "scripts/tdd.py")
module = importlib.util.module_from_spec(loader)
loader.loader.exec_module(module)


def run_demo(root):
    (root / "src").mkdir()
    (root / "tests").mkdir()
    (root / ".ai-tdd").mkdir()
    config = json.loads((PLUGIN / "templates/config.unittest.json").read_text())
    (root / ".ai-tdd/config.json").write_text(json.dumps(config))
    spec = json.loads((PLUGIN / "templates/spec.example.json").read_text())
    (root / ".ai-tdd/spec.json").write_text(json.dumps(spec))
    plan = {"scenarios": [{"ac": item["id"], "case": case} for item, case in zip(spec["acceptance"], ["0 and 9999 without membership", "10000 and 10001", "zero and positive member carts", "-1 for both member flags"])]}
    (root / ".ai-tdd/review-plan.json").write_text(json.dumps(plan))
    source = root / "src/fee.py"
    tests = root / "tests/test_fee.py"
    source.write_text("def shipping_fee(cents, member=False):\n    return 799\n")
    tests.write_text("import unittest\nfrom src.fee import shipping_fee\n\nclass FeeTests(unittest.TestCase):\n    def test_baseline(self):\n        self.assertEqual(shipping_fee(100), 799)\n")
    c = module.Controller(root)
    c.begin()
    steps = [
        ("threshold", "AC2", "self.assertEqual(shipping_fee(10000), 0)", "def shipping_fee(cents, member=False):\n    return 0 if cents >= 10000 else 799\n"),
        ("member", "AC3", "self.assertEqual(shipping_fee(0, True), 0)", "def shipping_fee(cents, member=False):\n    return 0 if member or cents >= 10000 else 799\n"),
        ("negative_member", "AC4", "with self.assertRaises(ValueError):\n            shipping_fee(-1, True)", "def shipping_fee(cents, member=False):\n    if cents < 0:\n        raise ValueError('negative cart')\n    return 0 if member or cents >= 10000 else 799\n")
    ]
    for index, (name, ac, assertion, implementation) in enumerate(steps):
        if index:
            c.next()
        with tests.open("a") as stream:
            stream.write(f"\n    def test_{name}(self):\n        {assertion}\n")
        c.red(tests=["test_fee.FeeTests.test_" + name], ac=[ac], expect="AssertionError", because="Literal independent example from " + ac)
        source.write_text(implementation)
        c.green()
    c.next()
    with tests.open("a") as stream:
        stream.write("\n    def test_lower_boundary(self):\n        self.assertEqual(shipping_fee(9999), 799)\n")
    c.cover(tests=["test_fee.FeeTests.test_lower_boundary"], ac=["AC1"], because="Independent lower-boundary example already holds")
    correct = source.read_text()
    mutants = {
        "exclusive_threshold": correct.replace("cents >= 10000", "cents > 10000"),
        "membership_before_validation": "def shipping_fee(cents, member=False):\n    if member:\n        return 0\n    if cents < 0:\n        raise ValueError('negative cart')\n    return 0 if cents >= 10000 else 799\n"
    }
    killed = {}
    try:
        for name, mutation in mutants.items():
            source.write_text(mutation)
            receipt = c.run("selected-mutant")
            killed[name] = [item["id"] for item in receipt["results"] if item["status"] != "passed"]
            if not killed[name]:
                raise RuntimeError("Selected mutant survived: " + name)
    finally:
        source.write_text(correct)
    c.verify()
    review = {"receipt_id": c.state["green_receipt"]["id"], "checked_ac": [item["id"] for item in spec["acceptance"]],
              "findings": [], "limitations": ["Synthetic pure function; deterministic role simulation; two selected mutants, no completeness claim"], "recommendation": "accept"}
    (root / ".ai-tdd/review.json").write_text(json.dumps(review))
    result = c.finish()
    return {"phase": result["phase"], "red_cycles": 3, "existing_coverage_cycles": 1,
            "executed_tests": len(result["completion_receipt"]["results"]), "selected_mutants_killed": killed,
            "note": "Real test executions; this script simulates role edits and does not call an AI."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="ai-tdd-demo-") as folder:
        value = run_demo(Path(folder))
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2) + "\n")
    print(json.dumps(value, indent=2))


if __name__ == "__main__":
    main()
