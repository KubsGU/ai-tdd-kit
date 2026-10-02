# Improvements and evidence still needed

These are open design goals, not shipped guarantees or a claim of comparative
superiority. Version 1.1.0 addresses execution-boundary and report bugs; 1.2.0
adds model inheritance, compact output and measured whole-tree cache usage.
Version 1.3.0 freezes prior test files, requires per-test adequacy assessments
and executes existing repository quality commands with fresh final receipts.
Version 1.4.0 adds explicit frozen role routing and a small paired model study;
it does not establish broad quality equivalence or automatic lossless escalation.
Version 1.5.0 adds verified bundled controller runtimes and evaluated .NET
VSTest paths for bounded xUnit/NUnit configurations; unsupported report/layout
variants remain explicit errors rather than reduced evidence requirements.

| Priority | Gap | Acceptance evidence before shipping |
| --- | --- | --- |
| High | Role/phase checks do not bind every write to a specific worker and cycle. | A persisted worker lease keyed by native agent ID; stale workers and overlapping owners denied in a real Claude session, including interruption and resume. |
| High | Adequacy assessments contain model judgment; complete fields do not prove independent oracles or useful defect detection. | Pre-register representative tasks and incorrect implementations; measure missed faults and redundant cases against independent contract-based oracles, with reviewer calibration. |
| High | Small synthetic model trials cannot measure whether extra agents justify their cost on real repositories. | Pre-registered varied repository tasks and independent behavioral oracles; repeated runs against single-agent and instruction-only TDD baselines. Publish success, regressions, total model cost, runner invocations, wall-clock time and uncertainty, including failed tasks. |
| Medium | Explicit role models stay fixed; failed cheap attempts cannot automatically escalate. | A pre-registered escalation policy with strong failure signals, monotonic model choices, persisted decisions and total failed-attempt costs; test interruption/resume and retain all acceptance gates. |
| Medium | Python adapters do not establish support for JS/TS or other languages. | Integration-test actual Vitest/Jest reports with assertion vs import/collection/setup failures, skips, parameterized cases, missing inventory and nonzero exits. Do not label typeless JUnit failure as an assertion. |
| Medium | Native .NET setup does not cover ordinary MSTest TRX, MTP, every framework version or custom project layouts. | A validated native extension/report path with independently observed body assertion evidence; actual setup/cleanup/host and missing-inventory regressions. Preserve every project/TFM without forced migrations or message-based assertion heuristics. |
| Medium | Bundled runtime support is limited to advertised native host/architecture builds. | Build and test on each additional actual host, with Python absent, verified release assets/source provenance, licensing notices and measured hook latency. Do not infer support from a mocked platform value. |
| Medium | Runtime fingerprints do not capture every dependency, service or source of nondeterminism. | Explicit project-selected dependency/version and service fixtures; prove receipt invalidation for declared inputs, document uncaptured inputs, and measure flakiness without hiding retries. |
| Medium | Required executed test IDs cannot be dropped, even if later review identifies redundant new cases. | Select the portfolio before RED. Any future retirement flow needs explicit reviewed evidence of preserved baseline and useful defect detection; removing regressions must remain blocked. |
| Medium | The runner budget is not an AI spending/time limit. The opt-in evaluator now observes final whole-tree usage, but ordinary tasks have no enforced model-spend cap. | Supported live usage/budget handling; stop with a preserved, honest partial result when a configured limit is reached. No estimated cost presented as an enforced cap. |

Executable test code remains trusted. OS isolation and truly private holdouts
would need separate execution infrastructure. A stronger workflow still needs
correct requirements, appropriate regression scope and review of test quality.

Contributions should start with a reproducible failure and state precisely which
claim the fix can support. See [CONTRIBUTING.md](CONTRIBUTING.md).
