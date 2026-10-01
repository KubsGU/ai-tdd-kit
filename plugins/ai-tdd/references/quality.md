# Test quality and repository conventions

Good tests detect meaningful contract violations with independently justified
expectations. Passing receipts establish executed checks, not exhaustive correctness.
Use the existing repository's conventions and tools. Test counts, assertion counts,
coverage quotas and mutation scores are not acceptance requirements by themselves.

## Before begin

Read instructions, relevant neighboring code/tests, CI workflows, scripts, tool
configuration and lockfiles. Record `.ai-tdd/repo-profile.json` with the paths read,
concrete naming/error/type/format patterns, existing read-only quality commands,
their scope and unavailable checks. Cite repository paths and factual observations;
exclude secrets, private logs and raw transcripts. The profile is frozen at begin,
including its absence. Complete it during setup, not by changing it after review.

Reuse established patterns and local tooling. Do not add a new formatter, impose
global rules or restyle unrelated code as part of this task. A repository with no
configured quality tools needs an explicit limitation, not invented lint evidence.

## Choose tests by faults

Before writing each test, state:

1. A concrete faulty implementation or behavior that should fail it.
2. The contract clause, example or independent calculation that fixes its oracle.
3. What defect it detects that the other tests would miss.

Prefer observable outputs, real local components and faithful fakes. Interaction
assertions are useful when dependency calls, side effects, cache hits or rate
limits are themselves part of observable contract behavior. A mock should preserve
the relevant semantics; asserting only the return value configured on that mock
does not test the feature. Never derive expected output by calling production code,
copying its algorithm, comparing a value to itself, or checking source text exists.

Merge redundant cases when no meaningful fault detection is lost. Contract-justified
property, stateful, metamorphic and mutation checks can help complex behavior; they
are optional tools, not a requirement to make a simple example elaborate. A relation
or reference implementation needs independent justification. Equivalent mutants
need no artificial killing. Do not demand 100% mutation scores. A timeout or
import/compile error is not a behavioral kill; an actually executed exception can
disprove a contract when that input must succeed. Label proposed probes separately
from probes the coordinator actually executed.

A useful test must also accept different correct implementations permitted by
the contract. When using reference replacements to measure fault detection,
first oracle-check structurally different correct controls and run the generated
suite against them with the same inventory. Failure, skip, collection error or
changed inventory makes that measurement unavailable; it is not a detected fault.
This catches tests bound to source spelling or incidental implementation choices.
Use this extra check when suitable controls exist; it is not a mandatory extra
model call or a demand for alternative implementations on every feature.

In normal TEST create a new file. Files present at begin/next are frozen; new files
may be revised within the same TEST cycle. Existing-file correction requires AMEND,
independent contract evidence, coordinator-managed spec.version +1, and preserved
required IDs. The implementer never rewrites its own test oracle.

## Worked fee contract

The example spec charges non-members 799 cents below 10000 cents, gives free
delivery at/above 10000 cents and to members, and rejects negative carts for both
member states. Inputs are integer cents; other types are outside its scope.

| Scenario | Independent expectation | Distinct faulty behavior |
| --- | --- | --- |
| Non-member, 9999 | AC1 says 799 | Always returning free delivery |
| Non-member, 10000 and 10001 | AC2 says 0 | Using `>` at the threshold, or freeing only exactly 10000 |
| Member, 0 and 9999 | AC3 says 0 | Ignoring membership below the threshold |
| Negative, both member states | AC4 says ValueError | Missing validation, or returning early for members |

Adding twenty more ordinary below-threshold values adds little to these faults.
An additional case is useful when it exposes a concrete gap, such as a separately
specified upper limit. Do not invent requirements for floats or network behavior.

The complete test file below illustrates the final contract checks. It is not a
command to prewrite a whole feature: build small increments in separate new files
as the workflow requires. In an actual task, retain the exact IDs from its runner.

```python
import unittest

from shipping import shipping_fee


class ShippingContract(unittest.TestCase):
    def test_non_member_below_threshold(self):
        self.assertEqual(shipping_fee(9999, member=False), 799)

    def test_free_threshold_and_above(self):
        for cents in (10000, 10001):
            with self.subTest(cents=cents):
                self.assertEqual(shipping_fee(cents, member=False), 0)

    def test_member_below_threshold(self):
        for cents in (0, 9999):
            with self.subTest(cents=cents):
                self.assertEqual(shipping_fee(cents, member=True), 0)

    def test_negative_for_both_member_states(self):
        for member in (False, True):
            with self.subTest(member=member):
                with self.assertRaises(ValueError):
                    shipping_fee(-1, member=member)
```

For unittest, subtests share their parent ID. The illustrative review below assumes
the runner collected the listed IDs from `test_shipping_contract.py` and there are
no other added or AC-mapped IDs. It is not executed evidence. Replace receipt IDs,
paths and every judgment with facts from the actual task; assess any other required
IDs as well. Here no quality tools were configured, so the limitation is explicit.

```json
{
  "receipt_id": "REPLACE_WITH_CURRENT_GREEN_RECEIPT_ID",
  "quality_receipt_id": "REPLACE_WITH_PRE_REVIEW_NOT_CONFIGURED_RECEIPT_ID",
  "checked_ac": ["AC1", "AC2", "AC3", "AC4"],
  "findings": [],
  "limitations": ["Only the integer-cent pure-function contract is assessed; other input types are outside scope."],
  "quality_limitations": ["No lint, format, typecheck or security tools were configured or executed."],
  "repo_conventions": "Illustrative: neighboring shipping tests use unittest, integer cents and ValueError; cite the actual repository paths before acceptance.",
  "test_assessment": [
    {
      "test_id": "test_shipping_contract.ShippingContract.test_non_member_below_threshold",
      "detects": "A function that always returns zero fails the 9999-cent case.",
      "oracle": "AC1 fixes the fee at 799 for a non-member below 10000.",
      "why_needed": "The free-delivery cases cannot detect charging no fee below the threshold."
    },
    {
      "test_id": "test_shipping_contract.ShippingContract.test_free_threshold_and_above",
      "detects": "A strict greater-than comparison charges at 10000; an equality-only rule charges at 10001.",
      "oracle": "AC2 includes the threshold and all larger nonnegative carts.",
      "why_needed": "Checks the inclusive boundary and continuation above it in one focused parent test."
    },
    {
      "test_id": "test_shipping_contract.ShippingContract.test_member_below_threshold",
      "detects": "Ignoring membership charges 799 at zero or 9999.",
      "oracle": "AC3 makes delivery free for a member's nonnegative cart.",
      "why_needed": "Non-member boundaries do not exercise the membership exemption."
    },
    {
      "test_id": "test_shipping_contract.ShippingContract.test_negative_for_both_member_states",
      "detects": "Missing validation or a membership return before validation accepts -1.",
      "oracle": "AC4 requires ValueError for each member state.",
      "why_needed": "Positive output tests cannot establish rejection or validation order."
    }
  ],
  "recommendation": "accept"
}
```

The fault descriptions above are reasoning, not claims that mutants were run.
The controller checks assessment fields and executed-ID coverage; the verifier
must judge whether each oracle and distinct-contribution claim is sound.

## Existing quality tools

For a project already using Ruff, this minimal fragment can be added to its
otherwise complete config before begin. Use the repository's actual commands and
configuration paths. This example is not a requirement to install Ruff.

```json
{
  "quality_checks": [{
    "name": "ruff-lint",
    "kind": "lint",
    "argv": ["{python}", "-m", "ruff", "check", "src", "tests"],
    "timeout_seconds": 120,
    "inputs": ["pyproject.toml", "uv.lock"]
  }],
  "max_quality_runs": 20
}
```

An existing formatter uses check mode (for example its existing `--check` command),
never --fix. Do not add --exit-zero, ignore type errors, disable rules or weaken
configuration to get a pass. inputs are protected config/lockfile paths, including
absent files; source/test roots are already hashed and cannot overlap them.
Commands are argv arrays, execute without a shell and support {python}, {root} and
{plugin}. Up to 20 commands are allowed; max_quality_runs counts batches, not
individual commands, and is frozen at begin. See protocol for timeouts and budgets.

begin executes a baseline batch, verify refreshes stale evidence, and finish
always executes a fresh batch followed by full tests. Optional quality in GREEN or
VERIFY is useful for a concrete diagnostic need; do not run it again solely to
duplicate current evidence. Native incremental tool caches are allowed, but final
commands are invoked afresh. Check diagnostics and unexecuted commands in the
actual receipt, including missing executables, nonzero exits and timeouts.

Report each missing kind explicitly even when another check passed: the Ruff
fragment above provides lint evidence, not format/typecheck/security evidence.
A custom check does not establish those categories just by returning zero.
With no configured tools, the result is not_configured with explicit limitations,
never a lint pass.
Quality tools can miss defects and inspect only their configured scope. Receipts
and workflow guards are not an OS sandbox or a proof of complete correctness.
