---
name: feature
description: Use when a user wants a feature or bug fix developed with clarified requirements, independent test authorship and verified TDD, or wants to resume such a task.
argument-hint: "<feature description>"
allowed-tools: Read, Glob, Grep, Write, Edit, Agent, AskUserQuestion, Bash(python -B "${CLAUDE_PLUGIN_ROOT}/scripts/tdd.py" *), Bash(python3 -B "${CLAUDE_PLUGIN_ROOT}/scripts/tdd.py" *)
---

# AI TDD coordinator

User request: $ARGUMENTS

You coordinate; dedicated agents write tests and source. Read
[the execution protocol](../../references/protocol.md) before the first run.
Plugin path: `${CLAUDE_PLUGIN_ROOT}`. Controller:
`python -B "${CLAUDE_PLUGIN_ROOT}/scripts/tdd.py" --root "." <command>`
(use `python3` if that is the available Python 3.10+ executable).
Use forward slashes in command paths, quote spaces and use one direct command
per Bash call. Do not chain commands, redirect output or run another shell.
Dispatch agents synchronously; do not use background or concurrent workers.

## Clarify and prepare

Read repo instructions and existing APIs/tests. Preserve dirty work. Ask concrete
behavior questions only where different answers change acceptance: show an input
and plausible outputs. Resolve routine implementation decisions yourself.
Respect existing authorization; do not add ceremonial approval rounds. If the user
requests no questions, document reasonable assumptions and their impact. A genuine
unresolved behavior decision belongs in open_questions and prevents `begin`.

Run `doctor` to confirm that the real hook works. If a prior task exists, inspect
`status`: resume an active task; use `archive` for DONE to retain its evidence
before starting this new feature. Run `init`, adapt config to existing conventions,
and write `.ai-tdd/spec.json`
with version, goal, acceptance IDs/descriptions/examples, assumptions and
open_questions. Protect all test fixtures/helpers/config/lockfiles and runner
inputs, including initially absent files. Keep source/test roots disjoint and
narrow. The runner command must run the required suite, not just the newest test.
Do not replace an existing suite with a convenient smaller one.

Delegate PLAN to `ai-tdd:verifier` using only the spec and existing interface
constraints. Save its scenarios in `.ai-tdd/review-plan.json`. This precedes the
new patch. Run `begin` to establish an actual passing baseline. Greenfield code
may use explicit `begin --allow-empty` after creating a discoverable test folder
and minimal interface stubs; document that waiver. Never delete user code to
recreate a staged TDD history.

## One increment at a time

1. Read `status`. In TEST, dispatch `ai-tdd:test-author` in a fresh context with
   the agreed spec, one small behavior, paths and baseline. Do not send an
   implementation plan, a proposed patch or the previous implementer's rationale.
2. Run `red --tests <exact-IDs> --ac <AC-IDs> --because "<oracle basis>"`.
   Only an executed behavior failure authorizes implementation. For an explicit
   interface stub use `--expect NotImplementedError`. Import/collection errors,
   zero tests, skips, timeout or missing regressions require diagnosis, not handoff.
   If the new test is already green, run `cover` with the same test/AC/rationale
   arguments; retain it as existing-behavior coverage without fake RED.
3. In IMPLEMENT, dispatch `ai-tdd:implementer` in a separate fresh context with
   the spec, frozen tests, source paths, state and RED receipt. Do not implement
   source yourself. Run `green`; relay actual failure evidence for a bounded fix.
   After GREEN, refactor only if useful and rerun `green` after any source edit.
4. Use `next` for the next small increment. Keep prior test IDs and regressions.
   Continue until every AC is meaningfully exercised, not merely mapped to an ID.

Workers cannot execute a shell. The coordinator runs tests exclusively through
the controller. Hook checks supplement worker tool allowlists. Do not disable
hooks, loosen tools or edit `.ai-tdd/state.json` to progress.

## Verify and complete

Run `verify`. Dispatch fresh `ai-tdd:verifier` in REVIEW mode with the original
plan, full spec, code, tests and current GREEN receipt. Its review must examine
boundary/interaction cases and test adequacy. Execute proposed regression cases
through new test-author cycles (`next`), then request fresh review. An additional
test in this repository is not a hidden holdout. Use real mutation/property or
integration checks where useful and supported; do not fabricate their results.

Write `.ai-tdd/review.json` exactly from the verifier's findings, checked ACs,
limitations, recommendation and current receipt ID. Preserve every open finding
across fixes; close it only after its concrete reproduction is rechecked. Run
`finish`, which reruns the full required suite and permits DONE only with current
evidence and no unresolved findings. Report behavior, tests executed, material
limitations and assumptions. A model's summary never substitutes for DONE.

## Corrections, budgets and resume

An incorrect test needs an independent contract/example justification. Use
`amend --reason "<evidence>" --ac <impacted-ACs>`, delegate correction to the
test author, increment spec.version, then obtain fresh RED or honest coverage.
The implementer cannot adjust expectations for its own patch.

For a demonstrated runner/dependency setup defect, use `reconfigure --reason
"<diagnosis>" [--paths <declared-config-files>]`. Only the coordinator edits the
unlocked config files; source, tests, ownership and permissions stay protected.
Run `rebase` to re-execute the full inventory and obtain fresh RED or GREEN.
Never restore an old receipt after a setup change. An already tampered artifact
must first be restored to its recorded version; do not hide the change.

After the attempt limit, classify and diagnose the failure before `retry --reason
"<new diagnosis>"`. Repeated identical failure must change the diagnosis/context,
not reset the budget endlessly. If an external blocker remains, report incomplete.

On resume, read state and actual artifacts instead of restarting or trusting
conversation memory. A stale GREEN needs rerunning. A completed task becomes
quiescent; use `archive` before preparing a different feature. Never merge,
publish or deploy merely because DONE passed.
