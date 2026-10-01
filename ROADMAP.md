# Improvements and evidence still needed

These are open design goals, not shipped guarantees or a claim of comparative
superiority. Version 1.1.0 addresses concrete execution-boundary and report bugs.

| Priority | Gap | Acceptance evidence before shipping |
| --- | --- | --- |
| High | Role/phase checks do not bind every write to a specific worker and cycle. | A persisted worker lease keyed by native agent ID; stale workers and overlapping owners denied in a real Claude session, including interruption and resume. |
| High | A test author can alter old assertions while adding new tests in a test file. IDs and passing results do not prove preserved semantics. | Either enforce separate files for new tests or define reviewable changes to existing tests; demonstrate that weakening an existing assertion requires an explicit amendment. Avoid unreliable text-only assertion equivalence claims. |
| High | One synthetic feature cannot measure whether the extra agents justify their cost. | Pre-registered varied tasks and independent behavioral oracles; repeated runs against single-agent and instruction-only TDD baselines. Publish success, regressions, total model cost, runner invocations, wall-clock time and uncertainty, including failed tasks. |
| Medium | Python adapters do not establish support for JS/TS or other languages. | Integration-test actual Vitest/Jest reports with assertion vs import/collection/setup failures, skips, parameterized cases, missing inventory and nonzero exits. Do not label typeless JUnit failure as an assertion. |
| Medium | Runtime fingerprints do not capture every dependency, service or source of nondeterminism. | Explicit project-selected dependency/version and service fixtures; prove receipt invalidation for declared inputs, document uncaptured inputs, and measure flakiness without hiding retries. |
| Medium | The runner budget is not an AI spending/time limit. | Observe actual coordinator and subagent usage through supported runtime APIs; stop with a preserved, honest partial result when a configured limit is reached. No estimated cost presented as an enforced cap. |

Executable test code remains trusted. OS isolation and truly private holdouts
would need separate execution infrastructure. A stronger workflow still needs
correct requirements, appropriate regression scope and review of test quality.

Contributions should start with a reproducible failure and state precisely which
claim the fix can support. See [CONTRIBUTING.md](CONTRIBUTING.md).
