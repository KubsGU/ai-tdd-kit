# Execution protocol

Managed state and quality-log directories must be real local directories, not
symlinks or Windows junctions. Version 1.3.1 checks their resolved identity before
state initialization, lock creation, controller reads or quality-log writes.
This rejects existing redirection; it does not provide OS isolation or protection
against a hostile process racing filesystem operations.

## Runtime and authority

For model selection, compact handoffs and native cache checks, follow
[the efficiency policy](efficiency.md). All workers explicitly inherit the chosen
session model; omit per-invocation model overrides. There is no automatic cheaper
test-author/reviewer. The bundled launch helper defaults to Opus; a direct Claude
launch uses the model you choose. Normal provider/organization rules still apply.
For repository profiling, test oracles and tool scope, follow
[the quality guidance](quality.md).

Tested Claude Code: 2.1.285 and 2.1.286. Use a compatible current release;
older hook/subagent behavior is not validated. Python 3.10+ and Node.js must be
on PATH; use an actively supported Node LTS release. The Node launcher chooses
`python` on Windows and `python3` on Unix;
AI_TDD_PYTHON can specify an actual interpreter executable (not a shell alias).
Use the same interpreter for controller calls and hooks. The controller has no
third-party dependencies. pytest/Jest/etc remain dependencies of the host project.

Start Claude with `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1` in its environment.
This forces foreground subagents, including interactive sessions where fork mode
can otherwise choose background execution. Set it before launching Claude; keep
the same value when resuming. `doctor` and CLI `begin` reject an active Claude
runtime without this setting. Outside Claude, standalone controller checks do
not require it. See the main README for PowerShell and Unix launch examples.

The main Claude conversation is the coordinator. Use the plugin's named agents
through Agent, sequentially. Their allowlists omit Bash, other execution tools,
MCP tools and further delegation. Do not run them as the main agent. Pass only
task artifacts each role needs; they can read existing code to learn its APIs.
Do not pass a candidate implementation to the test author as design guidance.

During an active task the global PreToolUse hook limits writes by role and phase.
Coordinator Bash is limited to a direct bundled controller invocation; unknown
execution/mutation tools are denied. The coordinator writes setup before begin,
the agreed spec correction in AMEND and review during VERIFY. Test/source edits
are delegated to their owner roles.
No active state means the plugin is quiescent. DONE also releases the workflow
guard, so a historical completion receipt does not certify later edits.
Use synchronous agent calls. Wait for an active worker to finish, or cancel its
task through Claude's lifecycle control, before changing phase or owner.
The hook accepts only fresh plugin-qualified named agents allowed in the current
phase. Resumed workers, explicit background/isolation requests, foreign plugin
roles, worker delegation and agent dispatch during a controller run are denied.
This is a role/phase boundary, not a per-agent lifecycle lease: the coordinator
must still finish the worker before transitioning to another cycle.

These are workflow safeguards, not OS security. The user controls settings and
can disable hooks; a malicious executable test can modify its own process, forge
its report, or reach resources outside declared paths. Run untrusted code only
with an independently configured sandbox. No hidden-test isolation is claimed.

## Setup artifacts

- `config.json`: schema=1; disjoint narrow source_roots and test_roots; protected_paths
  for fixtures/helpers/config/dependency manifests/custom runner inputs. Paths
  are relative to the project root, with no parent traversal or symlinks.
- `spec.json`: positive integer version, nonempty goal and acceptance list with
  unique nonempty id and description. Add examples, scope, invariants,
  nonfunctional requirements and assumptions where relevant. open_questions
  must be empty before begin.
- `review-plan.json`: `{"scenarios":[{"ac":"AC1","case":"concrete scenario"}]}`;
  cover every AC before baseline/implementation. It stays frozen during the run.
- `repo-profile.json`: factual convention evidence from instructions, neighboring
  code, CI/scripts, tool configuration and lockfiles; record existing read-only
  quality commands and gaps before begin. The controller fingerprints this file
  whether present or absent; it does not validate the truth of the profile.

Prepare the profile and quality configuration before an active task starts.
Preserve established naming, errors, types, formatting and API conventions.
Do not introduce a formatter, global style change or unrelated restyling merely
to satisfy the kit. Include applicable repository CI checks that can run locally
without modifying managed files; describe unavailable checks as limitations.

Adapt the template to the existing project. Do not configure the entire repository
as a source root. Include all executed test roots and all external expected data.
The default template lists common config/lockfile names even when absent; add the
project's actual equivalents and custom runner/helper files. Hashes detect file
creation as well as changes. Do not include .env, credentials or live state.

For greenfield code create only directories and interface stubs during setup.
No new feature logic belongs in bootstrap. An empty baseline requires the explicit
--allow-empty waiver. Existing failures/skips must be resolved separately before
this version can certify a feature; it does not silently grandfather them.

## Controller commands

Prefix every command with:

```text
python -B "/absolute/path/to/ai-tdd/scripts/tdd.py" --root "/absolute/project"
```

Use `python3` on Unix where appropriate. In an active task use Bash, forward
slashes, and a single command; no cd, pipes, substitutions, redirection, operators
or command chaining. Keep rationale text plain without shell metacharacters.

| Command | Preconditions and resulting behavior |
| --- | --- |
| init | Creates config template without overwriting any existing config. |
| doctor | Executes the actual Node/Python hook with a sentinel input and validates its structured denial response. No task or source changes. |
| archive | DONE only; moves .ai-tdd into a unique project-local .ai-tdd-history/task-id without overwriting old evidence or changing feature files. |
| begin [--allow-empty] | Validated spec/plan, passing full test and configured quality baselines; checkpoint existing test files → TEST. |
| status | Recomputes freshness and returns the compact decision view with receipt paths; never changes state. Put --full before status for the complete diagnostic state. |
| red --tests ID... --ac AC... --because "basis" [--expect AssertionError] | TEST/AMEND; unchanged source, exactly target behavior failures, old regressions pass → IMPLEMENT. Only AssertionError/explicit stub NotImplementedError accepted. |
| cover --tests ID... --ac AC... --because "basis" | New tests already pass with unchanged source → GREEN without claiming a RED cycle. |
| green | IMPLEMENT/GREEN; immutable tests/config, every required ID executes and passes → GREEN. Also used after a justified refactor. |
| next | Fresh GREEN/VERIFY; checkpoint all current test files → TEST for another increment in a new file. |
| quality | Fresh GREEN/VERIFY; execute the configured read-only quality batch and record actual evidence. Optional before review. |
| verify | Fresh GREEN and all AC IDs mapped; refresh stale quality evidence → VERIFY. Mapping completeness still requires semantic review. |
| finish | Fresh GREEN, current accepting review, zero findings; freshly execute quality batch then full required tests → DONE. |
| amend --reason "independent evidence" --ac AC... | AMEND; coordinator manages spec.version +1 and test author corrects agreed tests. Impacted AC evidence is invalidated; required IDs remain. |
| retry --reason "new diagnosis" | BLOCKED → IMPLEMENT with an audited new per-increment attempt budget; the task-wide runner limit does not reset. |
| reconfigure --reason "diagnosis" [--paths FILE...] | IMPLEMENT/GREEN/VERIFY/BLOCKED → RECONFIGURE; only coordinator may edit config.json and named existing protected setup files. Source/tests, path ownership, protected inventory and permission/instruction files remain locked. |
| rebase [--expect AssertionError] | RECONFIGURE; re-execute the full existing inventory with unchanged feature artifacts → fresh IMPLEMENT/RED or GREEN. No required test ID may disappear. |

The configured timeout bounds each runner invocation, not the total LLM runtime.
max_attempts bounds GREEN invocations in an increment, including refactor reruns.
`max_runner_runs` bounds all runner invocations in one task (default 100, integer
1..10000). The baseline counts as the first run. Attempts count before execution,
including timeouts, malformed reports, setup repairs and the final completion
check. Retry and reconfigure cannot raise the limit frozen at begin. Choose a
sufficient limit during setup; exhausted tasks cannot produce new evidence.
This is not a model-token, spending or total wall-clock budget. Permission
denials, unavailable environments and unknown requirements should be reported
honestly; do not fabricate evidence to complete a task.

`max_quality_runs` independently bounds configured quality batches for the whole
task (default 20, integer 1..10000). One batch counts once even with several
commands, including failed or timed-out batches; configured baseline and fresh
finish batches count. No configured commands produce a not_configured receipt
without consuming this budget. Quality definitions and limit are frozen at begin;
reconfigure/rebase/retry cannot drop checks, weaken arguments or raise the limit.
Reserve budget for completion rather than repeating unchanged pre-review checks.

If protected artifacts were changed outside their owner flow, restore their
recorded contents before opening amendment/setup repair. reconfigure unlocks
named regular files already in protected_paths, not new source ownership or
arbitrary directories. Installing dependencies on the host is a separate normal
environment action outside the active managed session; never edit permission
settings to bypass a denied command. Revalidation binds subsequent receipts to
the new declared setup; review must be repeated.

## Test evidence and adapters

Normal TEST adds a new file. Every test file present at begin or the most recent
next is frozen by hook denial and checkpoint hashes, including tests/helpers not
selected for that increment. New files can be edited repeatedly during the same
TEST cycle. Neither appending to a frozen file nor retaining its IDs while changing
assertions is permitted. Only controlled AMEND allows the test author to correct
an existing file, with independent evidence and spec.version +1 managed by the
coordinator. Initial and subsequently required test IDs cannot disappear.

The controller executes argv without a shell, with a unique fresh report path.
No manual receipt command exists. It verifies exit/report consistency, exact
collected/executed ID inventories, no duplicates, no skips, previously required
IDs, file hashes before/after execution and source freshness at subsequent gates.
CLI begin also requires a working hook self-test. Receipts include the
spec/config/test/helper manifests, bundled controller/runner/hook code, role and
coordinator instructions,
source and a hash of interpreter/platform/relevant environment options. Dependency
lockfiles are bound when configured; installed package contents, every environment
variable, external services and nondeterministic state are not fully fingerprinted.

Built-in unittest JSON adapter supports ordinary tests and subtests. Failed
subtests count against their parent ID. Skips, expectedFailure and fixture/discovery
errors cannot certify a pass. Whole-suite inventory is the acceptance unit.

For pytest use templates/config.pytest.json, adapt roots and use actual pytest
node IDs, such as `tests/test_fee.py::FeeTests::test_threshold`. The bundled JSON
runner captures the exception type through public pytest hooks, aggregates setup,
call and teardown, and retains deselected tests as skipped evidence. Skip, xfail,
xpass and incomplete execution cannot certify the workflow. xdist parallel runs
are unsupported; use a serial runner. pytest remains a project dependency.

Generic JUnit uses stable `classname.name` IDs. All declared suite/root tests,
failures, errors and skipped counts must match actual cases; contradictory case
outcomes are rejected. RED requires an explicit compatible failure `type`.
A typeless `<failure>` is `UnknownFailure`, never an inferred AssertionError;
`<error>` represents an execution error. Plain pytest JUnit does not reliably
carry actual exception types, so use the bundled pytest JSON adapter instead.
Other runners must emit consistent JUnit or JSON, with exit 0 for pass/1 for
failure. They are extension points, not evidence of tested support for every
language/framework.

Alternatively emit JSON:

```json
{"schema":1,"collected":["module.Class.test_case"],"results":[{"id":"module.Class.test_case","status":"passed","exception":"","detail":""}]}
```

Statuses: passed, failed, error, skipped. The runner—not an agent—produces this
report. New IDs grow the required suite. A JUnit report cannot independently prove
that tests excluded before baseline ever existed; correct suite configuration and
independent review remain necessary. A report is not a defense against compromised
test execution.

## Executed quality checks

Optional config quality_checks is a list of at most 20 commands. Each has a unique
safe lowercase name (kebab-case, at most 64 characters), kind (lint, format,
typecheck, security or custom), nonempty argv, timeout_seconds (default 120,
positive and at most 3600) and inputs (repository-relative configuration paths).
The inputs are automatically protected, including initially absent files. Source
and test roots are already fingerprinted and cannot overlap inputs. See the
[minimal configuration example](quality.md#existing-quality-tools).

Commands execute as actual subprocesses without a shell, from the project root;
argv supports {python}, {root} and {plugin}. Use existing tools in read-only/check
mode. No --fix, --exit-zero, ignored type errors, disabled rules or similar gate
weakening. The kind label does not prove the argv performs that kind of check:
the profile and independent reviewer must assess command scope and diagnostics.
Normal tool caches are allowed; final commands still execute afresh.

Each batch retains a unique .quality.json receipt, actual exit/timeout/error
results, stdout/stderr log paths and hashes, plus unexecuted command names after
the first failure. Fingerprints reject changes to source, tests, protected setup,
environment, state or review. A failing tool returns the task to GREEN for bounded
repair. A source-only mutating formatter is also rejected and returns to GREEN;
source must be repaired by its owner, green rerun, and review repeated. Mutating
protected artifacts does not become an authorized setup repair.

begin requires passing configured quality checks. verify refreshes stale evidence;
quality can explicitly run in GREEN/VERIFY when useful. No checks produce
not_configured, never a lint/format/type/security pass. The review must state this
limitation. finish always performs a fresh batch before full tests, even when the
review's evidence was current. Its new receipt ID is completion evidence; review
continues to reference the latest pre-review ID for unchanged reviewed artifacts.
These safeguards do not sandbox hostile tools or fully fingerprint installed
packages, external services and every environment variable.
The reviewer must name each unchecked lint/format/type/security category even
when another category or a custom command passed; the controller does not infer
category coverage from command names or require tools for every category.

## Review and defects

Review schema:

```json
{
  "receipt_id": "current GREEN id",
  "quality_receipt_id": "latest pre-review quality id",
  "checked_ac": ["AC1"],
  "findings": [],
  "limitations": [],
  "quality_limitations": ["Actual tool scope or missing checks"],
  "repo_conventions": "Factual convention evidence from this repository",
  "test_assessment": [{
    "test_id": "executed test id",
    "detects": "Concrete faulty behavior",
    "oracle": "Independent contract basis for expected value",
    "why_needed": "Distinct defect contribution"
  }],
  "recommendation": "accept"
}
```

test_assessment must cover every added ID and every AC-mapped ID, with no duplicate
or unexecuted IDs. For each, give a concrete faulty implementation, independently
justified expected behavior and distinct contribution; do not use a test count or
coverage quota. quality_receipt_id must be the current pre-review ID. Every quality
limitation is a nonempty string; the array must be nonempty when no tools are
configured. repo_conventions must give factual evidence, not generic praise.
The controller checks schema, ID coverage and freshness. It cannot prove the
semantic truth of assessment strings, test oracles or repository consistency.
The verifier makes that judgment using code, contract and real execution evidence.

A finding needs id, ac, case, expected, actual and impact. If found, keep its exact
reproduction in coordinator context/artifacts, use next for a new test-author
increment, obtain RED/GREEN, and request a fresh verifier review. Do not discard
unresolved findings when replacing a review object. The controller accepts only
an empty current finding list; semantic truth of that review remains the verifier's
responsibility. Required IDs retain newly added regression reproductions.

For an actual wrong test, amend before changing it, record independent evidence,
let the coordinator increment the spec version and the test author correct the
test, then re-execute. Do not use amend for an implementation
that simply fails correct requirements. Keep AC IDs stable for the task; new scope
should normally be a new task. Security/performance/integration requirements need
appropriate executable checks, not solely unit assertions or an LLM's confidence.

## Resume and next feature

One active task per checkout; no concurrent workers. Atomic state and an exclusive
controller.lock prevent normal competing phase writes. If interrupted during a
runner call, first confirm the process is dead; remove only that stale lock manually.
Do not reset state to recover. Tests and local evidence stay in .ai-tdd; stdout/
stderr logs may contain private project output and must not be published by default.

After DONE, run archive before init for another feature. It retains the entire
task in .ai-tdd-history under its unique ID; source and test files stay in place.
Never publish either state directory by default. Moving to another computer requires a
new environment-bound baseline; moving the plugin ZIP does not require moving
project state or any credentials.

In DONE, `status` checks the final completion receipt and the actual review-file
hash. Editing/removing that review invalidates freshness without rewriting state.
Finish and archive active tasks before updating the plugin: its protected runtime
and protocol hashes intentionally invalidate receipts from another version.
An active 1.2 task without test_checkpoint cannot be resumed by 1.3. Finish and
archive using the original plugin first. Do not infer a checkpoint from current
files or edit state to migrate an active task.

## Primary format references (checked 2026-10-01)

- [Plugin layout](https://code.claude.com/docs/en/plugins-reference)
- [Skills and substitutions](https://code.claude.com/docs/en/skills)
- [Agent tool allowlists](https://code.claude.com/docs/en/sub-agents)
- [Hooks, exec arguments and role fields](https://code.claude.com/docs/en/hooks)
- [Local marketplace installation](https://code.claude.com/docs/en/plugin-marketplaces)
- [Node main-module path handling](https://nodejs.org/api/cli.html#--preserve-symlinks-main)
- [pytest hook API](https://docs.pytest.org/en/stable/reference/reference.html#pytest.hookspec.pytest_runtest_makereport)
