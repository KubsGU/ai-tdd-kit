# Contributing

Keep the execution protocol and the controller's behavior consistent. A change
to role ownership, phase gates, test inventory, report parsing or correction
flows should include a concrete failure case and real execution evidence.

Use Python 3.10+ and a supported Node LTS on PATH. From the repository root:

```text
python -m pip install -r requirements-dev.txt
python -B -m unittest discover -s plugins/ai-tdd/tests -v
python -B scripts/smoke_demo.py
```

The Claude CLI is only needed for native plugin validation and an actual model
evaluation. Changes to skills or agent prompts should also be exercised with
real Claude Code; `scripts/evaluate_claude.py` creates a synthetic temporary
project and uses normal account usage. Report that separately from deterministic
tests. Do not call a role-edit simulation an agent benchmark.

Preserve regressions and justified test expectations. Do not bypass failing
checks by removing test IDs, weakening the runner, adding skips, editing task
state or resetting retry limits indefinitely. Correct bad expectations from the
contract, and record the new evidence.

Use synthetic examples in issues and pull requests. Share sanitized summaries
instead of `.ai-tdd/`, `.ai-tdd-history/` or raw model transcripts. Explain the
reproduction, expected behavior and actual result. Keep unrelated edits out of
the change.

Every public file must be listed in `BUILD_MANIFEST.json`. Local output belongs
outside that list. For a release, keep marketplace, plugin and build manifest
versions equal, update CHANGELOG.md, run native strict validation and an isolated
installation check, then follow [PUBLISHING.md](PUBLISHING.md).
