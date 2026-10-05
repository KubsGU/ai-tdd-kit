---
name: feature
description: Use when a user wants a feature or bug fix developed with clarified requirements, independent test authorship and verified TDD, or wants to resume such a task.
argument-hint: "<feature description>"
allowed-tools: Read, Glob, Grep, Write, Edit, Agent, AskUserQuestion, Bash(node "${CLAUDE_PLUGIN_ROOT}/scripts/tdd-launcher.cjs" *), Bash(python -B "${CLAUDE_PLUGIN_ROOT}/scripts/tdd.py" *), Bash(python3 -B "${CLAUDE_PLUGIN_ROOT}/scripts/tdd.py" *)
---

# AI TDD coordinator

User request: $ARGUMENTS

You coordinate; named agents own tests and source. Read
[the execution protocol](../../references/protocol.md) before starting, and
[quality guidance](../../references/quality.md) for tool setup and test assessment.
Controller: `node "${CLAUDE_PLUGIN_ROOT}/scripts/tdd-launcher.cjs" --root "." <command>`.
Use forward slashes, quote spaces and one
direct command per Bash call. No chaining, redirection or another shell. Dispatch
fresh agents synchronously, without background or concurrent workers.

## Prepare the contract and repository

Read instructions, neighboring APIs/tests, CI/scripts, tool configuration and
lockfiles. Preserve dirty work. Ask behavior questions only when plausible outputs
change acceptance; resolve routine implementation choices yourself. Honor prior
authorization. If questions are declined, document assumptions and impacts.
Unresolved behavior decisions in open_questions prevent begin.

Inspect whether task state already exists. If so, run status with its recorded
backend and resume active work or archive DONE before a new feature. Otherwise
probe `node "${CLAUDE_PLUGIN_ROOT}/scripts/tdd-launcher.cjs" --runtime-info`.
Only if no backend is available on a supported host, run
`node "${CLAUDE_PLUGIN_ROOT}/scripts/tdd-launcher.cjs" setup-runtime --root "."`
before init/begin. Hooks never download; do not provision over state/lock or
replace a corrupt/frozen backend. Unsupported hosts need actual Python 3.10+.

Run init, then doctor. Detected C# projects receive evaluated .NET setup; read
[the .NET guide](../../references/dotnet.md) for package/layout/evidence limits.
Do not upgrade packages, migrate framework or change global settings. Adapt
narrow disjoint roots and protect all
fixtures/helpers/config/runner inputs, including relevant absent files. The runner
must preserve the full required suite. Keep existing supported runsettings and
package content intact; do not edit `.csproj`, strip settings or exclude assets
merely to bypass setup. Missing/stale package provenance calls for the repository's
normal restore of existing versions. For shared user inputs outside a selected
solution subdirectory, choose the full repository root before a new task and
recheck project ownership. Inspect precise local diagnostics; private source/logs
need not be published. Before begin, record factual conventions
and existing read-only quality commands in `.ai-tdd/repo-profile.json` (for .NET,
include existing build/analyzers, .editorconfig, format checks and CI), configure
applicable quality_checks and budgets, and write `.ai-tdd/spec.json`.

Read [model and cache guidance](../../references/efficiency.md) when choosing
cost-sensitive routing. Respect the explicitly selected session model. Before
begin, configure worker_models only when a deliberate profile is requested;
default every role to inherit. Haiku implementation is an opt-in for a complete,
bounded contract, never an automatic cheaper author/verifier. Use the normalized
policy in status: omit Agent model for inherit; pass the exact alias for each
override, including the verifier PLAN before begin. Keep review and execution
gates unchanged. The policy is frozen; do not switch models through config repair
or environment overrides after a failure, and do not claim lossless routing.

Delegate PLAN to `ai-tdd:verifier` with the spec and existing interface constraints;
save scenarios in `.ai-tdd/review-plan.json`. Run begin for actual passing test and
configured quality baselines. Greenfield setup permits only interface stubs and
an explicit documented begin --allow-empty waiver. Never delete user code to
recreate a TDD history.

## One behavior at a time

1. Read status. In TEST, dispatch `ai-tdd:test-author` with the spec, profile,
   one behavior, paths and baseline. It creates a new test file; files present at
   begin/next are frozen. Give no candidate implementation or implementer's rationale.
2. Run red --tests <exact-IDs> --ac <AC-IDs> --because "<independent oracle>".
   Only executed behavior failure authorizes source edits. An explicit stub can
   use --expect NotImplementedError. Infrastructure errors, skips or zero tests
   need diagnosis. Already passing new tests use cover with the same arguments.
3. In IMPLEMENT, dispatch fresh `ai-tdd:implementer` with contract, profile,
   frozen tests, source ownership and RED receipt. Run green; relay actual failure
   evidence for bounded repair. Useful refactoring in GREEN requires another green.
4. Use next for another increment. Retain every required ID. Complete meaningful
   behavioral coverage of every AC; counts and mapping alone do not show adequacy.

Workers have no shell. Run tests and quality tools through the controller. Keep
hooks, role tools and state intact.

## Review and finish

Run verify; it executes configured quality tools if evidence is stale. The optional
quality command in GREEN/VERIFY gives explicit evidence when useful. Avoid duplicate
pre-review runs. Dispatch fresh verifier REVIEW with plan, contract, profile,
source/tests and current GREEN/quality receipts. Review independent oracles,
distinct defect value, conventions and actual tool diagnostics. Execute proposed
regressions through new test-author cycles, then request fresh review.

Write `.ai-tdd/review.json` from its complete review object, including per-test
assessment and quality limitations. Preserve open findings until their concrete
reproductions are rechecked. Run finish: a fresh quality batch then full tests must
pass before DONE. Report behavior, executed checks, assumptions and material gaps;
not_configured is not a quality-tool pass. DONE does not authorize publication.

## Correction and recovery

Use amend only for an independently demonstrated contract/test error. You manage
spec.version +1; the test author corrects existing tests in AMEND while retaining
IDs, then red/cover supplies fresh evidence. The implementer cannot adjust its own
expectations. Follow protocol reconfigure/rebase for diagnosed setup defects and
retry for a new diagnosis after attempt exhaustion. Frozen quality definitions
and task budgets cannot be weakened. Resume from state/artifacts; rerun stale
evidence. Finish/archive active legacy tasks with their original plugin before
upgrading. Report genuine blockers as incomplete.
