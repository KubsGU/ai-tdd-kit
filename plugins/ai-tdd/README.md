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

Requires Node.js on PATH and your project's working test runner. On Windows x64,
Linux x64 and macOS arm64, explicit runtime setup provides a version-pinned,
SHA256/size-verified controller without a separate Python installation. Other
hosts need Python 3.10+. Hooks never download a runtime. The Node facade preserves
the same controller and verifies the actual hook before beginning. It stores private
task state and execution receipts under `.ai-tdd/` in the target project.

For .NET, `init` detects and evaluates existing C# projects using SDK 8+/MSBuild
17.8+. The built-in VSTest runner supports xUnit with adapter >=3.0.0 and NUnit
>=3.14.0 with NUnit3TestAdapter >=4.5.0. It reconciles full project/TFM discovery,
native framework evidence and TRX, without a manually written adapter or package
upgrade. MSTest TRX and Microsoft.Testing.Platform fail closed until adequate
native evidence is supported. See [the .NET guide](references/dotnet.md) for
layout limits, runtime setup and existing build/analyzer/format checks.

Existing in-repository runsettings and verified restored NuGet content remain
inputs to setup. A genuinely absent external linked `Content`/`None` declared
by its owning project is accepted only without output/publish copying. Its
canonical path and absence are checked again during execution and freshness
gates; creating it invalidates setup. This grants no external write ownership.
Existing user-authored external files still need a reviewed custom setup.
Do not edit project files or create placeholder inputs merely to bypass setup.

xUnit IDs come from native discovery and execution, with readable display names
kept as metadata even when repeated or shortened. Read actual baseline report
and RED log/report IDs for acceptance mappings and review; do not build IDs from
names. Consistent discovery of theory parents and complete native child lifecycles
support rows enumerated at runtime, including nonserializable MemberData. Every
existing parent's row inventory is frozen; TRX independently corroborates all
outcomes per parent. xUnit v2 child IDs identify row ordinals, not argument values.
Keep data stable and native diagnostic logs local because they may contain fixture
values and paths. Incomplete module reports identify the cause and preserve later
module observations; they cannot certify a passing baseline, RED or GREEN.

Workers write only their declared tests or source. The coordinator runs the
required suite through the Node controller facade. Behavioral failures authorize
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

MIT license. Version 1.7.0.
