# Agensi submission package

Prepared 2026-10-09 for the original MIT-licensed AI TDD Kit, release 1.7.0.
This is a submission draft, not marketplace approval or a published listing.

## Uploads

Build with `python -B scripts/build_skills.py`. Upload **one archive per skill**:

| ZIP | Listing draft | Contents |
| --- | --- | --- |
| `ai-tdd-1.7.0.zip` | [ai-tdd listing](ai-tdd-listing.md) | `ai-tdd/SKILL.md`, README, MIT license, self-contained runtime sources, references, native Claude definitions and checksums |
| `ai-tdd-test-review-1.7.0.zip` | [test-review listing](ai-tdd-test-review-listing.md) | `ai-tdd-test-review/SKILL.md`, README, MIT license, adequacy guide, synthetic example and checksums |

Use the [public release assets](https://github.com/KubsGU/ai-tdd-kit/releases/tag/v1.7.0).
The full `ai-tdd-kit` plugin repository ZIP is a separate distribution and is not
the individual skill upload. Standard fields `name` and `description` match each
folder; optional metadata is strings. No private sources or execution logs are
included. Both drafts are **free**, retaining the project's MIT license. Paid
pricing, payout onboarding and legal acceptance remain the publisher's decisions.

## Behavior and permission disclosure

The full skill reads repository instructions, relevant source/tests and tool
configuration. It writes local `.ai-tdd/` state, reports and receipts; may archive
completed state to `.ai-tdd-history/`; fresh test-author and implementation workers
edit only their assigned paths in the selected project. The coordinator runs
existing project tests/build/analyzer/format-check commands through a source-visible
controller. Run commands only in a trusted project: its build/test code executes
with the invoking user's permissions. No automatic deployment or publication.

Runtime bootstrap is an explicit local preparation step when a backend is missing.
It downloads the pinned 1.5.0 interpreter asset from GitHub Releases, verifies its
recorded size and SHA-256 and caches it under the skill's `.runtime/`. GitHub may
redirect to its release-asset host. Subsequent controller runs reuse that local
backend. The ZIP contains no executable binary. Restore/test tools may contact
the project's configured package sources (for example NuGet) and have their own
local caches. Agent model requests and prompt caching are controlled by the host
agent/provider. There is no kit telemetry endpoint, credential upload or automatic
repository upload. The optional native Claude installation writes only the
selected Claude plugin scope; the verification harness uses isolated settings.

The read-only reviewer makes no command, network or mutation requests. It reads
only supplied/relevant files and returns findings in the conversation. Neither
skill is an OS security sandbox. Private source, test data and logs should remain
local; redact them when preparing a public report.

## Compatibility and evidence limits

The full controller is the canonical implementation, with no new framework adapter.
.NET retains Node.js plus the existing SDK/framework packages and, on supported
hosts, the optional pinned runtime. Other hosts can use existing Python 3.10+.
Python test projects still require their own interpreter/test dependencies.

Fresh sequential worker contexts are required for test/implementation/review
independence. Host-neutral execution keeps deterministic phase and freshness
checks; native Claude interception and enforced role tool lists require the
registered plugin. `doctor` verifies guard process health, not host installation.
Do not advertise equivalent interception in Cursor/Copilot or automatic support
for every marketplace agent. This release tests packaging, relocated subprocess
execution, native fixtures and isolated Claude registration; actual model behavior
in other clients is not certified. No guarantee of zero bugs or cheaper models
without quality loss is made.

## Publisher steps

1. Sign in/create the publisher account personally and review current terms.
2. Create two free listings using the individual drafts and ZIPs; inspect any
   current dashboard fields and scanner feedback rather than guessing their schema.
3. Submit for Agensi's automated and manual review. Resolve concrete review
   feedback without weakening controller or quality gates.
4. Add the actual accepted listing URLs to the repository after approval.

No account was created, message sent, legal terms accepted or listing submitted
by this rebuilding task.

## Primary requirements

- [Agensi creator checklist](https://www.agensi.io/learn/skill-md-creator-checklist)
- [Agensi security and review](https://www.agensi.io/security)
- [Agensi terms](https://www.agensi.io/terms)
- [Agent Skills specification](https://agentskills.io/specification)
- [Claude Code skills](https://code.claude.com/docs/en/skills)
- [Cursor skills](https://cursor.com/docs/skills)
- [Copilot skills](https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/customize-cloud-agent/add-skills)

The public requirements do not specify every dashboard field, ZIP byte/file limit
or a mandatory `external_urls` frontmatter schema. Do not invent those fields or
present our local verification as Agensi scanner approval.
