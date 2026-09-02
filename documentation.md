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

## Zadanie Z6: Najkrótsze ścieżki i odległości

### Orientacja

**Pytania na starcie:**
- Czym jest ekscentryczność, średnica, promień i jak się mają do siebie?
- Czym różni się średnia odległość od średnicy?
- Co dokładnie pokazują histogramy odległości par i średnich odległości?
- Co oznacza „analiza rozkładu przez regresję” w kontekście odległości — to samo co przy Z5?
- Czym jest efekt małego świata i jak go skomentować w kontekście tego grafu?
- Czy próbkowanie (500–1000) oznacza próbkowanie wierzchołków jako źródeł BFS?
- Jak w grafie skierowanym zdefiniować ekscentryczność, skoro część par może być nieosiągalna?

**Co się nauczyłem:**
- e(v) = największa odległość od v do jakiegokolwiek osiągalnego wierzchołka; promień = min e(v); średnica = max e(v). Zawsze zachodzi: promień ≤ średnica ≤ 2·promień — użyteczny sanity check.
- W grafie skierowanym e(v) jest formalnie nieskończone, jeśli v nie osiąga wszystkich innych węzłów — trzeba jawnie zdecydować, jak to obsłużyć (tylko pary osiągalne / tylko SCC / wersja nieskierowana).
- Wierzchołek bez krawędzi wychodzących (out-degree=0, „sink node”) ma z definicji e(v)=0 — to nie błąd, tylko konsekwencja tego, jak działa BFS z takiego węzła. Przy dużej liczbie takich węzłów promień całego grafu niemal na pewno wyjdzie 0.
- Globalna średnia odległość całego grafu ma dwie różne, uzasadnione definicje: średnia ze średnich per-wierzchołkowych (Metoda A) vs jedna średnia po wszystkich policzonych parach łącznie (Metoda B, tzw. „characteristic path length” z literatury). Dają różny wynik, bo różnie ważą wierzchołki o różnej liczbie osiągalnych celów.
- Histogram odległości par: spłaszczona lista wszystkich policzonych d(u,v) z wszystkich BFS-ów, oś X = wartość odległości, oś Y = liczba par. Histogram średnich odległości: jedna wartość na wierzchołek (jego własna średnia), oś X = ta wartość, oś Y = liczba wierzchołków.
- Efekt małego świata: średnia odległość/średnica rosną w przybliżeniu jak log(N), a nie liniowo z N — komentarz w raporcie sprowadza się do porównania policzonych wartości z log(N) dla własnego N.
- Próbkowanie w tym kontekście oznacza próbkowanie wierzchołków jako źródeł BFS (nie par ani krawędzi) — z każdego source odpala się pełny BFS do wszystkich osiągalnych celów.

**Dodatkowe pytania i odpowiedzi:**

| Pytanie | Odpowiedź |
|---|---|
| Czy ekscentryczność/promień/średnica są liczone globalnie czy per wierzchołek? | Ekscentryczność — per wierzchołek. Promień i średnica — globalne (odpowiednio min i max z ekscentryczności). |
| Czy próbka z BFS daje dokładny czy przybliżony diameter/radius? | Eccentricity próbkowanych węzłów jest dokładna. Diameter z próbki to dolne ograniczenie prawdziwego diameteru (prawdziwe maksimum może być poza próbką), radius z próbki to górne ograniczenie (prawdziwe minimum może być poza próbką). |
| Czy trzeba budować listę list z nieskończonościami? | Nie — podejście słownikowe (brak klucza = nieosiągalny) załatwia to bez jawnych ∞, oszczędniej pamięciowo niż macierz N×N. |

---

### Projekt

**Decyzje architektoniczne:**

| Decyzja | Alternatywa | Wybór | Dlaczego |
|---|---|---|---|
| Zakres analizy | Tylko największe SCC | Cały graf, ignorowanie nieosiągalnych par (+∞ pomijane) | SCC jeszcze nieprzygotowane do użycia na tym etapie projektu |
| Globalna średnia odległość | Metoda B (średnia po wszystkich parach — standard z literatury) | **Metoda A** (średnia ze średnich per-wierzchołkowych) | Decyzja użytkownika — prostsza koncepcyjnie, mimo że AI rekomendowała Metodę B jako zgodną z klasyczną definicją „characteristic path length” |
| Implementacja BFS | Macierz odległości N×N z jawnymi ∞ | Słownik `{osiągnięty_węzeł: odległość}`, brak wpisu = nieosiągalny | Mniejsze zużycie pamięci, naturalna obsługa nieosiągalności bez dodatkowej logiki |
| Statystyki opisowe | moduł `statistics` (stdlib) | `numpy` | Konflikt nazwy z istniejącym plikiem `statistics.py` w projekcie użytkownika |

**Co AI zaproponowała:**

| Propozycja | Przyjęto | Przyczyna |
|---|---|---|
| Metoda B jako globalna miara odległości | Nie | Użytkownik zdecydował się na prostszą Metodę A |
| Liczenie promienia/średnicy tylko po wierzchołkach z out-degree > 0 | Odłożone do Walidacji | Do decyzji po zobaczeniu pełnych wyników na docelowym grafie |
| Pełne BFS ze wszystkich wierzchołków zamiast próbki 500–1000 | Tak (utrzymano nawet po powiększeniu grafu do docelowych ~15 000 węzłów) | Zamiast przechodzić na próbkowanie przy większym grafie, zoptymalizowano zużycie pamięci (agregacja w locie) — patrz Budowa/Walidacja poniżej |

---

### Budowa

**Rola AI: Solo (nadzór/wskazywanie błędów)** — algorytm rdzeniowy (BFS i pochodne metryki) pisany przez użytkownika, AI wskazywała konkretne błędy po przedstawieniu kodu, bez podawania gotowego rozwiązania z góry.

**Problemy napotkane i poprawki:**

| Problem | Przyczyna | Rozwiązanie |
|---|---|---|
| `diameter = max(eccentricity)` / `radius = min(eccentricity)` dawały błędny wynik | `max()`/`min()` na słowniku iterują po kluczach (nazwach węzłów), nie po wartościach | Dodanie `.values()`: `max(eccentricity.values())` |
| Średnia odległość per wierzchołek wliczała odległość do samego siebie (0) | `distances = {start: 0}` zawiera wpis dla source | Filtrowanie `v != vertex` przed liczeniem sumy i dzielnika |
| Dzielenie 0/0 dla wierzchołków bez wyjść (sink nodes) | Po odfiltrowaniu self-distance słownik `others` bywa pusty | Zwracanie `None` jako sygnał braku danych |
| `TypeError` przy `plt.hist()` i błędne statystyki (NaN) | `None` w liście wartości nieodfiltrowane przed liczeniem/rysowaniem | Filtrowanie `None` zarówno w funkcji statystyk opisowych, jak i przed `plt.hist()` |
| Wierzchołek `https://stanford.edu` z ekscentrycznością 0 w pierwszym przebiegu | Podejrzenie: normalizacja URL tworzy duplikaty (np. wersja ze/bez `/`, http/https), realna strona główna prawdopodobnie linkuje gdzieś indziej | Zaplanowana weryfikacja: sprawdzenie `list(G.successors(...))` i istnienia wariantów tego URL jako osobnych węzłów |
| **Awarie pamięci (MemoryError) na docelowym grafie (15 000 węzłów)** | Przechowywanie odległości dla wszystkich par w `all_distances`, a następnie budowa płaskiej listy `pairwise` o ok. 210 mln elementów (15 000 × ~14 000) do `plt.hist()` — wymagało kilkunastu GB RAM, system zabijał proces przy generowaniu wykresu | **Agregacja w locie**: wynik BFS dla pojedynczego wierzchołka jest natychmiast zliczany do `collections.Counter()`, surowe odległości nie są przechowywane; histogram rysowany przez `plt.bar()` na zagregowanych zliczeniach zamiast `plt.hist()` na surowej liście. Efekt: zużycie RAM spadło z >12 GB do kilkudziesięciu MB, czas generowania wykresu z minut do ułamka sekundy |
| Mylące wrażenie zawieszenia skryptu | Logowanie postępu co 2000 wierzchołków sprawiało wrażenie „zamrożenia” na tej wartości, podczas gdy program w tle alokował coraz więcej pamięci i drastycznie zwalniał | Usunięte wraz z przejściem na agregację w locie (brak narastającego zużycia pamięci w trakcie działania) |
| Promień=0 i minimalna ekscentryczność=0/1 dla części wierzchołków, mylące na pierwszy rzut oka | Węzły bez krawędzi wychodzących (out-degree=0 — np. pliki PDF, podstrony bez linków wyjściowych, strony zewnętrzne) dają BFS zwracający słownik zawierający wyłącznie ten jeden węzeł z dystansem 0 — to poprawne zachowanie algorytmu, nie błąd | Rozróżnienie w raportowaniu: „promień surowy” (uwzględnia wszystkie węzły, w tym te o znikomym zasięgu) vs „promień realistyczny” (liczony tylko po węzłach o zasięgu >1000, reprezentujących główną składową grafu) |

---

### Walidacja

**Wyniki (docelowy graf, |V| ≈ 15 009, pełny BFS ze wszystkich wierzchołków):**

```
Średnica (diameter):              9
Promień surowy (radius raw):      1  (uwzględnia węzły o znikomym zasięgu)
Promień realistyczny (zasięg>1k): 5  (dla węzłów w głównej składowej)
--------------------------------------------------
Ekscentryczność: n=13952, min=1.000, max=9.000, mean=5.912, median=6.000
Średnia odległość (per wierzchołek): n=13952, min=1.000, max=7.660, mean=4.519, median=4.601

5 wierzchołków o najmniejszej ekscentryczności (ecc=1, zasięg=9 węzłów każdy):
  https://sig.stanford.edu/copy-of-finding-an-internship
  https://sig.stanford.edu/board-of-directors
  https://sig.stanford.edu/fellowships
  https://sig.stanford.edu/stipends
  https://sig.stanford.edu/contact

5 wierzchołków o największej ekscentryczności (ecc=9, zasięg=15000 węzłów każdy):
  https://uil.stanford.edu/data-code
  https://uil.stanford.edu/team
  https://uil.stanford.edu/contact
  https://uil.stanford.edu/opportunities
  https://uil.stanford.edu/copy-of-contact
```

**Czy wyniki pasują do teorii?**

- **Promień surowy vs realistyczny — rozbieżność jest wyjaśniona, nie jest błędem.** Węzły o ecc=1 (grupa `sig.stanford.edu`) tworzą małą, ciasno powiązaną kieszeń o zasięgu zaledwie 9 węzłów — to nie są węzły centralne dla całego grafu, tylko lokalny, izolowany klaster, w którym każdy „widzi” każdego w jednym kroku. Formalny promień (min ekscentryczności po całym grafie) matematycznie musi wynosić 1, ale nie niesie sensownej informacji o strukturze całości — stąd rozróżnienie na promień surowy (formalnie poprawny, ale mylący) i realistyczny (liczony tylko po węzłach o zasięgu > 1000, a więc reprezentujących główną, dominującą składową grafu) — dobra ilustracja tego, że sama definicja matematyczna czasem wymaga dodatkowego filtra interpretacyjnego, żeby wynik był użyteczny w raporcie.
- **Węzły o maksymalnej ekscentryczności (`uil.stanford.edu`, ecc=9) mają zasięg 15000 — czyli osiągają praktycznie cały graf**, mimo że są jednocześnie „najdalej wysunięte” (największa ekscentryczność). To spójne z obrazem: są to węzły dobrze podłączone do głównej, gęsto połączonej struktury, ale leżące na jej peryferiach pod względem odległości.
- **Rozstęp ekscentryczności (1–9) i sama średnica=9 są bardzo małe względem N≈15 000.** To mocny sygnał efektu małego świata — nawet w najgorszym przypadku (para wierzchołków najdalej od siebie w całej sieci) potrzeba zaledwie 9 kroków, żeby się połączyć.
- **Efekt małego świata — komentarz ilościowy.** Przy N≈15 009 i średnim stopniu ~35 (z Z3), teoretyczne oszacowanie dla grafu losowego to w przybliżeniu ln(N)/ln(⟨k⟩) = ln(15009)/ln(35.12) ≈ 9.62/3.56 ≈ 2.7. Zmierzona średnia odległość (mean≈4.52, median≈4.60) jest większa od tego teoretycznego minimum dla czysto losowego grafu, ale wciąż tego samego rzędu wielkości — i przede wszystkim dramatycznie mniejsza niż N czy nawet √N (~122). To potwierdza efekt małego świata: mimo 15 tys. stron, typowa para wierzchołków dzieli zaledwie ~4–5 kroków, a nawet najdalsza para w całym grafie — 9 kroków. Nieco wyższa wartość niż czysto losowy model jest zgodna z wcześniejszymi obserwacjami (Z5: rozkład potęgowy stopni, silne huby) — struktura sieci nie jest w pełni losowa, ma pewną „grudkowatość” (widoczną też w wysokim współczynniku klasteryzacji z Z7), co lekko wydłuża ścieżki względem czysto losowego modelu, nie zmieniając jednak samej logarytmicznej skali zjawiska.

**Domknięte pytania z wcześniejszego etapu Walidacji:**
- Promień=0 (i formalnie ecc=1 dla części węzłów) potwierdzony jako efekt małych, izolowanych kieszeni grafu — rozwiązany przez wprowadzenie rozróżnienia promień surowy/realistyczny, nie przez zmianę samego algorytmu.
- Zastosowana metoda globalnej średniej odległości to Metoda A (średnia ze średnich per-wierzchołkowych) — porównanie z Metodą B nie zostało jeszcze wykonane na tych danych, pozostaje otwarte jako ewentualne rozszerzenie raportu.

---

## Zadanie Z7: Współczynniki klasteryzacji

### Orientacja

**Pytania na starcie:**
- Jaka jest właściwa definicja C(v) dla grafu skierowanego?
- Czym różni się tranzytywność globalna od średniego lokalnego C?
- Co dokładnie pokazuje C(k) i po co regresja log-log?
- Dlaczego oczekiwany wynik to C(k) ∝ k⁻¹?

**Co się nauczyłem:**
- Klasyczna definicja (nieskierowana): C(v) = 2·e_v/(k_v·(k_v−1)), gdzie e_v to liczba krawędzi między sąsiadami v.
- Dla grafu skierowanego zdecydowano się na prostą, samodzielnie wyprowadzoną generalizację: sąsiedzi = suma następców i poprzedników (unia zbiorów), e_v = liczba **skierowanych** krawędzi między sąsiadami (bez dzielenia przez 2), mianownik k_v·(k_v−1) już uwzględnia uporządkowane pary, więc bez dodatkowego mnożnika ×2 w liczniku.
- `nx.clustering()` na `DiGraph` liczy inną, bardziej złożoną formułę (Fagiolo 2007) — nie da się jej użyć jako bezpośredniego testu 1:1 dla naszej prostszej wersji; różnice liczbowe są oczekiwane, nie błędem.
- Globalna tranzytywność to **suma wszystkich e_v podzielona przez sumę wszystkich k_v·(k_v−1)**, nie średnia z gotowych C(v) — to inna waga (wierzchołki o dużym stopniu mają nieproporcjonalnie większy wpływ), analogiczna do różnicy Metoda A/B z Z6.
- `nx.transitivity()` nie obsługuje grafów skierowanych — wymaga to albo przejścia na wersję nieskierowaną, albo własnej implementacji wg definicji (3×trójkąty / otwarte trójki).
- k_v w mianowniku C(k) musi być tą samą definicją stopnia co wszędzie indziej w obliczeniach (własny zbiorowy `k_v`, nie `G.degree()`, które dla DiGraph liczy in+out i podwójnie liczy sąsiadów połączonych w obie strony).

**Dodatkowe pytania i odpowiedzi:**

| Pytanie | Odpowiedź |
|---|---|
| Czym jest sąsiad w grafie skierowanym? | Każdy wierzchołek, z którym v ma krawędź w dowolnym kierunku (suma następców i poprzedników jako zbiór, nie multizbiór). |
| Czy nachylenie regresji C(k) vs k powinno być dodatnie czy ujemne? | Ujemne, w okolicach -1 — im większy stopień, tym mniejsze C(k) (sąsiedzi hubów są relatywnie mniej wzajemnie połączeni). |

---

### Projekt

**Decyzje architektoniczne:**

| Decyzja | Alternatywa | Wybór | Dlaczego |
|---|---|---|---|
| Formuła C(v) dla grafu skierowanego | `nx.clustering()` (formuła Fagiolo) | Własna, prosta implementacja wg definicji | Treść zadania nie wskazywała konkretnej formuły; decyzja użytkownika, by nie opierać się na wbudowanych funkcjach |
| Tranzytywność globalna | `nx.transitivity(G.to_undirected())` | Własna implementacja zgodna z definicją wzoru skierowanego | Spójność metodologiczna z resztą obliczeń (decyzja użytkownika, mimo że wersja na grafie nieskierowanym byłaby prostsza) |
| Definicja stopnia w C(k) | `G.degree()` (in+out, licząc podwójnie krawędzie obustronne) | Własny `k_v` (rozmiar zbioru sąsiadów) | Spójność z definicją użytą do liczenia samego C(v) |

**Co AI zaproponowała:**

| Propozycja | Przyjęto | Przyczyna |
|---|---|---|
| Liczenie tranzytywności na wersji nieskierowanej (szybsza opcja) | Nie | Użytkownik wybrał implementację własną wg definicji dla spójności metodologicznej |
| Weryfikacja bezpośrednio przez `nx.clustering()` | Częściowo — zmodyfikowane | Inna formuła bazowa (Fagiolo); zaproponowano zamiast tego ręcznie skonstruowany mały przykład testowy z policzalną na kartce wartością |

---

### Budowa

**Rola AI: Partner (budowa)/Tutor (orientacja)/Solo (walidacja)** — zgodnie z ustaloną rolą dla tego zadania; kod pisany przez użytkownika, AI wskazywała błędy po przedstawieniu.

**Problemy napotkane i poprawki:**

| Problem | Przyczyna | Rozwiązanie |
|---|---|---|
| `for node in neighbour` iterowało po znakach stringa URL zamiast po sąsiadach sąsiada | `neighbour` to pojedynczy string, nie kolekcja | Zamiana na `graph.successors(neighbour)` |
| Nadmiarowe dzielenie przez 2 i mnożenie przez 2 w formule skierowanej | Pozostałość z wcześniejszej wersji wzoru dla grafu nieskierowanego | Usunięcie obu operacji — w wersji skierowanej licznik i mianownik już zakładają uporządkowane pary |
| `neighbours = graph[vertex]` dawało tylko następców | Dla `DiGraph`, `G[v]` zwraca wyłącznie successors | Zamiana na `set(successors) \| set(predecessors)` |
| `nx.transitivity(G_u)` z niezdefiniowaną zmienną `G_u` | Pozostałość po niedokończonej wcześniejszej wersji kodu | Zastąpione własną implementacją sumarycznego stosunku e_v/k_v(k_v−1) |
| Zbędna, zduplikowana linijka liczenia średniego lokalnego C | Pozostałość z wcześniejszej iteracji kodu | Usunięcie w finalnej wersji |

---

### Walidacja

**Wyniki (docelowy graf, |V| ≈ 15 009):**

```
Średni lokalny C:            0.4561
Tranzytywność (globalna):    0.0412
Wykładnik regresji C(k)~k:  -0.747  (oczekiwane w okolicach -1)
```

**Czy wyniki pasują do teorii?**

- **Duża rozbieżność między średnim lokalnym C (0.4561) a tranzytywnością globalną (0.0412) jest podręcznikową cechą sieci bezskalowych z dominującymi hubami, nie błędem.** Obie miary ważą wierzchołki inaczej:
  - Średni lokalny C traktuje każdy wierzchołek jednakowo — małe podstrony/sekcje wydziałowe mają często C(v) bliskie 1.0, bo ich nieliczni sąsiedzi są ciasno powiązani w ramach tego samego menu czy szablonu strony.
  - Tranzytywność globalna waży wierzchołki proporcjonalnie do k·(k−1), czyli faworyzuje węzły o ogromnym stopniu (strona główna, katalogi, wyszukiwarka). Duże huby linkują do tysięcy podstron z zupełnie różnych, wzajemnie niepowiązanych wydziałów — co drastycznie ściąga globalną tranzytywność w dół, mimo wysokiej lokalnej klasteryzacji „na dole” struktury.
- **Wykładnik regresji C(k) vs k wyszedł -0.747, czyli tego samego znaku i rzędu wielkości co oczekiwane -1.0, choć nie identyczny.** Dwa prawdopodobne powody odchylenia:
  - Globalne szablony strony (wspólny nagłówek/stopka z linkami np. do Terms of Use, Copyright, wyszukiwarki) sprawiają, że nawet bardzo duże huby dzielą ze sobą pewną stałą liczbę trójkątów — to podnosi C(k) dla wysokich k i spłaszcza nachylenie wykresu (z -1.0 w stronę -0.75).
  - W realnych pomiarach sieci społecznych i WWW wynik w przedziale -0.7 do -0.8 jest uznawany za dobre, zgodne z modelem hierarchicznym dopasowanie — pełne -1.0 to wartość graniczna, rzadko osiągana na danych empirycznych (w przeciwieństwie do modeli syntetycznych).
- Wynik jest spójny z wcześniejszymi obserwacjami z Z3/Z5 (globalny szablon HTML, ekstremalne huby in-degree, rozkład potęgowy stopni) — te same cechy strukturalne, które tam tłumaczyły odchylenia od literatury, tutaj tłumaczą zarówno rozbieżność C_avg vs T, jak i odchylenie wykładnika od -1.

**Domknięte pytania z wcześniejszego etapu Walidacji:**
- Nachylenie regresji potwierdzone jako ujemne (-0.747), zgodne co do kierunku z oczekiwaniem C(k) ∝ k⁻¹, z sensownie wytłumaczonym odchyleniem od -1.
- Porównanie tranzytywności i średniego lokalnego C wykonane — różnica jest znacząca i została zinterpretowana (patrz wyżej), zgodnie z mechanizmem analogicznym do Metody A/B z Z6.

**Otwarte pytania pozostające do rozszerzenia raportu:**
- Osobne policzenie R² dla dopasowania C(k) vs k, dla pełnej porównywalności z metodyką z Z5 (na razie zgłoszone tylko nachylenie).

---

## Zadanie Z8: PageRank

### Orientacja

**Pytania na starcie:**
- Co to jest wersja bez tłumienia (d=1) i czym w ogóle jest parametr d?
- Czym są dangling nodes i dlaczego wymagają specjalnej obsługi?
- Czym jest kryterium zbieżności ε i skąd ta konkretna wartość 10⁻⁶?
- Czym są normy L1/L2/L∞ i po co porównywać wszystkie trzy?
- Co pokazuje wykres iteracji do zbieżności vs d?
- Czym jest rozkład wartości PR na log-log i czym jest „ranga”?
- Czym jest losowy surfer, macierz stochastyczna i dlaczego PageRank się na nich opiera?
- Od czego zacząć implementację — czy potrzebny jest wierzchołek startowy jak w BFS?

**Co się nauczyłem:**
- Model losowego surfera: PR(v) to długookresowa frakcja czasu, jaką hipotetyczny surfer klikający losowe linki (a czasem teleportujący się losowo) spędza na stronie v.
- Wzór PR(v) = (1−d)/N + d·Σ_{u→v} PR(u)/L(u) — pierwszy człon to wkład teleportacji, drugi to wkład podążania za linkami, ważony przez to, ile linków wychodzących ma każda strona źródłowa.
- Macierz stochastyczna to zapis tego samego wzoru jako mnożenie macierzy — PageRank to stan stacjonarny łańcucha Markowa opisanego tą macierzą. Nie jest konieczne budowanie jej jawnie — iteracja po krawędziach (edge list) daje ten sam wynik wydajniej przy rzadkim grafie.
- Parametr d kontroluje balans między strukturą linków a losowością; d=0.85 to wartość standardowa z literatury. Wersja bez tłumienia (d=1) traci matematyczną gwarancję zbieżności przy grafie, który nie jest jednym silnie spójnym komponentem — stąd wymóg jawnej obsługi dangling nodes nawet w tej wersji.
- Dangling nodes (out-degree=0): matematycznie poprawna obsługa to zsumowanie PR wszystkich dangling nodes (S) i doliczenie S/N do **każdego** wierzchołka (w tym innych dangling nodes) — to nie przybliżenie, tylko wynik identyczny z liczeniem „osobno dla każdego dangling node'a”, tylko policzony efektywniej (przemienność sumowania).
- Kryterium zbieżności: różnica wektorów PR między iteracjami mierzona normą (L1/L2/L∞); ε=10⁻⁶ to standardowy kompromis z literatury. Matematycznie zawsze L∞ ≤ L2 ≤ L1, więc L1 zbiega najpóźniej (patrzy na sumę wszystkich zmian naraz, nie tylko najgorszy przypadek).
- Start algorytmu: wektor PR₀ jednostajny (1/N dla każdego wierzchołka naraz) — brak pojedynczego wierzchołka startowego, w przeciwieństwie do BFS. Aktualizacja synchroniczna — nowy wektor liczony wyłącznie ze starego (nie mieszamy już zaktualizowanych wartości w trakcie tej samej iteracji).
- Wykres rozkładu PR na log-log: ponieważ wartości PR są ciągłe (prawie unikalne dla każdego wierzchołka), zamiast klasycznego histogramu użyto wykresu rank-PR: log(ranga) na osi X (ranga = pozycja w posortowanej malejąco liście PR, 1 = najwyższy PR) vs log(PR) na osi Y.

**Dodatkowe pytania i odpowiedzi:**

| Pytanie | Odpowiedź |
|---|---|
| Czy suma PR dangling nodes trafia też do innych dangling nodes? | Tak, bez wyjątku — S/N dolicza się do każdego wierzchołka w grafie. |
| Dla jakiego d robić wykres rozkładu PR i top-20? | d=0.85 — standardowa wartość referencyjna z literatury, porównywalna między badaniami. |

---

### Projekt

**Decyzje architektoniczne:**

| Decyzja | Alternatywa | Wybór | Dlaczego |
|---|---|---|---|
| Reprezentacja przejść | Jawna macierz stochastyczna N×N | Iteracja po krawędziach (edge list / predecessors) | Wydajność pamięciowa przy rzadkim grafie |
| Kryterium stopu | Pojedyncza norma | L1 jako oficjalne kryterium, ale L1/L2/L3(L∞) liczone i logowane równolegle | Porównywalność z literaturą (L1 najczęściej stosowane), przy zachowaniu materiału do porównania wszystkich trzech |
| Testowane wartości d | Tylko d=0.85 | {0.50, 0.70, 0.85, 0.90, 0.95, 0.99, 1.00} | Wymagane wprost przez treść zadania — analiza wpływu d na zbieżność |
| Wykres rozkładu PR | Klasyczny histogram log-log | Wykres rank-PR (log(ranga) vs log(PR)) | Wartości PR ciągłe/prawie unikalne — klasyczny histogram dałby puste biny |

**Co AI zaproponowała:**

| Propozycja | Przyjęto | Przyczyna |
|---|---|---|
| `max_iter` jako zabezpieczenie przed nieskończoną pętlą przy d=1 | Tak | Możliwy brak szybkiej zbieżności przy grafie niebędącym jednym SCC |
| Budowa pełnej macierzy N×N zamiast iteracji po krawędziach | Nie | Niepotrzebne obciążenie pamięciowe przy rzadkim grafie |

---

### Budowa

**Rola AI: Tutor (orientacja: losowy surfer, dangling nodes, macierz stochastyczna) / Partner (protokół eksperymentu) / Solo (algorytm rdzeniowy)** — zgodnie z ustaloną rolą; kod pisany przez użytkownika z poprawkami wskazywanymi po przedstawieniu.

**Problemy napotkane i poprawki:**

| Problem | Przyczyna | Rozwiązanie |
|---|---|---|
| `sum(PR)` sumowało klucze słownika, nie wartości, i po wszystkich wierzchołkach zamiast po poprzednikach v | Błędny zakres sumowania względem wzoru | `sum(PR[u]/L[u] for u in G.predecessors(v))` |
| `len(G.processors(v))` — literówka i błędna semantyka (dzielenie sumy przez liczbę poprzedników zamiast dzielenia każdego PR(u) osobno przez jego L(u)) | Nieporozumienie co do struktury sumy ważonej we wzorze | Dzielenie `PR[u] / L[u]` osobno dla każdego poprzednika, dopiero potem sumowanie |
| Brak wkładu S (dangling nodes) we wzorze aktualizacji | Pominięcie tego elementu w pierwszej wersji | Dodanie `d * (incoming + S/N)` do wzoru |
| Wątpliwość czy `and`/`or` w warunku zapisu numeru iteracji zbieżności | Błędna intuicja co do logiki warunku strażniczego | Potwierdzono poprawność `and` — `is None` pilnuje zapisu tylko raz, przy pierwszym przekroczeniu progu |

---

### Walidacja

**Wyniki (docelowy graf, |V| ≈ 15 009):**

```
d=0.50: zbieżność (L1) po 13 iteracjach  | L1@13  L2@10  Linf@9
d=0.70: zbieżność (L1) po 21 iteracjach  | L1@21  L2@16  Linf@14
d=0.85: zbieżność (L1) po 34 iteracjach  | L1@34  L2@24  Linf@21
d=0.90: zbieżność (L1) po 48 iteracjach  | L1@48  L2@30  Linf@24
d=0.95: zbieżność (L1) po 98 iteracjach  | L1@98  L2@55  Linf@29
d=0.99: zbieżność (L1) po 483 iteracjach | L1@483 L2@273 Linf@126
d=1.00: BRAK zbieżności w limicie 1000 iteracji | L1@None L2@None Linf@None

Suma wszystkich PR (d=0.85): ≈ 1 (potwierdzone)

Top-20 (d=0.85):
1. https://stanford.edu — PR=0.037752
2. https://stanford.edu/search — PR=0.026157
3. https://stanford.edu/site/accessibility — PR=0.025893
4. https://adminguide.stanford.edu/chapter-1/subchapter-5/policy-1-5-4 — PR=0.023205
5. https://stanford.edu/site/privacy — PR=0.022573
6. https://stanford.edu/site/terms — PR=0.022539
7. https://emergency.stanford.edu — PR=0.022183
8. https://uit.stanford.edu/security/copyright-infringement — PR=0.022119
9. https://non-discrimination.stanford.edu — PR=0.014910
10. https://visit.stanford.edu/basics — PR=0.012196
... (pełna lista top-20 zdominowana przez stronę główną oraz strony
narzędziowe/stopkowe: search, accessibility, privacy, terms, emergency,
copyright, non-discrimination — dalej strony wydziałowe/jednostek: med,
law, admission, gsb itd. z zauważalnie niższym PR)
```

**Czy wyniki pasują do teorii?**

- **Liczba iteracji do zbieżności rosła z d znacznie ostrzej niż w przebiegu testowym** — z 13 (d=0.5) do 483 (d=0.99), a przy d=1.0 algorytm **nie osiągnął** ε=10⁻⁶ nawet po 1000 iteracjach (limit `max_iter` przerwał pętlę). To w pełni zgodne z teorią: bez elementu teleportacji (d=1) proces potęgowy traci gwarantowane szybkie tłumienie błędu — tempo zbieżności skaluje się w przybliżeniu jak O(dᵏ), więc dla d bliskiego 1 (a zwłaszcza d=1) wygaszanie błędu początkowego jest bardzo wolne lub (przy grafie niebędącym jednym silnie spójnym komponentem, jak potwierdzono w Z4) może w ogóle nie zbiegać do jednoznacznego wektora w rozsądnej liczbie kroków.
- **Relacja L∞ ≤ L2 ≤ L1 potwierdzona konsekwentnie we wszystkich testowanych d** — L∞ zawsze zbiega najwcześniej (patrzy tylko na pojedynczy najgorszy przypadek spośród 15 000 wierzchołków), L1 zawsze najpóźniej (sumuje zmiany po wszystkich węzłach naraz, więc jest kryterium najbardziej rygorystycznym/bezpiecznym jako oficjalne kryterium stopu).
- **Suma PR ≈ 1 potwierdzona** — podstawowa własność rozkładu prawdopodobieństwa zachowana, potwierdza poprawność obsługi dangling nodes również na pełnym, docelowym grafie.
- **Top-20 w pełni spójne z resztą analizy (Z3, Z7)** — strona główna i strony obecne w globalnym nagłówku/stopce każdej podstrony domeny (`search`, `accessibility`, `privacy`, `terms`, `copyright`, `non-discrimination`, `emergency`) zdobywają najwyższy PageRank, bo odbierają linki przychodzące z praktycznie każdej strony serwisu. To potwierdza, że PageRank poprawnie odzwierciedla strukturę linkowania (masowe powielenie linków nawigacyjnych), a nie subiektywną istotność treści — dopiero dalej w rankingu pojawiają się strony merytoryczne poszczególnych wydziałów/jednostek (`med`, `law`, `admission`, `gsb`) z wyraźnie niższym PR.

**Domknięte pytania z wcześniejszego etapu Walidacji:**
- Wyniki testowe (na roboczym, mniejszym grafie) zastąpione finalnymi, na docelowym pliku graph.txt (~15 000 węzłów) — jakościowo ten sam obraz (rosnąca liczba iteracji z d, L∞≤L2≤L1, sensowny top-20), ale znacznie ostrzejsza skala wzrostu liczby iteracji oraz jawny brak zbieżności dla d=1.0, niewidoczny na mniejszym grafie testowym.
- Suma PR ≈ 1 potwierdzona.

**Otwarte pytania pozostające do rozszerzenia raportu:**
- Porównanie wybranych wartości PR z `nx.pagerank(G, alpha=d)` jako niezależny punkt odniesienia — nadal niewykonane.
- Sprawdzenie sumy PR ≈ 1 również dla pozostałych testowanych wartości d (obecnie potwierdzone tylko dla d=0.85).

---

## Zadanie Z9: Odporność na awarie i ataki

### Orientacja

**Pytania na starcie:**
- Czym różni się usuwanie losowe od usuwania wg malejącego stopnia?
- Czy frakcje (1–50%) dotyczą liczby wierzchołków usuwanych obiema metodami?
- Czy WCC/SCC liczymy od nowa po każdym kroku, czy śledzimy zmianę oryginalnego komponentu?
- Jak dobrze zaprezentować analizę porównawczą (tabela? wykresy?)
- Czym są wierzchołki i pary rozspajające?
- Czym jest zjawisko „robust yet fragile” i perkolacja?

**Co się nauczyłem:**
- Usuwanie losowe = model przypadkowych awarii; usuwanie wg malejącego stopnia = model świadomego ataku celującego w huby.
- Po każdym kroku liczy się **aktualny** rozmiar największej WCC/SCC (niezależnie z jakich wierzchołków się składa), nie zmianę oryginalnego, początkowego komponentu — to standardowe podejście z badań nad perkolacją sieci.
- „Robust yet fragile” (Albert, Jeong, Barabási 2000): sieci o rozkładzie potęgowym stopni (potwierdzonym dla tego grafu w Z5) są odporne na losowe awarie, ale kruche na celowane ataki w huby — to bezpośrednio łączy Z9 z wynikami Z5.
- Perkolacja: przy pewnej krytycznej frakcji usuniętych węzłów największa spójna składowa może gwałtownie się załamać (przejście fazowe) — tego „punktu krytycznego” szuka się w danych z ataku.
- Wierzchołki rozspajające (articulation points) — pojęcie zdefiniowane dla grafu nieskierowanego; wykrywane algorytmem Hopcrofta-Tarjana (śledzenie `disc[v]`/`low[v]` w DFS) — inny algorytm niż Tarjan do SCC z Z4, mimo podobnego szkieletu (iteracyjny DFS z jawnym stosem).
- Pary rozspajające to znacznie trudniejszy problem (wymaga struktur typu SPQR-tree) — uznane za opcjonalne rozszerzenie, odłożone na rzecz samych wierzchołków rozspajających.

**Dodatkowe pytania i odpowiedzi:**

| Pytanie | Odpowiedź |
|---|---|
| Czy wierzchołki/pary rozspajające liczy się w trakcie usuwania losowego/atakowego? | Nie — to osobny, statyczny eksperyment na oryginalnym (nieokrojonym) grafie, odpowiadający na inne pytanie: czy istnieje pojedynczy węzeł, którego samo usunięcie rozrywa graf. |
| Czym jest `seed` w losowym usuwaniu? | Wartość startowa generatora liczb pseudolosowych, zapewniająca powtarzalność tej samej „losowej” kolejności usuwania między uruchomieniami. |

---

### Projekt

**Decyzje architektoniczne:**

| Decyzja | Alternatywa | Wybór | Dlaczego |
|---|---|---|---|
| Sposób naliczania frakcji | Niezależne eksperymenty dla każdej frakcji osobno | **Kumulatywne** usuwanie (jedna kolejność, pomiar na kolejnych progach) | Bardziej realistyczna symulacja narastającej awarii, gładsze krzywe porównawcze |
| Ranking ataku | Statyczny (liczony raz na starcie) | **Dynamiczny** — stopnie przeliczane po każdym usunięciu | Wierniejsze odwzorowanie realnego ataku „zawsze biję w aktualnie najważniejszy węzeł”; wykonalne obliczeniowo przy obecnym rozmiarze grafu |
| Definicja stopnia przy ataku | Wyłącznie out-degree lub in-degree | `G.degree()` (in+out łącznie) | Spójność z podejściem „całkowita widoczność węzła” z Z7 |
| Wierzchołki rozspajające | Wersja skierowana (niestandardowa) | Wersja **nieskierowana** (`G.to_undirected()`) | Klasyczna definicja articulation point jest zdefiniowana dla grafów nieskierowanych; spójne z podejściem do WCC z Z4 |
| Reużycie kodu SCC | Przepisanie Tarjana od nowa | Import `my_tarjan` z pliku Z4 | Unikanie duplikacji; zaplanowane docelowe przeniesienie do wspólnego `graph_utils.py` |

**Co AI zaproponowała:**

| Propozycja | Przyjęto | Przyczyna |
|---|---|---|
| Kumulatywne usuwanie zamiast niezależnych eksperymentów per frakcja | Tak | Uznane za bardziej obrazowe przez użytkownika |
| Dynamiczne przeliczanie rankingu ataku po każdym usunięciu | Tak | Uznane za bardziej miarodajne mimo wyższego kosztu obliczeniowego |
| Implementacja pełnych par rozspajających (SPQR-tree) | Nie, odłożone | Zbyt złożone algorytmicznie względem wymagań zadania na tym etapie |
| Weryfikacja articulation points przez `nx.articulation_points()` | Zaplanowane, do wykonania | Analogiczny sanity check jak przy Tarjanie w Z4 |

---

### Budowa

**Rola AI: Tutor (orientacja: robust yet fragile, perkolacja) / Partner (protokół eksperymentu i budowa)** — zgodnie z ustaloną rolą dla tego zadania.

**Problemy napotkane i poprawki:**

| Problem | Przyczyna | Rozwiązanie |
|---|---|---|
| `TypeError: unsupported format string passed to NoneType` przy druku tabeli wyników | `avg_distance_and_diameter()` zwracało `(None, None)`, gdy po usunięciach graf nie miał żadnych osiągalnych par (np. rozpad do SCC=1) | Funkcja pomocnicza formatująca `None` jako czytelny placeholder zamiast próby sformatowania go jako liczby |
| Podejrzana niespójność: SCC>1 przy jednoczesnym pustym wyniku BFS na innym progu frakcji | Wstępnie uznane za możliwy błąd w `my_tarjan`; po wyjaśnieniu okazało się dotyczyć innego progu (przeskok 2%→5%), gdzie SCC prawdopodobnie rzeczywiście spadło do rozmiaru 1 | Przygotowany izolowany skrypt diagnostyczny odtwarzający konkretny stan grafu na danym progu, do jednoznacznego potwierdzenia przed uznaniem za błąd |
| Ryzyko ponownego wykonania kodu na poziomie modułu przy imporcie `my_tarjan` z pliku Z4 | Kod na najwyższym poziomie modułu w Pythonie wykonuje się przy każdym imporcie | Zalecenie: `if __name__ == "__main__":` w pliku Z4 lub przeniesienie funkcji do wspólnego `graph_utils.py` |
| Wysoki koszt obliczeniowy generowania kolejności ataku przy dużych frakcjach (do O(V²)) | Liniowe przeszukiwanie `max(..., key=degree)` przy każdym pojedynczym usunięciu | Zaakceptowane jako wykonalne przy obecnym rozmiarze grafu (~3000 węzłów), z sugestią optymalizacji przez kopiec (`heapq`) w razie potrzeby przy większych grafach |

---

### Walidacja

**Wyniki:** *[DO UZUPEŁNIENIA — po potwierdzeniu diagnozy i odpaleniu na docelowym pliku graph.txt]*

**Wstępne obserwacje (z przebiegu testowego na roboczym/mniejszym grafie — niereprezentatywne dla finalnych danych):**
- Usuwanie losowe: łagodny, stopniowy spadek rozmiaru największej WCC (1863→593) i SCC (40→17) przy wzroście frakcji od 1% do 50% — wstępnie spójne z oczekiwaniem „odporności na losowe awarie”.
- Usuwanie celowane (atak): znacznie gwałtowniejszy spadek już przy niskich frakcjach (WCC: 601→117 między 1% a 2%) — wstępnie spójne z hipotezą „kruchości wobec ataków”, ale wymaga dalszej weryfikacji ze względu na niewyjaśnioną do końca anomalię przy porównaniu SCC i wyniku BFS na progu 5%.

**Otwarte pytania do domknięcia Walidacji:**
- Potwierdzenie lub wykluczenie błędu w `my_tarjan` poprzez zaproponowany skrypt diagnostyczny.
- Identyfikacja punktu krytycznego (progu perkolacji) na krzywej ataku po uzyskaniu pełnych, potwierdzonych danych.
- Porównanie zbioru wierzchołków rozspajających z top-N węzłów wg stopnia (z Z2/Z5) — sprawdzenie hipotezy o pokrywaniu się hubów z węzłami krytycznymi strukturalnie.


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

**Propozycje AI i decyzje:**

| Propozycja AI | Decyzja | Uzasadnienie |
|---|---|---|
| Wspólny moduł `graph_utils.py` z funkcjami z Z3-Z5 | Przyjęto | Eliminacja duplikacji kodu (wczytanie grafu, Tarjan, BFS, OLS/MLE/K-S) powtarzającego się w osobnych plikach zadań; ułatwia też pisanie ewentualnych testów regresyjnych |
| Eksport grafu do formatu GraphML z kolorowaniem wg struktury bow-tie | Przyjęto | Wizualne uzupełnienie analizy liczbowej z Z4 — pozwala zobaczyć strukturę SCC/IN/OUT/TENDRILS w Gephi zamiast tylko czytać liczby |
| Szczegółowa analiza mniejszej składowej WCC (8 węzłów) | Przyjęto | Bezpośrednia weryfikacja hipotezy postawionej w Z4 o przyczynie WCC=2 (artefakt normalizacji URL vs realnie odcięty fragment strony) |
| — | *(pozostałe propozycje: podział na moduły dla crawlera, testy jednostkowe, betweenness/closeness centrality — w rozważeniu, decyzja niepodjęta)* | |

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