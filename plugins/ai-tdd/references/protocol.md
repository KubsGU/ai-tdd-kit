# Execution protocol

## Runtime and authority

Tested Claude Code: 2.1.285. Use this version or a newer compatible release;
older hook/subagent behavior is not validated. Python 3.10+ and Node.js must be
on PATH; use an actively supported Node LTS release. The Node launcher chooses
`python` on Windows and `python3` on Unix;
AI_TDD_PYTHON can specify an actual interpreter executable (not a shell alias).
Use the same interpreter for controller calls and hooks. The controller has no
third-party dependencies. pytest/Jest/etc remain dependencies of the host project.

The main Claude conversation is the coordinator. Use the plugin's named agents
through Agent, sequentially. Their allowlists omit Bash, other execution tools,
MCP tools and further delegation. Do not run them as the main agent. Pass only
task artifacts each role needs; they can read existing code to learn its APIs.
Do not pass a candidate implementation to the test author as design guidance.

During an active task the global PreToolUse hook limits writes by role and phase.
Coordinator Bash is limited to a direct bundled controller invocation; unknown
execution/mutation tools are denied. The coordinator writes setup before begin
and review during VERIFY. Test/source edits are delegated to their owner roles.
No active state means the plugin is quiescent. DONE also releases the workflow
guard, so a historical completion receipt does not certify later edits.
Use synchronous agent calls. Wait for an active worker to finish, or cancel its
task through Claude's lifecycle control, before changing phase or owner.

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
| begin [--allow-empty] | Validated spec/plan, passing full baseline → TEST. |
| status | Reads task, receipts and history; never changes state. |
| red --tests ID... --ac AC... --because "basis" [--expect AssertionError] | TEST/AMEND; unchanged source, exactly target behavior failures, old regressions pass → IMPLEMENT. Only AssertionError/explicit stub NotImplementedError accepted. |
| cover --tests ID... --ac AC... --because "basis" | New tests already pass with unchanged source → GREEN without claiming a RED cycle. |
| green | IMPLEMENT/GREEN; immutable tests/config, every required ID executes and passes → GREEN. Also used after a justified refactor. |
| next | Fresh GREEN/VERIFY → TEST for another small increment. |
| verify | Fresh GREEN and all AC IDs mapped → VERIFY. Mapping completeness still requires semantic review. |
| finish | Fresh GREEN, current accepting review, zero findings and final full passing execution → DONE. |
| amend --reason "independent evidence" --ac AC... | Unlocks test/spec ownership → AMEND; spec.version must increase by one and impacted AC evidence is invalidated. Old test IDs cannot disappear. |
| retry --reason "new diagnosis" | BLOCKED → IMPLEMENT with an audited new attempt budget. Not an automatic infinite loop. |
| reconfigure --reason "diagnosis" [--paths FILE...] | IMPLEMENT/GREEN/VERIFY/BLOCKED → RECONFIGURE; only coordinator may edit config.json and named existing protected setup files. Source/tests, path ownership, protected inventory and permission/instruction files remain locked. |
| rebase [--expect AssertionError] | RECONFIGURE; re-execute the full existing inventory with unchanged feature artifacts → fresh IMPLEMENT/RED or GREEN. No required test ID may disappear. |

The configured timeout bounds each runner invocation, not the total LLM runtime.
max_attempts bounds GREEN invocations in an increment, including refactor reruns.
The coordinator must bound repeated diagnosis/retry cycles itself. Permission
denials, unavailable environments and unknown requirements should be reported
honestly; do not fabricate evidence to complete a task.
If protected artifacts were changed outside their owner flow, restore their
recorded contents before opening amendment/setup repair. reconfigure unlocks
named regular files already in protected_paths, not new source ownership or
arbitrary directories. Installing dependencies on the host is a separate normal
environment action outside the active managed session; never edit permission
settings to bypass a denied command. Revalidation binds subsequent receipts to
the new declared setup; review must be repeated.

## Test evidence and adapters

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

For pytest use templates/config.pytest.json, adapt roots and use JUnit IDs
`classname.name` (not pytest node IDs). A `<failure>` without an explicit type is
treated as AssertionError by the JUnit adapter convention; `<error>` is a runner
error. Other runners must emit standard JUnit with stable unique testcase IDs,
consistent declared counts and exit 0 for pass/1 for failure. They are an extension
point, not a claim that every language/framework has been integration-tested.

Alternatively emit JSON:

```json
{"schema":1,"collected":["module.Class.test_case"],"results":[{"id":"module.Class.test_case","status":"passed","exception":"","detail":""}]}
```

Statuses: passed, failed, error, skipped. The runner—not an agent—produces this
report. New IDs grow the required suite. A JUnit report cannot independently prove
that tests excluded before baseline ever existed; correct suite configuration and
independent review remain necessary. A report is not a defense against compromised
test execution.

## Review and defects

Review schema:

```json
{"receipt_id":"current GREEN id","checked_ac":["AC1"],"findings":[],"limitations":[],"recommendation":"accept"}
```

A finding needs id, ac, case, expected, actual and impact. If found, keep its exact
reproduction in coordinator context/artifacts, use next for a new test-author
increment, obtain RED/GREEN, and request a fresh verifier review. Do not discard
unresolved findings when replacing a review object. The controller accepts only
an empty current finding list; semantic truth of that review remains the verifier's
responsibility. Required IDs retain newly added regression reproductions.

For an actual wrong test, amend before changing it, record independent evidence,
increment the spec version and re-execute. Do not use amend for an implementation
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

## Primary format references (checked 2026-09-30)

- [Plugin layout](https://code.claude.com/docs/en/plugins-reference)
- [Skills and substitutions](https://code.claude.com/docs/en/skills)
- [Agent tool allowlists](https://code.claude.com/docs/en/sub-agents)
- [Hooks, exec arguments and role fields](https://code.claude.com/docs/en/hooks)
- [Local marketplace installation](https://code.claude.com/docs/en/plugin-marketplaces)
- [Node main-module path handling](https://nodejs.org/api/cli.html#--preserve-symlinks-main)
