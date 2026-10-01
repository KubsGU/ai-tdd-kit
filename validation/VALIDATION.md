# Validation report — AI TDD Kit

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
