# Contributing

Keep the execution protocol and the controller's behavior consistent. A change
to role ownership, phase gates, test inventory, report parsing or correction
flows should include a concrete failure case and real execution evidence.

Use Python 3.10+ and a supported Node LTS on PATH. From the repository root:

These are development requirements. A normal supported .NET plugin installation
uses Node, the project's .NET SDK/packages and the verified controller bundle;
it does not require a separate Python installation.

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

CI runs for pull requests and main, with six OS/Python combinations. Superseded
runs are canceled; pinned package downloads use setup-python's pip cache. Actual
lint, tests and demos still run. Open a PR or use workflow_dispatch for branch CI.

Runtime releases require actual native builds on every advertised platform,
Python-free facade/hook execution and matching source-hash metadata. Keep
PyInstaller a development-only dependency and distribute its/CPython's bundled
license notices. Never freeze a build or run a managed integration while its
protected source/instruction files are still being edited. See
[PUBLISHING.md](PUBLISHING.md) for the release sequence.

.NET changes need actual VSTest discovery/native/TRX evidence, not just hand-made
XML fixtures. Distinguish body assertions from runtime/constructor/setup/cleanup
failures; retain native categories/types instead of inferring from prose. Test
missing/duplicate inventory, unsupported runner selection and generated-output
ownership. Preserve every project/TFM and existing quality rule. Package migration
or a universal formatter is not a setup fix. Record bounded host/framework scope
in the validation report.

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
