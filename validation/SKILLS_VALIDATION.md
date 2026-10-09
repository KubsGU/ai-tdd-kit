# Standalone skills validation — 2026-10-09

Release candidate 1.7.0 keeps the canonical controller sources and immutable
runtime manifest. No external model API calls or private project data were used.

## Local executed checks

- Agent Skills `name`/`description`/license/metadata structural validation passed
  for both entry points with skill-creator's `quick_validate.py` (UTF-8).
- The two archives contain one named folder each, direct `SKILL.md`, README,
  license, all mapped support files and per-file SHA-256 inventory. Repeated builds
  produce identical bytes. Canonical runtime sources are byte-identical to the
  plugin sources; relative Markdown references resolve inside each package.
- Archives extracted outside the checkout to paths with spaces. The production
  Node facade ran a passing baseline, actual assertion RED, GREEN, independent
  review artifact and fresh DONE. An actual AST syntax command ran as a configured
  quality check. No lint/type/security coverage is inferred from that syntax check.
- Source editing before RED and changing a frozen baseline test were rejected.
  A RED-first controller regression demonstrated that changing the standalone
  coordinator entry used to be accepted, then verified the new protected inventory
  rejects it. New host guide and native registration definitions are also frozen.
- Traversal, duplicate archive entries, multiple top-level roots and unlisted files
  were rejected before extraction.
- Claude Code 2.1.294 validated the extracted native definitions and registered
  `ai-tdd@ai-tdd-local-skills` using a temporary `CLAUDE_CONFIG_DIR`. Existing user
  settings were untouched. This verifies registration, not a paid Claude feature run.
- The complete local suite passed: 363 tests and 350 subtests, with six platform/
  native-runtime prerequisites skipped. Repository Ruff checks also passed.

## Read-only skill forward test

A fresh Codex subagent loaded `ai-tdd-test-review` and its references, then reviewed
a different synthetic message-forwarding contract. The test input contained a
self-equality assertion, a mock interaction/receipt identity test, and an author's
unsupported assertion of success. No execution evidence was supplied.

The reviewer identified the ineffective assertion, preserved the contract-observable
mock test, proposed a distinct message-forwarding case that distinguishes a
hardcoded-message implementation, and labeled counterexamples unexecuted. It
reported absent quality evidence and the independence limit from seeing the source
in its initial input. It ran no fixture commands, wrote no reports/state and did
not claim DONE. This is one narrow instruction-behavior probe, not a statistical
review-accuracy benchmark or proof of Claude/Cursor/Copilot model execution.

## CI and unverified scope

The source matrix repeats controller regressions and extracted CLI checks on
Windows, Linux and macOS with Python 3.10/3.12. Native runtime jobs additionally
run real xUnit/NUnit, long paths/theories, restored package content, inherited
runsettings and deferred child-row workflows from the extracted skill with Python
absent from the controller's PATH. See the attached release PR checks for actual
per-platform results; workflow configuration alone is not passing evidence.

Copying Markdown does not install Claude's hooks in other agents, authenticate
authors/models, or provide independent contexts. Full portable execution requires
real fresh workers. Actual orchestration in Cursor, Copilot and other clients,
Agensi scanner/manual approval, production defect rates and lossless cheaper-model
routing are not certified. DONE remains scoped fresh evidence rather than a
guarantee against bugs, hostile tampering or later edits.
