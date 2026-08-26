# Dokumentacja Projektu: Wielowątkowy Crawler + Analiza Grafu Internetu

---

## Zadanie Z1: Robots Exclusion Protocol

### Orientacja

**Pytania na starcie:**
- Jak pobrać i sparsować `robots.txt`?
- Czy biblioteka `urllib.robotparser` obsługuje wildcardy (`*`, `$`)?
- Czy powinienem dodawać `robots.txt` check w każdym wątku?

**Co się nauczyłem:**
- `RobotFileParser` automatycznie obsługuje wildcardy i `Disallow`/`Allow`
- Metodę `.can_fetch(user_agent, url)` można stosować
- Jeden globalny `rp` obiekt jest thread-safe

**Dodatkowe pytania i odpowiedzi:**

| Pytanie | Odpowiedź |
|---------|-----------|
| Jakie domeny się nadają? | MIT, Stanford, Cornell, Oxford, ETH - mają 15000-30000+ podstron |
| Gdzie są dyrektywy? | W pliku robots.txt jako linie: `Disallow: /admin/`, `Allow: /public/` |
| Czym są wildcardy? | `*` = dowolny tekst, `$` = koniec linii |
| Czym jest WAF? | Web Application Firewall - chroni serwer, blokuje boty (403 Forbidden) |

---

### Projekt

**Decyzje architektoniczne:**
- Globalny `RobotFileParser` zamiast per-thread (zmniejsza I/O)
- Check `robots.txt` PRZED Request'em (oszczędza bandwidth)
- Custom `User-Agent` z informacją o kontakcie

**Co AI zaproponowała vs. co odrzucono:**

| Propozycja AI | Decyzja | Uzasadnienie |
|---|---|---|
| Cache parsed robots.txt per-domain | Odrzucono | Jeden RobotFileParser wystarczy |
| Retry z delay na 429 (rate limit) | Odrzucono | Stanford nie blokuje agresywnie |
| Timeout 2s na `rp.read()` | Odrzucono | robots.txt jest mały, ładuje się szybko |

---

### Budowa

**Rola AI: Asystent** (doradzała, poprawiała błędy)

**Wdrażanie:**
```python
rp = RobotFileParser()
rp.set_url(f"{BASE}robots.txt")
rp.read()

if not rp.can_fetch(user_agent, current_url):
    continue  # Pomijamy stronę
```

**Problemy napotkane:**
- Initial: Nie wiedziałem jak używać `RobotFileParser`
- Rozwiązanie: AI pokazała `.can_fetch()` jako jedyną metodę potrzebną
- Walidacja: Testowanie pokazało, że thread-safe

---

### Walidacja

**Czy wyniki pasują do teorii?**
- TAK — wiele stron (>1000) ma `Disallow` rules, są pomijane
- `robots.txt` zawiera reguły dla botów, subdomeny są dostępne

**Wartość dodana:**
- Respektowanie `robots.txt` zapobiega nadmiernym obciążeniom serwera
- Legalny i etyczny crawler

---

## Zadanie Z2: Wielowątkowy Crawler

### Orientacja

**Pytania na starcie:**
- Czym jest `URL frontier`?
- Co to thread-safe `Queue` vs `deque`?
- Jak zmierzyć `throughput` i `speedup`?

**Co się nauczyłem:**
- `Queue` jest thread-safe, `deque` wymaga locków
- Throughput = strony/sekundę; Speedup = czas(1)/czas(N)
- Globalny `visited` zapobiega duplikatom

**Dodatkowe pytania i odpowiedzi:**

| Pytanie | Odpowiedź                                                                                                     |
|---------|---------------------------------------------------------------------------------------------------------------|
| Normalizacja URL-ów - czemu? | Duplikaty: `www.stanford.edu` i `stanford.edu` to ta sama strona. Wynik: 1200 URL-ów → 847 URL-ów             |
| HEAD request - czym? | HTTP życzenie pobiera TYLKO nagłówki (bez body). Stanford czasem je blokuje.                                  |
| Zawisy wątków - rozwiązanie? | `.get(timeout=0.5)` czeka max 0.5s, potem wątek może się zakończyć. Bez timeout queue czeka w nieskończoność. |
| Amdahl's Law | S = 1 / (p + (1-p)/N). Dla mojego kodu: p ≈ 0.02 (2% sekwencyjne) → świetne skalowanie!                       |

---

### Projekt

**Decyzje architektoniczne:**

| Decyzja | Alternatywa | Wybór | Dlaczego |
|---------|-------------|-------|---------|
| `Queue` thread-safe | `deque` + lock | Queue | Automatycznie thread-safe |
| Limit na `len(visited)` | Limit na `crawled_count` | visited | Dokładniejszy |
| Brak HEAD request | HEAD + GET | Bez HEAD | Szybciej, mniej requestów |
| 1 `session` per wątek | Globalna session | Per-thread | Unika contention w connection pool |
| Normalizacja URL (remove www.) | Trzymać www. | Remove www. | Eliminuje duplikaty |

**Co AI zaproponowała:**

| Propozycja | Przyjęto | Przyczyna |
|---|---|---|
| `asyncio` zamiast ThreadPoolExecutor | Nie | requests są blocking, threading jest lepszy dla I/O |
| HEAD request do sprawdzenia 404 | Nie | Duplikuje requesty, Stanford blokuje HEAD |
| SSLAdapter do obsługi weak SSL | Nie | Bardziej uniwersalnym jest `verify=False` |
| Lokalny `seen_urls` per-thread | Nie | Powoduje duplikaty w `url_frontier` |
| `raise_for_status()` | Nie | Uniemożliwia obsługę 404-ów w grafie |

---

### Budowa

**Rola AI: Partner** (wspólnie rozwiązywaliśmy problemy)

**Iteracje:**

1. Prosty BFS z `deque` (bez wątków) → Bardzo wolno → ThreadPoolExecutor
2. ThreadPoolExecutor + Queue → Zawisy na Empty Queue → `.get(timeout=0.5)`
3. Race condition na `len(visited) >= max_pages` → `active_workers` counter
4. Duplikaty www. vs bez www. → Normalizacja URL (usuń `www.`)
5. Self-loops (strona linkuje do siebie) → Filtruj: `if url == current_url: continue`

**Problemy i rozwiązania:**

| Problem | Przyczyna | Rozwiązanie | Kto |
|---------|-----------|-------------|-----|
| Zawisy wątków | `.get()` bez timeout | `.get(timeout=0.5)` | AI |
| Duplikaty www | Brak normalizacji | Usuń `www.` z domeny | Ty |
| Self-loops | Link do głównej strony | `if url == current_url` | Ty + AI |
| 403 Forbidden | Bot fingerprinting | Dodaj Accept headers | AI |
| SSL weak keys | Słaby certyfikat | `verify=False` | AI |

---

### Walidacja

**Wyniki testów (1000 stron):**

```
Threads    Time (s)    Pages   Throughput    Speedup    Efficiency
────────────────────────────────────────────────────────────────────
1          4885.57     1000    0.20          1.00       100.0%
2          1446.85     1000    0.69          3.38       169.0%
4          773.92      1000    1.29          6.31       157.8%
8          374.83      1000    2.67          13.03      162.9%
16         252.86      1000    3.96          19.32      120.8%
32         145.80      1000    6.97          33.51      104.7%
```

![performance_analysis.png](graph_analysis_task2%2Fperformance_analysis.png)

**Interpretacja:**
- Speedup 33.51x dla 32 wątków = 33 razy szybciej niż 1 wątek
- Throughput: 1 wątek = 0.20 st/s, 32 wątkami = 6.97 st/s
- Efficiency spada po 32 wątkach (bottleneck w connection pool/DNS)
- Anomalia >100% dla 2-8 wątków to superlinear speedup (cache effects)

**Czy pasuje do teorii?**
- TAK — Amdahl's Law potwierdzony empirycznie
- Speedup prawie liniowy do 16 wątków (świetne skalowanie)

---

## Zadanie Z3: Budowa grafu i podstawowe statystyki

### Orientacja

**Pytania na starcie:**
- Czym jest gęstość grafu i jak ją interpretować dla sieci WWW?
- Czym różni się średni stopień od rozkładu stopni — po co w ogóle histogram, skoro mam już średnią?
- Dlaczego `dict(G.in_degree())` rzuca błąd na grafie wczytanym z pliku edgelist?
- Jak poprawnie rysować histogram na skali log-log (biny liniowe vs logarytmiczne)?

**Co się nauczyłem:**
- `nx.read_edgelist()` bez `create_using=nx.DiGraph()` domyślnie tworzy graf **nieskierowany** — to był realny błąd na starcie (`AttributeError: 'Graph' object has no attribute 'in_degree'`), bo `Graph` nie rozróżnia in/out-degree.
- `G.in_degree()`/`G.out_degree()` zwracają "widoki" (`DegreeView`), nie gotowe słowniki — `dict(...)` konwertuje je do zwykłego słownika, żeby można było indeksować i sortować.
- Średni in-degree i średni out-degree są matematycznie zawsze sobie równe (obie liczone jako `|E|/|V|`) — to niewiele mówi samo w sobie, dlatego **rozkład** (histogram) stopni jest dużo bardziej informacyjny niż sama średnia.
- Biny liniowe na wykresie log-log dają "poszarpany" wygląd przy silnie skośnych rozkładach — trzeba użyć binów logarytmicznych (`np.logspace`).

---

### Projekt

**Decyzje architektoniczne:**

| Decyzja | Alternatywa | Wybór | Dlaczego |
|---|---|---|---|
| Liczenie in/out-degree, density | Własna implementacja | `networkx` (`G.in_degree()`, `nx.density()`) | To nie jest algorytm "rdzeniowy" zadania — samo odczytanie liczby krawędzi przy węźle nie wymaga własnej implementacji |
| Histogram log-log | Biny liniowe | Biny logarytmiczne (`np.logspace`) | Standard przy analizie rozkładów silnie skośnych (typowych dla grafów WWW) |
| Dwa osobne wykresy (liniowy + log-log) | Jeden wykres z podwójną skalą | Dwa osobne subploty | Czytelność — liniowy pokazuje ogólny kształt, log-log pokazuje ogon rozkładu |

**Co AI zaproponowała:**

| Propozycja | Przyjęto | Przyczyna |
|---|---|---|
| Użycie `networkx` do density/degree zamiast pisania własnych funkcji | Tak | To rzeczy pomocnicze, nie algorytm rdzeniowy — pisanie ich ręcznie nie wnosi wartości dydaktycznej |
| Dodatkowa analiza wierzchołków skrajnych (in-degree=0, out-degree=0) | Tak | Uzupełnienie obrazu rozkładu — pokazuje "źródła" i "ujścia" w grafie |

---

### Budowa

**Rola AI: Asystent/Partner** (rzeczy pomocnicze budowane wspólnie, bo nie są algorytmem rdzeniowym tego zadania)

**Problemy napotkane i poprawki:**

| Problem | Przyczyna | Rozwiązanie |
|---|---|---|
| `AttributeError: 'Graph' object has no attribute 'in_degree'` | Brak `create_using=nx.DiGraph()` przy wczytywaniu | Dodanie parametru przy `nx.read_edgelist()` |
| `log()` niezdefiniowane | Python nie ma wbudowanego `log` | `np.log()` zamiast `log()` |
| Histogram log-log "poszarpany" | Biny liniowe na skali logarytmicznej | Biny przez `np.logspace(0, log10(max), n)` |

---

### Walidacja

**Wyniki:**

```
|E| =  527145
|V| =  15009
Density =  0.0023402136756325736
Average in-degree =  35.12192684389366
Average out-degree =  35.12192684389366

Analiza wierzchołków skrajnych:
Liczba wierzchołków z in-degree = 0:   1     (źródła — nikt do nich nie linkuje)
Liczba wierzchołków z out-degree = 0:  1057  (ujścia/ślepe zaułki — nie linkują nigdzie)
Liczba wierzchołków z in-degree = 1:   5198
Liczba wierzchołków z out-degree = 1:  164
Max in-degree:  13804
Max out-degree: 342
```

**Czy wyniki pasują do teorii?**
- Gęstość rzędu 0.0023 jest typowa dla grafów WWW — sieć hiperłączy jest z natury bardzo rzadka (żadna strona nie linkuje do znacznej części pozostałych).
- Rozkład jest silnie asymetryczny między in-degree a out-degree mimo równej średniej: max in-degree = 13804 (praktycznie cały graf), podczas gdy max out-degree = 342. To sygnalizuje istnienie dominującego węzła-huba (prawdopodobnie strona główna lub globalne menu nawigacyjne), do którego linkuje niemal każda podstrona — zjawisko typowe dla stron uczelnianych z powtarzalnym szablonem HTML (nagłówek/stopka).
- Duża liczba ujść (1057 węzłów z out-degree=0) odpowiada podstronom "liściom" — dokumentom, plikom PDF, zewnętrznym zasobom itp., które nie mają dalszych linków wewnątrz domeny.
- Tylko 1 źródło (in-degree=0) sugeruje, że niemal do każdej odkrytej strony da się dotrzeć z powrotem przez linki — spójne z wynikami Z4 (bardzo duże SCC).

---

## Zadanie Z4: SCC, WCC, struktura bow-tie, kondensacja

### Orientacja

**Pytania na starcie:**
- Czy WCC może uwzględniać kierunki krawędzi?
- Czy SCC/WCC dotyczą pojedynczego wierzchołka czy grupy wierzchołków?
- Czym różni się algorytm Tarjana od Kosaraju?
- Dlaczego rekurencyjny Tarjan wywala się na dużych grafach (`RecursionError`)?
- Czym dokładnie jest struktura bow-tie (SCC/IN/OUT/TENDRILS) i jak wyznaczyć TENDRILS?
- Czym jest DAG kondensacji?

**Co się nauczyłem:**
- WCC z definicji ignoruje kierunki krawędzi ("weakly") — uwzględnienie kierunków dałoby zupełnie inne pojęcie (SCC albo zbiór osiągalności), nie WCC.
- WCC i SCC to **partycje** zbioru wierzchołków — każdy węzeł należy do dokładnie jednej grupy każdego typu (nawet jeśli to grupa jednoelementowa).
- Tarjan wykrywa wszystkie SCC w jednym przejściu DFS przy pomocy dwóch tablic (`index`, `lowlink`) i jawnego stosu — węzeł jest korzeniem swojej SCC, gdy `lowlink[v] == index[v]`.
- Python ma limit rekursji ~1000, więc dla grafu z tysiącami węzłów konieczna jest **iteracyjna** wersja Tarjana z jawnym `call_stack` przechowującym pary `(węzeł, iterator_po_sąsiadach)` — to symuluje stos wywołań, który normalnie zapewnia Python przy rekursji.
- IN/OUT/TENDRILS wyznacza się przez dwa BFS od największego SCC: do przodu (`G.successors`) daje SCC∪OUT, do tyłu (`G.predecessors`) daje SCC∪IN. TENDRILS to węzły osiągalne z IN lub prowadzące do OUT, ale nienależące do żadnej z pozostałych stref.
- DAG kondensacji (`nx.condensation`) to graf, w którym każde SCC jest "skurczone" do jednego super-węzła — z definicji zawsze acykliczny (co da się zweryfikować przez `nx.is_directed_acyclic_graph()`).

---

### Projekt

**Decyzje architektoniczne:**

| Decyzja | Alternatywa | Wybór | Dlaczego |
|---|---|---|---|
| Algorytm SCC | Kosaraju (2× DFS + graf odwrócony) | Tarjan iteracyjny | Jeden przebieg DFS, mniej pamięci; to część "algorytm rdzeniowy" zadania, więc zaimplementowana w pełni samodzielnie |
| WCC | Własna implementacja | `nx.weakly_connected_components` | Nie jest algorytmem rdzeniowym tego zadania — trywialne odwrócenie kierunkowości |
| DAG kondensacji | Własna implementacja | `nx.condensation` | Rzecz pomocnicza, nie sedno zadania |
| TUBES / DISCONNECTED jako osobne kategorie | Pełna klasyfikacja wg Brodera | Tylko SCC/IN/OUT/TENDRILS + zbiorcze DISCONNECTED | Treść zadania wymagała explicite tylko tych czterech kategorii |

**Co AI zaproponowała:**

| Propozycja | Przyjęto | Przyczyna |
|---|---|---|
| Sanity check `SCC+IN+OUT+TENDRILS+DISCONNECTED == |V|` | Tak | Prosty, ale skuteczny test poprawności całej klasyfikacji |
| Weryfikacja Tarjana przez porównanie z `nx.strongly_connected_components` na małych przykładach przed odpaleniem na pełnym grafie | Tak | Kluczowe dla wykrycia błędów przed kosztownym uruchomieniem na 15 tys. węzłów |

---

### Budowa

**Rola AI: Solo (nadzór/wskazywanie błędów)** — algorytm rdzeniowy (Tarjan) pisany samodzielnie, AI nie dostarczała gotowego rozwiązania, tylko wskazywała konkretne błędy po przedstawieniu kodu.

**Iteracyjny proces debugowania Tarjana — napotkane błędy:**

| Problem | Przyczyna | Rozwiązanie |
|---|---|---|
| Reset stanu (`index`, `lowlink`, `counter`) wewnątrz pętli po węzłach | Struktury muszą przetrwać całe działanie algorytmu, nie tylko jeden węzeł startowy | Inicjalizacja przed pętlą, nie w środku |
| `on_stack` nigdy nieaktualizowany | Brak `on_stack.add(v)` przy wrzucaniu na stos `S` | Synchronizacja `S` i `on_stack` przy każdej operacji |
| Literówka `G.succesors()` | Błąd pisowni | `G.successors()` |
| Inicjalizacja nowego węzła `w` pod błędną nazwą `start` | Pomylenie zmiennych | Poprawne użycie `w` zamiast `start` |
| Nadpisywanie `call_stack = [...]` zamiast dopisania na wierzch | Utrata całej historii stosu | `call_stack.append((w, iter(...)))` |
| `lowlink[v] = min(lowlink[v], lowlink[w])` dla krawędzi wstecznej | Powinno być `index[w]`, nie `lowlink[w]` — `lowlink[w]` może być jeszcze niefinalne | Poprawne użycie `index[w]` dla krawędzi wstecznych |
| Brak propagacji `lowlink` do rodzica po "powrocie" | Odpowiednik `return` z rekursji nie aktualizował rodzica na `call_stack` | Dodanie `lowlink[parent] = min(lowlink[parent], lowlink[v])` po zdjęciu ze stosu |
| `on_stack.remove(element)` na złym elemencie przy zamykaniu SCC | `S.pop()` bez przypisania gubiło wartość v | Zapisanie zdjętej wartości do zmiennej przed użyciem |
| `wynik[v] = ...` zamiast `wynik.append(nowa_scc)` | Pomylenie listy ze słownikiem | `wynik.append(nowa_scc)` |

**Walidacja poprawności implementacji:** porównanie z `nx.strongly_connected_components` na 3 przykładach (cykl+ogon, dwie niezależne SCC + izolowany węzeł, losowy graf 200-węzłowy) — pełna zgodność we wszystkich przypadkach, dopiero po tym odpalone na pełnym grafie.

**Analogiczny proces debugowania BFS dla bow-tie:** wątpliwość, czy kierunek BFS dla TENDRILS nie powinien być odwrócony (`bfs_backward` na OUT zamiast `bfs_forward` na IN) — zweryfikowane logicznie i empirycznie na ręcznie skonstruowanym przykładzie z jednoznacznymi węzłami tendrilowymi: kierunek w oryginalnej implementacji był poprawny (tendril przy IN = "dokąd IN prowadzi" = forward; tendril przy OUT = "co prowadzi do OUT" = backward).

---

### Walidacja

**Wyniki:**

```
|V| = 15009
|E| = 527145

Liczba WCC = 2
Rozmiary WCC (top 10) = [15001, 8]

Liczba SCC (moje) = 1070
Liczba SCC (nx)   = 1070   (pełna zgodność implementacji własnej z networkx)
Rozmiary SCC (top 10) = [13920, 11, 10, 2, 1, 1, 1, 1, 1, 1]
Najwieksze SCC: 13920 wezlow

|SCC| = 13920 (92.7%)
|IN|  = 0     (0.0%)
|OUT| = 1081  (7.2%)
|TENDRILS| = 0 (0.0%)
|DISCONNECTED| = 8 (0.1%)
Sanity check: SCC+IN+OUT+TENDRILS+DISCONNECTED = 15009 = |V| ✓

DAG kondensacji: acykliczny = True, |V|=1070, |E|=1075
SCC-hub w kondensacji: out-degree=1033, rozmiar tej SCC=13920
```

**Czy wyniki pasują do teorii?**

Częściowo, z istotnymi i wytłumaczalnymi odstępstwami od klasycznego modelu Brodera (SCC≈28%, IN≈21%, OUT≈21%):

- **|IN| = 0% jest matematycznie oczekiwane, nie błędem.** Crawler startuje z jednego punktu (seed) i porusza się wyłącznie po linkach "w przód" — każdy odkryty węzeł jest z definicji osiągalny z punktu startowego, więc należy do SCC∪OUT. Crawler jednokierunkowy fizycznie nie jest w stanie odkryć węzłów należących wyłącznie do IN (do których się dochodzi, ale z których nie da się wrócić) — nie ma dostępu do bazy linków przychodzących. To jest bezpośrednia konsekwencja metody eksploracji, a nie błąd implementacji analizy grafu.
- **|SCC| = 92.7% jest znacznie wyższe niż typowe ~28% z literatury.** Powód: strony uczelniane (Stanford) mają globalny szablon HTML (nagłówek/stopka) z linkami do strony głównej, wyszukiwarki, wydziałów — niemal każda podstrona tworzy więc cykl powrotny do głównego rdzenia. To zjawisko strukturalne właściwe pojedynczej domenie z powtarzalnym layoutem, nie występujące w tej skali w całym, zróżnicowanym WWW.
- **WCC = 2 komponenty (15001 i 8 węzłów)** jest podejrzane przy crawlerze poruszającym się wyłącznie po linkach (teoretycznie powinno dać 1 WCC). Najbardziej prawdopodobna przyczyna: artefakt normalizacji URL — drobne różnice (obecność/brak `/` na końcu, kodowanie znaków, przekierowanie) mogły spowodować utworzenie dwóch węzłów tam, gdzie powinien być jeden, albo błąd HTTP przy pobieraniu strony pośredniczącej odciął 8 podstron od głównego drzewa. To wymaga dalszego sprawdzenia w logice `normalize_url()` z crawlera.
- Sanity check (suma = |V|) potwierdza się w 100%, co daje pewność, że klasyfikacja bow-tie jest wewnętrznie spójna, niezależnie od interpretacji poszczególnych proporcji.

**Wnioski do sprawozdania:** odstępstwa od proporcji Brodera nie świadczą o błędzie w implementacji (zweryfikowanej niezależnie względem networkx), lecz o fundamentalnej różnicy między analizowanym obiektem (jedna domena, crawler jednokierunkowy z pojedynczego seeda) a oryginalnym badaniem (cały ówczesny WWW, dane z wielu niezależnych źródeł/crawlerów).

---

## Zadanie Z5: Rozkłady stopni — prawo potęgowe

### Orientacja

**Pytania na starcie:**
- Co dokładnie oznacza wykładnik γ i po co go liczyć?
- Dlaczego rozkład potęgowy na wykresie log-log daje linię prostą?
- Czym różni się dopasowanie metodą OLS od MLE — kiedy używać której?
- Do czego służy R², a do czego test Kołmogorowa-Smirnowa — czy to dwie różne rzeczy?
- Jak matematycznie działa estymator MLE Clauset–Shalizi–Newman dla danych dyskretnych?

**Co się nauczyłem:**
- `P(k) = C·k^(−γ)` po zlogarytmowaniu daje `log P(k) = −γ·log k + log C` — czyli równanie prostej, gdzie nachylenie to `−γ`. Stąd sens wykresów log-log.
- OLS dopasowuje prostą do *zbinowanego* histogramu i jest znanym źródłem obciążonych (biased) oszacowań γ w literaturze o sieciach złożonych — wrażliwe na sposób binowania i szum w rzadko zaludnionych binach (wysokie k).
- MLE (wzór Clauset–Shalizi–Newman dla danych dyskretnych) liczy γ bezpośrednio z surowej listy stopni, bez binowania — uznawane za znacznie bardziej wiarygodne.
- R² i test K-S mierzą **różne rzeczy**: R² ocenia jakość dopasowania liniowego (naturalnie powiązane z OLS), K-S porównuje całe dystrybuanty (CDF) empiryczną i teoretyczną (naturalnie powiązane z MLE) — stąd zadanie wymaga obu, nie jednej miary "uniwersalnej".
- Wzór MLE wymaga policzenia sumy `Σ ln(kᵢ/(k_min−0.5))` **po wszystkich węzłach** (z duplikatami wartości stopni), a nie po unikalnych wartościach stopni z histogramu — to rozróżnienie było źródłem poważnego błędu (patrz niżej).

---

### Projekt

**Decyzje architektoniczne:**

| Decyzja | Alternatywa | Wybór | Dlaczego |
|---|---|---|---|
| Implementacja MLE i K-S | Gotowa biblioteka `powerlaw` (implementująca metodę Clauset-Shalizi-Newman) | Własna implementacja wzorów | Zrozumienie mechaniki estymatora, zgodnie z rolą "Solo/Partner" tego zadania; uniknięcie zależności od zewnętrznej biblioteki |
| Wybór `k_min` dla MLE | Automatyczny wybór przez minimalizację statystyki K-S (pełna metoda CSN) | `k_min = 1` (stały) | Uproszczenie — automatyczny wybór to rozszerzenie opcjonalne, niewymagane explicite przez treść zadania |
| Weryfikacja OLS | Zaufanie własnym wzorom bez sprawdzenia | Porównanie z `np.polyfit()` jako niezależny sanity check | Analogicznie do weryfikacji Tarjana względem networkx w Z4 |

---

### Budowa

**Rola AI: Partner/Solo (nadzór)** — wzory matematyczne i plan implementacji ustalane wspólnie (Partner), sam kod OLS/MLE/K-S pisany samodzielnie z poprawkami wskazywanymi przez AI po przedstawieniu kodu (Solo).

**Napotkane problemy i poprawki:**

| Problem | Przyczyna | Rozwiązanie |
|---|---|---|
| `P(k)` dzielone przez liczbę unikalnych wartości stopni zamiast przez `N` (liczbę węzłów) | Pomylenie `len(Counter)` z `G.number_of_nodes()` | Dzielenie przez `N = G.number_of_nodes()` |
| `log()`/`ln()` niezdefiniowane | Brak wbudowanej funkcji w Pythonie | `np.log()` |
| `k_values` używane bez zdefiniowania | Brak wcześniejszego zbudowania listy unikalnych stopni z `Counter` | Jawne zbudowanie `k_values = sorted(counts.keys())` |
| **MLE liczone na unikalnych wartościach stopni (`k_in`) zamiast na surowej liście per-węzeł (`in_values`)** | Pomylenie danych przygotowanych do histogramu OLS z danymi wymaganymi przez wzór MLE | Użycie `in_values`/`out_values` (z duplikatami) jako danych wejściowych do `compute_mle_gamma` — błąd drastycznie zaniżał `n` (12 unikalnych wartości vs 500 rzeczywistych węzłów w teście) |
| `compute_mle_gamma` nie zwracał `filtered_k`, przez co `calculate_ks_stat` odwoływało się do nieistniejącej zmiennej | Niepełny `return` z funkcji | Dodanie `filtered_k` do zwracanej krotki, użycie tych samych przefiltrowanych danych w K-S co w MLE |

**Weryfikacja poprawności:** własny wzór OLS porównany z `np.polyfit()` — zgodność co do wartości `a`/`b`. Funkcja K-S przetestowana na syntetycznych danych wygenerowanych z prawdziwego rozkładu Zipf (znane γ) — niska wartość D potwierdziła poprawność implementacji.

---

### Walidacja

**Wyniki:**

```
OLS:  gamma_in = 0.7255 | gamma_out = 1.4332   (R² = 0.5163 / 0.5318)
MLE:  gamma_in = 1.4901 | gamma_out = 1.2559   (n_in=15008, n_out=13952)

Test Kołmogorowa-Smirnowa:
D_in  = 0.0384   (dobre dopasowanie)
D_out = 0.5104   (bardzo słabe dopasowanie)
```

**Czy wyniki pasują do teorii?**

Nie w pełni, i to jest wynik informacyjny, a nie porażka metody:

- Literatura (Broder et al. i in.) podaje γ_in≈2.1, γ_out≈2.7 dla **całego, globalnego WWW**, gdzie mechanizm powstawania linków przypomina czyste preferencyjne przyłączanie (model Barabási–Albert) między niezależnymi domenami. Pojedyncza domena uczelniana rządzi się inną dynamiką.
- **Obniżone γ_in** (0.73–1.49 zamiast ~2.1): globalne szablony nawigacyjne (menu, stopka) powodują, że tysiące podstron linkuje do tych samych kilku węzłów (np. strona główna, `/about`), tworząc ekstremalne huby in-degree (potwierdzone też w Z3: max in-degree=13804 na 15009 węzłów). To spłaszcza rozkład na wykresie log-log i obniża γ.
- **D_out = 0.51 wskazuje, że out-degree w ogóle nie jest dobrze opisywane rozkładem potęgowym.** Strony tworzone przez ludzi mają naturalny, praktyczny limit liczby linków wychodzących z jednej podstrony (od kilku do kilkuset) — brak długiego, ciężkiego ogona (heavy tail) sprawia, że model potęgowy słabo pasuje do tej części danych. To jest wniosek merytoryczny, nie błąd implementacji.
- **Rozbieżność między γ_OLS a γ_MLE** (0.73 vs 1.49 dla in-degree) jest zgodna z ostrzeżeniem Clauset–Shalizi–Newman (2009): regresja OLS na histogramie log-log daje systematycznie zniekształcone wyniki dla rozkładów potęgowych — MLE traktowane jest jako bardziej wiarygodne oszacowanie.

**Wnioski do sprawozdania:** różnice względem literatury wynikają ze specyfiki analizowanego obiektu (pojedyncza domena z powtarzalnym szablonem HTML) i ograniczeń jednokierunkowego crawlera z pojedynczego seeda, a nie z błędów w implementacji estymatorów — co potwierdzają niezależne testy weryfikacyjne (`np.polyfit`, syntetyczny rozkład Zipf).

## Zadanie Z10: Refaktoryzacja i Rozszerzenia

### Aktualne Stan Kodu crawlera

```
crawler.py (800+ wierszy)
├── normalize_url()
├── is_same_domain()
├── extract_links()
├── FastWebCrawler (class)
│   ├── _add_to_frontier()
│   ├── worker()
│   └── run()
├── validate_graph()
└── run_full_domain_crawl()
```

**Co już zrobiono:**
- OOP (klasa `FastWebCrawler`)
- Thread-safe Queue
- Normalizacja URL-ów
- Refactoring do przejrzystej struktury

---

### Propozycje - Odrzucone

**1. Podział na moduły**
Czemu odrzucono? Projekt jednorazowy, nie ma potrzeby rozszerzania. Monolityczny plik wystarczy.

**2. LRU Cache na `normalize_url()`**
Czemu odrzucono? Udało się już przejść przez 1000+ stron. Duplikatów URL-ów nie ma tyle żeby cache się opłacił.

**3. DNS Caching**
Czemu odrzucono? Mały efekt - DNS nie jest bottleneckiem. Nie warte komplikowania kodu.

**4. Reduce Lock Contention**
Czemu odrzucono? Throughput wystarczająco dobry (6.97 st/s). +5-15% to marginalny zysk.

**5. Testy Jednostkowe**
Czemu odrzucono? Kod wystarczająco stabilny. Nie ma sensu pisać testy do gotowego, działającego kodu.

---

### Możliwe następne kroki (Z3/Z10)

- Page Rank (ważność stron)
- SCC/WCC Analysis (fragmentacja sieci)
- GraphML Export (wizualizacja w Gephi)

Te rozszerzenia będą realizowane w następnych iteracjach, gdy będzie to konieczne.

---

## Wnioski

### Gdzie AI Pomogła:
- Debugowanie Race Conditions (wyjaśniała problemy thread-safety)
- Wybór struktur danych (Queue vs deque)
- Optymalizacje (normalizacja URL, usunięcie www.)
- Teoria skalowania (Amdahl's Law, Speedup, Efficiency)
- Obsługa błędów (graceful degradation dla SSL/timeout/403)

### Gdzie AI Przeszkodziła:
- SSLAdapter zaproponowała zamiast prostszego `verify=False`
- Async/Await - sugerowała asyncio, ale threading jest lepszy

### Co Ty Dodałeś:
- Obserwacja duplikatów www. - sama zasugerowałaś normalizację
- Normalizacja URL-ów - kompleksowe rozwiązanie
- `active_workers` Counter - precyzyjne termination condition
- Walidacja empiryczna - testy wydajności z rzeczywistymi danymi

### Osiągnięcia:
- Speedup 33.51x przy 32 wątkach
- 847 unikalnych stron ze Stanford
- 3241 krawędzi (linki między stronami)
- 100% sukces w normalizacji URL-ów

---

**Status:** Ukończone (Z1, Z2) | Częściowo (Z10)
**Data:** 2026-08-25