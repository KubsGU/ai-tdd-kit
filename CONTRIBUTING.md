# Contributing

Keep the execution protocol and the controller's behavior consistent. A change
to role ownership, phase gates, test inventory, report parsing or correction
flows should include a concrete failure case and real execution evidence.

Use Python 3.10+ and a supported Node LTS on PATH. From the repository root:

```text
python -m pip install -r requirements-dev.txt
python -m ruff check .
python -B -m unittest discover -s plugins/ai-tdd/tests -v
python -B scripts/smoke_demo.py
python -B scripts/test_strength_demo.py
python -B scripts/measure_context.py
```

The Claude CLI is only needed for native plugin validation and an actual model
evaluation. Changes to skills or agent prompts should also be exercised with
real Claude Code; `scripts/evaluate_claude.py` creates a synthetic temporary
project and uses normal account usage. Report that separately from deterministic
tests. Do not call a role-edit simulation an agent benchmark.

Efficiency changes must preserve behavioral evidence and full regression scope.
The byte measurement is not a token/cost/time benchmark. Real comparisons need
the same pinned model and effort, independent oracles, repeated varied tasks and
failed runs included. Use final `modelUsage` totals, including subagents, rather
than adding streamed usage fragments or treating missing counters as zero.

Preserve regressions and justified test expectations. Do not bypass failing
checks by removing test IDs, weakening the runner, adding skips, editing task
state or resetting retry limits indefinitely. Correct bad expectations from the
contract, and record the new evidence.

Use the repository's established tool configuration and conventions. Review
cases by the concrete faults they distinguish and their independently justified
oracles, rather than count or coverage quotas. Quality-tool failures, missing
tools and skipped checks must remain explicit. A model's prose assessment is not
execution evidence; deliberately constructed fault demos are not LLM benchmarks.

Use synthetic examples in issues and pull requests. Share sanitized summaries
instead of `.ai-tdd/`, `.ai-tdd-history/` or raw model transcripts. Explain the
reproduction, expected behavior and actual result. Keep unrelated edits out of
the change.

Every public file must be listed in `BUILD_MANIFEST.json`. Local output belongs
outside that list. For a release, keep marketplace, plugin and build manifest
versions equal, update CHANGELOG.md, run native strict validation and an isolated
installation check, then follow [PUBLISHING.md](PUBLISHING.md).
