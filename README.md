# AI TDD Kit

A Claude Code plugin that turns a feature request into verified, incremental TDD.

Clarify behavior → versioned acceptance criteria → separate test author →
**executed RED** → separate implementer → **executed GREEN** → independent review.
A Python controller owns phase transitions and execution evidence. Claude Code
hooks and role tool lists check who may change each artifact.

[Polska instrukcja](README.pl.md) · [Protocol](plugins/ai-tdd/references/protocol.md)
· [Models and efficiency](plugins/ai-tdd/references/efficiency.md)
· [Validation](validation/VALIDATION.md) · [Roadmap](ROADMAP.md) · [MIT license](LICENSE)

Version **1.2.0**.

## Install

Requirements: Claude Code, Python **3.10+**, Node.js on PATH, and Git for fetching
this marketplace. Use a supported Node LTS release. Your project's test runner
and application dependencies remain project dependencies.

Run in your terminal:

```text
claude plugin marketplace add KubsGU/ai-tdd-kit
claude plugin install ai-tdd@ai-tdd-kit --scope user
```

Start Claude in your feature project with foreground agents enabled and an
explicit model. The conservative quality default is Opus. In PowerShell:

```powershell
$env:CLAUDE_CODE_DISABLE_BACKGROUND_TASKS = "1"
claude --model opus
```

On macOS/Linux:

```sh
CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1 claude --model opus
```

This setting is required for sequential agents. The preflight check explains it
if missing. Keep it set when resuming a task. In that session, run:

```text
/ai-tdd:feature Add a loyalty discount of 10%. Amounts are integer cents. It cannot be combined with a promotion.
```

The coordinator inspects existing APIs and tests, asks about behavior-changing
ambiguities, records the acceptance contract, and delegates each small increment.
Routine implementation decisions do not need approval rounds. If you ask for
no questions, it records reasonable assumptions; a genuinely unresolved behavior
decision remains a blocker.

After interruption or a context reset:

```text
/ai-tdd:resume
```

If Python is outside PATH, set `AI_TDD_PYTHON` to its executable. Node must be
available on PATH. The `doctor` check verifies the actual Node → Python hook
before a task can begin. Claude Code's normal permissions still apply.

## Models, tokens and caching

All three roles explicitly inherit the session model. Active-task dispatch rejects
per-call model overrides. There is no automatic cheap test-author or reviewer.
Keep the chosen model and effort stable; Claude's configured effort applies unless
you explicitly change it. Sonnet remains an explicit user's choice, with a possible
quality tradeoff rather than a promised equivalent substitution.

If you download or clone this repository, its optional helper selects the project,
defaults to Opus, enables foreground workers and removes cache-disable/forced
worker-model environment variables **only in the child process**:

```text
python -B scripts/launch_claude.py --project /path/to/your-project
```

Use `--effort high` when deeper reasoning is needed, `--model` for an explicit
choice, and `--dry-run` to inspect launch choices. Extra Claude options follow `--`.
The helper does not edit settings, permissions, authentication or MCP configuration.
For direct launches, remove cache-disable flags and forced worker-model overrides
if preflight reports them.

Claude Code manages prompt caching automatically; this plugin keeps native TTL
defaults. Compact controller output and short artifact-based handoffs avoid
repeating whole histories, hashes and passing logs. Full requirements and evidence
remain accessible. **Every prescribed test execution still runs.** Scripts needing
the former full JSON can pass `--full` before the controller command, for example
`tdd.py --root /project --full status`.

The deterministic demo's DONE response was 88.4% smaller in bytes. Two real Opus runs
reported 92.1–92.6% of input tokens read from cache, including subagents; see the
[validation report](validation/VALIDATION.md). Neither number is a measured
percentage reduction in total tokens, cost or duration. The evaluator reports
actual models and whole-tree cache counters; missing data stays unavailable.
See [the efficiency policy](plugins/ai-tdd/references/efficiency.md) for limits
and current primary documentation.

## What happens during a task

1. **Clarify:** inspect repository instructions, existing interfaces and the full
   regression suite. Record examples, AC IDs and assumptions.
2. **Plan verification:** the verifier derives scenarios from the contract before
   the new implementation exists. Establish a real passing baseline.
3. **RED:** a fresh test author writes one behavior increment. The coordinator
   executes it and checks the failure reason and prior passing tests.
4. **GREEN:** a fresh implementer changes declared source files. The controller
   reruns the required suite and checks frozen test/configuration artifacts.
5. **Review:** a separate verifier reviews the contract, code, test adequacy,
   boundaries and interactions. Findings lead to further small test cycles.
6. **DONE:** the controller requires a current accepting review with no open
   findings and executes the complete required suite again.

Refactor only when useful, then rerun the suite. A test that already passes is
recorded as existing-behavior coverage, without manufacturing a RED phase.

The test author and implementer have separate contexts and write ownership.
Workers have no shell, MCP or further delegation tools. The coordinator executes
tests through the controller. Import failures, collection errors, skips, missing
required test IDs and stale results cannot stand in for behavioral RED or GREEN.

An incorrect test has an evidence-based, versioned `amend` flow. A demonstrated
runner configuration problem has `reconfigure` and `rebase`. Both invalidate old
evidence and require new execution; the implementer cannot weaken its own tests.
Fresh agent dispatch is checked by phase. A task-wide runner budget (default 100
invocations, including baseline and final check) also survives retries and setup
repairs. It bounds test execution, not model usage or spending.

## Project setup and scope

The coordinator creates `.ai-tdd/` with the contract, configuration, state and
local execution evidence. One checkout supports one active task. Before another
feature it archives a completed task into `.ai-tdd-history/`, preserving evidence,
source and tests. Keep these local state directories private.

Use the repository's existing suite. Bundled JSON adapters support unittest and
serial pytest; pytest records actual exception types and native node IDs.
Generic JUnit is also supported, but a behavioral RED needs an explicit failure
type. Typeless failures are rejected as ambiguous. See the
[configuration examples](plugins/ai-tdd/templates/) and the
[execution protocol](plugins/ai-tdd/references/protocol.md) for ownership roots,
protected helpers/configuration, test reports and controller commands.

The passing baseline must include the real regression scope. Repositories with
existing failures or skipped tests need baseline work before starting. Narrow
source/test roots and correct protection of helpers, fixtures, lockfiles and
runner inputs matter. Small cosmetic changes may not justify this workflow.

## Evidence and limitations

The [validation report](validation/VALIDATION.md) records controller and
integration tests, a deterministic demo with three RED/GREEN cycles and two
selected mutation probes, and a real Claude Code run through DONE followed by a
successful second-session resume. The instruction-only baseline already handled
the cases tested; no measured prompt improvement is claimed.

Separate contexts reduce direct expectation drift, but models can share the
same mistaken interpretation. Hashes and test counts do not establish semantic
correctness. The hook protects workflow boundaries; it is not an OS sandbox.
A malicious test process can undermine runner evidence, and tests in the same
repository are not a secret holdout.

The initial local validation used Windows, Python 3.12.10 and Claude Code 2.1.285.
GitHub CI is configured for Windows, Linux and macOS with Python 3.10 and 3.12; inspect its
actual results for each commit. One small feature does not establish comparative
superiority, large-repository effectiveness, or a favorable cost/time tradeoff.
The complete workflow targets **Claude Code**, with local hooks and execution.

## Update or uninstall

Finish and archive active tasks before updating. Receipts bind the controller,
runner and protocol version; changing them invalidates earlier evidence. DONE
status also detects an edited or missing final review.

```text
claude plugin update ai-tdd@ai-tdd-kit
claude plugin uninstall ai-tdd@ai-tdd-kit
```

Automatic updates for a custom marketplace depend on the user's marketplace
settings. See [Claude Code's distribution documentation](https://code.claude.com/docs/en/plugins/publish).

## Develop and verify

From this repository:

```text
python -m pip install -r requirements-dev.txt
python -B -m unittest discover -s plugins/ai-tdd/tests -v
python -B scripts/smoke_demo.py
python -B scripts/measure_context.py
python -B scripts/build_zip.py
```

The controller uses Python's standard library. The development pytest dependency
enables actual pytest adapter integration tests. The demo simulates role edits and
does not call a model. An optional real-Claude evaluation uses normal account
usage: `python -B scripts/evaluate_claude.py --output validation/local-claude.json --resume-check`.

ZIPs are built from `BUILD_MANIFEST.json`, with a generated `CHECKSUMS.json`.
Local task states, raw model logs and evaluation JSON are excluded. See
[contributing](CONTRIBUTING.md), [releases](CHANGELOG.md) and
[publishing](PUBLISHING.md).
