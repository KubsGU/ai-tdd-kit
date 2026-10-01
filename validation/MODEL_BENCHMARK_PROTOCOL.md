# Pre-registered native model comparison — revision 2

The original run stopped as a **9/18 partial pilot** after a reproduced grader
false positive: a source-spelling assertion could receive four fault-detection
credits while rejecting another correct implementation. Its original protocol is
preserved in [MODEL_BENCHMARK_PILOT_PROTOCOL.md](MODEL_BENCHMARK_PILOT_PROTOCOL.md).
Pilot workflow, oracle, time and cost observations remain separate; fault counts
are uncontrolled/provisional. Reported pilot API-equivalent outlay was
**USD 10.1697152**. No pilot trial is silently replaced or rerolled.

Revision 2 is written after that grader discovery and **before all new primary
and mixed-profile trials**, 2026-10-01. Contracts and native budgets are unchanged;
new controls, retained synthetic capsules and exact routing audit correct the
measurement. This experiment compares whole
workflows on small synthetic Python tasks. It cannot establish equal quality on
arbitrary projects, security-sensitive production changes or larger tasks.

## Fixed design

- Three cases (`fee`, `authorization`, `ledger`) × three full model aliases
  (`claude-opus-5-5`, `claude-sonnet-5-5`, `claude-haiku-4-5`) × two repetitions:
  **18 independent complete-workflow trials**. Every worker model is `inherit`.
- Separately activated, already registered follow-up: **six distinct trials**,
  three cases × two repetitions, with coordinator `claude-sonnet-5-5`, test
  author/verifier `inherit`, and implementer explicitly `haiku`. The requested
  frozen policy and actual coordinator/role response models are audited. Baseline
  remains all-inherit unless `--profile mixed-haiku` is explicitly selected.
- Deterministic blocked random order: seed **20261001**. Shuffle the six
  case/repetition blocks, then shuffle the model order within each block.
  Finish a block before launching the next. The generated plan is stored before
  the first trial, alongside hashes of case content and all executable/instruction
  inputs. At most three isolated processes run concurrently.
- Identical contracts, initial source, one existing passing regression, quality
  instructions and budgets for every model on a case. Synthetic projects and
  Claude sessions are new for each trial. Existing CLI authentication is used;
  no credentials or real repository data enter the fixtures or reports.
- **USD 3 reported API-equivalent budget**, **60 turns**, **600 seconds of model
  process wall time** per trial. Maximum configured aggregate budget: USD 54;
  this is neither an invoice nor a guarantee about billing. `--max-budget-usd`
  is a CLI limit; its reported usage is retained as observed. The mixed-profile
  follow-up has a separate USD 18 configured aggregate cap. Report baseline,
  mixed and pilot costs separately, then give total experiment outlay too.
- An outer evaluator deadline of **780 seconds** bounds stalled inspection as
  well. Inspection is separate from the 600-second model deadline. Its timeout
  remains a failed attempt with unavailable usage, never zero observed cost.
- No `--effort` flag. Sonnet/Opus native defaults and Haiku native behavior differ;
  this compares usable native configurations, **not equal thinking budgets**.
  No fallback model, model switching, selective rerolls or repair by the evaluator.
- Failures, turn/budget exhaustion, timeouts, missing reports, missing usage and
  mismatched actual response/worker models stay in the trial table. No failed
  trial is silently retried or replaced. A changed frozen input stops remaining
  launches; an interrupted run remains incomplete rather than becoming a result.

## Cases and observations

`scripts/model_benchmark_cases.py` is the frozen source of fixtures, independent
oracles and selected plausible faults. **Oracle files and fault implementations
are never copied into the model's project or prompt.** The full required behavior
is stated to the model; hidden checks do not introduce unstated requirements.
These checks are independently withheld from the task prompt/project, **not a
secured private holdout**: the public harness is on the same host and generated
source/tests are trusted executable code. There is no OS sandbox or proof against
benchmark leakage or malicious grading manipulation.

| Case | Contract | Hidden executed scenarios | Selected faults |
| --- | --- | ---: | --- |
| Fee | Below 10000 costs 799; at/above costs 0; nonnegative integers, typed API | 6 | Always paid; threshold late; threshold early; free only at threshold |
| Authorization | Archived and anonymous deny; exact owner or sharing permits other active access | 32 truth-table rows | Archived owner allowed; anonymous allowed; sharing ignored; outsider allowed |
| Ledger | Capacity/exact fit; rejected duplicates preserve state; cancellation restores capacity/reuse; independent instances including zero capacity | 9 stateful scenarios | Exact fit rejected; duplicate overwrites; cancellation retains state; shared instance storage |

Every task uses stdlib unittest, preserved public types, existing conventions and
three actual read-only repository checks: Ruff `F` lint over the project, Ruff
source format check and strict Mypy over source. Their shared `pyproject.toml` is
protected. No forced dependencies or formatter/linter weakening is permitted.
Ruff and Mypy must already be installed in the evaluator's Python environment.

Workflow completion requires actual `DONE`, a successful native CLI final result,
current runner and quality receipts, passing configured checks, preserved original
test bytes, repository profile, per-test adequacy review, and dispatch plus observed
response models for all three required roles. Benchmark completion additionally
requires final whole-tree usage and reported cost, not streamed-delta estimates.
No claim about semantic adequacy follows from the presence of review fields alone.

After auditing the real workflow, independent oracle and strength checks run in
fresh isolated copies. The evaluator does not repair code, tests or managed state.
Generated tests must first pass the candidate implementation. Before fault credit,
they must also pass **both** the correct base corresponding to the fault bodies
and a structurally distinct correct alternative. Each correct control separately
passes its complete independent oracle; generated suites must preserve the same
collected/executed inventory as the candidate baseline. Fee uses a reversed
comparison branch; authorization uses a conjunction expression; ledger uses an
independent available-capacity counter and refund rather than deriving capacity
from summed reservations. Exact named typed public APIs remain unchanged, so
legitimate signature and keyword-value tests still work.

A failed correct-control oracle, assertion, error, skip, timeout or changed test
inventory makes strength **unavailable**, with actual control outcome/witnesses
and no credited faults. Two correct controls reduce implementation-coupling risk;
they do not prove every generated assertion is behavioral. They add no model calls.

Each selected fault then replaces only the source file in a copied project. Detection requires the
same collected/executed test IDs and **actual assertion-failure witnesses** from
`unittest_runner.py`. Import/compile/setup/application errors, missing reports,
timeouts, skips and changed IDs are **unusable**, never detected faults. Returned
witnesses contain synthetic test IDs and exception classes; raw transcripts and
arbitrary exception text are not published. Only stdlib unittest is supported by
this selected-fault inspection; runner changes are reported honestly.

## Reporting and decision rule

`python -B scripts/benchmark_models.py` displays the frozen baseline plan without
model calls. Explicitly add `--run --jobs 3 --output dist/local-model-benchmark-v2.json`
to execute the new baseline; use `--profile mixed-haiku --run --output
dist/local-model-benchmark-mixed.json` for the separate six-trial follow-up.
Default output is ignored
`dist/local-model-benchmark.json`; raw Claude output exists only in temporary
directories. The report records the pre-trial protocol and file hashes, each trial,
whole-tree final token/cache totals, reported API-equivalent cost, model process
wall time, native turns, generated required IDs, runner/quality batches, final
phase, requested frozen routing, actual coordinator/role models, hidden oracle,
correct-control outcomes and each selected fault outcome. Report status `complete`
means all planned attempts finished, including failures, rather than all passed.
Workflow success and eligible strength are separate fields; a control failure
does not conceal a completed workflow.

Each trial retains an ignored local ZIP capsule adjacent to its report, containing
**only synthetic `src/` and `tests/` Python files**, never configuration, review,
managed state, transcripts, authentication or real project material. Capsule hashes
allow future grading without paid model rerolls. Raw code capsules require separate
curated review before any public sharing. Existing reports/capsules cannot be
overwritten. Numeric/relative-ID summaries may be curated for public reporting.

Aggregate all attempted trials, including failures. Missing costs remain missing;
observe available cost separately instead of treating missing cost as zero.
Present case/repetition rows alongside totals so a cheap incomplete workflow cannot
look efficient. Selected-fault results are a constructed diagnostic, not a universal
mutation score or an estimate of production bugs.

Consider whole-workflow Sonnet for ordinary small-task use only if it completes
**6/6** trials, passes every independent oracle, preserves all gates, has complete
usage and actual model evidence, valid correct controls and no unusable fault
outcomes, and in **each paired case/repetition** detects
every selected fault detected by the valid Opus reference. If the paired Opus
trial fails or has unavailable workflow/control/fault evidence, no non-inferiority claim can be made for
that block. Whole-workflow Haiku must meet that same bar; otherwise it is only a
possible candidate for a separately measured narrow mixed-role profile. A
mixed-role follow-up is the separate six-trial experiment registered above. Its
narrow support bar requires **6/6** workflow/oracle passes, valid correct controls,
complete usage and exact routing/models, no unusable fault outcome, and in every
paired case/repetition every valid selected fault detected by all-Sonnet v2. An
invalid Sonnet reference prevents the corresponding support claim. Report cost
including failures against that complete baseline; lower price per token alone
is insufficient. No observation-driven reroll changes either experiment.
Six trials per model are too few to prove non-inferiority or "no quality loss";
publication must retain that limitation and avoid general cost/quality guarantees.
Publish per-case denominators and oracle/fault evidence, rather than treating
`DONE` alone as quality. Fewer generated test IDs are an observation, **not a
score to optimize**. Concurrent native requests contend for local resources and
service limits, so latency is confounded; reported native effort is unequal too.
