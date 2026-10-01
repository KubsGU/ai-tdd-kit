# AI TDD

Claude Code plugin with clarified acceptance criteria, separate test author and
implementer contexts, verified RED/GREEN phases, and independent final review.

```text
claude plugin marketplace add KubsGU/ai-tdd-kit
claude plugin install ai-tdd@ai-tdd-kit --scope user
```

Start a new session with `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1` set in its
environment and `claude --model sonnet`, then use `/ai-tdd:feature <description>`. This enforces foreground
workers; see the repository README for PowerShell and Unix launch examples.
Resume an interrupted task with `/ai-tdd:resume`.

Workers inherit the selected session unless an explicit frozen worker_models
policy requests an override. Haiku implementation and an Opus verifier are opt-in;
the same quality gates apply, without an equal-quality guarantee. Native prompt caching
stays enabled; preflight detects cache-disable flags and forced worker models.
Compact controller output avoids repeated evidence, with full state on disk and
`--full` before the command for diagnostics. Tests are always executed afresh.
The optional repository launcher defaults to Sonnet and keeps normal user settings.
See [models and efficiency](references/efficiency.md) for launch options and limits.

Normal increments use new test files; prior files remain frozen until an explicit
AMEND. Every new or acceptance-mapped test needs a concrete defect/oracle/value
assessment. Existing repo lint, formatting, types and security checks run through
the controller, including fresh checks before DONE. Missing configuration is an
explicit limitation. See [test quality and repository checks](references/quality.md).

Requires Python 3.10+, Node.js on PATH, and your project's working test runner.
The controller verifies the actual hook before beginning. It stores private
task state and execution receipts under `.ai-tdd/` in the target project.

Workers write only their declared tests or source. The coordinator runs the
required suite through the Python controller. Behavioral failures authorize
implementation; missing/skipped tests, import errors and stale evidence do not.
Incorrect tests and runner configuration have distinct, audited correction flows.
The task-wide test-run limit survives retry and setup repair. The pytest JSON
adapter captures actual exception types, deselection and xfail/xpass. Generic
JUnit behavioral failures require an explicit type. DONE freshness includes the
final review file. Finish and archive active tasks before a plugin update.

See [the protocol](references/protocol.md) for commands, configuration and limits,
and [the project repository](https://github.com/KubsGU/ai-tdd-kit) for full
documentation, source, tests, the validation report and releases.

Hooks are workflow controls, not OS isolation. Separate contexts can still share
a mistaken interpretation, and tests in the same repository are not a secret
holdout. One validated example is not a comparative benchmark.

MIT license. Version 1.4.0.
