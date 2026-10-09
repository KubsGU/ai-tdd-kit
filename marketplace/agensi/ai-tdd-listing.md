# Agensi listing draft: AI TDD

Draft for the project owner to submit. This document is not a live listing,
marketplace approval, or proof of agent-specific execution.

## Listing fields

- Title: AI TDD — Independent Tests and Verified Implementation
- Skill name: `ai-tdd`
- Version: 1.7.0
- Price: Free
- License: MIT
- Author/source: KubsGU / AI TDD Kit contributors, [source repository](https://github.com/KubsGU/ai-tdd-kit)
- Suggested category: Development / Testing, if present in the actual submission form
- Tags: TDD, agent workflow, test quality, .NET, Claude Code, verification
- Upload: the generated standalone `ai-tdd` ZIP, with one top-level `ai-tdd/`
  directory containing `SKILL.md`, README, LICENSE, scripts, references, templates,
  and optional native Claude integration files

## Short description

Turn a feature description into an agreed contract, independent tests, separate
implementation, and independent review with actual baseline, RED, GREEN, and fresh
completion evidence.

## Full description

AI TDD is an original Agent Skill distribution of AI TDD Kit, free under MIT. It
combines clarified acceptance criteria with a separate test author, implementer,
and read-only reviewer. A bundled controller executes real tests and records
baseline, targeted behavioral RED, GREEN, immutable test checkpoints, repository
quality checks, and a fresh completion run.

Test quality comes from independent expected values and distinct fault protection,
not test-count or coverage quotas. The workflow catches weak assertions in review,
preserves useful existing tests, follows repository conventions, and incorporates
existing read-only lint/format/type/security tooling. Missing or unavailable checks
are stated as limitations. The implementer cannot repair its own test oracle.

The package contains the controller, supported runners, guidance, templates,
installation instructions, and optional local native Claude marketplace. In Claude
Code, original plugin-qualified agents and enabled hooks provide the native
integration. Prefer an existing official plugin; only one `ai-tdd` plugin should be
enabled. Supported native .NET workflows use existing projects, SDK and xUnit/NUnit
VSTest packages, without new custom adapter code or project changes merely for setup.

Other supporting hosts must supply real fresh independent worker contexts or
separate sessions. The same controller preserves execution/checkpoint evidence,
but copying a skill does not install preventive host hooks, authenticate authorship
or selected backend models, or prove those contexts are fresh. A single conversation
pretending to hold three roles is not represented as independent execution.

Model choice remains deliberate; workers inherit by default. Compact handoffs
avoid unnecessary repetition, while the host/provider manages prompt caching.
Neither cheaper models nor this skill promise unchanged quality, lower bills, or
faster delivery without measured evidence. Prescribed fresh checks still execute.

## Requirements and honest boundaries

Node.js and either actual Python 3.10+ or an explicitly provisioned supported
checksum-verified runtime are required. Native .NET needs the repository's installed
SDK and supported VSTest packages. Python project tests need their actual interpreter
and dependencies. No npm modules or third-party controller libraries are required.
The optional pinned runtime setup explicitly downloads from the project's release;
hooks never download. Keep task evidence and private project logs local.

Documented Claude Code, Cursor, and GitHub Copilot skill locations establish
installation guidance, not executed compatibility in every product. Attach actual
release validation results with their scope. Do not claim “tested in 20+ agents,”
guaranteed defect detection, superiority, marketplace acceptance, an OS security
sandbox, or a bug-free implementation. DONE is current scoped execution evidence,
not publication authorization or a claim about later edits.

## Publisher notes

Submit the owner's original project with distribution rights, preserve its MIT
notice, and keep the listing free and non-exclusive. It is not a repackaged
third-party skill for resale. Do not promise exclusive rights or add marketplace
restrictions inconsistent with MIT. Use the marketplace account's current submission
process and review; acceptance depends on Agensi. The ZIP contains the runtime
closure rather than the full source repository or developer benchmark harness.
