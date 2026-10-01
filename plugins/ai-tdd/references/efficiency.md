# Models, context and caching

The ordinary launch defaults to Sonnet. Every role inherits the explicitly
selected session model unless a deliberate worker policy was configured before
begin. Lower price is not evidence of equal quality: keep the same contract,
test assessment, independent verification and execution gates for every profile.

## Session launch and model choice

From the downloaded/cloned marketplace root, select the project whose feature
you want to implement:

```text
python -B scripts/launch_claude.py --project /path/to/your-project
```

The launcher requests `sonnet`, enables foreground workers and removes cache-disable
and forced worker-model variables from its child environment. It does not edit
user/project settings or override normal permissions, authentication or providers.
Use an explicit Opus session for complex or consequential reasoning. All three
role definitions retain `model: inherit`; the controller permits only the model
specified by the task's frozen `worker_models` policy, never arbitrary overrides.

An explicitly chosen model/effort remains possible:

```text
python -B scripts/launch_claude.py --project /path/to/your-project --model opus --effort high
python -B scripts/launch_claude.py --project /path/to/your-project --model sonnet
```

Alternatively, invoke the helper by its absolute path from your feature project;
without `--project` it keeps the current directory. Extra Claude options go after
`--`, for example `-- --continue`. `--dry-run` displays the launch choices without
starting a session.

Without `--effort`, Claude uses its ordinary configured/model-default effort. Use
high effort when the task needs deeper verification; there is no automatic
reduction and no blanket max setting. Sonnet is an explicit user's cost/quality
choice, not an automatically equivalent substitute. Pin a full provider-supported
model ID for reproducible comparisons. Provider aliases, organization rules and
native fallback can affect the actual model; inspect runtime usage instead of
treating the requested alias as proof. Deterministic bookkeeping stays in Python.

## Deliberate role routing

Configure `worker_models` in `.ai-tdd/config.json` before begin. Omitted roles
inherit the session; `{}` is the same all-inherit default. Supported overrides
for the author and verifier are `opus` only; the implementer may explicitly use
`haiku`, `sonnet` or `opus`. These names select models, not capability proofs.
The session itself remains the user's choice; a Haiku session makes inherited
roles Haiku and is an experimental whole-workflow choice, not our default.

For a bounded implementation experiment with a Sonnet session:

```json
"worker_models": {
  "test-author": "inherit",
  "implementer": "haiku",
  "verifier": "inherit"
}
```

For an Opus verifier with a Sonnet session, set `verifier` to `opus` and retain
the other roles as `inherit`. The coordinator must pass the exact configured
override in each named Agent invocation, including PLAN before begin; omit the
invocation model for `inherit`. The active hook rejects omitted or wrong explicit
models and freezes this map independently of setup-repair permissions. Compact
status includes the normalized map. Legacy missing snapshots permit only inherit.

Choose smaller implementation models only deliberately for complete, bounded
contracts. Do not weaken the test oracle, review or tool scope to make a cheap
attempt pass. There is no automatic escalation in this release: a failed small
model still needs a diagnosis and bounded repair under the same frozen policy.
If a different model is needed, preserve the incomplete evidence; do not change
config, use forced environment overrides or silently retry a different profile.
The current fixed policy trades flexibility for auditable model choices.

Use [the paired benchmark protocol](../../../validation/MODEL_BENCHMARK_PROTOCOL.md)
and its observed results to assess profiles. Small synthetic samples do not prove
lossless routing for arbitrary repositories or security-critical changes.

## Small, faithful handoffs

Controller commands return a compact decision view by default: phase, cycle,
current increment, AC mapping, runner/quality budgets, receipt IDs/paths, actual
nonpassing test/tool reasons, and completed review limitations. Full state and
receipts remain on disk. Use `--full` before the command for diagnostic output:

```text
python -B /path/to/ai-tdd/scripts/tdd.py --root /project --full status
```

Dispatch briefs contain these parts in order:

1. Role/mode, phase/cycle and the one behavior/affected ACs.
2. Spec/plan/profile paths and relevant interface/source/test paths and ownership,
   including frozen test files and the new file allowed for this TEST cycle.
3. Current GREEN/quality receipt IDs/paths and concrete failures or findings.
4. Required return facts: exact test IDs/oracle for the author, changed paths/gaps
   for implementation, or the complete review object and test assessments for
   verification.

Workers read the referenced contract and relevant real code, expanding to callers,
dependencies, fixtures and full evidence when needed. This is a navigation brief,
not a lossy replacement for requirements. Preserve every open finding and review
limitation. Repository instructions and all applicable acceptance criteria still
apply. Avoid repeated full hash inventories, whole histories, unchanged file
contents and raw passing logs in prompts. No fixed token cap truncates relevant
requirements or failure evidence. Workers remain fresh and sequential.

Choose checks by distinct contract defects and the repository's existing commands,
not by a test quota. Combine redundant examples when no meaningful fault detection
is lost. Verify refreshes stale quality evidence; an extra quality call is useful
only when it resolves a concrete question. Finish always reruns the configured
quality commands and full required tests. Native incremental tool caches are
allowed, but old receipts never replace those fresh invocations. Consult
[quality guidance](quality.md) for oracles, tool scope and limitations.

## Native cache, measured rather than assumed

Claude Code manages prompt caching automatically. Preflight rejects active Claude
sessions with cache-disable flags or a forced worker-model override. Stable role
definitions, scoped tools and a continuing coordinator session avoid avoidable
prefix churn. The launcher leaves TTL selection to Claude's provider/billing
defaults; forcing an hour for every short-lived worker can cost more in writes.
Each model has a separate cache, and each fresh subagent starts its own prefix.
Changing the main model reads the existing history cold; stable per-role choices
avoid repeated switching. Haiku 4.5 needs a 4,096-token cacheable prefix, versus
512 for the current 5.5 models. Do not pad prompts to manufacture cache hits.
Effort-change behavior depends on model and provider. Haiku 4.5 does not support
the effort parameter; retaining model-native defaults is not identical thinking.
Opus 5.5 and Sonnet 5.5 have the same cache-read unit price, so a smaller model
does not imply a proportional discount on a cache-heavy task. Include failed
attempts, output tokens and all role costs in comparisons.

The plugin does not inject API `cache_control`, intercept authenticated traffic,
cache model answers, or reuse previous runner results. Cached prompt processing
does not shrink the context window. Hits depend on matching prefixes, minimum
length, lifetime and provider support. The workflow still executes all prescribed
baseline, RED, GREEN and final checks and recomputes freshness against current files.

The real-Claude evaluator records requested and observed models, final per-model
input/output/cache-write/cache-read totals including subagents, estimated API
cost, controller-output bytes and independent behavioral checks. Missing counters
stay unavailable. Its cache-read fraction is the proportion of reported input
tokens read from cache, not a request hit rate or a promised bill reduction.
Resume usage is reported separately; stream fragments are never summed as totals.
Subscription usage is not a per-call invoice. `scripts/measure_context.py` measures
response bytes without a model, not savings in model tokens or wall-clock time.

One small successful run supports that task only. A claim of unchanged quality
or lower total cost/time across repositories needs repeated paired tasks with
the same model/effort, independent oracles and failures included. See ROADMAP.md.

Primary documentation checked 2026-10-01:

- [Model configuration](https://code.claude.com/docs/en/model-config)
- [Subagent model precedence](https://code.claude.com/docs/en/sub-agents#choose-a-model)
- [Claude Code cache behavior and TTL](https://code.claude.com/docs/en/prompt-caching)
- [Whole-tree usage accounting](https://code.claude.com/docs/en/agent-sdk/cost-tracking)
- [Costs and subscription usage](https://code.claude.com/docs/en/costs)
- [Cost/intelligence optimization and evidence limits](https://platform.claude.com/docs/en/about-claude/models/optimizing-for-cost-and-intelligence)
- [Haiku 4.5 model constraints](https://platform.claude.com/docs/en/models/haiku-4-5/overview)
