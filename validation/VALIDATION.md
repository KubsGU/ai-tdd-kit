# Validation report — AI TDD Kit

## 1.5.3 repository compatibility — 2026-10-05

The preset preserves the effective existing in-repository runsettings file,
including inherited `RunSettingsFilePath` and higher-priority `VSTestSetting`.
Its path and raw SHA256 bind both discovery and execution. Regressions distinguish
coverage exclusions from test filters, early stopping and collapsed theory
discovery, and reject malformed/ambiguous XML, external settings and settings drift.
The coverage acceptance regressions failed against the previous blanket rejection.

Package content regressions cover exact reachable restored dependencies,
package file/import membership, generated `contentFiles` imports, recorded fallback
caches and target aliases. They also reject orphan/stale packages, user-authored
external assets and mismatched project/cache/import/item metadata. Eight content
regressions failed before the provenance correction. Shared in-repository assets
remain protected. No user project, package version or settings edits are required.

An actual local SDK 10.0.301 restore/evaluation accepted the combined synthetic
fixture with inherited coverage settings, direct NuGet `contentFiles` and a
transitive build-imported `Content` asset. It preserved all authored project and
configuration hashes. This setup result is separate from native test execution.
The native fixture additionally requires real attached Cobertura reports with
executed `Demo.Fee` line hits, copied package payload assertions, unchanged project/
props/settings hashes, and full xUnit/NUnit DONE workflows. Existing 105-row xUnit
identity and 70-project setup checks remain in the native CI path.

Final full-suite, native host/SDK and public install/download results are recorded
in the [1.5.3 release notes](https://github.com/KubsGU/ai-tdd-kit/releases/tag/v1.5.3).
Plugin 1.5.3 retains the original pinned 1.5.0 interpreter and its historical
provenance; native CI separately exercises the anonymously downloaded old binary
with the current external sources. These fixtures use public synthetic inputs and
deterministic role simulation, without private repository data or paid model calls.

## 1.5.1 project-count correction — 2026-10-02

The native preset's arbitrary 50-project rejection is removed. New 70/128-project
regressions verify the complete project/test-module, source/test root, protected
project and generated-output inventories. A separate large overlapping layout
must still fail on ownership. Three regression assertions failed on the old
limit; all 21 native setup/parser methods then passed after the two-line removal.
The large unit fixtures mock external MSBuild metadata; native released-runtime
CI additionally evaluates actual 70-project init on Windows/Linux/macOS. Its
exact results and final full-suite/install/CI checks belong in the
[1.5.1 release notes](https://github.com/KubsGU/ai-tdd-kit/releases/tag/v1.5.1).

Plugin 1.5.1 reuses the unchanged pinned interpreter 1.5.0, which executes current
external sources. Historical build/source metadata and 1.5 validation below stay
unchanged; they do not claim the modified setup source was part of the old build.
No new interpreter imports, binary replacement or paid model calls are needed.

## 1.5.0 validation — 2026-10-02

**All 13 CI jobs passed** at runtime-source candidate `26f3332`: six source/
controller jobs and seven native runtime/.NET jobs. Windows x64, Linux x64 and
macOS arm64 execute the bundle with Python absent from the controller PATH and
complete xUnit/NUnit DONE demonstrations. Windows/Linux jobs also exercise
SDK 8.0.100 and 10.0.301. Released binaries are pinned by their actual SHA256/
size; metadata source hashes match committed controller and builder bytes.
The final local suite ran 247 tests in 148.222 seconds, with five environment/
opt-in skips. Ruff, strict manifests and deterministic gate/strength demos pass.
See the
[bounded .NET/runtime evidence](DOTNET_VALIDATION.md) and
[native CI](https://github.com/KubsGU/ai-tdd-kit/actions/runs/36989995992) and
[source/controller CI](https://github.com/KubsGU/ai-tdd-kit/actions/runs/36989996001).

The demonstrations execute actual installed SDK/frameworks with isolated
synthetic projects and simulate role edits/review; they do not call a model.
Native MSTest/MTP support and universal framework/layout coverage are not
claimed. The local unsigned bundle was blocked by Windows Application Control;
that is not a successful local Python-free runtime check. CI proves ordinary
host execution separately. Fresh-process timings show bundled startup overhead;
they are not cold-cache timings. No new paid model or real-Claude .NET integration
was run. Post-publication download/bootstrap/install checks are linked in the
release notes. Historical model benchmark results below remain scoped to 1.4.

## 1.4.0 validation — 2026-10-01

**167 tests ran in 124.1 seconds: 166 passed, one local directory-symlink permission
skip**, on Windows/Python 3.12.10. New frozen worker-policy regressions observed
eight failing methods before implementation, then all eleven passed. The default
Sonnet launch test failed before the default changed; explicit Opus remains
available. Fourteen no-model benchmark tests validate independent contract tables,
stateful scenarios, selected assertion witnesses, invalid reports, missing usage,
model mismatch, deterministic trial ordering, exact mixed routing, synthetic
capsule filtering and alternative correct implementations. Two source-identity
false-credit regressions failed before the grader fix, then passed. Repository Ruff and native
strict marketplace/plugin manifests passed.

All three initial and three reference fixtures passed actual Ruff F lint,
source-only format checks and strict Mypy: eighteen real quality commands. The
paired native benchmark is governed by its [pre-registered protocol](MODEL_BENCHMARK_PROTOCOL.md).
Its observed results belong in [the comparison report](MODEL_BENCHMARK.md), rather
than being inferred from model prices or cache fractions.

An original instruction probe correctly reported that mixed-role dispatch was
unsupported. A fresh updated-policy pressure probe selected exact Haiku-only
implementation routing, kept author/verifier inherited, rejected forced-model
and setup-repair bypasses, preserved failed-attempt evidence and denied silent
escalation. These are qualitative instruction checks, not quality equivalence.

The complete native revision-2 comparison used Claude Code 2.1.286 and the frozen
source/protocol at `f6931d2`: eighteen attempts across three synthetic Python
tasks and two repetitions/model. Opus 5.5 and Sonnet 5.5 each passed all six
workflow, external-oracle, exact-model, usage and test-strength checks. Each
detected 24 selected fault executions (twelve distinct patterns repeated twice),
after accepting two independently validated correct implementations with the
same test inventory. Sonnet's reported API-equivalent outlay was $5.7623923,
versus Opus $12.1433844: 52.55% lower, with mean native time 41.05% lower.
Whole-workflow Haiku 4.5 passed only one of six; all failures are retained and
two timeout costs are unavailable. This narrow sample does not prove general
quality equality, production bug-rate improvement or matched reasoning budgets.

A separate pre-registered Sonnet/Haiku-implementer profile passed all six paired
trials and the same 24 fault executions. Cost was $5.64096105: 2.11% lower than
all-Sonnet, cheaper in only three pairs, with mean native time 2.22% longer.
Concurrency differed between experiments; the difference does not establish a
robust advantage. The ordinary default remains Sonnet. See the
[complete comparison](MODEL_BENCHMARK.md) and [curated data](MODEL_BENCHMARK_RESULTS.json).

A separate final native mixed feature/resume integration passed: DONE, six
required IDs and six adequacy assessments, preserved original regression,
current evidence, actual Ruff lint/source format/strict Mypy, the six-case
external oracle, both correct controls and four selected faults. Response
metadata showed Sonnet coordinator/author/verifier and Haiku implementer,
matching the frozen policy. The first session took 33 turns and 171.6 native
seconds; reported API-equivalent cost was $0.67039505. A separate resume session
preserved exact DONE state, reported $0.096459, and made no feature changes.
Reported input cache-read fractions were 93.559% and 91.382% respectively;
these are not bill-savings percentages. Both costs are separate from the
33 registered comparison/pilot attempts. The fixture does not configure a
security scanner or dependency audit, and format/type checks cover source only.

The release allowlist contains 57 source files plus generated CHECKSUMS.json.
Public data contain numeric/model/outcome observations, not raw transcripts,
configuration, state or account data. Six CI jobs passed for the frozen code
[before the trials](https://github.com/KubsGU/ai-tdd-kit/actions/runs/36883350096).
Final commit CI and installation results are recorded on the release/PR.

## 1.3.1 validation — 2026-10-01

**141 tests ran in 62.8 seconds: 140 passed, one local directory-symlink permission
skip**, on Windows/Python 3.12.10. All four new directory-boundary regressions
passed with real native junctions and zero skips; repository Ruff also passed.

A separate real Windows/Python 3.12.14 probe reproduced three defects before the
fix: init wrote external config.json, lock acquisition created an external
controller.lock, and Controller accepted config/state from an external sibling
directory. The native junction reported is_symlink false. New regressions observed
all three failures, with actual external file/read witnesses. Quality-log rejection
already passed on Python3.12; the same real junction case now covers Python3.10.

State initialization, locking and controller reads now require the managed
directory's resolved identity to match its intended absolute path before I/O.
Quality log paths use the same rule. Python documents
[is_junction as added in 3.12](https://docs.python.org/3/library/pathlib.html#pathlib.Path.is_junction),
so protection does not rely on that optional method. Tests use native Windows
junctions or POSIX directory symlinks, not mocked path predicates. They reject
pre-existing redirection before writes, reads or command execution; they do not
establish OS isolation or freedom from malicious filesystem races.

The allowlist has 48 source files plus generated CHECKSUMS.json. Earlier 1.3.0
quality, model and cache integration results below remain specific to that version.

**A fresh real Claude Code 2.1.286 trial of 1.3.1 passed:** DONE, five required
test IDs and five adequacy assessments, the original test file preserved, current
completion evidence, actual Ruff lint/formatter check and strict Mypy in three
batches, and a six-case external oracle. The coordinator and every named role
used actual `claude-opus-5-5`. A separate resume session preserved exact DONE state.
The review named the limited F lint rules, source-only format/type scope, and
absent security scanner, lockfile audit and CI configuration in this fixture.

The first session took 32 turns and 274.6 seconds. Reported whole-tree totals were
86 ordinary input, 100,172 cache-write input, 1,173,621 cache-read input and 25,944
output tokens: **92.13% of reported input read from cache**, estimated API-equivalent
cost $1.4254392. Separate resume used 8 ordinary input, 19,799 cache-write input,
95,169 cache-read input and 1,837 output tokens; estimated $0.2141978. These are
observed integration results, not subscription invoices, comparative savings,
a quality benchmark or proof of a minimum test count.

## 1.3.0 validation — 2026-10-01

**137 controller/integration/helper tests ran in 68.4 seconds: 136 passed, one
platform skip** on Windows/Python 3.12.10, with pytest 9.1.1. The skipped case
requires creating a directory symlink, unavailable to this local test identity.
The CI matrix exercises platform behavior separately; a skip is not a passed
symlink test. The kit's Ruff 0.16.9 rules passed. Relevant regressions were observed
failing before the fixes, including earlier-test weakening and the final quality
check leaving a source-mutation failure in an uneditable verification phase.

New real-process cases cover configured check failures at baseline and completion,
actual final reruns, missing tools, timeouts, changed artifacts, frozen quality
definitions/inputs/budgets, unavailable categories, missing per-test assessment
and deletion of a final quality receipt. No missing configuration is labeled a
lint/type/security pass. These controller cases use synthetic commands to test
execution gates; they do not establish a particular linter's defect coverage.

The 1.2 instruction baseline already rejected count quotas, circular oracles and
mock assertions that erased behavior. It permitted adding to an existing file and
had no dedicated repository-quality execution gate. Five fresh qualitative
pressure probes of the new instructions rejected baseline weakening, artificial
counts, quality bypass flags, fake mutation scores and retroactive checkpoints.
They required factual conventions, actual receipts and honest missing categories.
These are instruction tests, not a measured oracle-quality gain or agent benchmark.

Native strict marketplace/plugin validation passed. The deterministic TDD demo
reached DONE: three RED/GREEN cycles, one existing-coverage increment, five tests
and two selected behavioral mutation detections. Its per-test review now explains
the distinct defect, oracle and useful boundary for each mapped ID.

`scripts/test_strength_demo.py` executed **48 unittest cases** across four
deliberately constructed comparisons. Each suite has three cases: correct code
passes both; weak tests miss each faulty implementation, while stronger tests
detect all four through seven actual assertion failures. Import errors, timeouts,
skips and inconsistent reports cannot count as detections. The examples isolate
circular assertions, call-only spies, absent threshold boundaries and absent
validation/membership interactions. They are not an LLM benchmark or a universal
mutation score, and equal counts do not mean equal input coverage.

The new compact/full DONE byte comparison was **3,381 vs 32,483 bytes, 89.59%
less**, with current evidence and exact disk state preserved. This measures
response bytes, not model tokens, bills or elapsed-time improvement. Additional
quality receipts are retained in full on disk.

**First real Claude Code 2.1.286 trial passed:** the coordinator and every named
role used actual `claude-opus-5-5`. The synthetic typed-fee project reached DONE
with eight required tests and eight adequacy assessments. Actual Ruff lint,
Ruff formatter check and strict Mypy passed in three batches (baseline, review,
completion). A six-case external oracle passed. A separate resume session
preserved exact state and DONE. The review explicitly reported that lint rules
were limited to F, formatting/types covered source only, and security scanning,
lockfiles and CI were absent.

The first session took 30 turns and 281.5 seconds. Final whole-tree totals were
82 ordinary input, 113,842 cache-write input, 1,090,730 cache-read input and 26,007
output tokens: **90.54% of reported input read from cache**. Estimated API-equivalent
cost was $1.522672, not a subscription invoice. Separate resume totals were 12
ordinary input, 26,848 cache-write input, 173,584 cache-read input and 2,566 output
tokens; estimated $0.3008688. This is a successful integration example, not a
controlled comparison with another framework or proof of minimum test count.

**Second trial of the final evaluator also passed**, including exact original
test-file bytes, current completion/quality evidence, all three actual Opus 5.5
roles, all quality tools in three batches, external six-case oracle and unchanged
DONE resume. It kept three executed IDs: the existing regression and two focused
groups using subtests for below/at/above-threshold cases and the retained integer
return contract. Inspection of the saved assessments found independent literal
oracles and concrete threshold, equality-only, upper-band and zero-cart faults.
Those descriptions are reviewed reasoning; only the actual RED and separate
mutation demos establish executed fault detections.

Second first-session metrics: 36 turns, 289.6 seconds, 100 ordinary input, 104,112
cache-write input, 1,422,301 cache-read input and 26,874 output tokens. Cache reads
were **93.17% of reported input**, estimated API-equivalent cost $1.5171882. Separate
resume used 8 ordinary input, 24,776 cache-write input, 95,072 cache-read input,
1,932 output tokens and estimated $0.2558944. Variation in test counts and context
between these trials is not a measured reduction in bugs, tokens or execution time.

CI retains six OS/Python combinations, runs on PRs and main rather than duplicating
branch push/PR matrices, cancels superseded runs and caches pinned package downloads.
All actual lint/test/demo executions remain fresh. This uses documented
[setup-python caching](https://github.com/actions/setup-python#caching-packages-dependencies)
and [GitHub concurrency](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency).

The public allowlist contains 47 source files, plus generated CHECKSUMS.json.
An isolated ZIP install passed inventory/checksums, strict manifests, marketplace
registration, plugin installation and the inactive-project hook without changing
normal user settings. Final public CI and distribution checks are recorded with
the release. See [the research review](RESEARCH.md) for source-supported choices
and limits. Historical results below remain specific to their original versions.

## 1.2.0 validation — 2026-10-01

**100 controller/integration/helper tests passed, zero skips, in 51.1 seconds**
on Windows/Python 3.12.10 with pytest 9.1.1. New cases cover child-only launch
settings, selecting the feature project, model-override rejection, disabled-cache
preflight, whole-tree usage accounting, missing/invalid counters, compact/full
decision parity, real failure details, retained review limitations and exact setup
repair paths. They also check that status preserves disk evidence without another
runner execution. Relevant regressions failed before their fixes.

Native strict marketplace/plugin validation returned no errors or warnings.
`scripts/measure_context.py` executed the existing deterministic demo, then compared
two read-only DONE responses: **2,690 bytes compact vs 23,188 bytes full, 88.4% less**.
Both receipts were current and the exact state bytes were preserved. This measures
response bytes; it does not measure model tokens, total cost or wall-clock savings.

The instruction-only 1.1 baseline already preserved model quality, fresh workers,
test execution and artifact references. It used full `status` because compact
output did not exist. Five fresh instruction pressure checks for the new policy
all selected compact `status`, an ordered artifact brief, inherited session models,
fresh sequential workers and complete requirements/failure evidence, while rejecting
cached answers/results or skipped checks. This is qualitative instruction testing,
not an LLM benchmark or evidence of a quality increase.

**First real Claude Code 2.1.286 trial passed**, on the synthetic shipping-fee task:

- Requested `opus`; actual streamed model was `claude-opus-5-5` for the coordinator
  and all three named roles. No cheaper role model appeared.
- Reached DONE with six required tests, one executed RED/GREEN cycle and two honest
  existing-behavior coverage increments. An external six-case behavioral oracle
  passed; a separate resume session kept DONE and preserved the exact state.
- First session/evidence collection: 32 turns, 277.4 seconds, success without
  timeout. Controller tool-result output totaled 30,922 bytes.
- Final whole-tree `modelUsage`: 96 ordinary input, 92,840 cache-write input,
  1,161,546 cache-read input and 24,595 output tokens. Cache reads were **92.59% of
  all reported input tokens**, not a request hit rate or bill-reduction percentage.
- Estimated CLI API-equivalent cost: $1.3394232 for the first session. This is not
  a subscription invoice. Resume is separate: 10 ordinary input, 33,679 cache-write
  input, 141,011 cache-read input and 2,622 output tokens; estimated $0.3501142.

**A second trial of the final candidate also passed**, including all three actual
Opus 5.5 role models, DONE, an external six-case oracle and unchanged-state resume.
It recorded one RED/GREEN cycle and one existing-coverage increment with four
required tests. First session: 24 turns, 167.2 seconds, 16,363 controller-output
bytes; 66 ordinary input, 61,612 cache-write input, 716,162 cache-read input and
15,077 output tokens. Cache reads were **92.07%** of reported input; estimated
API-equivalent cost $0.8606884. Separate resume: 10 ordinary input, 19,747 cache-write
input, 127,382 cache-read input, 2,239 output tokens and estimated $0.2282724.
These two runs are repeatability checks, not a before/after efficiency comparison.

The role model policy, compact output and normal native caching were exercised
together. Relevant full evidence remains available on disk and all prescribed
runner checks still execute. These are successful examples, not paired evidence
of lower overall token use, cost, duration or identical quality across repositories.
Provider/model/effort choices, task structure and TTLs influence actual outcomes.
Raw transcripts and evaluation JSON are excluded from the public package.

The release allowlist has 40 source files, plus generated CHECKSUMS.json. Per-commit
CI and isolated/public installation results are recorded in the pull request and
release. Historical validation below remains specific to its original version.

## 1.1.0 validation — 2026-10-01

**84 controller and integration tests passed, zero skips, in 51.4 seconds** on
Windows/Python 3.12.10 with pytest 9.1.1. New tests reproduce dispatch before RED,
foreign role names, worker delegation, resumed/background/isolated workers,
dispatch during controller execution, missing foreground configuration, JUnit
count/outcome inconsistencies, typeless failures, stale/missing DONE reviews and
runner-budget reset attempts. The relevant new regression cases were observed
failing before their controller fixes.

Actual pytest integration reproduced a missing import inside a test body being
accepted as behavioral RED by the old JUnit convention. It also reproduced
invisible deselection and a non-strict xpass being accepted at baseline. The new
JSON adapter rejects these cases, uses native parameterized node IDs, preserves
teardown failure evidence and completes a real RED/GREEN cycle. A typeless generic
JUnit failure no longer defaults to AssertionError.

The deterministic demo again reached DONE with three RED/GREEN cycles, one
existing-coverage cycle, five tests and both selected mutation probes detected.
Native strict marketplace/plugin validation returned no errors or warnings.

**Real Claude Code 2.1.286 evaluation passed**, with foreground workers enabled:

- Both `/ai-tdd:feature` and `/ai-tdd:resume` loaded.
- Verifier planned first, test author wrote tests, implementer delivered the
  feature, a further test-author cycle added existing-behavior coverage, and a
  fresh verifier reviewed the result.
- The controller reached DONE with six required tests. One real RED/GREEN cycle
  and one existing-coverage cycle were recorded; every runner start was audited.
- The CLI returned success without error/timeout after 24 turns. The first
  session/evidence collection took 183.0 seconds.
- A separate resume session returned success, retained DONE and preserved the
  exact task state.

This is a synthetic shipping-fee task with the unittest runner, plus deterministic
pytest/controller integrations. It does not test interactive fork-mode behavior
in a terminal UI, every task/language, or comparative cost/performance. The native
foreground flag follows the documented runtime contract and is checked in the
preflight. Role prompts are unchanged. Raw model logs and local evaluation JSON
remain excluded from the public package.

The release workflow adds macOS to Windows/Linux, each with Python 3.10/3.12.
The portable ZIP passed native strict validation, all 36 public-file checksums,
actual marketplace/plugin installation in a temporary `CLAUDE_CONFIG_DIR`, and
the inactive hook check. It contains 37 members including generated CHECKSUMS.json;
ordinary user settings were not the installation target.
Per-commit CI and release installation results are recorded in the public pull
request/release. The historical records below describe the earlier releases.

## 1.0.1 English summary (historical)

On 2026-10-01, **56 controller and integration tests passed with zero skips**.
They include actual Node → Python hook execution, hook health failures, pytest
JUnit reports, test/configuration protection, stale results, inventory/skip
checks, test amendment, runner reconfiguration/rebase and completed-task archive.
They passed again for release 1.0.1 in 43.2 seconds. Native strict validation of
the 1.0.1 marketplace and plugin manifests passed without errors or warnings.
The 1.0.1 ZIP also passed checksum verification of all 34 public files and an
actual marketplace/plugin installation in a temporary `CLAUDE_CONFIG_DIR`;
the user's normal settings were not the installation target. Its generated
CHECKSUMS.json makes 35 ZIP members in total.

The deterministic demo reached DONE through three RED/GREEN cycles and one
existing-coverage cycle, executing five tests and detecting both selected
mutants. It simulates role edits and does not call a model. Separately, real
Claude Code 2.1.285 used all three named roles and reached DONE with three
required tests, a real RED/GREEN cycle and independent final review. A second
Claude session resumed the task successfully and preserved its exact state.
The instruction baseline already solved the tested cases; no measured prompt
improvement or comparative benchmark is claimed.

The real model run and original isolated ZIP installation exercised 1.0.0.
Release 1.0.1 adds public distribution metadata, documentation and CI. Its
controller, runner, hook, role/skill prompts and protocol are byte-identical to
the validated 1.0.0 files. The runtime behavior is unchanged.

Local checks used Windows and Python 3.12.10. The development pytest version is
9.1.1. CI is configured for Windows/Linux and Python 3.10/3.12 with supported
Node LTS; consult the [actual workflow results](https://github.com/KubsGU/ai-tdd-kit/actions)
for a particular commit. Local results alone do not establish Linux/macOS
support or behavior on large repositories.

This is workflow protection, not OS isolation. Malicious test processes can
undermine evaluation. Tests in the same repository are not a secret holdout,
and hashes/test counts do not prove a correct contract or adequate review.

## Original 1.0.0 validation record (Polish)

Stan sprawdzenia: **1 października 2026**. Poniżej opisujemy wykonane próby,
ich zakres i ograniczenia. Wyniki pochodzą ze sztucznych projektów i testów
kontrolera; żaden test nie dotykał produkcji.

## Kontroler i adaptery

Polecenie z katalogu pluginu:

```text
python -B -m unittest discover -s tests -q
```

**56 testów przeszło, 0 pominiętych.** Czas tej próby: 38,7 s. Sprawdzono m.in.:

- poprawne i niepoprawne przejścia faz, rzeczywisty RED i GREEN;
- odrzucanie błędów importu, pominiętych testów, brakujących identyfikatorów,
  sprzecznych raportów i przekroczenia czasu;
- ochronę testów, konfiguracji i narzędzi oceny oraz wykrywanie nieaktualnych wyników;
- korektę błędnego testu przez `amend`, zmianę wersji i ponowny RED;
- naprawę konfiguracji runnera przez `reconfigure` i ponowne wykonanie `rebase`;
- ograniczenie kolejnych prób naprawy i kontrolowane wznowienie;
- archiwizację DONE z zachowaniem dowodów, kodu i testów;
- rzeczywiste uruchomienie hooka Node → Python oraz blokadę `begin`, gdy hook
  nie działa;
- adapter unittest i rzeczywiste raporty JUnit z pytest.

`doctor` zwrócił `hook_health: pass`. Walidacja natywnych manifestów marketplace
i pluginu przez `claude plugin validate --strict --json` zakończyła się bez błędów
i ostrzeżeń.

## Odtwarzalny demonstrator

```text
python -B scripts/smoke_demo.py
```

Wynik: **DONE, 3 cykle RED/GREEN, 1 cykl istniejącego pokrycia, 5 wykonanych testów**.
Obie wybrane celowe usterki zostały wykryte: wyłączenie wartości granicznej progu
i sprawdzanie członkostwa przed walidacją ujemnego wejścia.

To rzeczywiste wykonania runnera. Skrypt symuluje edycje poszczególnych ról;
nie wywołuje modeli. Dwa wskazane mutanty nie są pełnym mutation score projektu.

## Zachowanie instrukcji i rzeczywisty Claude Code

Próba instrukcji bez nowego skillu już poprawnie rozwiązała trzy sprawdzane
przypadki. Po dodaniu skillu osobny agent poprawnie wskazał postępowanie w pięciu
przypadkach: błąd importu, brak wymaganych testów, nacisk na zmianę oczekiwania,
test już zielony i uzasadniona korekta błędnego oracle. To jakościowy test
instrukcji, bez dowodu poprawy względem baseline i bez benchmarku modeli.

Próba rzeczywistego CLI korzysta z `scripts/evaluate_claude.py --resume-check`.
Tworzy mały, tymczasowy projekt opłaty za wysyłkę, ładuje plugin i uruchamia
normalnego Claude Code z osobnymi rolami. Druga sesja sprawdza wznowienie.

**Końcowa próba przeszła:**

- Claude Code 2.1.285 załadował `/ai-tdd:feature` i `/ai-tdd:resume`;
- wywołał nazwane role verifier, test-author i implementer; verifier pracował
  przed implementacją oraz na końcu;
- kontroler zapisał rzeczywisty RED, GREEN, kolejny przyrost z uczciwym
  istniejącym pokryciem, niezależną weryfikację i DONE;
- wymagany końcowy zbiór obejmował 3 testy, w tym istniejącą regresję;
- sesja zakończyła się sukcesem, bez błędu i timeoutu, po 24 turach;
- czas pierwszej sesji i zebrania wyniku: 172,2 s;
- osobna sesja `/ai-tdd:resume` również zakończyła się sukcesem,
  potwierdziła DONE i zachowała identyczny stan zadania.

Skrypt sprawdzający wymaga zarówno DONE, jak i poprawnego wyniku CLI, użycia
wszystkich trzech ról oraz poprawnego wznowienia. Surowy transcript nie jest
dołączany do paczki. Podczas wcześniejszej próby skrypt walidacyjny ujawnił
błąd domyślnego kodowania stdout na Windows; końcowa próba użyła poprawionego
odczytu UTF-8. Nie był to błąd specyfikacji ani implementowanej funkcji.

## Przenośna paczka i instalacja

`scripts/build_zip.py` używa jawnej listy plików. ZIP zawiera kod pluginu,
instrukcje, przykłady, testy i ten raport. Nie zawiera lokalnych stanów zadań,
surowych logów, danych konta ani zawartości projektu użytkownika.

`scripts/check_install.py <ZIP>` sprawdził sumy wszystkich 26 plików, manifesty,
rzeczywiste dodanie marketplace, instalację `ai-tdd@ai-tdd-kit`, obecność pluginu
w katalogu zainstalowanych dodatków oraz hook w nieaktywnym projekcie.
**Wszystkie te kontrole przeszły.** ZIP ma 27 plików: 26 z listy i CHECKSUMS.json.

Ustawienia Claude skierowano do własnego katalogu tymczasowego przez
`CLAUDE_CONFIG_DIR`. Zwykłe ustawienia użytkownika nie były celem instalacji.
Pierwsza próba w ograniczonym środowisku nie pozwoliła CLI sklasyfikować lokalnej
ścieżki; powtórzenie poza tym ograniczeniem przeszło. To test lokalnej paczki,
bez publikowania marketplace i bez pobierania zależności aplikacji.

## Środowisko i granice dowodów

Sprawdzono Windows, Python 3.12.10 i Claude Code 2.1.285. Na tym komputerze hook
uruchomiono także z Node 14.8.0. Do własnego użycia zalecamy wspieraną wersję LTS;
stary lokalny runtime nie stanowi rekomendacji. Wymagany Python: 3.10+.

Nie wykonano próby na macOS/Linux ani integracji z innymi runnerami niż unittest
i pytest. Jeden mały feature nie dowodzi skuteczności na dużych repozytoriach,
wyższej jakości od innych metod ani opłacalności dodatkowych wywołań modeli.

Hook i hash plików pilnują procesu; nie tworzą izolacji systemowej. Złośliwy
proces testowy może podważyć ocenę. Testy w tym samym repo nie są tajnym holdoutem.
Zadeklarowanie pełnej konfiguracji i zakresu regresji oraz poprawność specyfikacji
i niezależnego review nadal wymagają oceny człowieka lub modelu.
