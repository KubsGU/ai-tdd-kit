"""Frozen synthetic model-comparison contracts, hidden oracles and selected faults.

Oracle files are never copied to the model's project. They run afterwards in
isolated source copies. These are selected behavioral checks, not all-bug proof.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from textwrap import dedent, indent
import zipfile

KIT = Path(__file__).resolve().parents[1]
RUNNER = KIT / "plugins/ai-tdd/scripts/unittest_runner.py"


def suite(imports, statements, name="OracleTests"):
    text = "import unittest\n" + imports + "\n\nclass " + name + "(unittest.TestCase):\n"
    for index, statement in enumerate(statements):
        text += f"    def test_case_{index:03d}(self):\n" + indent(statement, "        ") + "\n\n"
    return text


FEE_CORRECT = "def fee(cents: int) -> int:\n    return 0 if cents >= 10000 else 799\n"
FEE_ROWS = [(0, 799), (1, 799), (9999, 799), (10000, 0), (10001, 0), (20000, 0)]
FEE_ORACLE = suite("from src.fee import fee", [
    f"result = fee({cart})\nself.assertEqual(result, {expected})\nself.assertIs(type(result), int)"
    for cart, expected in FEE_ROWS
])

AUTH_CORRECT = dedent("""\
    def can_access(
        user_id: str | None, owner_id: str, shared_with: set[str], archived: bool
    ) -> bool:
        if archived or user_id is None:
            return False
        return user_id == owner_id or user_id in shared_with
""")
AUTH_INITIAL = AUTH_CORRECT.replace(
    "    if archived or user_id is None:\n        return False\n    return user_id == owner_id or user_id in shared_with",
    "    return user_id == owner_id",
)
# Each literal column corresponds to owner, reader, outsider, unauthenticated.
# This independent truth table does not call or inspect the candidate function.
AUTH_TABLE = [
    (set(), [True, False, False, False]),
    ({"reader"}, [True, True, False, False]),
    ({"owner", "reader"}, [True, True, False, False]),
    ({"outsider-reader"}, [True, False, False, False]),
]
AUTH_STATEMENTS = []
for shared, expected in AUTH_TABLE:
    shared_literal = "{" + ", ".join(repr(item) for item in sorted(shared)) + "}" if shared else "set()"
    for index, user in enumerate(["owner", "reader", "outsider", None]):
        for archived in [False, True]:
            allowed = False if archived else expected[index]
            AUTH_STATEMENTS.append(
                f"self.assertIs(can_access({user!r}, 'owner', {shared_literal}, {archived}), {allowed})"
            )
AUTH_ORACLE = suite("from src.authorization import can_access", AUTH_STATEMENTS)

LEDGER_CORRECT = dedent("""\
    class ReservationLedger:
        def __init__(self, capacity: int) -> None:
            self._capacity = capacity
            self._reservations: dict[str, int] = {}

        def available(self) -> int:
            return self._capacity - sum(self._reservations.values())

        def reserve(self, reservation_id: str, seats: int) -> bool:
            if reservation_id in self._reservations or seats > self.available():
                return False
            self._reservations[reservation_id] = seats
            return True

        def cancel(self, reservation_id: str) -> bool:
            if reservation_id not in self._reservations:
                return False
            del self._reservations[reservation_id]
            return True
""")
LEDGER_INITIAL = dedent("""\
    class ReservationLedger:
        def __init__(self, capacity: int) -> None:
            self._capacity = capacity

        def available(self) -> int:
            return self._capacity

        def reserve(self, reservation_id: str, seats: int) -> bool:
            return False

        def cancel(self, reservation_id: str) -> bool:
            return False
""")
LEDGER_STATEMENTS = [
    "ledger = ReservationLedger(3)\nself.assertEqual(ledger.available(), 3)\n"
    "self.assertIs(type(ledger.available()), int)",
    "ledger = ReservationLedger(3)\nself.assertIs(ledger.reserve('exact', 3), True)\n"
    "self.assertEqual(ledger.available(), 0)\nself.assertIs(ledger.reserve('extra', 1), False)\n"
    "self.assertEqual(ledger.available(), 0)",
    "ledger = ReservationLedger(3)\nself.assertIs(ledger.reserve('over', 4), False)\n"
    "self.assertEqual(ledger.available(), 3)",
    "ledger = ReservationLedger(5)\nself.assertIs(ledger.reserve('one', 2), True)\n"
    "self.assertIs(ledger.reserve('two', 3), True)\nself.assertEqual(ledger.available(), 0)",
    "ledger = ReservationLedger(5)\nself.assertIs(ledger.reserve('duplicate', 2), True)\n"
    "self.assertIs(ledger.reserve('duplicate', 1), False)\nself.assertEqual(ledger.available(), 3)\n"
    "self.assertIs(ledger.reserve('duplicate', 4), False)\nself.assertEqual(ledger.available(), 3)",
    "ledger = ReservationLedger(3)\nself.assertIs(ledger.reserve('cancel', 2), True)\n"
    "self.assertIs(ledger.cancel('cancel'), True)\nself.assertEqual(ledger.available(), 3)\n"
    "self.assertIs(ledger.cancel('cancel'), False)\nself.assertEqual(ledger.available(), 3)\n"
    "self.assertIs(ledger.reserve('cancel', 3), True)\nself.assertEqual(ledger.available(), 0)",
    "ledger = ReservationLedger(2)\nself.assertIs(ledger.cancel('missing'), False)\n"
    "self.assertEqual(ledger.available(), 2)",
    "first = ReservationLedger(3)\nsecond = ReservationLedger(7)\n"
    "self.assertIs(first.reserve('same-name', 2), True)\nself.assertEqual(second.available(), 7)\n"
    "self.assertIs(second.reserve('same-name', 4), True)\nself.assertEqual(first.available(), 1)\n"
    "self.assertEqual(second.available(), 3)\nself.assertIs(first.cancel('same-name'), True)\n"
    "self.assertEqual(second.available(), 3)",
    "ledger = ReservationLedger(0)\nself.assertIs(ledger.reserve('zero', 1), False)\n"
    "self.assertEqual(ledger.available(), 0)\nself.assertIs(ledger.cancel('zero'), False)",
]
LEDGER_ORACLE = suite("from src.ledger import ReservationLedger", LEDGER_STATEMENTS)

CORRECT_ALTERNATIVES = {
    "fee": "def fee(cents: int) -> int:\n    if cents < 10000:\n        return 799\n    return 0\n",
    "authorization": dedent("""\
        def can_access(
            user_id: str | None, owner_id: str, shared_with: set[str], archived: bool
        ) -> bool:
            return (
                not archived
                and user_id is not None
                and (user_id == owner_id or user_id in shared_with)
            )
    """),
    "ledger": dedent("""\
        class ReservationLedger:
            def __init__(self, capacity: int) -> None:
                self._available = capacity
                self._active: dict[str, int] = {}

            def available(self) -> int:
                return self._available

            def reserve(self, reservation_id: str, seats: int) -> bool:
                if reservation_id in self._active:
                    return False
                if seats > self._available:
                    return False
                self._active[reservation_id] = seats
                self._available -= seats
                return True

            def cancel(self, reservation_id: str) -> bool:
                reserved = self._active.pop(reservation_id, None)
                if reserved is None:
                    return False
                self._available += reserved
                return True
    """),
}

CASES = {
    "fee": {
        "module": "fee", "source_path": "src/fee.py", "test_path": "tests/test_fee.py",
        "initial_source": "def fee(cents: int) -> int:\n    return 799\n",
        "initial_test": "import unittest\nfrom src.fee import fee\n\nclass FeeTests(unittest.TestCase):\n    def test_regular(self):\n        self.assertEqual(fee(100), 799)\n",
        "correct_source": FEE_CORRECT, "oracle_tests": FEE_ORACLE, "oracle_cases": len(FEE_ROWS),
        "contract": "Change src/fee.py fee(cents) so nonnegative integer carts at or above 10000 cents have fee 0, while carts below 10000 retain fee 799. Public typed API stays fee(cents) -> int. Other input types and negative values are out of scope.",
        "style": "Keep existing typed fee API, four-space indentation and unittest style.",
        "mutants": {
            "always_paid": "def fee(cents: int) -> int:\n    return 799\n",
            "threshold_late": FEE_CORRECT.replace(">= 10000", "> 10000"),
            "threshold_early": FEE_CORRECT.replace(">= 10000", ">= 9999"),
            "free_only_at_threshold": FEE_CORRECT.replace(">= 10000", "== 10000"),
        },
    },
    "authorization": {
        "module": "authorization", "source_path": "src/authorization.py", "test_path": "tests/test_authorization.py",
        "initial_source": AUTH_INITIAL,
        "initial_test": suite("from src.authorization import can_access", [
            "self.assertIs(can_access('owner', 'owner', set(), False), True)"
        ], name="AuthorizationTests"),
        "correct_source": AUTH_CORRECT, "oracle_tests": AUTH_ORACLE, "oracle_cases": len(AUTH_STATEMENTS),
        "contract": "Implement src/authorization.py can_access(user_id: str | None, owner_id: str, shared_with: set[str], archived: bool) -> bool. All archived resources deny every user, including owners and shared users. A None user is unauthenticated and always denied. For unarchived resources an authenticated user is allowed exactly when their ID equals owner_id or is an exact member of shared_with; every other user is denied. IDs are nonempty strings and inputs of other types are out of scope. Keep the typed public signature and boolean return values.",
        "style": "Keep the existing typed can_access API, four-space indentation and unittest style.",
        "mutants": {
            "archived_owner_allowed": AUTH_CORRECT.replace("    if archived or user_id is None:", "    if user_id == owner_id:\n        return True\n    if archived or user_id is None:"),
            "anonymous_allowed": AUTH_CORRECT.replace("    if archived or user_id is None:", "    if user_id is None and not archived:\n        return True\n    if archived or user_id is None:"),
            "sharing_ignored": AUTH_CORRECT.replace("return user_id == owner_id or user_id in shared_with", "return user_id == owner_id"),
            "outsider_allowed": AUTH_CORRECT.replace("return user_id == owner_id or user_id in shared_with", "return True"),
        },
    },
    "ledger": {
        "module": "ledger", "source_path": "src/ledger.py", "test_path": "tests/test_ledger.py",
        "initial_source": LEDGER_INITIAL,
        "initial_test": suite("from src.ledger import ReservationLedger", [
            "self.assertEqual(ReservationLedger(3).available(), 3)"
        ], name="LedgerTests"),
        "correct_source": LEDGER_CORRECT, "oracle_tests": LEDGER_ORACLE, "oracle_cases": len(LEDGER_STATEMENTS),
        "contract": "Implement src/ledger.py ReservationLedger(capacity: int), available() -> int, reserve(reservation_id: str, seats: int) -> bool and cancel(reservation_id: str) -> bool. Capacity is a nonnegative integer, seats are positive integers, IDs are nonempty strings; other inputs are out of scope. A new reservation succeeds exactly when its seats do not exceed currently available capacity, stores it, and decreases availability. Reject an already active ID and reject excess seats, returning False and leaving every reservation and availability unchanged. Cancel an active ID once, return True and restore its seats; a missing or already cancelled ID returns False without change. A cancelled ID may be reused. Separate instances have independent reservations and capacities, including capacity zero. Preserve typed signatures and the existing regression. Group the contract into at most four acceptance criteria; do not impose a test-count quota.",
        "style": "Keep the typed ReservationLedger API, four-space indentation, per-instance state and unittest style.",
        "mutants": {
            "exact_capacity_rejected": LEDGER_CORRECT.replace("seats > self.available()", "seats >= self.available()"),
            "duplicate_overwrites": LEDGER_CORRECT.replace("reservation_id in self._reservations or ", ""),
            "cancel_keeps_reservation": LEDGER_CORRECT.replace("        del self._reservations[reservation_id]\n", ""),
            "shared_instance_storage": LEDGER_CORRECT.replace("class ReservationLedger:\n", "class ReservationLedger:\n    _shared: dict[str, int] = {}\n").replace("self._reservations: dict[str, int] = {}", "self._reservations = self._shared"),
        },
    },
}
for case_id, frozen_case in CASES.items():
    frozen_case["correct_controls"] = {"fault_reference": frozen_case["correct_source"],
                                      "structural_alternative": CORRECT_ALTERNATIVES[case_id]}


def case_fingerprint():
    """Hash full contracts, initial fixtures, independent oracles and selected faults."""
    payload = json.dumps(CASES, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def classify_results(payload, returncode):
    """A kill needs completed assertion witnesses, never an exit code by itself."""
    if not isinstance(payload, dict):
        return {"outcome": "unusable", "reason": "No runner report"}
    collected = payload.get("collected")
    results = payload.get("results")
    if not isinstance(collected, list) or not collected or not isinstance(results, list):
        return {"outcome": "unusable", "reason": "No executed test evidence"}
    if any(not isinstance(item, dict) for item in results):
        return {"outcome": "unusable", "reason": "Invalid runner records"}
    ids = [item.get("id") for item in results]
    if len(set(collected)) != len(collected) or len(set(ids)) != len(ids) or set(collected) != set(ids):
        return {"outcome": "unusable", "reason": "Collection/execution mismatch"}
    if any(item.get("status") not in {"passed", "failed"} or
           (item.get("status") == "failed" and item.get("exception") != "AssertionError") for item in results):
        return {"outcome": "unusable", "reason": "Import, setup, application error or skipped test"}
    failures = [item for item in results if item["status"] == "failed"]
    if returncode != (1 if failures else 0):
        return {"outcome": "unusable", "reason": "Exit code contradicts test evidence"}
    # Only synthetic IDs and exception classes leave the ephemeral fixture.
    return {"outcome": "assertion_failure" if failures else "passed", "executed_count": len(ids),
            "test_ids": sorted(ids), "witnesses": [{"test_id": item["id"], "exception": item["exception"]} for item in failures]}


def run_project_tests(root, timeout=20):
    report = Path(root) / "runner-report.json"
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        completed = subprocess.run([sys.executable, "-B", str(RUNNER), "--start-dir", "tests", "--report", str(report)],
                                   cwd=root, env=env, capture_output=True, timeout=timeout)
        payload = json.loads(report.read_text(encoding="utf-8")) if report.is_file() else None
        return classify_results(payload, completed.returncode)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return {"outcome": "unusable", "reason": "Execution failed, invalid report or timeout"}


def execute_fixture(case, source, tests):
    with tempfile.TemporaryDirectory(prefix="ai-tdd-oracle-") as folder:
        root = Path(folder)
        (root / "src").mkdir()
        (root / "tests").mkdir()
        (root / case["source_path"]).write_text(source, encoding="utf-8")
        (root / "tests/test_oracle.py").write_text(tests, encoding="utf-8")
        return run_project_tests(root)


def inspect_behavior(case, project):
    path = Path(project) / case["source_path"]
    if not path.is_file():
        return {"cases": case["oracle_cases"], "passed": False, "outcome": "unusable", "reason": "Missing source"}
    with tempfile.TemporaryDirectory(prefix="ai-tdd-behavior-") as folder:
        root = Path(folder)
        shutil.copytree(Path(project) / "src", root / "src", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        (root / "tests").mkdir()
        (root / "tests/test_oracle.py").write_text(case["oracle_tests"], encoding="utf-8")
        result = run_project_tests(root)
    if result.get("executed_count") != case["oracle_cases"]:
        result = {"outcome": "unusable", "reason": "The complete independent oracle did not execute"}
    return {"cases": case["oracle_cases"], "passed": result["outcome"] == "passed", **result}


def inspect_test_strength(case, project):
    """Require correct controls before crediting replacement-source fault witnesses."""
    with tempfile.TemporaryDirectory(prefix="ai-tdd-mutants-") as folder:
        root = Path(folder)
        for name in ("src", "tests"):
            original = Path(project) / name
            if not original.is_dir():
                return {"available": False, "reason": "Missing source or tests", "mutants": []}
            shutil.copytree(original, root / name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        original_source = (root / case["source_path"]).read_text(encoding="utf-8")
        baseline = run_project_tests(root)
        if baseline["outcome"] != "passed":
            return {"available": False, "reason": "Generated tests do not pass candidate source", "baseline": baseline, "mutants": []}
        controls = []
        for name, source in case["correct_controls"].items():
            oracle = execute_fixture(case, source, case["oracle_tests"])
            if oracle.get("executed_count") != case["oracle_cases"]:
                oracle = {"outcome": "unusable", "reason": "Complete correct-control oracle did not execute"}
            (root / case["source_path"]).write_text(source, encoding="utf-8")
            generated = run_project_tests(root)
            if generated.get("test_ids") != baseline.get("test_ids"):
                generated = {"outcome": "unusable", "reason": "Correct control changed executed test IDs"}
            controls.append({"id": name, "oracle": oracle, "generated_tests": generated})
        if any(row["oracle"]["outcome"] != "passed" or row["generated_tests"]["outcome"] != "passed" for row in controls):
            return {"available": False, "reason": "Independent correct control failed or generated tests reject a correct implementation",
                    "baseline": baseline, "correct_controls": controls, "mutants": []}
        rows = []
        for name, source in case["mutants"].items():
            (root / case["source_path"]).write_text(source, encoding="utf-8")
            result = run_project_tests(root)
            if result.get("test_ids") != baseline.get("test_ids"):
                result = {"outcome": "unusable", "reason": "Mutant changed executed test IDs"}
            status = {"passed": "survived", "assertion_failure": "detected", "unusable": "unusable"}[result["outcome"]]
            rows.append({"id": name, "status": status, **result})
        (root / case["source_path"]).write_text(original_source, encoding="utf-8")
        return {"available": True, "baseline": baseline, "correct_controls": controls, "selected_faults": len(rows),
                "detected": sum(row["status"] == "detected" for row in rows),
                "survived": sum(row["status"] == "survived" for row in rows),
                "unusable": sum(row["status"] == "unusable" for row in rows), "mutants": rows}


def write_project_artifact(project, target):
    """Retain synthetic Python source/tests only; never config, state or transcripts."""
    root = Path(project).resolve()
    paths = []
    for name in ("src", "tests"):
        folder = root / name
        if not folder.is_dir() or folder.is_symlink() or folder.resolve() != folder:
            raise ValueError("Synthetic source/test directory is missing or redirected")
        for path in sorted(folder.rglob("*")):
            if path.is_symlink() or path.resolve() != path:
                raise ValueError("Synthetic artifact contains a redirected path")
            if path.is_file() and path.suffix == ".py" and "__pycache__" not in path.parts:
                paths.append(path)
    if not paths:
        raise ValueError("No synthetic Python source or tests")
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("xb") as output:
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in paths:
                info = zipfile.ZipInfo(path.relative_to(root).as_posix(), date_time=(2026, 10, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, path.read_bytes())
    return {"saved": True, "format": "zip", "scope": "synthetic src/tests Python files only",
            "file_count": len(paths), "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}
