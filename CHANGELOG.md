# Changelog

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
