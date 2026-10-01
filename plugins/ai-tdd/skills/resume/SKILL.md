---
name: resume
description: Use when an AI TDD task was interrupted, its context was reset, or its latest phase and evidence need inspection before continuing.
allowed-tools: Read, Glob, Grep, Write, Edit, Agent, AskUserQuestion, Bash(python -B "${CLAUDE_PLUGIN_ROOT}/scripts/tdd.py" *), Bash(python3 -B "${CLAUDE_PLUGIN_ROOT}/scripts/tdd.py" *)
---

Read `${CLAUDE_PLUGIN_ROOT}/skills/feature/SKILL.md` and its execution protocol.
Run the bundled controller's `status` for the current project. Resume the
recorded phase with the appropriate named agent and verified artifacts. Preserve
user changes, open review findings, test checkpoints and previous test IDs.
In TEST, create new test files; changing any file frozen at begin/next requires
AMEND. Inspect current GREEN and quality evidence: rerun stale tests with green,
and let verify refresh quality or use quality explicitly in GREEN/VERIFY. No
configured tools means not_configured with explicit review limitations.
Read the frozen repository profile and current per-test review assessments.
Do not run init/begin
over an existing task, hand-edit state, use old conversational claims as evidence,
or claim DONE without fresh required execution. If the task is DONE, report its
actual completion evidence and whether its recorded artifacts still match.
An active task from a version without test_checkpoint must be finished and
archived using its original plugin before upgrading; do not invent a checkpoint
from current files or migrate it by editing state.
