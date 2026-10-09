---
name: ai-tdd
description: Develop a feature or bug fix through clarified acceptance criteria, an independent test author, a separate implementer, and a read-only reviewer. Use when a user requests verified TDD with real baseline, RED, GREEN, repository quality checks, and fresh completion evidence, or wants to resume that workflow.
license: MIT
metadata:
  author: KubsGU
  version: "1.7.0"
  source: https://github.com/KubsGU/ai-tdd-kit
---

# AI TDD coordinator

You coordinate the contract, execution, and review. Fresh, sequential workers own
tests and production source separately. The bundled controller records actual
runner evidence and verifies workflow checkpoints; an LLM's account of a passing
test is never a receipt.

Read [host integration](references/host-integration.md) first to select a truthful
execution mode, then [the protocol](references/protocol.md) and
[quality guidance](references/quality.md). Host integration distinguishes the
canonical protocol's Claude plugin enforcement from a portable host's checkpoint
checks. Read [the .NET guide](references/dotnet.md) for native setup and evidence
limits, or [efficiency guidance](references/efficiency.md) for model/cost decisions.

## Resolve the installation and existing task

Resolve the absolute path of this installed skill as `SKILL_ROOT` and the full
feature repository as `REPO_ROOT`. Use forward slashes, quote each path/argument,
and one direct coordinator command per shell call. The command prefix is:

```text
node "<SKILL_ROOT>/scripts/tdd-launcher.cjs" --root "<REPO_ROOT>"
```

The underlying controller is `<SKILL_ROOT>/scripts/tdd.py`; direct
`python -B "<SKILL_ROOT>/scripts/tdd.py" --root "<REPO_ROOT>" <command>` calls remain
available with a real interpreter. Keep one recorded engine root/backend per task.
Do not mix a copied skill, an installed plugin, or a newer version with an active
task. Inspect its existing artifacts and use its original engine and runtime for
`status` and resume. Finish/archive before changing installations. Missing or
corrupt original backends are concrete blockers, not permission to rewrite state.

In Claude Code, route execution through the native plugin's `/ai-tdd:feature` or
`/ai-tdd:resume` and original named agents. Prefer an already installed official
plugin. A skill folder alone does not register agents or hooks. The optional local
marketplace installs the bundled native plugin; see host integration. Use only
one `ai-tdd` plugin installation for the task.

In another host, require real fresh worker contexts or separate sessions. A role
label in this coordinator's conversation is not an independent agent. If the host
cannot supply separate contexts, complete useful preparation and report that
independent execution is unavailable. Do not pretend the workflow completed.

## Prepare a reviewable contract

Read repository instructions, neighboring APIs/tests, CI/scripts, tool configuration
and lockfiles. Preserve dirty work. Ask focused behavior questions only when the
answer changes acceptance. Resolve routine implementation choices yourself; honor
prior authorization. If questions are declined, document scope assumptions and
their impact. Material unresolved questions prevent `begin`.

For a new task without state/lock, probe the backend:

```text
node "<SKILL_ROOT>/scripts/tdd-launcher.cjs" --runtime-info
```

Only if no backend is available on a supported host, explicitly provision the
pinned runtime before initialization:

```text
node "<SKILL_ROOT>/scripts/tdd-launcher.cjs" setup-runtime --root "<REPO_ROOT>"
```

This action downloads a checksum-verified interpreter from the project's release;
it is not a hidden installation step. Existing Python can avoid that download.
Hooks never download. Do not provision over existing state/lock or evade a corrupt
backend. Python project tests need their actual project interpreter and packages.

Run `init`, then `doctor` through the prefix. `doctor` exercises the actual hook
program with a sentinel; its `hook_health: pass` does not prove a host registered
that hook. Configure narrow, disjoint source/test roots and protect fixtures,
helpers, config, runner inputs, relevant absent files, and dependency manifests.
Native .NET setup evaluates existing projects without requiring project edits or
new adapter code for supported layouts. Preserve supported runsettings, coverage,
package versions, and repository ownership; diagnose precise failures locally.

Before `begin`, write `.ai-tdd/spec.json`, factual `.ai-tdd/repo-profile.json`, and
applicable existing read-only `quality_checks` and budgets in config. Use the
bundled spec/config templates as examples, not acceptance requirements. The spec
requires positive `version`, `goal`, unique acceptance IDs/descriptions, and empty
`open_questions`. Include relevant scope, examples, invariants and assumptions.

Dispatch a fresh verifier in PLAN mode with the contract and existing API
constraints before exposing a proposed implementation. Save its complete
`{"scenarios":[{"ac":"AC1","case":"concrete scenario"}]}` as
`.ai-tdd/review-plan.json`, covering every acceptance ID. Run `begin`: actual full
test and configured quality baselines must pass before feature edits. Existing
failures, skips, incomplete discovery, and policy blocks need diagnosis, not
waivers or excluded modules. Greenfield `begin --allow-empty` requires an explicit
documented waiver and permits only interface bootstrap, not prewritten feature logic.

## One meaningful behavior at a time

Read `status` and honor its phase, receipt freshness, frozen paths and run budgets.
Only the coordinator runs commands; workers never run a shell or delegate.

1. **TEST:** dispatch a fresh test author with the spec, profile, one behavior,
   source/test ownership and baseline. It writes a new test file. Every test file
   present at `begin` or the latest `next`, including helpers, is frozen. Do not
   append to or rewrite one. Give no candidate implementation or implementer rationale.
   Before writing, the author names a concrete fault, independent oracle, and distinct
   contribution. Preserve useful existing tests; counts and coverage are not goals.
2. Run `red --tests "<exact-runner-ID>" --ac "<AC-ID>" --because "<oracle basis>"`.
   Only a real, targeted behavior failure authorizes IMPLEMENT; import/compile errors,
   timeouts, skipped tests, and zero tests are not RED. An explicit interface stub may
   use `--expect NotImplementedError`. Already passing new tests use `cover` with the
   same arguments and are reported as existing-behavior coverage. Use actual runner
   IDs; never derive native theory IDs from display names.
3. **IMPLEMENT:** dispatch a fresh implementer with the whole contract, profile,
   frozen tests, source ownership, and runner-issued RED receipt. It changes source
   only. Run `green`; relay actual failures for bounded repair. The implementer never
   changes its oracle, tests, helpers, collection, dependencies, or state. A useful
   refactor after GREEN requires another actual `green`.
4. Run `next` for another increment in a new test file. Retain every required ID.
   Cover each acceptance criterion meaningfully. An AC mapping alone proves no adequacy.

Prefer behavioral outputs and faithful local fakes. Self-equality, source-presence
checks, copied production calculations, and mock setup repeated as expectations
do not establish behavior. Contract-observable side effects, cache interactions,
and dependency calls can justify interaction assertions. Optional properties and
selected mutations need an independent contract basis; proposed probes are not
executed results. Do not impose mutation quotas or kill equivalent mutants.

## Independent review and actual completion

Run `verify`; it refreshes stale configured quality evidence. Use `quality` in
GREEN/VERIFY only for a concrete diagnostic need, not to duplicate current results.
Dispatch a fresh read-only verifier in REVIEW mode with the plan, contract, profile,
source/tests, current GREEN and latest pre-review quality receipt. It assesses every
added and AC-mapped test's fault, oracle, and distinct value; repository conventions;
and real lint/format/type/security evidence and gaps. The reviewer does not run
commands, edit files, or certify DONE.

Save its complete current review object to `.ai-tdd/review.json` using the protocol
schema. Preserve all open findings and concrete reproductions. New regressions
go through a new test-author cycle, actual RED/GREEN, and fresh review. Never resolve
a finding merely because the implementer reports a fix. `not_configured` is a
quality limitation, not a tool pass.

Only `finish` can record DONE, after accepting current review, a fresh configured
quality batch, and a fresh full required suite. Report implemented behavior,
executed checks, assumptions, and material gaps. A receipt is scoped evidence,
not proof of no bugs, a security sandbox, or authorization to publish.

For genuine contract/test errors, use `amend` with independent evidence; the
coordinator increments spec.version and the test author corrects agreed tests while
retaining IDs. Use the protocol's `reconfigure`/`rebase` for diagnosed setup defects
and `retry` for a new repair diagnosis. Do not weaken quality definitions, frozen
model choices, ownership, test inventory, or task budgets. Resume from actual
artifacts; never hand-edit state to migrate or invent a TDD history.
