# AI TDD Kit — plugin do Claude Code

[English guide](README.md)

Przenośny workflow: opis zadania → doprecyzowanie → kontrakt akceptacji → osobny
autor testów → rzeczywisty RED → osobny implementer → GREEN → niezależny review.
Kontroler w Pythonie egzekwuje fazy na podstawie wykonanych testów. Hook i ograniczenia
narzędzi agentów pilnują właścicieli zmian. Wersja 1.1.0, licencja MIT.

## Instalacja z GitHuba

W terminalu:

```text
claude plugin marketplace add KubsGU/ai-tdd-kit
claude plugin install ai-tdd@ai-tdd-kit --scope user
```

Uruchom Claude z ustawieniem wymuszającym agentów na pierwszym planie.
W PowerShell:

```powershell
$env:CLAUDE_CODE_DISABLE_BACKGROUND_TASKS = "1"
claude
```

Na macOS/Linux:

```sh
CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1 claude
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

1. Przenieś ZIP `ai-tdd-kit-1.1.0.zip` i rozpakuj go. Zachowaj ukryty katalog
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
claude --plugin-dir "/pełna/ścieżka/ai-tdd-kit/plugins/ai-tdd"
```

Nie kopiuj kluczy API ani konfiguracji konta z tego komputera. Na drugim korzystaj
ze swojego zwykłego logowania Claude Code. Jeżeli Python jest poza PATH, ustaw
zmienną `AI_TDD_PYTHON` na ścieżkę do jego pliku wykonywalnego. Node musi być na PATH.

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
- RED wymaga rzeczywistej porażki wybranych testów z powodu zachowania. Błąd importu,
  pominięte testy lub samo zapewnienie modelu nie otwierają implementacji.
- GREEN wymaga wykonania wszystkich wcześniej wymaganych identyfikatorów testów.
  Zmiana chronionych plików i nieaktualny wynik uniemożliwiają następny etap.
- Błędny test poprawia jego właściciel przez wersjonowane `amend`. Udowodniony
  problem runnera ma osobne `reconfigure` i `rebase`, z ponownym wykonaniem testów.
- DONE wymaga aktualnego review bez otwartych uwag i końcowego pełnego wykonania.
  Zmiana lub usunięcie review unieważnia aktualność wyniku w `status`.
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

## Weryfikacja paczki

Z katalogu `ai-tdd-kit`:

```text
python -B -m unittest discover -s plugins/ai-tdd/tests -v
python -B scripts/smoke_demo.py
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
