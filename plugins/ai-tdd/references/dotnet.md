# .NET setup and native evidence

Use this guide when configuring an existing C# repository. The kit runs the
repository's existing tests and tools; it does not migrate its test framework,
upgrade NuGet packages or change global .NET/Claude settings. Contributor build
dependencies are separate from end-user setup.

## Normal user path

Install the marketplace/plugin, launch Claude in the solution directory with
`CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1`, and invoke `/ai-tdd:feature <request>`.
The coordinator performs these setup steps before `begin`:

1. Inspect whether `.ai-tdd/state.json` already exists. For an existing task,
   run `status` using its recorded backend, then resume active work or archive
   DONE. Do not probe/provision a new runtime over existing state or a lock.
2. For a new task, probe the controller with
   `node "${CLAUDE_PLUGIN_ROOT}/scripts/tdd-launcher.cjs" --runtime-info`.
3. If no backend is available on a supported host, run
   `node "${CLAUDE_PLUGIN_ROOT}/scripts/tdd-launcher.cjs" setup-runtime --root "/project"`.
   Do this before a task state or controller lock exists. A resume restores the
   recorded backend; it never provisions a replacement over an active task.
4. Run `init`, which auto-detects `.csproj` files only when creating new configuration.
   Existing configuration is not overwritten. Run `doctor` before `begin`.
5. Inspect the evaluated configuration, complete the contract/profile and
   protect relevant helpers, fixture data and absent configuration inputs.
   Configure the repository's actual quality commands before the baseline.

Controller commands use one direct invocation:

```text
node "${CLAUDE_PLUGIN_ROOT}/scripts/tdd-launcher.cjs" --root "/project" status
```

`${CLAUDE_PLUGIN_ROOT}` is Claude Code's plugin substitution. In an ordinary
terminal, replace it with the installed plugin's actual directory.

## Runtime requirements

Node.js must be on PATH; use a maintained LTS release. The native .NET setup
requires the project's existing .NET SDK 8+/MSBuild 17.8+ and its test packages.
The selected SDK and controller backend are bound to task evidence; installing
or switching SDK/runtime versions mid-task requires diagnosis and fresh evidence.

For Windows x64, Linux x64 and macOS arm64, explicit `setup-runtime` downloads
the exact GitHub release asset named in `runtime-manifest.json`. The launcher
checks a pinned size and SHA256, rejects linked cache paths, and verifies the
binary again before use. Once provisioned, that cached bundle is preferred to
an installed Python. Corruption is an error, not a fallback to a different
backend. First setup needs network access and a writable plugin cache.

Windows Application Control blocked the unsigned PyInstaller bundle during the
local native execution attempt. An already installed Python backend works;
without Python, that policy requires an approved trusted runtime. Do not weaken
OS policy to install the kit. A provisioned bundle that is blocked or corrupt
fails closed. Before provisioning, an existing compatible Python can be used.
Actual native CI smoke results establish only their tested host scope; this
local attempt does not prove Python-free use under strict Application Control.

The cache lives under the plugin's `.runtime/<version>/<platform>/` directory.
Plugin and interpreter versions are independent: plugin 1.5.4 reuses the pinned
1.5.0 interpreter, which executes the installed external controller sources.
Its historical build metadata describes the original build inputs; the new
plugin source is covered by the source ZIP/checksums and task fingerprints.
Each native release binary has `.json` build metadata with source hashes and
tool versions, and a `.LICENSES.txt` sidecar with bundled component notices.
These are provenance and integrity records, not an author signature or proof
against a compromised release publisher. Native host/architecture compatibility
must match the release; a platform label alone does not prove every OS version.

The hook never downloads anything. Missing runtime during an active task blocks
managed actions with a diagnostic. Even DONE state must be archived before
runtime provisioning. Other hosts can use a real Python 3.10+ interpreter;
`AI_TDD_PYTHON` selects its executable when it is outside PATH. Direct Python
controller commands remain compatible.

The bundle is an interpreter for the existing standard-library controller.
It is not an arbitrary project Python environment: pytest and custom `{python}`
runner/quality commands still need their real interpreter and dependencies.

## Supported native test paths

The preset has no fixed project-count limit. It evaluates every discovered
project and retains every configured test module; 70/128-project regressions
also check exact ownership/output inventory and rejection of overlapping layouts.
Large solutions can take longer to evaluate and execute. Select the repository's
`timeout_seconds` before `begin` if the default 600 seconds is insufficient
(supported maximum 3600); the task freezes it. A larger repository does not
relax ownership, reporter, inventory or quality checks.

| Path | Existing package requirements | Evidence used |
| --- | --- | --- |
| xUnit + VSTest | `Microsoft.NET.Test.Sdk`, xUnit, `xunit.runner.visualstudio >= 3.0.0` | Separate structured VSTest discovery, native xUnit JSON events, and TRX. |
| NUnit + VSTest | `Microsoft.NET.Test.Sdk`, `NUnit >= 3.14.0`, `NUnit3TestAdapter >= 4.5.0` | Native discovery XML, structured native execution XML, and TRX. |
| MSTest ordinary TRX | Unsupported | TRX does not preserve sufficient body assertion type evidence. |
| Microsoft.Testing.Platform | Unsupported | Its reports and runner selection need a separately validated evidence path. |

Package versions must evaluate to exact stable versions. Central package
management is evaluated through MSBuild; configuration is not inferred only
from literal XML in `.csproj`. The kit does not silently upgrade an older
adapter or turn an unsupported report into a passing gate.

The preset evaluates all `.csproj` files below the chosen root and includes
each test project/TFM in the suite. Each source and test project needs its own
disjoint subdirectory, for example `src/App/` and `tests/App.Tests/`.
Root-level, shared or nested project ownership is unsupported. Projects need
explicit supported `net...` target frameworks, ordinary project-local `bin/`
and `obj/` output paths, and no selective test filters or MTP selection.
Existing user-authored external or unowned linked inputs need a reviewed custom
setup. A narrowly checked absent external content link is described below.
Test-project linked C# sources are accepted only when they belong to an
independently evaluated source project inside the root, whose source tree is
fingerprinted. Links into another test project are rejected. Ordinary evaluated
package-owned assets remain
tool dependencies; they are not copied into public evidence.

## Existing runsettings, package content and absent links

`init` accepts an existing regular `.runsettings` file inside the selected
repository root. It uses the evaluated effective `VSTestSetting`, falling back
to `RunSettingsFilePath`, including values inherited from `Directory.Build.props`.
A bare relative path is resolved from the project directory. The preset records
the resolved path and SHA256, protects the original file and passes its absolute
path through `--settings` for both discovery and execution. It does not rewrite
the file, clear the MSBuild property or copy a reduced version over it.

Coverage collectors and coverage-only Include/Exclude configuration remain
supported. A coverage exclusion controls what is measured, not which tests run.
The runner supplies its required evidence options and fresh output locations;
the repository's original runsettings remains the input to each phase. Test
filters, early stopping, collapsed theory discovery and unsupported adapter
controls are rejected with the setting identified. An unknown control needs a
precise compatibility rule before it can be accepted; removing the setting to
make the gate pass is not a setup repair.

Evaluated `Content`/`None` assets can come from direct or transitive NuGet packages.
An existing asset outside the repository is accepted only when its exact package
version is present in the selected restored target graph, its file is in that
package's recorded inventory and the defining import has the required provenance. This
supports direct `contentFiles` supplied through NuGet-generated imports in the
project's `obj/` directory and transitive assets supplied through resolved package
build imports. It does not change NuGet's own content propagation rules.
A cache directory or package-like path alone is insufficient. User-authored
external content does not become a trusted dependency through this exception.

An external linked `Content`/`None` may name a file that does not exist, such as
an ancestor `.dockerignore` left in a project's ordinary Docker tooling setup.
The preset accepts such an item only when the owning in-root `.csproj` declares
it, the canonical target is genuinely absent and it has no output or publish
copy. Imported items, existing external files and absent inputs copied by the
project remain unsupported. No project edit, placeholder file, root expansion
or changed coverage configuration is needed for this case.

Accepted targets are recorded in optional `dotnet.external_absent_inputs`, with
their canonical paths and required absence. These paths remain private local
configuration and grant no agent ownership outside the repository. Configuration
checks, native execution before and after each run, and controller protected
input/freshness gates recheck absence. Creating the file invalidates the recorded
setup and requires a supported configuration before execution can continue.
This is an absence assertion, not a blanket exclusion for external inputs.

If package ownership cannot be established because restore records are missing
or stale, restore the repository's existing package versions using its normal
setup before starting the task. Do not edit `.csproj`, add `ExcludeAssets`, remove
`Content`/`None` items or change package versions merely to bypass setup. Shared
user-authored fixtures inside the full repository root remain protected inputs;
when a narrower solution directory excludes them, choose the full repository root
before a new task and recheck the disjoint project layout. Existing configuration
is never overwritten by `init`.

Only the exact evaluated project `bin/` and `obj/` directories are excluded
from source/test manifests. Exclusions are frozen at `begin`; workers cannot
write there. C# source, projects, central package files, MSBuild inputs and test
fixtures remain protected/fingerprinted. A directory called `bin` elsewhere is
not automatically trusted. Discovery/build/test execution can create normal
generated output without making the task's source receipt stale.

Every run performs full unfiltered discovery and execution, with fresh report
locations and reconciliation of native IDs, outcomes and TRX counters. Duplicate
or unstable IDs, missing cases, malformed/truncated events, filters, skips,
unexecuted cases and inconsistent totals fail closed. The baseline must pass the
real suite; pre-existing skips or failures need separate resolution.

Native TRX and NUnit XML reports have a 64 MiB budget and must remain fresh regular
files without linked paths. Missing, unsafe and oversized artifacts receive
separate diagnostics. This accommodates verbose reports from large theory suites
without dropping cases or XML payload sections. Native ID/outcome reconciliation
and the separate normalized controller JSON/message bounds remain unchanged.

For xUnit, discovery uses fresh VSTest `--diag` transport JSON rather than the
readable `--list-tests` output. It collects `TestDiscovery.TestFound` cases and
the completion message's `LastDiscoveredTests` tail, requiring non-aborted
completion, matching totals and a fully discovered source assembly. Native
discovery transport batches use 100 cases to bound individual messages; this
does not filter or limit the total test inventory. Discovery warnings/errors
also prevent acceptance evidence. Native
`XunitTestCaseUniqueID` values must match the typed execution lifecycle. The
observed VSTest GUIDs must match TRX definitions, assembly source, class/method,
execution IDs and outcomes. Exactly one execution per discovered case is
required; non-serializable theories whose rows are enumerated only at runtime
remain unsupported.

The external xUnit ID is `project|TFM|xunit:<native-case-ID>`, for example with a
project prefix of `tests/App.Tests/App.Tests.csproj`. `display_name` is readable
metadata and may legitimately repeat or differ from a shortened discovery name.
Long theory data and long fixture paths do not require name-based identity.
The coordinator reads actual case IDs from the baseline report and each new
case's RED log/report before selecting tests, mapping ACs or reviewing executed
cases. Copy the complete reported ID; do not synthesize it from class, method
or display names.

Native discovery/execution diagnostics remain in fresh local report directories.
They can contain fixture values, serialized theory data and local paths; retain
them locally for diagnosis, outside public validation evidence. This evidence
path requires no dependency, package or project changes.

## What can establish RED

xUnit's generic failure `Cause` is insufficient, especially for v2 tests routed
through a v3 adapter. The runner requires observed assertion exception types
from its bounded allowlist plus a stack witness in the actual test body.
Runtime exceptions and assertions from constructors/setup/disposal cannot
certify the feature's RED.

NUnit supplies structured assertion outcomes rather than an actual assertion
exception type. The runner retains that native category and requires an
assertion result plus a stack witness in the actual test method before
normalizing a behavioral failure to `AssertionError`. It does not pretend to
have observed an exception type that XML omits. Errors, invalid/not-runnable
cases and setup/teardown failures are rejected, including suite-level cleanup
failures after otherwise passing child tests.

The ordinary controller then applies its unchanged gates: selected behavioral
failures only, every earlier required test passing, immutable contract/tests/
configuration, actual GREEN, independent test-quality review, and a fresh full
execution before DONE. Passing TRX or an LLM's classification alone is not
evidence of TDD.

## Existing style, build and analyzer checks

The preset leaves `quality_checks` empty because a tool cannot infer each
repository's quality policy. The coordinator records instructions, neighboring
code, `.editorconfig`, `Directory.Build.*`, central packages and CI commands in
the frozen repository profile, then configures applicable read-only checks.
An empty configuration yields `not_configured`, with explicit review limitations.

For a repository already using these exact commands, entries could be:

```json
"quality_checks": [
  {
    "name": "solution-build",
    "kind": "custom",
    "argv": ["dotnet", "build", "App.sln", "--no-restore"],
    "timeout_seconds": 600,
    "inputs": ["App.sln", "Directory.Build.props", "Directory.Build.targets", "global.json"]
  },
  {
    "name": "existing-format-check",
    "kind": "format",
    "argv": ["dotnet", "format", "App.sln", "--verify-no-changes", "--no-restore"],
    "timeout_seconds": 600,
    "inputs": ["App.sln", ".editorconfig", "Directory.Build.props"]
  }
]
```

Replace filenames and arguments with the repository's established commands;
these are examples, not automatically enabled rules. Restore required packages
through the normal project setup before the active task. Existing build
analyzers and warning policy remain the repository's decision. Protect every
command's actual inputs, including relevant absent files. Do not add `--fix`,
disable analyzers, lower warning severity or reformat unrelated code to pass.
See [quality guidance](quality.md) for budgets and final receipts.

## Troubleshooting and limits

An older xUnit adapter, ordinary MSTest TRX, MTP selection, custom output layout,
selective filters, unsupported runsettings or ambiguous evidence produces a
specific setup/run error.
Resolve the existing environment separately or retain the task as incomplete;
do not bypass it with a message regex, a narrowed suite or manual receipts.
For a runsettings error, inspect the resolved file and named setting locally.
For an ownership error, inspect the item's defining import and restored assets
graph; confirm the chosen root contains user-authored shared inputs. For an
absent external content link, confirm its own project declares it and no copy
metadata requests output/publish copying; do not create the missing file to
work around setup. If a previously recorded absent input appears, the setup
must be reviewed again rather than editing receipts to ignore it. Keep private
repository paths, fixture contents and native logs local. A public repository or
uploading private source is not required to use the kit or diagnose these checks.
MSBuild/test execution is trusted project code, not a sandbox for hostile code.
External services, installed package contents and nondeterminism are not fully
fingerprinted. Framework support is bounded; consult the
[validation report](../../../validation/VALIDATION.md) for actual executed scope.
Finish and archive active tasks with their original plugin before upgrading;
the existing baseline, RED/GREEN and evidence freshness guards still apply.

Primary references:

- [VSTest dotnet test options](https://learn.microsoft.com/en-us/dotnet/core/tools/dotnet-test-vstest)
- [Microsoft runsettings configuration and project properties](https://learn.microsoft.com/en-us/visualstudio/test/configure-unit-tests-by-using-a-dot-runsettings-file)
- [NuGet generated MSBuild props and targets](https://learn.microsoft.com/en-us/nuget/concepts/msbuild-props-and-targets)
- [NuGet contentFiles generation source](https://source.dot.net/NuGet.Commands/RestoreCommand/ContentFiles/ContentFileUtils.cs.html)
- [Microsoft.Testing.Platform dotnet test integration](https://learn.microsoft.com/en-us/dotnet/core/tools/dotnet-test-mtp)
- [xUnit runsettings/reporters](https://xunit.net/docs/config-runsettings)
- [xUnit 3.0.0 discovery identities and display names](https://github.com/xunit/visualstudio.xunit/blob/3.0.0/src/xunit.runner.visualstudio/Sinks/VsDiscoverySink.cs)
- [VSTest 17.14.1 discovery transport and completion](https://github.com/microsoft/vstest/blob/v17.14.1/src/Microsoft.TestPlatform.CommunicationUtilities/TestRequestSender.cs)
- [NUnit adapter settings](https://docs.nunit.org/articles/vs-test-adapter/Tips-And-Tricks.html)
- [dotnet format check mode](https://learn.microsoft.com/en-us/dotnet/core/tools/dotnet-format)
- [PyInstaller operation and host builds](https://pyinstaller.org/en/stable/operating-mode.html)
