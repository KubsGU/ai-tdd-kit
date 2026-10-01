# Native model comparison — 2026-10-01

Primary revision-2 results are pending. This document retains the earlier pilot,
including its methodological failure and costs. It does not establish quality
equivalence between models.

See [the fixed protocol](MODEL_BENCHMARK_PROTOCOL.md) and
[model/caching policy](../plugins/ai-tdd/references/efficiency.md). Lower model
price and a high cache-read fraction do not establish lower accepted-task cost.

## Pilot: stopped after nine trials

The [original protocol](MODEL_BENCHMARK_PILOT_PROTOCOL.md) specified eighteen
trials. Nine completed before a deliberate protocol change triggered the frozen
input guard; the remaining nine were never launched. This is not a completed
paired benchmark. Every completed attempt is retained, including a failed Haiku
attempt. Costs are Claude Code's reported whole-tree API equivalents, not an
account invoice.

| Case / repetition | Model | Workflow + independent oracle | Model seconds | Reported API-equivalent USD |
| --- | --- | --- | ---: | ---: |
| Fee / 1 | Sonnet 5.5 | Pass | 175.7 | 0.7385489 |
| Fee / 1 | Haiku 4.5 | Pass | 461.9 | 0.65370065 |
| Fee / 1 | Opus 5.5 | Pass | 303.8 | 1.779703 |
| Ledger / 2 | Sonnet 5.5 | Pass | 315.7 | 1.3222338 |
| Ledger / 2 | Haiku 4.5 | Fail | 318.7 | 0.44526105 |
| Ledger / 2 | Opus 5.5 | Pass | 381.7 | 1.8870528 |
| Authorization / 2 | Sonnet 5.5 | Pass | 217.6 | 0.8396999 |
| Authorization / 2 | Opus 5.5 | Pass | 358.7 | 1.8146348 |
| Authorization / 2 | Haiku 4.5 | Pass | 558.9 | 0.6888803 |

Total reported pilot cost: **$10.1697152**, with no missing final cost reports.
The Haiku ledger invocation ended with CLI exit zero and a final `success` result,
but the controller remained in TEST, no quality commands ran, and the external
oracle found five failures in nine stateful scenarios. The evaluator rejected it.
A model's success message is not completion evidence.

During examination of the grader, a separate counterexample exposed a false
positive: a test comparing source text could reject all four selected faulty
implementations while also rejecting a different, correct implementation.
Checking only that the tests pass the candidate is insufficient. The pilot's
fault-detection counts therefore cannot support a test-quality conclusion. The
original transient projects were deleted, so these counts cannot be regraded.

Revision 2 adds independently oracle-validated, structurally different correct
implementations. Generated tests must pass those controls with the same test
inventory before faults receive any detection credit. It also retains local
synthetic source/test capsules for regrading. The new experiment is separate;
it does not replace or silently reroll the pilot.
