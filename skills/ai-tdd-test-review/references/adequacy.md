# Test adequacy decisions

Use the agreed behavior contract as the source of expectations. A test contributes
when it rejects a plausible, consequential violation and accepts materially
different correct implementations allowed by that contract.

## Independent oracles

Prefer a contract-fixed result, an independently justified calculation, an approved
external fixture, or a relation derived from the domain. Cite its source. Calling
the system under test to produce the expected value, copying its algorithm, or
generating a golden file from the proposed implementation without independent
approval does not establish the expected behavior.

A snapshot can be useful for an approved stable output contract. Its size and
existence do not make it independent. A numerical tolerance must follow domain
precision or an agreed contract; do not choose one merely to make a test pass.

When reviewing a property or metamorphic test, ask why the relation is required.
“Calling twice gives the same result” is unsound for an intentionally varying
output and too weak for an incorrect function that always returns zero. State the
input domain and the meaningful fault the relation distinguishes. Stateful checks
can expose invalid transitions when those transitions belong to the contract;
they are optional, not an obligation on a simple pure function.

## Doubles and observable interactions

A local fake or mock must preserve the semantics relevant to the scenario. Mocking
the very calculation or persistence behavior under review removes its test value.
For a contract requiring “the second lookup of the same key makes no provider call,”
a counting fake can establish an observable interaction. Asserting an incidental
private helper call usually constrains implementation instead of behavior.

An assertion about a returned stub value needs a meaningful system-under-test
path: direct calls to the stub prove its setup, while a contract-required forwarding
or caching result can be useful. Inspect the setup, call, and assertion together.
Use a real local component when needed to expose an integration boundary; do not
assume every unit test should start a database or use a network.

## Distinct contribution

Explain what another useful test would miss. Threshold, continuation beyond the
threshold, validation precedence, state transition, and cross-key cache collision
can be distinct faults. Twenty arbitrary values in the same equivalence class may
add no meaningful protection. Do not assume redundancy solely from similar names:
different inputs may exercise a separate contract rule or integration path.

Retain existing useful tests. Recommend merging or removing only a specifically
justified redundant or invalid assertion, with the behavior protection preserved.
Coverage and test counts help locate gaps; they cannot substitute for this judgment.

## Execution and selected mutations

The reviewer proposes probes; an authorized coordinator or developer executes them
outside this read-only role. Keep these categories separate:

| Evidence | What the review can say |
| --- | --- |
| Static counterexample | “This faulty behavior would satisfy the assertion,” with reasoning; not an executed result. |
| Supplied valid behavioral failure | Identify the input, expected outcome, executed outcome, and supplied artifact. |
| Collection/import/compile failure or timeout | Execution unavailable or infrastructure error; not a behavioral mutation kill. |
| Supplied exception from an executed required-success input | May disprove that specific behavior contract. |
| Equivalent or out-of-contract mutant | No defect established; do not require an artificial kill. |
| Passed selected probes | Evidence for those faults and inputs only, not complete correctness. |

Before relying on replacement-based fault measurements, check any supplied
structurally different correct controls against the same test inventory. A failed,
skipped, or uncollected correct control makes that measurement unavailable. This is
useful when such controls exist; it is not a demand to generate alternative
implementations or extra model calls for every review.

## Repository conventions and check evidence

Cite concrete instruction, neighboring-code, configuration, or CI paths when
describing a convention. An established convention supports consistency findings;
a reviewer preference does not create a new requirement.

Reading configured lint, formatter, type, or security settings proves configuration
only. A supplied run must identify what executed and its scope. An unrelated custom
check or a lint pass does not establish all four categories. Report each unverified
category plainly. Do not recommend disabling a rule, narrowing discovery, changing
packages, weakening security policy, or skipping a failure merely to obtain green.

This skill supplies judgment, not mechanical enforcement. Host access controls and
the developer's real runner determine what can execute and what evidence exists.
