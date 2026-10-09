# Agensi listing draft: AI TDD Test Review

Draft for the project owner to submit. This document does not represent a live
listing, marketplace approval, or an execution record.

## Listing fields

- Title: AI TDD Test Review
- Skill name: `ai-tdd-test-review`
- Price: Free
- License: MIT
- Author/source: KubsGU / AI TDD Kit contributors, [source repository](https://github.com/KubsGU/ai-tdd-kit)
- Suggested category: Development / Testing, if available in the submission form
- Tags: TDD, test review, test quality, code review, acceptance criteria
- Upload: the generated standalone `ai-tdd-test-review` ZIP, with one top-level
  `ai-tdd-test-review/` directory containing `SKILL.md`, README, LICENSE, and references

## Short description

Review whether your tests detect meaningful behavior defects. Find weak assertions,
justify expected values independently, and keep useful contract-based tests.

## Full description

AI TDD Test Review is a self-contained Agent Skill for an independent, read-only
assessment of a specification, affected tests, implementation diff, and supplied
test evidence. It is an original adaptation of the review role from AI TDD Kit,
released free under MIT.

For each test it asks: what concrete faulty behavior would fail this assertion,
where does the expected value come from, and what protection does this test add?
The resulting Markdown report separates observations, proposed counterexamples,
and supplied executed results. It identifies self-equality and duplicated
production logic without rejecting useful contract-observable interaction tests.

The package includes a focused adequacy reference, a synthetic cache example,
license, and installation instructions for the documented skill locations in
Claude Code, Cursor, and GitHub Copilot. It contains no executable scripts,
external services, runtime downloads, plugin dependencies, or fixed model choice.

The review leaves implementation and execution to the developer. It does not
modify files, run commands, publish results, issue controller receipts, or certify
feature completion. Test counts and coverage percentages are not quality quotas.
It recommends the smallest useful changes justified by your agreed contract and
preserves valuable existing tests.

## Honest compatibility and validation statement

The package follows the Agent Skills format and uses documented installation
paths. Structural checks and synthetic examples do not prove that it has run in
every agent. Attach actual evaluation results separately if performed. Do not
claim “tested in 20+ agents,” guaranteed defect detection, superiority to other
tools, marketplace acceptance, or a bug-free implementation.

The skill's read-only instructions are not an operating-system sandbox. The host
agent controls access and can make reasoning errors. A reviewer needs enough
contract and code context to substantiate findings; missing inputs are explicit
limitations.

## Publisher notes

Confirm authorship and that all uploaded files are the owner's original work or
covered by distribution rights. Preserve the included MIT notice. This is the
owner's existing open-source project, not a repackaged third-party skill for resale.
Keep the listing free and non-exclusive; do not claim exclusive rights or impose
restrictions inconsistent with MIT. Submit the final package through the marketplace
account and its current review process. Acceptance depends on Agensi's review.
