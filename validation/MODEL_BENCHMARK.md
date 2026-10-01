# Native model comparison — 2026-10-01

Primary revision-2 and the separate mixed-role follow-up are complete.
This document retains the earlier pilot, including its methodological
failure and costs. It does not establish broad quality equivalence between models.

See [the fixed protocol](MODEL_BENCHMARK_PROTOCOL.md),
[curated numeric observations](MODEL_BENCHMARK_RESULTS.json) and
[model/caching policy](../plugins/ai-tdd/references/efficiency.md). Lower model
price and a high cache-read fraction do not establish lower accepted-task cost.

## Revision 2: all eighteen attempts retained

Source/instructions/protocol were committed as `f6931d2` before these trials.
Whole-model protocol fingerprint:
`3e1141d41916c418f57378a5bdf7265e09b07b752e11c8ca5f68739548a9f20f`.
Case fingerprint:
`68082f5d30fa1be9ded5d7328846bf8c1f7d0ba4f1aebbca770dd24208f2b212`.

| Whole workflow | Completed + all required evidence | Independent oracle | Valid strength trials | Selected fault executions detected | Reported cost, all attempts | Mean native seconds |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Opus 5.5 | 6/6 | 6/6 | 6/6 | 24/24 | $12.1433844 | 400.42 |
| Sonnet 5.5 | 6/6 | 6/6 | 6/6 | 24/24 | $5.7623923 | 236.05 |
| Haiku 4.5 | 1/6 | 5/6 | 5/6 | 20 detections; one trial unavailable | $2.5897323 observed; two costs missing | 523.87 |

The 24 executions repeat twelve distinct constructed fault patterns twice; they
are not twenty-four independent real bugs or universal mutation coverage.

Sonnet meets the registered small-task support bar: every paired Opus reference
is valid, all workflow/oracle/model/usage/correct-control evidence is available,
and each pair detects the same four selected faults with zero unusable outcomes.
Its total reported cost was **52.55% lower**, and mean native trial duration
**41.05% lower**, than Opus in this experiment. Median durations were 205.9 and
400.35 seconds respectively. All failures stay in the denominators. These are
three synthetic Python tasks repeated twice, not a general quality equivalence
or production bug-rate estimate. Native configurations have different reasoning
behavior; at most three baseline trials ran concurrently, so resource contention
and service variability also affect time.

Haiku does not meet the registered bar. Its one accepted attempt was fee/repetition
2. Other failures were: fee/1 reached DONE but its configured quality receipt
omitted required format evidence; ledger/2 timed out in IMPLEMENT; authorization/2
hit the turn limit in TEST; ledger/1 reported native success but remained TEST and
failed five independent scenarios; authorization/1 timed out in TEST. The two
timeouts have no final usage/cost report. Their spend is **unknown**, never zero.
Five valid strength measurements detect all four selected faults each; this
does not turn unfinished or incompletely checked work into a completed task.

## Separate Sonnet + Haiku implementation follow-up

All six trials met the pre-registered narrow support bar: actual Sonnet
coordinator/author/verifier, actual Haiku implementer, the requested frozen map,
complete final usage, workflow/oracle/correct-control passes and the same four
fault detections as the all-Sonnet reference in every pair. No unusable fault
outcomes occurred. Mixed protocol fingerprint:
`7c22697d88bbee6ad653dad11eb49bf1af33ec9aee85ef30698d2150e6a42700`.

| Profile | Accepted trials | Selected fault executions detected | All-attempt cost | Mean / median native seconds |
| --- | ---: | ---: | ---: | ---: |
| All Sonnet | 6/6 | 24/24 | $5.7623923 | 236.05 / 205.9 |
| Sonnet; Haiku implementation | 6/6 | 24/24 | $5.64096105 | 241.30 / 238.15 |

The mixed profile cost **2.11% less overall**, but was cheaper in only three of
six paired rows. Mean native duration was **2.22% longer**. Mixed blocks contain
one trial and run sequentially; whole-model blocks contain three concurrent
trials, so latency is not measured under identical contention. These small
differences and two repetitions per case do not establish a robust cost/time
advantage. The measurements support technical use of a bounded Haiku implementer
here, rather than a blanket economical routing rule. **All-Sonnet remains the
ordinary default.** Optional Opus author/verifier routing has controller and
instruction checks; that separate profile was not economically benchmarked.

Observed comparison outlay is at least **$26.13647005** (v2 + mixed), plus
**$10.1697152** for the stopped pilot: at least **$36.30618525** across the 33
registered attempts. Two final cost reports are missing; this is a lower bound,
not a full bill. Any separate feature/resume integration probe is reported
separately and excluded from the comparison and its selection rule.

The final separate mixed feature/resume integration passed all workflow,
exact-model, external-oracle and correct-control/four-fault checks. Feature
native time was 171.6 seconds over 33 turns; reported cost was $0.67039505.
The separate resume preserved exact DONE state and reported $0.096459. These
additional $0.76685405 are outside every comparison denominator and selection
rule. Including them gives an observed experimental outlay lower bound of
$37.0730393; the two timed-out comparison costs still remain unknown. Reported
API-equivalent estimates are not an account invoice or subscription quota.

## Every revision-2 trial

| Case / repetition | Model | Full trial accepted | Native seconds | Reported API USD | Valid controls / detected faults |
| --- | --- | --- | ---: | ---: | --- |
| fee / 1 | sonnet-5-5 | Yes (DONE) | 208.8 | $0.8037925 | yes / 4/4 |
| fee / 1 | haiku-4-5 | No (DONE) | 590.2 | $0.7389737 | yes / 4/4 |
| fee / 1 | opus-5-5 | Yes (DONE) | 278.9 | $1.4458360 | yes / 4/4 |
| ledger / 2 | sonnet-5-5 | Yes (DONE) | 203.0 | $0.8171874 | yes / 4/4 |
| ledger / 2 | haiku-4-5 | No (IMPLEMENT) | 601.0 | unknown | yes / 4/4 |
| ledger / 2 | opus-5-5 | Yes (DONE) | 428.5 | $2.3494560 | yes / 4/4 |
| authorization / 2 | sonnet-5-5 | Yes (DONE) | 314.1 | $1.3190757 | yes / 4/4 |
| authorization / 2 | opus-5-5 | Yes (DONE) | 372.2 | $1.8439156 | yes / 4/4 |
| authorization / 2 | haiku-4-5 | No (TEST) | 596.8 | $0.8528424 | yes / 4/4 |
| ledger / 1 | sonnet-5-5 | Yes (DONE) | 293.1 | $1.2131315 | yes / 4/4 |
| ledger / 1 | haiku-4-5 | No (TEST) | 262.1 | $0.3838712 | unavailable |
| ledger / 1 | opus-5-5 | Yes (DONE) | 563.2 | $2.6159344 | yes / 4/4 |
| authorization / 1 | opus-5-5 | Yes (DONE) | 464.9 | $2.3817290 | yes / 4/4 |
| authorization / 1 | haiku-4-5 | No (TEST) | 601.2 | unknown | yes / 4/4 |
| authorization / 1 | sonnet-5-5 | Yes (DONE) | 201.6 | $0.8268384 | yes / 4/4 |
| fee / 2 | haiku-4-5 | Yes (DONE) | 491.9 | $0.6140450 | yes / 4/4 |
| fee / 2 | sonnet-5-5 | Yes (DONE) | 195.7 | $0.7823668 | yes / 4/4 |
| fee / 2 | opus-5-5 | Yes (DONE) | 294.8 | $1.5065134 | yes / 4/4 |

A valid diagnostic on partial work does not satisfy the full-trial acceptance gate.

## Every mixed-profile trial

| Case / repetition | Full trial accepted | Native seconds | Reported API USD | Valid controls / detected faults |
| --- | --- | ---: | ---: | --- |
| fee / 1 | Yes (DONE) | 198.6 | $0.79567090 | yes / 4/4 |
| ledger / 2 | Yes (DONE) | 302.7 | $1.15254665 | yes / 4/4 |
| authorization / 2 | Yes (DONE) | 216.6 | $0.83807715 | yes / 4/4 |
| ledger / 1 | Yes (DONE) | 227.7 | $0.91375485 | yes / 4/4 |
| authorization / 1 | Yes (DONE) | 253.6 | $0.96160470 | yes / 4/4 |
| fee / 2 | Yes (DONE) | 248.6 | $0.97930680 | yes / 4/4 |

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
