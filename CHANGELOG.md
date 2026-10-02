# Changelog

## 1.5.0 — 2026-10-02

- Add a stable Node facade and explicit, version-pinned bundled controller
  runtime for Windows x64, Linux x64 and macOS arm64. Verify cached/downloaded
  binary SHA256 and size; reject linked caches and provisioning over task state
  or locks. Hooks never download. Existing Python controller calls remain usable.
- Record the local Windows Application Control block on the unsigned bundle;
  strict-policy hosts need an approved trusted runtime or existing Python.
  Native CI smoke evidence applies to its actual hosts, not every OS policy.
- Add a Node Claude launch helper with the existing Sonnet/foreground/cache
  policy scoped to its child process, preserving global settings and direct launches.
- Remove separate Python installation and manually authored adapters from the
  supported .NET user path while retaining the existing controller implementation.
  Bundled standard-library dependencies do not replace project Python packages.
- Detect/evaluate existing C# projects at init, preserving existing config.
  Configure disjoint project ownership and frozen exact bin/obj exclusions;
  protect project/package/MSBuild inputs without upgrading NuGet or global settings.
- Add bounded VSTest evidence paths for xUnit adapter >=3.0.0 and NUnit >=3.14.0
  with NUnit3TestAdapter >=4.5.0. Reconcile separate full discovery, native events
  or XML, and TRX across configured projects/TFM; require actual test-body
  assertion evidence. Reject runtime/setup/teardown, skips and inventory errors.
- Fail closed for ordinary MSTest TRX, MTP, implicit filters, unsupported layouts
  or ambiguous reporter evidence instead of inferring assertion failures.
- Document existing .NET build/analyzer/format and CI configuration, keeping
  absent quality checks explicit. Preserve full tests, role routing, reviews and
  final fresh execution. Runtime/native test scope belongs in the validation report.
- Publish per-platform runtime build metadata/source hashes and bundled component
  license notices. Finish/archive active tasks with their original plugin before
  updating; do not migrate receipts by editing state.

## 1.4.0 — 2026-10-01

- Default ordinary launches to Sonnet, retaining explicit session-model choice.
  Smaller models are evaluated rather than declared equivalent from cache hits.
- Add explicit worker_models configuration frozen at begin and checked on every
  dispatch and transition, including setup repair. Missing roles inherit; the
  implementer can opt into Haiku/Sonnet/Opus, author/verifier overrides allow Opus.
- Require the exact configured invocation model, retaining named roles, fresh
  synchronous contexts and all test/quality/review gates. No automatic fallback
  or mid-task model switching is supplied.
- Add a pre-registered paired native model comparison on three synthetic tasks,
  independent contract checks and twelve selected behavior faults. Failed trials,
  unavailable costs, actual model mismatches and weak generated tests stay visible.
- Require generated suites to pass oracle-validated alternative correct
  implementations before fault-detection credit; retain synthetic local capsules
  for regrading. Preserve the stopped pilot and its uncontrolled-score limitation.
- Clarify model-specific cache prefixes, Haiku cache minimums, native effort
  differences and API-equivalent estimates versus subscription invoices.
- Publish all eighteen corrected comparison attempts and six mixed-role attempts.
  Sonnet meets the narrow registered gates at 52.55% lower cost than Opus;
  mixed Haiku implementation saves only 2.11% and remains optional. Whole-Haiku
  completes 1/6. Preserve unavailable costs and the stopped pilot.
- Finish/archive active tasks with their original plugin before updating.

## 1.3.1 — 2026-10-01

- Reject linked managed state directories before initialization, lock creation
  or controller reads. A native Windows junction could previously redirect these
  operations even though is_symlink returned false.
- Require canonical quality log folders/runs paths, including on Python 3.10
  where the optional is_junction method is unavailable.
- Add actual directory-link regressions with external-write/read witnesses;
  retained workflow controls do not claim OS isolation or race-proof execution.

## 1.3.0 — 2026-10-01

- Freeze existing test-file hashes at begin/next, preserving earlier assertions
  in normal TEST increments. New tests need new files; controlled AMEND remains
  the route for legitimate corrections. Hooks permit revising a newly authored
  file within the same increment.
- Require review of every new/acceptance-mapped executed test: concrete defect,
  independent oracle and distinct value. No count/coverage/mutation-score quota.
  Presence checks validate review completeness, not semantic correctness.
- Record repository conventions; execute configured read-only lint, format, type,
  security or custom checks through the controller with logs and bound receipts.
  Failed checks block completion; absent checks are explicitly not_configured.
- Freeze quality definitions/inputs and a separate batch budget (default 20).
  Final completion executes the commands afresh. Source-only mutating tools are
  rejected and return the task to GREEN for repair.
- Add project Ruff lint CI, actual Ruff/formatter/strict Mypy in the opt-in Claude
  fixture, and a real-execution comparison of weak vs contract-based tests.
- Run branch CI on pull requests and main, avoiding duplicate push/PR matrices;
  cancel superseded runs and cache pinned development package downloads.
- Document primary-source research, tradeoffs and limits of reviewer judgments.
- Upgrade: finish/archive active tasks with the prior version before updating.
  Legacy tasks without a checkpoint are never retroactively blessed.

## 1.2.0 — 2026-10-01

- Explicit `model: inherit` for test-author, implementer and verifier; active-task
  dispatch rejects per-invocation model changes. No automatic cheaper role profile.
- Optional launcher defaults to Opus and selects the feature project. It enables
  foreground workers and clears cache-disable/forced worker-model environment
  variables only for the child process, preserving ordinary settings/permissions.
- Claude preflight detects disabled prompt caching and forced worker-model
  overrides. Provider-native cache TTL and normal configured effort are retained.
- Compact JSON decision views for state-returning CLI commands, preserving phase,
  runner budget, relevant failures and review limitations. Full immutable receipts
  remain on disk. Existing JSON consumers can use `--full` before the command.
- Ordered artifact-based handoffs avoid repeated history/hashes/passing logs,
  without truncating relevant requirements or skipping test executions.
- Real-Claude evaluation reports requested/observed role models, final whole-tree
  token/cache totals, estimated API cost and independent behavioral checks.
  Missing metrics stay unavailable; resume usage is separate.
- Reproducible response-byte measurement, model/environment tests and documented
  distinctions between cache reuse and comparative token/cost/time savings.
- Upgrade: finish and archive active tasks before updating protected plugin files.

## 1.1.0 — 2026-10-01

- Phase-aware dispatch of fresh plugin-qualified agents. Reject worker delegation,
  resumed/background/isolated workers, foreign role names and dispatch during
  controller execution.
- Require `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1` in Claude sessions so interactive
  runtime defaults cannot make the sequential workflow asynchronous.
- Validate JUnit suite/root outcome totals and contradictory case outcomes.
  Typeless failures are ambiguous and cannot certify behavioral RED.
- Bundle a serial pytest JSON runner with actual exception types, native node IDs,
  setup/call/teardown aggregation, and deselection/xfail/xpass checks.
- Freeze a task-wide runner invocation budget at begin; retries and configuration
  repair cannot reset or raise it. Default: 100, including the final check.
- DONE freshness uses the final completion receipt and detects edited/missing
  review files without changing historical state.
- Add macOS to the Windows/Linux CI matrix and an evidence-oriented roadmap.
- Upgrade: finish and archive active tasks before updating protected plugin files.
  Set the foreground environment flag before launching or resuming Claude.

## 1.0.1 — 2026-10-01

- Public GitHub marketplace installation instructions and repository metadata.
- English main README, retained Polish guide, and plugin-level README.
- GitHub CI for Windows/Linux with Python 3.10/3.12 and supported Node LTS.
- Pinned development pytest version, contribution and release instructions.
- Controller, hook, role prompts and TDD protocol retain the 1.0.0 behavior.

## 1.0.0 — 2026-10-01

- Versioned acceptance contract and pre-implementation verification plan.
- Separate test-author, implementer and verifier roles.
- Deterministic RED/GREEN/verification gates, required test inventory and frozen
  tests, configuration and evaluation harness.
- Audited test amendments, runner reconfiguration/rebase, bounded retries,
  resume and completed-task archival.
- Native Node-to-Python hook health checks; unittest JSON and JUnit XML adapters.
- Portable allowlisted ZIP, controller tests, deterministic demo and optional
  real-Claude evaluation.
