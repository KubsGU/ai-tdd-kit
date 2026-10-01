# Models, context and caching

The quality-preserving default keeps the selected session model for every TDD
role. This release reduces unnecessary evidence repetition; it does not trade
test quality, review depth or regression scope for a cheaper model.

## Session launch and model choice

From the downloaded/cloned marketplace root, select the project whose feature
you want to implement:

```text
python -B scripts/launch_claude.py --project /path/to/your-project
```

The launcher requests `opus`, enables foreground workers and removes cache-disable
and forced worker-model variables from its child environment. It does not edit
user/project settings or override normal permissions, authentication or providers.
For difficult reasoning this is a conservative default, not a claim that Opus
beats every model on every task. All three role definitions explicitly use
`model: inherit`; active-task Agent calls cannot override that model.

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
treating the requested alias as proof. No Haiku test-author/reviewer profile is
supplied. Deterministic bookkeeping stays in Python.

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
Model changes start a different cache; effort-change behavior depends on model
and provider. Select settings deliberately and avoid unnecessary switching.

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
