# .NET and bundled runtime validation — 1.5.0

Status: **all 13 controller/native CI jobs passed on 2026-10-02**. This report
separates actual native execution from synthetic parser fixtures and role-edit
simulation. It does not claim every .NET framework/layout or Windows policy is
supported, nor comparative model quality or a production bug-rate reduction.

## Recorded native CI

The runtime-source candidate `26f333244ff4fed258e30f340c7ea4ee4e005c19`
passed all seven jobs in
[native run 36989995992](https://github.com/KubsGU/ai-tdd-kit/actions/runs/36989995992)
and all six source/controller jobs in
[CI run 36989996001](https://github.com/KubsGU/ai-tdd-kit/actions/runs/36989996001).
The released binaries below come from that successful native run. Their six
controller-source hashes and builder hash were compared with committed source
bytes before pinning. Numeric evidence is retained in
[DOTNET_CI_RESULTS.json](DOTNET_CI_RESULTS.json).

| Job scope | Actual recorded result |
| --- | --- |
| Runtime / Linux x64 | Passed native bundled execution with Python absent from the controller PATH, and complete xUnit/NUnit DONE demonstrations. |
| Runtime / macOS arm64 | Passed native bundled execution with Python absent from the controller PATH, and complete xUnit/NUnit DONE demonstrations. |
| .NET / Linux / SDK 8.0.100 | Passed native xUnit/NUnit evidence and complete DONE demonstrations. |
| .NET / Linux / SDK 10.0.301 | Passed native xUnit/NUnit evidence and complete DONE demonstrations. |
| Runtime / Windows x64 | Passed native bundled execution with Python absent from the controller PATH, and complete xUnit/NUnit DONE demonstrations. |
| .NET / Windows / SDK 8.0.100 | Passed native xUnit/NUnit evidence and complete DONE demonstrations. |
| .NET / Windows / SDK 10.0.301 | Passed native xUnit/NUnit evidence and complete DONE demonstrations. |

Earlier [run 36988224953](https://github.com/KubsGU/ai-tdd-kit/actions/runs/36988224953)
failed three Windows jobs because a standard transitive TestHost package was
absent from the direct-package ownership check. The correction binds the exact
restored selected-TFM dependency graph, owning project/cache, library file list
and imported build asset. A reproduced regression and ten negative provenance
cases cover that boundary. Earlier Unix separator and complete-plugin fixture
defects were also corrected before this successful candidate. Failed attempts
are not counted as passes; platform mocks are not native host evidence.

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
The final local suite ran **247 tests in 148.222 seconds: 242 passed, five
skipped**. Two bundled execution tests require the real CI artifact; three
local symlink tests lack privileges. Mandatory native jobs execute the built
bundle. Actual Windows junction tests, 19 native parser/setup methods, absent
build-input creation/fingerprint regressions, Ruff, strict Claude marketplace/
plugin validation, and both deterministic gate/strength demos passed. Those
counts remain separate from actual SDK/framework executions.

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
| Runtime-source commit and all 13 jobs | `26f3332`; both linked runs passed. Release tag identifies the final packaging/documentation commit. |
| Windows x64 binary | 10050900 bytes; SHA256 `ad37e22c7be5904981cd376a4eeec37e85510dd77dbf3baad8c680eef86823d1`; committed source hashes match. |
| Linux x64 binary | 22817992 bytes; SHA256 `fbab14f3d2bfc2a9b9973fc83746ed1cc50361e1cf24f30a8a688d3047f30c09`; committed source hashes match. |
| macOS arm64 binary | 9009824 bytes; SHA256 `4ee2073cc17e173e4fd97e1b49871013fbe5089554a8fa5de6182874bca785fc`; committed source hashes match. |
| Anonymous download/bootstrap and isolated installation | Post-publication checks are linked in [the release notes](https://github.com/KubsGU/ai-tdd-kit/releases/tag/v1.5.0); their actual outcome must be checked separately. |
| Real-Claude .NET feature/resume integration | Not run for 1.5; no additional paid model calls. The no-model demonstrations do not substitute for this evidence. |

| Actual CI host | Installed Python median | Bundled runtime median |
| --- | --- | --- |
| Windows x64 | 0.485 s | 1.230 s |
| Linux x64 | 0.260 s | 0.532 s |
| macOS arm64 | 0.357 s | 0.605 s |

Each median uses the three actual fresh-process doctor/nested-hook samples in
the JSON evidence. The bundle removes a manual Python dependency and adds
startup overhead in these measurements. An existing Python backend remains
available without downloading a runtime; switching an active task's backend is
rejected. These timings do not measure isolated hooks, model latency or every
host's performance.

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
