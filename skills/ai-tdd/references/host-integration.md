# Host integration and evidence boundaries

This guide selects the execution mode for the standalone `ai-tdd` skill. The
bundled protocol, roles, hooks, and nested Claude skills retain their canonical
semantics. Statements about plugin hook enforcement apply only when that native
integration is actually installed and enabled. Copying a skill does not configure
a host or authenticate an independent worker.

## Paths and active tasks

Resolve `SKILL_ROOT` from the actual installed `SKILL.md` directory and `REPO_ROOT`
from the full feature repository. They are absolute paths and may differ. In
portable mode, `{plugin}` in a configured command resolves to the installed
skill's engine root. In native plugin mode, it resolves to the actual plugin root.
The launcher imports sibling controller/runner files; it does not depend on the
public repository's `plugins/ai-tdd/` path.

Use one direct quoted command, without chaining, pipes, substitutions, redirection,
or a second shell. For example:

```text
node "C:/installed/skills/ai-tdd/scripts/tdd-launcher.cjs" --root "C:/work/My Repo" status
```

Do not switch roots/backends during an active task, including by updating or
reinstalling a skill. Use the original engine/runtime for resume. Finish/archive
using that engine first. Missing original assets require restoration or reporting
an environment blocker; do not manufacture current hashes or edit state.

## Claude Code: use the native plugin

An already installed official `ai-tdd@ai-tdd-kit` plugin is the preferred native
integration. Invoke `/ai-tdd:feature <description>` or `/ai-tdd:resume`. Its own
coordinator skill, root, named agents and hooks own that task; do not mix a standalone
controller with the installed plugin's state. Update only outside an active task.

If there is no `ai-tdd` plugin, the standalone ZIP also includes a local marketplace
and native plugin assets. Before a task, optionally install from its absolute root:

```text
claude plugin marketplace add "/absolute/installed/skills/ai-tdd"
claude plugin install ai-tdd@ai-tdd-local-skills
```

On Windows, use a quoted forward-slash absolute path. This registers a marketplace
and installs/enables a plugin through Claude's normal controls; it is a distinct,
visible setup action, not something a portable skill does implicitly. Do not
install it alongside another enabled `ai-tdd` plugin. Follow organizational policy
and the normal workspace trust/permission prompts. Restart Claude afterward.

Set foreground execution before launching the native session. Example PowerShell:

```powershell
$env:CLAUDE_CODE_DISABLE_BACKGROUND_TASKS = '1'
claude
```

Unix shell:

```sh
CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1 claude
```

The native coordinator dispatches fresh, sequential `ai-tdd:test-author`,
`ai-tdd:implementer`, and `ai-tdd:verifier` through Claude's Agent tool. Original
tool allowlists, plugin-qualified roles, phase/write boundaries, foreground rules,
and frozen routing remain intact. Do not run workers as the main coordinator,
reuse resumed workers, grant them shell access, or disable hooks to resolve a failure.
`doctor` confirms the hook program handles a real sentinel; confirm the plugin is
actually enabled before relying on preventive host hooks.

## Cursor, Copilot, and other supporting hosts

Install the entire folder in a documented skill location. Standard discovery
loads instructions, not Claude agent definitions, plugin hooks, or their allowlists.
Use the portable coordinator only if the host can create genuinely separate fresh
worker contexts, or provide distinct sessions that the coordinator can hand off to.
Do not emulate all roles within one conversation and describe that as independent.

Run workers sequentially and wait for each to finish before changing phase. No
parallel author/implementer, worker reuse, background work, worker delegation,
or concurrent controller commands belong in this workflow. The coordinator owns
execution and transitions. A worker's claim never substitutes for real runner output.

Use these canonical prompts as reference material, applying their responsibility
boundaries rather than attempting to register Claude YAML in a different host:

| Fresh worker | Prompt | Inputs and ownership | Returned artifact |
| --- | --- | --- | --- |
| Verifier PLAN | `agents/verifier.md`, PLAN section | Agreed spec and relevant existing API constraints; no proposed implementation. Read-only. | Scenarios covering every AC for `review-plan.json`. |
| Test author | `agents/test-author.md` | Spec/profile, one behavior, narrow paths, baseline, allowed new file, frozen files. Own tests only; no candidate implementation rationale. | Test paths/names or known actual IDs, ACs, fault, independent oracle, distinct value, expected behavior failure. Execution not claimed. |
| Implementer | `agents/implementer.md` | Whole spec/profile, frozen tests, current phase and actual RED, source ownership. Own source only. | Changed paths, implemented ACs, gaps and next action. No claimed test run. |
| Verifier REVIEW | `agents/verifier.md`, REVIEW section | Spec/plan/profile, source/tests, current GREEN/quality receipts and all open findings. Read-only. | Complete current review object and per-test assessments. |

Each dispatch begins with role/mode and current phase/cycle, then artifact paths,
ownership/frozen paths, actual receipt IDs/paths and relevant failures, then required
return facts. Give workers read access to the whole relevant contract, callers and
fixtures. Compact briefs are navigation, not lossy replacements for requirements.
No worker runs a shell. A portable host may not enforce these tool boundaries;
use available host restrictions and disclose any unenforced boundaries.

The controller still verifies passing baseline, target behavioral RED, required
test inventory, frozen test checkpoints, protected config and engine assets,
source freshness, quality evidence, and current review before fresh completion
checks. These are checkpoints after artifacts exist. They do not prevent every
unauthorized edit, authenticate who wrote a file, ensure the host created a fresh
worker, or verify the backend model. Keep those limitations in completion reporting.

`hook_health: pass` means the bundled hook executable passed its self-test. It is
not proof that Cursor/Copilot registered interception hooks or enforce Claude roles.
This package does not install equivalent host hooks or change their settings.

## Phase checklist and actual commands

Prefix every listed command with:

```text
node "<SKILL_ROOT>/scripts/tdd-launcher.cjs" --root "<REPO_ROOT>"
```

With a real interpreter, the underlying CLI is
`python -B "<SKILL_ROOT>/scripts/tdd.py" --root "<REPO_ROOT>" <command>`.
`doctor`/CLI `begin` still need Node to exercise the actual hook program. Use one
recorded backend consistently; the complete protocol specifies budgets/recovery.

| State | Coordinator action | Evidence/transition |
| --- | --- | --- |
| Before task | `init`, `doctor`; prepare spec/config/profile; fresh PLAN worker | Actual supported setup; no overwrite of existing config; complete frozen plan. |
| Before edits | `begin` | Full passing test and configured quality baseline; test checkpoint; TEST. |
| TEST | Fresh author writes a new file; `red --tests "ID" --ac "AC1" --because "independent basis"` | Exact targeted behavioral failure, old regressions pass; IMPLEMENT. |
| TEST, test already passes | `cover --tests "ID" --ac "AC1" --because "independent basis"` | Existing-behavior coverage with unchanged source; GREEN, no fabricated RED. |
| IMPLEMENT | Fresh source-only implementer; `green` | Entire required inventory executed and passing; GREEN. |
| GREEN/VERIFY | `next` when another behavior/regression is needed | All current test files checkpointed; new TEST cycle. |
| GREEN | `verify` | All ACs mapped, fresh test and applicable quality evidence; VERIFY. |
| GREEN/VERIFY | Optional `quality` only for a concrete need | Real read-only configured tool batch; no inferred categories. |
| VERIFY | Fresh REVIEW worker; coordinator writes complete review | Current GREEN and latest pre-review quality IDs, test assessments and limits. |
| VERIFY | `finish` | Fresh configured quality batch and full required suite, current accepting review; DONE only if actual checks pass. |
| Any inspectable phase | `status`; put `--full` before `status` for full local state | Compact current decision view or explicit full diagnostics, no phase reset. |
| DONE | `archive` before a new feature | Retains local task evidence and preserves feature files. |

ID and AC above are placeholders for actual runner IDs and agreed acceptance IDs.
Use precise native row IDs from reports; names can truncate/repeat. Do not write
runner reports by hand. Import/compile errors, incomplete module collection,
timeouts, skipped/xfail tests and unknown assertions are not successful gates.

## Artifact schemas and review quality

Prepare artifacts before baseline:

- `spec.json`: positive integer `version`, nonempty `goal`, unique nonempty AC
  IDs/descriptions, and empty `open_questions`. Scope/examples/invariants/assumptions
  clarify the user's contract; do not create speculative requirements.
- `review-plan.json`: `{"scenarios":[{"ac":"AC1","case":"concrete scenario"}]}`.
  Fresh independent PLAN covers every AC before implementation.
- `repo-profile.json`: factual paths and observations from instructions, neighboring
  code/tests, CI, configuration and locks; actual existing check commands and gaps.
- `config.json`: validated disjoint narrow roots, protected inputs, runner setup,
  quality checks and bounded budgets. Use supplied templates and actual repo setup.

The review object is the complete schema in `references/protocol.md`:

```json
{
  "receipt_id": "actual current GREEN id",
  "quality_receipt_id": "actual latest pre-review quality id",
  "checked_ac": ["AC1"],
  "findings": [],
  "limitations": ["Actual unchecked risks"],
  "quality_limitations": ["Actual checked scope and each unverified quality category"],
  "repo_conventions": "Factual repository path and convention evidence",
  "test_assessment": [{
    "test_id": "actual executed test id",
    "detects": "Concrete faulty behavior",
    "oracle": "Independent contract or approved fixture basis",
    "why_needed": "Distinct fault protection"
  }],
  "recommendation": "accept"
}
```

This is a shape example, not a ready-to-use accepting review. Replace every value
with current task facts. A finding has `id`, `ac`, `case`, `expected`, `actual`, and
`impact`. Every added and AC-mapped executed ID needs one assessment. The controller
validates shape, coverage and freshness; the reviewer judges semantic adequacy.
It cannot certify the truth of an oracle or assessment just because fields exist.

Use contract-justified observable behavior. Keep useful tests and combine genuinely
redundant cases without losing fault detection. Do not reward self-equality, mock
setup mirrors, source-text checks, or expected values copied from production logic.
An interaction assertion can establish a contract-observable side effect or cache
call. Counts, coverage and mutation scores do not define acceptance by themselves.
Selected properties/metamorphic probes/mutations are optional and must distinguish
allowed correct implementations from meaningful faults. Label proposed probes
separately from supplied executed results; a compile failure or timeout is not a
behavioral mutation kill, and an equivalent mutant needs no artificial killing.

Preserve repository style and applicable existing CI checks. Configure read-only
lint/format/type/security checks before `begin`; do not add a formatter, weaken a
rule, suppress errors, or restyle unrelated code. No configured tools yields
`not_configured`; report that limitation explicitly. A lint pass does not imply
format, type or security passes. The reviewer names each absent/unverified category.

Use `amend` only for independently justified contract/test corrections; the
coordinator owns spec.version +1 and the author owns the agreed test correction.
The implementer never changes expected values. Use `reconfigure`/`rebase` for
diagnosed setup repair and `retry` for a new bounded repair diagnosis. Frozen
ownership, inventory, model policy, quality definitions and budgets remain intact.

## Cost and caching

Default every worker to inherit the deliberately selected session model. In native
Claude integration, apply the canonical frozen `worker_models` policy and exact
overrides. Haiku implementation is an explicit bounded experiment, not an automatic
cheap author/reviewer. Other hosts must not pretend Claude aliases authenticate
their backend; default to inherit and report actual observed model/usage if available.

Keep stable prompts and compact artifact navigation. Do not omit requirements,
open findings, limits or relevant failures to save context. The engine handles
bookkeeping and retains full local receipts. Host/provider prompt caches and billing
are outside the skill's control. Do not pad prompts, inject fake cache hits, cache
model answers, or replace prescribed fresh tests with an old receipt. Native tool
caches may be reused, but final commands run afresh. Cost or time savings and
unchanged quality require measured comparisons, not model-name assumptions.

## Support and boundaries

The ZIP contains the runtime closure, not the repository's developer benchmark
harness. Node loads no third-party npm modules; bundled controller/runner logic uses
the Python standard library. Native .NET uses existing supported xUnit/NUnit VSTest
packages and installed SDK. Pytest requires the project's Python/pytest environment;
the pinned interpreter does not supply arbitrary project dependencies. Generic
JSON/JUnit runners are extension points, not validated support for every framework.

Pinned downloads support the platforms declared in `runtime-manifest.json`; actual
Python is required elsewhere. Keep private `.ai-tdd`/`.ai-tdd-history` data and raw
logs local. Neither receipts, hooks nor this skill are an OS sandbox or proof of
no defects. DONE concerns the recorded reviewed artifacts and executed scope, and
does not authorize publishing or certify later edits.
