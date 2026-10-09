# AI TDD Test Review

A self-contained, read-only Agent Skill for reviewing whether tests detect useful
contract violations. It identifies weak assertions, independently justified
expected values, missing behavior scenarios, and useful tests to preserve.

This skill is an original adaptation of the AI TDD Kit review role. It needs no
plugin, scripts, model subscription beyond your chosen agent, or runtime packages.
An agent needs the supplied specification and relevant repository files or excerpts.

## Install

Extract the skill ZIP and copy the entire `ai-tdd-test-review` directory to one
project location below. `SKILL.md` must be immediately inside that directory.

| Agent | Project path | Official installation documentation |
| --- | --- | --- |
| Claude Code | `.claude/skills/ai-tdd-test-review/` | [Claude Code skills](https://code.claude.com/docs/en/skills) |
| Cursor | `.cursor/skills/ai-tdd-test-review/` | [Cursor skills](https://cursor.com/docs/skills) |
| GitHub Copilot | `.github/skills/ai-tdd-test-review/` | [Copilot agent skills](https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/customize-cloud-agent/add-skills) |

These paths are documented discovery locations, not evidence that this package
has been executed in each product. Host versions, policies, file access, and skill
discovery determine availability. Avoid duplicate copies in paths scanned by the
same agent. Restart or refresh the agent if it has not discovered the new skill.

## Use

In Claude Code, invoke `/ai-tdd-test-review`. In any supporting agent, ask it to
use `ai-tdd-test-review` and supply the contract plus relevant files or excerpts:

```text
Use ai-tdd-test-review to review the tests for this diff.
Read the agreed acceptance criteria, repository instructions, relevant tests,
and implementation. Assess what concrete faults each changed test detects.
Return findings and proposed checks only. Do not edit files or run commands.
I have attached the current test and quality-check output separately.
```

Use a separate reviewer session when available. Otherwise disclose that the same
agent has already seen the implementation; changing a role label does not create
independent context. Missing files or clauses yield provisional findings and focused
questions, not invented requirements.

See [the synthetic example](references/example.md) for the distinction between a
self-equality assertion and a useful contract-observable cache interaction test.

## Validation and boundaries

The package uses the [Agent Skills format](https://agentskills.io/specification).
The official skill-creator `quick_validate.py` accepted its frontmatter and naming
during preparation on 2026-10-09. This does not establish model behavior, review
accuracy, marketplace acceptance, or actual execution across agents. The example
is illustrative and is not executed evidence. Any agent-executed evaluation should
be reported separately with its scope and result; do not infer one from format
validation.

This reviewer does not run tests, modify code, issue verification receipts, or
certify DONE. It cannot guarantee bug detection or enforce an operating-system
sandbox. Real test execution and implementation stay with the developer or the
coordinating workflow. Model reasoning can be wrong; findings require review.

Free under the [MIT license](LICENSE), including commercial use and redistribution
under its terms. Source: [KubsGU/ai-tdd-kit](https://github.com/KubsGU/ai-tdd-kit).
