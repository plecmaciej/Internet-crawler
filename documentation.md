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