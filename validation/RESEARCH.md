# Tests that distinguish correct behavior from plausible bugs

Research checked against primary sources on 2026-10-01. This is the reasoning
behind AI TDD Kit 1.3, not a claim that the kit wins a benchmark or eliminates bugs.

## What related approaches teach us

| Source | Useful finding | Consequence for this kit | Limit |
| --- | --- | --- | --- |
| [TDFlow, EACL 2026](https://aclanthology.org/2026.eacl-long.70.pdf) | Reproducing the requested defect is a difficult step; later agents can change tests to make a patch look successful. | Require an executed RED before implementation; freeze existing test files as well as IDs. | A frozen incorrect oracle remains incorrect. Our explicit AMEND path retains contract correction. Published task results do not establish superiority here. |
| [EvalPlus, NeurIPS 2023](https://proceedings.neurips.cc/paper_files/paper/2023/file/43e9d647ccd3e4b7b5baab53f0368686-Paper-Conference.pdf) | Expanded inputs expose incorrect solutions that pass smaller suites. Test reduction can preserve selected fault-detection criteria. | Review boundaries and distinct defect witnesses; keep a smaller useful portfolio instead of a count quota. | The study concerns Python synthesis tasks. Preserving known fault detection does not prove future completeness. |
| [Google, Software Engineering at Google, Test Doubles](https://abseil.io/resources/swe-book/html/ch13.html) | Mock interactions can miss wrong behavior; real implementations and faithful fakes often provide better evidence. | Prefer observable results/state. Call-count/order assertions need a real side-effect, caching or protocol contract. | Some interactions are themselves requirements; this is not a mock ban. |
| [Stryker mutant states](https://stryker-mutator.io/docs/mutation-testing-elements/mutant-states-and-metrics/) and [equivalent mutants](https://stryker-mutator.io/docs/mutation-testing-elements/equivalent-mutants/) | Survival, absent coverage, compilation problems and behavioral detection mean different things. Equivalent mutants exist. | Run selected plausible faults when useful; report failure witnesses and unusable mutants separately. | We require behavior evidence for a claimed selected kill; a timeout alone is not such a witness, even where a tool's score counts it as detected. No compulsory 100% target. |
| [Hypothesis stateful testing](https://hypothesis.readthedocs.io/en/latest/stateful.html) | Generated action sequences can be compared with a model and checked against invariants. | For stateful changes, consider a simple independent model and sequences, with reproducible failure examples. | Properties/models still need a justified contract. Introducing this tool for every small change would add unnecessary work. |
| [Metamorphic classifier testing study](https://pmc.ncbi.nlm.nih.gov/articles/PMC3082144/) | Relations between transformed inputs and outputs help where direct expected answers are difficult. | Use contract-justified metamorphic relations, paired with anchors that reject degenerate constant outputs. | Plausible relations may be wrong. This classifier study is not evidence for arbitrary application behavior. |
| [Anthropic, Demystifying evals](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents) | Outcome checks and deterministic graders complement model judgments; graders themselves need examination. | Combine actual tests and repository quality tools with a separate adequacy review. Inspect failures and repeat representative end-to-end trials. | Model review remains fallible. We have a small integration trial, not a broad calibrated benchmark. |
| [Anthropic, Harness design](https://www.anthropic.com/engineering/harness-design-long-running-apps) | Separate planning, generation and evaluation work best with concrete criteria and feedback. | Spec and independent scenarios precede the patch; frozen evidence and bounded repair connect the roles. | Extra agents do not automatically improve quality; context and runtime costs matter. |
| [Claude Code best practices](https://code.claude.com/docs/en/best-practices) | Explicit verification and scoped context help agents assess their changes. | Preserve repo instructions, local conventions and executable verification, with compact handoffs. | Guidance is not a controlled comparison of our framework. |

## What is implemented

Each newly added or acceptance-mapped executed test needs a reviewer assessment:
the concrete defect it detects, an independent oracle and why the case adds useful
evidence. Circular expectations, checking source text, counting tests and merely
asserting that a mock was called cannot establish an unrelated behavioral claim.
Parameterized cases may share a test ID; explain their useful boundaries together.

The controller validates assessment coverage and fields. It **cannot mechanically
prove that the prose or oracle is correct**. The author and independent verifier
must inspect them against the actual contract. Selected mutation and property
checks strengthen evidence where relevant; they are optional, executed work,
not imagined scores or obligations to generate dozens of tests.

Before beginning, the coordinator records the repository's conventions and
existing quality commands. It uses those rules rather than imposing a universal
formatter. Read-only lint, formatting, type and security commands run through the
controller with timeouts, logs and receipts bound to the checked artifacts.
Definitions and budgets remain frozen. A final fresh execution is required before
DONE. Missing commands are explicitly `not_configured`, with review limitations.
Existing internal tool caches may help, but the final command still executes.

For example, [Ruff documents the linter's exit codes](https://docs.astral.sh/ruff/linter/)
and [read-only formatter checks](https://docs.astral.sh/ruff/formatter/).
`--exit-zero` would conceal violations; `--fix` would mutate a supposedly checked
patch. [Mypy documents its configuration and suppression flags](https://mypy.readthedocs.io/en/stable/command_line.html);
turning checks off is not a repair. A tool label such as `security` alone proves
nothing about the command's coverage. These commands are trusted repository code,
and artifact hashes do not create an operating-system sandbox.

The kit's own CI runs its Ruff rules, controller regressions and both deterministic
demos. The real Claude integration project adds actual Ruff lint, formatter check
and strict Mypy. See [the validation record](VALIDATION.md) for observed results
and limitations rather than inferred quality improvements.

## Tradeoffs

- Independent test authorship reduces direct patch-driven expectation changes;
  agents may still share the same mistaken interpretation.
- Freezing prior files preserves more than an ID inventory; normal increments need
  new files, and legitimate corrections need the explicit AMEND workflow.
- Small defect-driven portfolios are easier to understand; deleting redundant
  tests is a reviewed decision, not something the implementer does to get green.
- Existing lint/types/style catch a different class of defects from behavior tests;
  they do not establish security, complete coverage or a correct specification.
- Quality batches add process time. Default budgets, native incremental caches and
  compact receipts bound overhead without reusing stale final evidence.

There is no credible universal recipe for the fewest tests and the fewest bugs at
once. Our optimization target is useful defect detection per reviewable case, with
honest limits and unchanged regression evidence.
