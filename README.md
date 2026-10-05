# AI TDD Kit

A Claude Code plugin that turns a feature request into verified, incremental TDD.

Clarify behavior → versioned acceptance criteria → separate test author →
**executed RED** → separate implementer → **executed GREEN** → independent review.
The controller owns phase transitions and execution evidence. A stable Node
launcher runs its Python implementation using an installed interpreter or a
verified bundled runtime. Claude Code hooks and role tool lists check who may
change each artifact.

[Polska instrukcja](README.pl.md) · [Protocol](plugins/ai-tdd/references/protocol.md)
· [Models and efficiency](plugins/ai-tdd/references/efficiency.md)
· [Test quality and repo checks](plugins/ai-tdd/references/quality.md)
· [.NET setup and evidence](plugins/ai-tdd/references/dotnet.md)
· [Research](validation/RESEARCH.md)
· [Validation](validation/VALIDATION.md) · [Roadmap](ROADMAP.md) · [MIT license](LICENSE)

Version **1.6.0**.

## Install

Requirements: Claude Code, Node.js on PATH, and Git for fetching this marketplace.
Use a supported Node LTS release. For .NET projects, use the project's existing
.NET SDK and test packages; the native setup requires SDK 8+/MSBuild 17.8+.
On Windows x64, Linux x64 and macOS arm64, a pinned controller runtime removes
the separate Python installation step when host policy permits that binary.
Windows Application Control blocked the unsigned bundle in the local attempt;
that policy needs an approved trusted runtime or existing Python. See the
[runtime limits](plugins/ai-tdd/references/dotnet.md#runtime-requirements).
Other hosts need Python **3.10+**.
Your application's dependencies remain project dependencies.

Run in your terminal:

```text
claude plugin marketplace add KubsGU/ai-tdd-kit
claude plugin install ai-tdd@ai-tdd-kit --scope user
```

Start Claude in your feature project with foreground agents enabled and an
explicit model. Start ordinary, bounded work with Sonnet; choose Opus deliberately
for complex or consequential reasoning. In PowerShell:

```powershell
$env:CLAUDE_CODE_DISABLE_BACKGROUND_TASKS = "1"
claude --model sonnet
```

On macOS/Linux:

```sh
CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1 claude --model sonnet
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

The coordinator probes the controller runtime before setup. If Python is absent
on a supported host, it runs explicit `setup-runtime` before starting a task.
That downloads the version-pinned GitHub release binary once and verifies its
size and SHA256. Cached binaries are verified again before use. Hooks never
download a runtime. If you use an installed Python outside PATH, set
`AI_TDD_PYTHON` to its executable. `doctor` verifies the actual hook/backend
before a task can begin. Claude Code's normal permissions still apply.

## .NET without manual adapters

Install the plugin, launch Claude in your solution directory, and use
`/ai-tdd:feature <description>`. `init` detects existing C# projects, evaluates
their MSBuild metadata and configures project ownership, generated output
directories and the native test runner. It does not upgrade NuGet packages or
change global settings. Existing configuration is never overwritten.

Existing in-repository `.runsettings` selected through MSBuild, including
`Directory.Build.props`, are retained and passed explicitly to both discovery
and execution. Coverage collectors and their coverage Include/Exclude rules
remain supported; settings that select tests, stop early or hide theory rows
are rejected. The selected file and its hash are bound to the task.
Package-supplied `Content`/`None` assets, including transitive dependencies, are
recognized through their restored package graph and import provenance. Restore
the repository's existing packages if those records are missing; setup does not
require editing `.csproj` files or excluding package content to bypass ownership.

An external linked `Content`/`None` declared by the owning project can also be
accepted when the file is genuinely absent and has no output or publish copy,
for example a missing ancestor `.dockerignore`. Its canonical path and absence
are bound to setup and rechecked at execution and freshness gates. Creating the
file invalidates that setup; it grants no external write ownership. Existing
user-authored external files still require a reviewed custom setup.

The built-in VSTest path supports existing xUnit projects with
`xunit.runner.visualstudio >= 3.0.0`, and NUnit projects with `NUnit >= 3.14.0`
and `NUnit3TestAdapter >= 4.5.0`. It reconciles separate discovery, native
framework evidence and TRX results across every configured test project/target
framework. Assertion evidence needs a test-body stack witness; runtime, setup,
teardown and missing-inventory failures cannot authorize implementation.

xUnit rows use native parent and child IDs; readable display names may be long,
shortened by the adapter, or repeated. The coordinator reads actual IDs from
the baseline report and new cases from the RED run's log/report, then uses
those IDs for acceptance mappings and review. It does not construct IDs from
test names. The runner discovers theory parents consistently and validates every
row emitted at execution, including nonserializable MemberData. It binds every
child lifecycle and compares per-parent outcomes with independent TRX results.
The existing parent row inventory is frozen across phases. xUnit v2 child IDs
identify ordinals, so authored data must remain protected and runtime data stable.

The runner collects all configured modules and retains incremental local progress
when a module fails. Incomplete discovery, a blocked assembly or missing evidence
produces a typed diagnostic and an incomplete report, never a passing receipt.
Existing test errors remain visible and prevent a passing baseline. No project
edit, coverage removal or security-policy change is an automatic repair.

Ordinary MSTest TRX and Microsoft.Testing.Platform are currently unsupported:
their available evidence is not treated as a typed behavioral RED. Unsupported
layouts, reporters or filters produce an actionable setup error. The
coordinator records existing `.editorconfig`, build/analyzer/format rules and
local CI commands before `begin`; missing quality configuration remains an
explicit limitation. See [the .NET guide](plugins/ai-tdd/references/dotnet.md)
for supported layouts, diagnostics and quality command examples.

## Models, tokens and caching

In the registered small-task comparison, Sonnet and Opus each completed 6/6
trials with the same selected fault detections. Sonnet cost 52.55% less and took
41.05% less mean native time. A Sonnet workflow with Haiku implementation also
passed 6/6, but saved only 2.11%; it remains opt-in. Whole-workflow Haiku passed
1/6. These three synthetic tasks repeated twice do not establish general quality
equivalence. See [all attempts and limitations](validation/MODEL_BENCHMARK.md).

All three roles inherit the session unless an explicit `worker_models` policy is
configured before begin. Dispatch must match that frozen map; setup repair cannot
change it. There is no automatic cheaper author/reviewer or mid-task escalation.
Choosing a model is a cost/quality decision, not a promise of equal capability.

For a bounded Haiku implementation experiment, launch Sonnet and request Haiku
for the implementer in your feature description. Before begin the coordinator sets:

```json
"worker_models": {"test-author": "inherit", "implementer": "haiku", "verifier": "inherit"}
```

Author/verifier overrides allow `opus` only; implementer overrides also allow
`haiku`/`sonnet`. An Opus verifier with a Sonnet session uses `verifier: "opus"`.
The same test oracles, review and final checks apply. If the fixed profile fails,
preserve the incomplete task rather than silently switching models or relaxing
checks. Profile experiments and limits are recorded in the
[paired benchmark protocol](validation/MODEL_BENCHMARK_PROTOCOL.md),
[observed results and limitations](validation/MODEL_BENCHMARK.md) and
[model/caching research](validation/MODEL_COST_RESEARCH.md).

If you download or clone this repository, its optional Node helper selects the project,
defaults to Sonnet, enables foreground workers and removes cache-disable/forced
worker-model environment variables **only in the child process**:

```text
node scripts/launch_claude.cjs --project /path/to/your-project
```

Use `--effort high` when deeper reasoning is needed, `--model` for an explicit
choice, and `--dry-run` to inspect launch choices. Extra Claude options follow `--`.
This helper is optional; direct Claude launches remain supported. The legacy
Python helper remains available for existing scripts.
The helper does not edit settings, permissions, authentication or MCP configuration.
For direct launches, remove cache-disable flags and forced worker-model overrides
if preflight reports them.

Claude Code manages prompt caching automatically; this plugin keeps native TTL
defaults. Compact controller output and short artifact-based handoffs avoid
repeating whole histories, hashes and passing logs. Full requirements and evidence
remain accessible. **Every prescribed test execution still runs.** Scripts needing
the former full JSON can pass `--full` before the controller command, for example
`node "/path/to/ai-tdd/scripts/tdd-launcher.cjs" --root /project --full status`.

In version 1.2, the deterministic demo's DONE response was 88.4% smaller in bytes. Two real Opus runs
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
3. **RED:** a fresh test author writes one behavior increment in a new test file,
   preserving prior test files. The coordinator
   executes it and checks the failure reason and prior passing tests.
4. **GREEN:** a fresh implementer changes declared source files. The controller
   reruns the required suite and checks frozen test/configuration artifacts.
5. **Review:** a separate verifier names each new/mapped test's concrete defect,
   independent oracle and distinct value, and checks repository conventions.
   Findings lead to further small test cycles.
6. **DONE:** the controller requires a current accepting review with no open
   findings and executes configured repo quality commands and the complete suite
   again. A missing quality configuration is an explicit limitation, not a pass.

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

## Useful tests and repository conventions

Optimize defect detection per useful case, rather than a test-count or coverage
quota. A test needs an independently justified expected answer and a plausible
incorrect implementation it would reject. The verifier must assess every new or
acceptance-mapped executed ID. The controller checks that the assessment is present
and complete; it cannot prove that the oracle or review judgment is right.

The coordinator records existing instructions, neighboring code and CI/tool rules
in a frozen repository profile. Configure the project's existing read-only lint,
format, type and security commands under `quality_checks`; their inputs are
protected. Commands actually run with bounded time, logs and fresh final receipts.
Defaults allow 20 quality batches, separately from the test-run budget. Configured
failures block completion; absent tools are reported as `not_configured` with
explicit limitations. Do not silently disable rules, auto-format the checked patch
or introduce a universal style. See [configuration and examples](plugins/ai-tdd/references/quality.md).

Selected mutation, property or stateful checks can strengthen appropriate changes.
They need actual execution and justified contracts; equivalent mutants and tool
failures do not justify a forced 100% score. The
[research comparison](validation/RESEARCH.md) connects these choices to primary
sources and records tradeoffs. `scripts/test_strength_demo.py` contrasts equal-count
weak and stronger suites on deliberately constructed faults, without calling AI.

## Project setup and scope

The coordinator creates `.ai-tdd/` with the contract, configuration, state and
local execution evidence. One checkout supports one active task. Before another
feature it archives a completed task into `.ai-tdd-history/`, preserving evidence,
source and tests. Keep these local state directories private.

Use the repository's existing suite. The built-in .NET runner is described
[above](#net-without-manual-adapters). Bundled JSON adapters support unittest and
serial pytest; pytest records actual exception types and native node IDs.
Generic JUnit is also supported, but a behavioral RED needs an explicit failure
type. Typeless failures are rejected as ambiguous. See the
[configuration examples](plugins/ai-tdd/templates/) and the
[execution protocol](plugins/ai-tdd/references/protocol.md) for ownership roots,
protected helpers/configuration, test reports and controller commands.

Python project runners still require their actual interpreter and packages.
The bundled controller contains standard-library dependencies, not pytest or
an arbitrary project's Python environment. Existing direct Python controller
commands remain compatible; `{python}` custom runner/quality commands need a
real project interpreter.

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
python -m ruff check .
python -B -m unittest discover -s plugins/ai-tdd/tests -v
python -B scripts/smoke_demo.py
python -B scripts/test_strength_demo.py
python -B scripts/measure_context.py
python -B scripts/build_zip.py
```

These are contributor commands; installing Python and development dependencies
is not part of the normal .NET user setup. The controller uses Python's standard
library. Pinned development dependencies
enable pytest integration, the kit's Ruff lint rules and the real-Claude fixture's
Ruff/strict Mypy checks. The demo simulates role edits and
does not call a model. An optional real-Claude evaluation uses normal account
usage: `python -B scripts/evaluate_claude.py --output validation/local-claude.json --resume-check`.

ZIPs are built from `BUILD_MANIFEST.json`, with a generated `CHECKSUMS.json`.
Local task states, raw model logs and evaluation JSON are excluded. See
[contributing](CONTRIBUTING.md), [releases](CHANGELOG.md) and
[publishing](PUBLISHING.md).
