---
name: resume
description: Use when an AI TDD task was interrupted, its context was reset, or its latest phase and evidence need inspection before continuing.
allowed-tools: Read, Glob, Grep, Write, Edit, Agent, AskUserQuestion, Bash(node "${CLAUDE_PLUGIN_ROOT}/scripts/tdd-launcher.cjs" *), Bash(python -B "${CLAUDE_PLUGIN_ROOT}/scripts/tdd.py" *), Bash(python3 -B "${CLAUDE_PLUGIN_ROOT}/scripts/tdd.py" *)
---

Read `${CLAUDE_PLUGIN_ROOT}/skills/feature/SKILL.md` and its execution protocol.
Run `node "${CLAUDE_PLUGIN_ROOT}/scripts/tdd-launcher.cjs" --root "." status`
for the current project using its recorded backend. Do not run setup-runtime
over existing state/lock or silently switch controller/.NET SDK versions.
If that backend is missing or corrupt, report the concrete environment blocker.
Resume the
recorded phase with the appropriate named agent and verified artifacts. Preserve
user changes, open review findings, test checkpoints and previous test IDs.
In TEST, create new test files; changing any file frozen at begin/next requires
AMEND. Inspect current GREEN and quality evidence: rerun stale tests with green,
and let verify refresh quality or use quality explicitly in GREEN/VERIFY. No
configured tools means not_configured with explicit review limitations.
Read the frozen repository profile and current per-test review assessments.
Use the frozen worker_models map for every dispatch; inherit omits the model,
while explicit overrides require their exact alias. Do not change routing to
evade a failed attempt or trust a requested model name as backend proof.
Do not run init/begin
over an existing task, hand-edit state, use old conversational claims as evidence,
or claim DONE without fresh required execution. If the task is DONE, report its
actual completion evidence and whether its recorded artifacts still match.
An active task from a version without test_checkpoint must be finished and
archived using its original plugin before upgrading; do not invent a checkpoint
from current files or migrate it by editing state.
