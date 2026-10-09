# AI TDD

A standalone Agent Skill for clarified requirements, independently authored tests,
separate implementation, and independent review backed by real execution evidence.
The skill package includes the same controller, supported runners, templates,
quality guidance, and optional native Claude integration used by AI TDD Kit.

It records actual baseline, targeted RED, GREEN, test checkpoints, repository
quality checks, and a fresh final run. Tests are chosen by useful contract faults
and independent expected values, not counts or coverage quotas.

## Install the skill

Extract the standalone ZIP and copy the complete `ai-tdd` folder to one location
below. `SKILL.md` must be immediately inside the folder; retain its bundled support
files. This ZIP is a single skill directory, not the full source-repository ZIP.

| Agent | Project path | Official documentation |
| --- | --- | --- |
| Claude Code | `.claude/skills/ai-tdd/` | [Claude skills](https://code.claude.com/docs/en/skills) |
| Cursor | `.cursor/skills/ai-tdd/` | [Cursor skills](https://cursor.com/docs/skills) |
| GitHub Copilot | `.github/skills/ai-tdd/` | [Copilot skills](https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/customize-cloud-agent/add-skills) |

These are documented discovery locations. They do not prove this package has
executed inside every product. Host versions, policies and tools affect availability.
Avoid duplicate skill copies in paths scanned by the same agent. Restart or refresh
the agent if it has not discovered the new skill.

## Claude Code native workflow

If the official `ai-tdd@ai-tdd-kit` plugin is already installed, use it and invoke
`/ai-tdd:feature <description>` or `/ai-tdd:resume`. A standalone skill need not
install a second copy or replace an active task's engine.

For a machine with no enabled `ai-tdd` plugin, an optional local marketplace is
included. Before a task, install it from the absolute extracted skill directory:

```text
claude plugin marketplace add "/absolute/installed/skills/ai-tdd"
claude plugin install ai-tdd@ai-tdd-local-skills
```

Use only one enabled `ai-tdd` plugin. Restart Claude with foreground workers enabled;
the [host integration guide](references/host-integration.md) gives platform examples.
Claude's original plugin-qualified agents, hook installation and tool boundaries
then apply. A skill folder alone does not register agents or hooks.

## Portable hosts

Ask your supporting agent to use `ai-tdd` with the feature description:

```text
Use ai-tdd to implement this feature through an agreed contract, independent
test author, separate implementer, and independent reviewer. Read repository
instructions and existing CI/style conventions. Use fresh sequential worker
contexts and the bundled controller for actual test and quality evidence.
```

The host must supply real independent worker contexts or separate sessions. Simply
renaming one conversation's role does not provide independence. Without that
capability the skill can prepare a contract, repository profile, configuration and
review plan inputs, but it must report the execution limitation rather than claim
the independent workflow completed.

Outside native Claude integration, controller checkpoints still verify executed
inventory, frozen artifacts, current evidence, and final checks. The skill does not
install preventive hooks in Cursor/Copilot, authenticate a worker's authorship or
backend model, or prove the host supplied fresh contexts. `hook_health: pass` means
the hook executable passed its self-test, not that the host registered it.

## Runtime and project prerequisites

- Node.js is required; use an actively supported LTS release. No npm packages or
  third-party Node modules need installation for the bundled launcher/hooks.
- Use installed Python 3.10+, or explicitly provision the pinned checksum-verified
  runtime on a declared supported platform. A native .NET workflow can use Node,
  the pinned runtime and the repository's existing .NET SDK without installing Python.
- Native .NET execution uses existing supported xUnit/NUnit VSTest packages. It
  evaluates existing projects/settings; supported projects need no new custom adapter
  or package/csproj changes. See [the exact .NET limits](references/dotnet.md).
- Python tests need the real project interpreter and packages. The pinned interpreter
  contains controller dependencies, not pytest or arbitrary project libraries.

The first backend probe is:

```text
node "/absolute/installed/skills/ai-tdd/scripts/tdd-launcher.cjs" --runtime-info
```

If needed, explicitly download the pinned runtime before a new task:

```text
node "/absolute/installed/skills/ai-tdd/scripts/tdd-launcher.cjs" setup-runtime --root "/absolute/feature/repository"
```

The command requires network access and a writable installation. Existing Python
can avoid that download. Hooks never download. Do not provision over state/lock or
replace a corrupt/frozen backend. Use absolute quoted paths and one direct command;
the [host guide](references/host-integration.md) explains phase commands and schemas.

## Quality, cost, and evidence

The author must justify expected values independently and name a distinct fault
each test catches. The reviewer assesses actual behavior and repository consistency,
including useful interaction tests and relevant integration boundaries. Existing
tests remain protected; correction requires an evidence-based amendment. Existing
read-only lint/format/type/security tooling can be configured before baseline. Missing
tools are explicit limitations; none are automatically installed or treated as passed.

Workers inherit the deliberately selected model by default. Lower-price routing is
opt-in and does not weaken execution or review gates. Prompt caching and billing are
managed by the host/provider. Compact artifact handoffs reduce avoidable repetition;
the skill does not promise lossless cost or time reductions, cache responses, or
reuse old test results instead of required fresh checks.

Format/layout validation and relocated controller execution must be distinguished
from actual agent invocation. See the release's published validation record for
executed scope. Documented skill paths alone do not justify a “tested in 20+ agents”
claim. Receipts establish their executed scope, not exhaustive correctness or an
operating-system sandbox. The ZIP includes runtime support, not developer benchmark
harnesses from the full repository.

Finish and archive an active task with its original installation/runtime before
updating or moving hosts. Keep private `.ai-tdd` and `.ai-tdd-history` logs and
state local. DONE does not authorize publication and does not certify subsequent edits.

Free under MIT; see `LICENSE` in the package. Source and releases:
[KubsGU/ai-tdd-kit](https://github.com/KubsGU/ai-tdd-kit).
