# Model cost and routing research

Primary documentation checked **2026-10-01**. This rationale contains no benchmark results or equal-quality promise.
Documentation pages have no publication date; model release dates are vendor metadata. Canonical pages supersede stale snippets.

## Current model choices

Prices are Anthropic API USD per million tokens, before provider-specific rates.

| Model | Release | Fresh input / output | Cache write 5m / 1h | Cache read | Native Claude Code effort |
| --- | --- | --- | --- | --- | --- |
| Haiku 4.5 | 2025-10-15 | $1 / $5 | $1.25 / $2 | $0.10 | Effort unsupported; manual extended thinking |
| Sonnet 5.5 | 2026-09-28 | $2 / $10 | $2.50 / $4 | $0.20 | Medium by default |
| Opus 5.5 | 2026-09-22 | $4 / $20 | $5 / $8 | $0.20 | Medium by default |

Sources: [Haiku](https://platform.claude.com/docs/en/models/haiku-4-5/overview), [Sonnet](https://platform.claude.com/docs/en/models/sonnet-5-5/overview),
[Opus](https://platform.claude.com/docs/en/models/opus-5-5/overview).
Sonnet's API default effort is high; Claude Code defaults to medium on both 5.5
models. Haiku has no equivalent effort control. Native defaults therefore do not
represent equal reasoning budgets. Aliases also vary by provider and CLI version;
pin full supported IDs for comparisons and inspect actual response usage.
[Claude Code model configuration](https://code.claude.com/docs/en/model-config)

**Opus and Sonnet 5.5 have the same cache-read price.** Their fresh input and output
prices differ, so total savings depend on writes, output, retries and context size.
Repricing historic tokens is a counterfactual, not evidence of another model's token use or quality. Claude Code reports
a local cost estimate; for Pro/Max subscribers it is not an invoice. Account usage
limits and actual billing must be interpreted separately.
[Cost tracking](https://code.claude.com/docs/en/costs)

## Dispatch must be explicit

Current native precedence: invocation `model`, agent frontmatter `model`, then
`CLAUDE_CODE_SUBAGENT_MODEL`, then session. `model: inherit` beats the environment
default. Before v2.1.251 the variable came first; v2.1.257 added a force override.
Organization rules can substitute models and cap effort. Frontmatter effort also
remains subject to environment controls. Requested aliases do not prove execution.
[Subagent model selection](https://code.claude.com/docs/en/sub-agents#choose-a-model)

AI TDD Kit freezes `worker_models` before begin; named invocations must match it.
Author/verifier overrides are Opus only; implementer overrides allow Haiku,
Sonnet or Opus. Inherited roles follow the session. **No automatic model fallback
or escalation policy is supplied.** See [implementation policy](../plugins/ai-tdd/references/efficiency.md).

## Cache and latency implications

Each model owns a separate cache: switching the main model or using `opusplan`
causes a cold history read. A normal subagent has a separate prefix and warms its
own cache; its first request does not reuse the parent's cache, while the parent's
prefix stays intact. Resuming a subagent can reuse its original cache.
[Native cache behavior](https://code.claude.com/docs/en/prompt-caching)

Within included subscription usage, the main conversation defaults to a one-hour
TTL and ordinary subagents to five minutes. API/usage-credit requests default to
five minutes. Native controls require v2.1.242+: settings `promptCacheTtl` and
`subagentPromptCacheTtl`, or variables `CLAUDE_CODE_PROMPT_CACHE_TTL` and
`CLAUDE_CODE_SUBAGENT_PROMPT_CACHE_TTL`. One-hour writes cost more; retain five
minutes for short uninterrupted loops, consider one hour for repeated longer pauses.
On native 5.5 API/subscription runs, effort changes preserve cache, with documented
provider, HIPAA and disabled-beta exceptions.
[TTL controls and exceptions](https://code.claude.com/docs/en/prompt-caching)

The minimum cacheable prefix is **4096 tokens for Haiku 4.5**, versus **512 for
Opus/Sonnet 5.5**. Short Haiku requests may be uncached. Keep meaningful context;
do not pad prompts just to increase cache metrics. Cache hit fractions describe input reuse, not a percentage reduction in the whole bill.
[API cache limitations](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)

## Candidates and selection bar

These are experiment candidates, not equivalent-quality assertions.

| Session | Test author | Implementer | Verifier | Candidate purpose |
| --- | --- | --- | --- | --- |
| Opus | Inherit | Inherit | Inherit | Existing whole-workflow reference |
| Sonnet | Inherit | Inherit | Inherit | Ordinary complete contracts |
| Sonnet | Inherit | Haiku | Inherit | Separately measured, bounded implementation |
| Sonnet | Inherit | Inherit | Opus | Stronger final judgment with cheaper execution |

Select using complete-task cost and time, preserved original tests, actual models,
independent hidden oracles and executed fault detection. A generated suite passing
its own implementation is insufficient. Keep identical acceptance gates and show
failures, unavailable usage and paired case results. Small synthetic samples cannot
establish no quality loss across arbitrary repositories. The registered design and
observations belong in the [benchmark protocol](MODEL_BENCHMARK_PROTOCOL.md) and
[result report](MODEL_BENCHMARK.md), separately from this research.

Anthropic classifies model choice, effort and multi-model architecture as quality
tradeoffs. Its low-first/high-on-failure coding result depends on a reliable failure
signal and adds latency on failures. Those vendor runs used a modified 478-task
SWE-bench Pro subset on **2026-09-19 to 2026-09-20**, not the public leaderboard or
this framework. A future escalation experiment must pre-register triggers, keep
the same oracle/review bar and count every failed cheap attempt. It is not shipped.
[Vendor measurements and limitations](https://platform.claude.com/docs/en/about-claude/models/optimizing-for-cost-and-intelligence)

Native `--advisor opus` pairs with Haiku or Sonnet; consultations read the entire
transcript uncached. Calls are model-selected, with no enforcement/cap setting.
Usage is added to session totals. It needs the Anthropic API and feature-flag
fetching; subagents inherit it. It is an optional experiment, not our default or
independent acceptance gate.
[Advisor requirements, costs and caching](https://code.claude.com/docs/en/advisor)
