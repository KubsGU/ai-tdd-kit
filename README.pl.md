# AI TDD Kit — plugin do Claude Code

[English guide](README.md)

Przenośny workflow: opis zadania → doprecyzowanie → kontrakt akceptacji → osobny
autor testów → rzeczywisty RED → osobny implementer → GREEN → niezależny review.
Kontroler w Pythonie egzekwuje fazy na podstawie wykonanych testów. Hook i ograniczenia
narzędzi agentów pilnują właścicieli zmian. Wersja 1.3.1, licencja MIT.

## Instalacja z GitHuba

W terminalu:

```text
claude plugin marketplace add KubsGU/ai-tdd-kit
claude plugin install ai-tdd@ai-tdd-kit --scope user
```

Uruchom Claude w projekcie, w którym chcesz wdrożyć feature. Ustaw agentów na
pierwszym planie i wybierz model. Konserwatywny domyślny wybór jakościowy to Opus.
W PowerShell:

```powershell
$env:CLAUDE_CODE_DISABLE_BACKGROUND_TASKS = "1"
claude --model opus
```

Na macOS/Linux:

```sh
CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1 claude --model opus
```

Ustawienie jest wymagane także przy wznowieniu; kontrola wstępna wykryje jego brak.
Następnie wpisz
`/ai-tdd:feature <opis zadania>`. Wznowienie: `/ai-tdd:resume`.
Repozytorium pełni jednocześnie rolę publicznego marketplace. Aktualizacja:
`claude plugin update ai-tdd@ai-tdd-kit`.

## Instalacja na drugim komputerze

Potrzebujesz aktualnego Claude Code (testowano 2.1.285 i 2.1.286), Python 3.10+ i Node.js
na PATH; dla Node wybierz wspieraną wersję LTS. Plugin nie wymaga dodatkowych
bibliotek Pythona. Zależności aplikacji
i jej runnera, np. pytest, pozostają częścią projektu.

1. Przenieś ZIP `ai-tdd-kit-1.3.1.zip` i rozpakuj go. Zachowaj ukryty katalog
   `.claude-plugin` oraz całą strukturę `ai-tdd-kit`.
2. W terminalu dodaj rozpakowany katalog i zainstaluj plugin:

```text
claude plugin marketplace add "/pełna/ścieżka/ai-tdd-kit"
claude plugin install ai-tdd@ai-tdd-kit --scope user
```

Na Windows ścieżka może wyglądać tak: `"C:/Users/Jan/Downloads/ai-tdd-kit"`.
Lokalna instalacja korzysta z tego katalogu: pozostaw go na dysku w stabilnym
miejscu. Uruchom nową sesję Claude Code w swoim projekcie lub użyj
`/reload-plugins` w istniejącej sesji. Instalacja i format odpowiadają
[oficjalnej dokumentacji](https://code.claude.com/docs/en/plugin-marketplaces).

Możesz też uruchomić plugin bez instalacji:

```text
claude --model opus --plugin-dir "/pełna/ścieżka/ai-tdd-kit/plugins/ai-tdd"
```

Nie kopiuj kluczy API ani konfiguracji konta z tego komputera. Na drugim korzystaj
ze swojego zwykłego logowania Claude Code. Jeżeli Python jest poza PATH, ustaw
zmienną `AI_TDD_PYTHON` na ścieżkę do jego pliku wykonywalnego. Node musi być na PATH.

## Modele, tokeny i cache

Każda rola ma `model: inherit`: autor testów, implementer i verifier korzystają
z modelu sesji. Hook aktywnego zadania odrzuca zmianę modelu w pojedynczym
wywołaniu agenta. Nie ma automatycznego obniżania jakości testów lub review przez
przełączanie na tańszy model. Sonnet można wybrać świadomie; nie zakładamy, że
zawsze daje tę samą jakość co Opus.

Po pobraniu ZIP lub sklonowaniu repo możesz skorzystać z launchera. Z katalogu
paczki wskaż projekt docelowy:

```text
python -B scripts/launch_claude.py --project "C:/projekty/moj-projekt"
```

Launcher wybiera Opusa, wymusza agentów na pierwszym planie i usuwa zmienne
wyłączające cache lub wymuszające inny model workerów tylko dla tej sesji.
Nie zmienia ustawień użytkownika, uprawnień, logowania ani MCP. `--dry-run` pokazuje
wybór bez uruchamiania Claude. Dodatkowe opcje Claude podaj po `--`.
Możesz ustawić `--effort high` dla trudniejszych zadań; domyślnie zachowujemy
zwykłe ustawienie Claude zamiast wymuszać maksymalny wysiłek na każdym kroku.

Cache promptów obsługuje sam Claude Code. Zachowujemy domyślne TTL dostawcy.
Krótkie odpowiedzi kontrolera i przekazywanie ścieżek do artefaktów ograniczają
powtarzanie historii, hashy i zielonych logów. Wymagania oraz pełne dowody pozostają
dostępne. Każde wymagane wykonanie testów nadal się odbywa; wyników runnera nie
cachujemy. Pełny JSON dla diagnostyki lub skryptów otrzymasz przez `--full` przed
poleceniem kontrolera, np. `tdd.py --root /projekt --full status`.

W wersji 1.2 odpowiedź DONE demonstratora była o 88,4% mniejsza w bajtach. W dwóch rzeczywistych
próbach Opusa 92,1–92,6% raportowanych tokenów wejściowych odczytano z cache, łącznie
z agentami. To nie jest dowód obniżenia całego rachunku, czasu lub liczby tokenów
o taki procent. Pomiar obejmuje rzeczywiste modele i końcowe liczniki wszystkich
agentów; brak danych nie jest traktowany jako zero.
Szczegóły: [polityka efektywności](plugins/ai-tdd/references/efficiency.md)
i [wykonane próby](validation/VALIDATION.md).

## Użycie

W Claude Code:

```text
/ai-tdd:feature Dodaj rabat dla stałych klientów. Rabat wynosi 10%, nie łączy się z promocjami, kwoty są w groszach.
```

Claude najpierw sprawdzi istniejące API i testy. Zada konkretne pytania o decyzje
zmieniające zachowanie, zapisze kryteria AC i uruchomi właściwe role. Rutynowe
decyzje implementacyjne podejmie sam. Możesz dopisać „nie zadawaj pytań; zapisz
rozsądne założenia”, jeśli zakres pozwala na takie domknięcie.

Po przerwaniu pracy lub resecie kontekstu:

```text
/ai-tdd:resume
```

Stan, dowody wykonania i historia faz są lokalne w `.ai-tdd/` projektu. Nie usuwaj
ich w celu uzyskania GREEN. Jeden checkout obsługuje jedno aktywne zadanie.
Przed kolejnym feature koordynator archiwizuje zakończone zadanie przez `archive`:
dowody zostają w prywatnej `.ai-tdd-history/`, a kod i testy pozostają na miejscu.
Plugin nie wykonuje automatycznie merge, publikacji ani deployu.

## Co jest egzekwowane

- Agent testów i implementer pracują w osobnych kontekstach. Żaden worker nie
  dostaje powłoki, MCP ani możliwości uruchamiania kolejnych agentów.
- Hook sprawdza nazwę roli i fazę przed delegowaniem. Odrzuca wznowiony kontekst
  workera, jawny tryb w tle, osobny worktree i role z innych pluginów.
- Implementer zapisuje wyłącznie zadeklarowany kod. Testy, oczekiwania, konfiguracja,
  zależności i stan kontrolera są chronione.
- Zwykły przyrost powstaje w nowym pliku testowym. Wcześniejsze pliki są zamrożone;
  korekta wymaga jawnego, uzasadnionego `amend`.
- RED wymaga rzeczywistej porażki wybranych testów z powodu zachowania. Błąd importu,
  pominięte testy lub samo zapewnienie modelu nie otwierają implementacji.
- GREEN wymaga wykonania wszystkich wcześniej wymaganych identyfikatorów testów.
  Zmiana chronionych plików i nieaktualny wynik uniemożliwiają następny etap.
- Błędny test poprawia jego właściciel przez wersjonowane `amend`. Udowodniony
  problem runnera ma osobne `reconfigure` i `rebase`, z ponownym wykonaniem testów.
- DONE wymaga aktualnego review bez otwartych uwag i końcowego pełnego wykonania.
  Zmiana lub usunięcie review unieważnia aktualność wyniku w `status`.
- Review ocenia każdy nowy lub przypisany do AC test: wykrywany defekt, niezależną
  oczekiwaną odpowiedź i przydatność przypadku. Kontroler sprawdza kompletność
  tej oceny; jej prawdziwość nadal wymaga merytorycznej weryfikacji.
- Polecenia lintowania, formatowania, kontroli typów i bezpieczeństwa z danego repo
  wykonują się rzeczywiście przez kontroler, również ponownie przed DONE. Błędy
  blokują zakończenie; brak konfiguracji jest jawnym ograniczeniem. Domyślny limit
  to 20 takich zestawów poleceń na zadanie.
- Łączny limit uruchomień runnera wynosi domyślnie 100 na zadanie. Obejmuje baseline,
  timeouty, naprawy konfiguracji i sprawdzenie końcowe; retry go nie resetuje.
  Ten limit nie ogranicza zużycia modelu ani wydatków.
- Kontrola `doctor` i bramka `begin` sprawdzają rzeczywiste działanie hooka;
  uszkodzony launcher nie pozwala rozpocząć zadania.

Adapter pytest zapisuje rzeczywisty typ wyjątku i identyfikatory node ID. Wykrywa
testy wyłączone filtrem, xfail/xpass oraz błędy setup/teardown. Zwykły JUnit bez
typu porażki nie daje wystarczającego dowodu RED. pytest uruchamiamy sekwencyjnie.

Szczegóły konfiguracji, polecenia, granice i format raportów:
[protokół wykonania](plugins/ai-tdd/references/protocol.md).

## Mniej pustych testów i spójność z repo

Nie ma celu „napisz jak najwięcej testów” ani wymogu 100% mutation score.
Dobry przypadek odróżnia poprawne zachowanie od konkretnego, wiarygodnego błędu.
Oczekiwany wynik pochodzi z kontraktu, a nie z tej samej implementacji. Wywołanie
mocka dowodzi interakcji; samo nie dowodzi poprawności zwróconej wartości.

Przed rozpoczęciem koordynator zapisuje profil repo: istniejące instrukcje,
nazewnictwo, błędy/API, przykłady sąsiedniego kodu, CI i reguły narzędzi.
`quality_checks` używa tych poleceń w trybie sprawdzającym. Nie narzucamy wszystkim
projektom jednego formattera ani nie wyłączamy reguł, żeby dostać zielony wynik.
Szczegóły i przykłady: [polityka jakości](plugins/ai-tdd/references/quality.md).

[Przegląd badań](validation/RESEARCH.md) opisuje TDFlow, EvalPlus, mutation testing,
własności i niezależną ocenę, wraz z ich ograniczeniami. Demonstrator
`scripts/test_strength_demo.py` pokazuje na czterech celowych usterkach, jak
zestawy o tej samej liczbie testów mogą dawać bardzo różne dowody. To konkretne
przykłady, a nie benchmark modeli ani gwarancja braku błędów.

## Weryfikacja paczki

Z katalogu `ai-tdd-kit`:

```text
python -B -m unittest discover -s plugins/ai-tdd/tests -v
python -m ruff check .
python -B scripts/smoke_demo.py
python -B scripts/test_strength_demo.py
python -B scripts/measure_context.py
```

Pierwsze polecenie sprawdza bramki i próby obejścia procesu. Drugie wykonuje trzy
realne cykle RED/GREEN oraz dwie wybrane mutacje na sztucznym projekcie, bez AI
i dostępu do produkcji. Integracyjne testy adaptera pytest wymagają pytest
w środowisku; bez niego są oznaczane jako pominięte. Zależności testów paczki
zainstalujesz przez `python -m pip install -r requirements-dev.txt`.

Opcjonalny test z rzeczywistym Claude, korzystający z normalnego konta i zużycia:

```text
python -B scripts/evaluate_claude.py --output validation/local-claude.json --resume-check
```

Szczegóły faktycznie wykonanej walidacji: [VALIDATION.md](validation/VALIDATION.md).
ZIP zawiera tylko pliki wymienione w BUILD_MANIFEST.json. CHECKSUMS.json pozwala
sprawdzić integralność jego zawartości; nie jest podpisem autora.

## Mocne strony i ograniczenia

| Zaleta | Koszt lub ograniczenie |
| --- | --- |
| Rozdzielenie autorstwa testów i kodu utrudnia dopasowywanie oczekiwań do patcha. | Ten sam model w różnych kontekstach nadal może popełniać podobne błędy. |
| Dowody wykonania i trwały stan ułatwiają audit oraz wznowienie. | Trzeba poprawnie zadeklarować zakres testów, helpery i konfigurację. |
| Małe cykle ograniczają błąd wczesnej dużej implementacji. | Więcej wywołań modeli i runnera; przy prostym kosmetycznym zadaniu zwykle zbędne. |
| Korekty mają jawny właściciel i nową weryfikację. | Repo z istniejącymi błędami/skips wymaga osobnego uporządkowania baseline. |
| Adaptery JSON dla unittest/pytest i obsługa JUnit umożliwiają integrację z istniejącą suite. | pytest wymaga wykonania sekwencyjnego; inne frameworki potrzebują własnej walidacji. |

Hook jest zabezpieczeniem procesu, a nie izolacją systemową. Złośliwy kod testu
może naruszyć proces runnera; właściciel komputera może wyłączyć hooki. Ukryte testy
umieszczone w tym samym repo nie stają się przez to tajne. Semantyczna poprawność
specyfikacji i review nie wynika z samych hashy ani liczby zielonych testów.
Nie twierdzimy, że pojedynczy przykład dowodzi przewagi nad wszystkimi metodami
AI coding. Realistyczne następne porównanie wymaga zestawu różnych zadań i pomiaru
regresji, kosztu, czasu oraz wyników niezależnej oceny.
Konkretne kolejne kroki i kryteria ich sprawdzenia: [ROADMAP.md](ROADMAP.md).

## Własna publikacja i aktualizacje

Przed aktualizacją zakończ i zarchiwizuj aktywne zadanie. Dowody są powiązane
z hashami kontrolera, runnera i protokołu; nowa wersja unieważnia stary zestaw.

Możesz opublikować **sam katalog ai-tdd-kit** w oddzielnym repozytorium Git lub
wysłać ten ZIP. Nie publikuj całego prywatnego projektu ani lokalnych stanów zadań.
Po publikacji odbiorca doda marketplace adresem tego repo i zainstaluje ten sam
`ai-tdd@ai-tdd-kit`. Ta paczka nie wykonuje publikacji ani nie wymaga hostingu.

Po zmianach uruchom testy, podnieś wersję w obu manifestach oraz BUILD_MANIFEST.json,
i zbuduj nowy ZIP:

```text
python -B scripts/build_zip.py
```
