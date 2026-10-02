# AI TDD Kit — plugin do Claude Code

[English guide](README.md)

Przenośny workflow: opis zadania → doprecyzowanie → kontrakt akceptacji → osobny
autor testów → rzeczywisty RED → osobny implementer → GREEN → niezależny review.
Kontroler egzekwuje fazy na podstawie wykonanych testów. Launcher Node uruchamia
tę samą implementację Pythona przez istniejący interpreter albo sprawdzony runtime
dołączony do wydania. Hook i ograniczenia narzędzi agentów pilnują właścicieli zmian.
Wersja 1.5.2, licencja MIT.

## Instalacja z GitHuba

W terminalu:

```text
claude plugin marketplace add KubsGU/ai-tdd-kit
claude plugin install ai-tdd@ai-tdd-kit --scope user
```

Uruchom Claude w projekcie, w którym chcesz wdrożyć feature. Ustaw agentów na
pierwszym planie i wybierz model. Do zwykłych, jasno określonych zadań wybierz
Sonneta; Opusa świadomie do bardziej złożonej oceny i zmian o dużych konsekwencjach.
W PowerShell:

```powershell
$env:CLAUDE_CODE_DISABLE_BACKGROUND_TASKS = "1"
claude --model sonnet
```

Na macOS/Linux:

```sh
CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1 claude --model sonnet
```

Ustawienie jest wymagane także przy wznowieniu; kontrola wstępna wykryje jego brak.
Następnie wpisz
`/ai-tdd:feature <opis zadania>`. Wznowienie: `/ai-tdd:resume`.
Repozytorium pełni jednocześnie rolę publicznego marketplace. Aktualizacja:
`claude plugin update ai-tdd@ai-tdd-kit`.
Przed aktualizacją zakończ i zarchiwizuj aktywne zadania w dotychczasowej wersji.

## Instalacja na drugim komputerze

Potrzebujesz aktualnego Claude Code (testowano 2.1.285 i 2.1.286) i Node.js na PATH;
wybierz wspieraną wersję LTS. W projekcie .NET potrzebny jest jego dotychczasowy SDK
i pakiety testowe; automatyczny setup wymaga SDK 8+/MSBuild 17.8+. Na Windows x64,
Linux x64 i macOS arm64 koordynator może przygotować przypięty runtime kontrolera
bez osobnej instalacji Pythona, jeśli polityka komputera pozwala go uruchomić.
Lokalna próba na Windows została zablokowana przez Application Control dla
niepodpisanego pliku. Taka polityka wymaga zatwierdzonego runtime albo istniejącego
Pythona; [szczegóły](plugins/ai-tdd/references/dotnet.md#runtime-requirements).
Na innych platformach potrzebny jest Python 3.10+.
Zależności aplikacji i jej runnera, np. pytest, pozostają częścią projektu.

1. Przenieś ZIP `ai-tdd-kit-1.5.2.zip` i rozpakuj go. Zachowaj ukryty katalog
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
claude --model sonnet --plugin-dir "/pełna/ścieżka/ai-tdd-kit/plugins/ai-tdd"
```

Nie kopiuj kluczy API ani konfiguracji konta z tego komputera. Na drugim korzystaj
ze swojego zwykłego logowania Claude Code. Przed rozpoczęciem zadania koordynator
sprawdza runtime i w razie braku Pythona wykonuje jawny `setup-runtime`. Pobierany
plik jest przypięty do wersji wydania i sprawdzany przez SHA256 oraz rozmiar,
także przy ponownym użyciu. Hook nigdy niczego nie pobiera. Jeżeli chcesz używać
własnego Pythona poza PATH, ustaw `AI_TDD_PYTHON` na jego plik wykonywalny.

## Projekt .NET bez ręcznego adaptera

Uruchom Claude w katalogu solution i wpisz `/ai-tdd:feature <opis zadania>`.
`init` wykrywa istniejące projekty C#, ocenia ich konfigurację MSBuild i ustawia
zakres kodu, testów, generowanych plików oraz runnera. Nie podnosi wersji NuGet,
nie zmienia ustawień globalnych i nie nadpisuje istniejącej konfiguracji pluginu.

Ścieżka VSTest obsługuje xUnit z `xunit.runner.visualstudio >= 3.0.0` oraz NUnit
`>= 3.14.0` z `NUnit3TestAdapter >= 4.5.0`. Runner porównuje pełne discovery,
natywne dowody frameworka i TRX dla wszystkich skonfigurowanych projektów oraz TFM.
RED wymaga porażki w ciele testu; błąd runtime, setupu, teardownu albo brakujące
testy nie otwierają implementacji. Zwykły TRX z MSTest i Microsoft.Testing.Platform
nie dają obecnie obsługiwanego dowodu: setup zgłosi konkretny brak.

xUnit używa stabilnych natywnych identyfikatorów przypadków. Czytelne nazwy mogą
być długie, skrócone przez adapter albo powtarzać się. Koordynator odczytuje
rzeczywiste ID z raportu baseline, a ID nowych przypadków z logu/raportu RED;
tych ID używa w mapowaniu AC i review. Nie tworzy ich z nazw testów. Każdy
odkryty przypadek musi wykonać się dokładnie raz. Teorie wyliczające wiersze
dopiero podczas wykonania pozostają nieobsługiwane. Natywne logi diagnostyczne
mogą zawierać dane fixture i ścieżki; zachowaj je lokalnie, poza publicznymi dowodami.

Koordynator przed `begin` dopasowuje istniejące reguły `.editorconfig`, build,
analyzery, sprawdzanie formatowania i polecenia CI. Nie narzuca nowego stylu;
brak skonfigurowanego narzędzia pozostaje jawnym ograniczeniem. Układ projektów,
diagnoza i przykłady poleceń: [instrukcja .NET](plugins/ai-tdd/references/dotnet.md).

## Modele, tokeny i cache

W zarejestrowanym porównaniu małych zadań Sonnet i Opus zaliczyły po 6/6 prób
z tymi samymi wykryciami wybranych usterek. Sonnet kosztował o 52,55% mniej,
a średni czas był o 41,05% krótszy. Sonnet z Haiku do implementacji też zaliczył
6/6, ale oszczędził tylko 2,11%; pozostaje opcją. Cały workflow na Haiku zaliczył
1/6. Trzy sztuczne zadania powtórzone dwa razy nie dowodzą ogólnej równości
jakości. Zobacz [wszystkie próby i ograniczenia](validation/MODEL_BENCHMARK.md).

Role dziedziczą model sesji, chyba że przed begin jawnie skonfigurujesz
`worker_models`. Hook wymaga zgodności z zamrożoną mapą; naprawa konfiguracji nie
pozwala jej zmienić. Nie ma automatycznego tańszego autora/reviewera ani eskalacji
w środku zadania. Wybór modelu nie jest gwarancją tej samej jakości.

Do eksperymentu z Haiku przy małej implementacji uruchom sesję na Sonnecie i poproś
w opisie feature'u o Haiku wyłącznie dla implementera. Koordynator przed begin ustawia:

```json
"worker_models": {"test-author": "inherit", "implementer": "haiku", "verifier": "inherit"}
```

Autor testów i verifier mogą otrzymać jawne `opus`; implementer również
`haiku` lub `sonnet`. Silniejszy reviewer z sesji Sonnet to `verifier: "opus"`.
Kontrakt, ocena testów i obowiązkowe wykonania pozostają takie same. Niepowodzenie
stałego profilu zachowaj jako nieukończone zadanie; nie zmieniaj modelu ani kontroli,
żeby uzyskać zielony wynik. Metodę porównania opisuje
[protokół benchmarku](validation/MODEL_BENCHMARK_PROTOCOL.md),
[wyniki i ograniczenia](validation/MODEL_BENCHMARK.md) oraz
[badania modeli i cache](validation/MODEL_COST_RESEARCH.md).

Po pobraniu ZIP lub sklonowaniu repo możesz opcjonalnie skorzystać z launchera
Node. Z katalogu paczki wskaż projekt docelowy:

```text
node scripts/launch_claude.cjs --project "C:/projekty/moj-projekt"
```

Ten pomocniczy skrypt nie jest potrzebny do bezpośredniego uruchomienia Claude.
Dotychczasowy wariant Pythona pozostaje dostępny dla istniejących skryptów.
Launcher wybiera Sonneta, wymusza agentów na pierwszym planie i usuwa zmienne
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
poleceniem kontrolera, np.
`node "/sciezka/ai-tdd/scripts/tdd-launcher.cjs" --root /projekt --full status`.

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
Pakiet runtime kontrolera nie zastępuje środowiska Pythona projektu ani jego
bibliotek. Własne polecenia runnera z `{python}` nadal wymagają prawdziwego
interpretera projektu.

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

To polecenia dla współtwórców paczki; użytkownik .NET nie musi instalować Pythona
ani narzędzi deweloperskich pluginu.

```text
python -B -m unittest discover -s plugins/ai-tdd/tests -v
python -m ruff check .
python -B scripts/smoke_demo.py
python -B scripts/test_strength_demo.py
python -B scripts/measure_context.py
```

Pierwsze polecenie sprawdza bramki i próby obejścia procesu. Demonstrator wykonuje trzy
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
| Wbudowany runner .NET oraz adaptery unittest/pytest i JUnit pozwalają wykorzystać istniejącą suite. | .NET ma jawne ograniczenia frameworka i układu; pytest wymaga wykonania sekwencyjnego. |

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
