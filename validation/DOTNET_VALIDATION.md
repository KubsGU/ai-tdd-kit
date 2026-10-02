# .NET and bundled runtime validation — 1.5.0

Status: **candidate evidence; final release validation pending**. This report
separates actual native execution from synthetic parser fixtures and role-edit
simulation. It does not claim every .NET framework/layout or Windows policy is
supported, nor comparative model quality or a production bug-rate reduction.

## Current recorded native CI

The candidate at `78b7531` was exercised in
[native run 36988224953](https://github.com/KubsGU/ai-tdd-kit/actions/runs/36988224953).
The recorded outcomes below apply to that candidate, before the pending Windows
package-input provenance correction:

| Job scope | Actual recorded result |
| --- | --- |
| Runtime / Linux x64 | Passed native bundled execution with Python absent from the controller PATH, and complete xUnit/NUnit DONE demonstrations. |
| Runtime / macOS arm64 | Passed native bundled execution with Python absent from the controller PATH, and complete xUnit/NUnit DONE demonstrations. |
| .NET / Linux / SDK 8.0.100 | Passed native xUnit/NUnit evidence and complete DONE demonstrations. |
| .NET / Linux / SDK 10.0.301 | Passed native xUnit/NUnit evidence and complete DONE demonstrations. |
| Runtime / Windows x64 | Failed on standard testhost package-owned Content provenance; repair and rerun pending. |
| .NET / Windows / SDK 8.0.100 | Failed on the same package-input provenance boundary; repair and rerun pending. |
| .NET / Windows / SDK 10.0.301 | Failed on the same package-input provenance boundary; repair and rerun pending. |

Failures are retained rather than counted as passes. Configuring a job or
mocking its platform value is not native host evidence. A final candidate must
pass all six source/controller CI jobs and seven runtime/.NET jobs before the
release is declared verified.

## Native fixture method

`scripts/dotnet_demo.py` creates isolated public C# source/test projects, a
temporary CLI home and NuGet cache, and explicit public package configuration.
Ordinary fixtures use `ProjectReference`, target `net8.0`, and pin:

| Framework | Packages in the native fixture |
| --- | --- |
| xUnit | xunit 2.9.3, xunit.runner.visualstudio 3.0.0, Microsoft.NET.Test.Sdk 17.14.1 |
| NUnit | NUnit 3.14.0, NUnit3TestAdapter 4.5.0, Microsoft.NET.Test.Sdk 17.14.1 |

The evidence demonstration executes a real passing baseline, then six
independently specified native cases per framework: pass, body assertion,
runtime exception, skip, setup assertion and cleanup assertion. The expected
classification is respectively passed, failed, error, skipped, error and error.
A subsequent deliberate C# compilation error must produce no acceptance report.
Discovery, native framework results and TRX are reconciled by the actual runner.

The separate full-workflow demonstration uses a literal 10000-cent delivery
boundary: an existing regression passes, a new test establishes actual
`AssertionError` RED, source is corrected, GREEN and verification execute, and
fresh final execution reaches DONE with both required IDs retained. The review
is a deterministic fixture object and role edits are simulated. **No model is
called by this demonstration.** It does not establish the quality of AI-authored
tests or a real Claude session's behavior.

Packaged-mode workflow transitions use the production Node facade and a copied
native runtime with its actual SHA256/size in an isolated plugin cache. The
child PATH contains only Node/.NET; Python executables are checked absent and
`AI_TDD_PYTHON`/`PYTHONPATH` are removed. Python remains a CI build/test driver
dependency, which is separate from controller availability in that child.

The fixture does not configure lint, formatting or security commands. Its review
explicitly records those quality limitations, and `not_configured` is not a
quality-tool pass. These small fixtures do not validate a repository's analyzer
policy, services, broad multi-target suite, custom outputs or every reporter
version.

## Assertion evidence and rejected paths

xUnit evidence retains actual native exception types; the generic `Cause`
field is not trusted to distinguish v2 body assertions from runtime/setup/
disposal failures. A behavioral failure needs the bounded assertion-type
classification and a stack witness in the actual test body.

NUnit XML supplies structured assertion outcomes without an actual assertion
exception type. The runner preserves that native category and requires a
test-body stack witness before normalizing to `AssertionError`; it does not
invent an observed exception type. Native errors, invalid cases and fixture
setup/cleanup failures remain errors, including suite-level cleanup failures.

Ordinary MSTest TRX, Microsoft.Testing.Platform, implicit filters/runsettings,
unsupported output ownership and ambiguous/truncated/missing inventory are
rejected. No native MSTest/MTP support or silent package migration is claimed.
Parser/controller regression counts and their final execution results will be
recorded with the final candidate, separately from the actual framework runs.

## Local Windows limitation

On the local Windows machine, Application Control blocked actual execution of
the unsigned PyInstaller bundle. That attempt is **blocked, not passed**, and
local bundled hook timing remains unavailable. An already installed Python
backend can run the controller. A host with that policy and no Python requires
an approved trusted runtime; weakening OS policy is not a setup procedure.

The ordinary `ProjectReference` local fixture also encountered policy restrictions
on a newly compiled unsigned referenced assembly. An explicitly separate
linked-source fixture can exercise native test evidence while preserving
evaluated source ownership; it does not prove the ordinary assembly-loading or
Python-free runtime path. Local observations and ordinary CI-host observations
must retain their different scopes.

## Runtime build provenance and timing

Native binaries are built on their actual hosts using CPython 3.12.10 and pinned
development-only PyInstaller 6.22.3/tools. Each output includes build metadata
with executable size/SHA256, source hashes and exact tool versions, plus bundled
component license notices. Final published asset hashes must match the runtime
manifest and the metadata's source hashes must match the packaged source files.

`scripts/measure_runtime.py` measures three fresh `doctor` processes per backend,
each executing its actual nested hook self-test. It verifies requested backend
identity and excludes Python from the bundled child's PATH. Filesystem caches
are uncontrolled: these are fresh-process timings, **not cold-cache startup
measurements**, token savings or .NET test-duration comparisons.

| Release evidence | Final recorded value |
| --- | --- |
| Final source commit and all 13 CI job results | Pending |
| Windows x64 binary size/SHA256 and metadata source-hash match | Pending |
| Linux x64 binary size/SHA256 and metadata source-hash match | Pending |
| macOS arm64 binary size/SHA256 and metadata source-hash match | Pending |
| Actual fresh-process doctor/hook samples by host/backend | Pending |
| Anonymous release download and fresh explicit setup-runtime | Pending |
| Allowlisted source ZIP/checksum manifest and isolated installation | Pending |
| Any final real-Claude .NET feature/resume integration | Pending; separate from these no-model demonstrations |

The 1.4 model benchmark remains historical evidence for its registered synthetic
tasks. This change includes no additional paid model benchmark and makes no
new lossless-routing or token/cost reduction claim.

## Primary implementation references

- [VSTest dotnet test](https://learn.microsoft.com/en-us/dotnet/core/tools/dotnet-test-vstest)
- [Microsoft.Testing.Platform dotnet test](https://learn.microsoft.com/en-us/dotnet/core/tools/dotnet-test-mtp)
- [xUnit runsettings and reporter configuration](https://xunit.net/docs/config-runsettings)
- [xUnit v2 message adaptation](https://github.com/xunit/xunit/blob/v3-1.0.0/src/xunit.v3.runner.utility/Frameworks/v2/Xunit2MessageAdapter.cs)
- [NUnit adapter native discovery/results settings](https://docs.nunit.org/articles/vs-test-adapter/Tips-And-Tricks.html)
- [PyInstaller host builds and one-file operation](https://pyinstaller.org/en/stable/operating-mode.html)

User-facing requirements and supported layouts are in
[the .NET guide](../plugins/ai-tdd/references/dotnet.md); the unchanged phase gates
are in [the execution protocol](../plugins/ai-tdd/references/protocol.md).
