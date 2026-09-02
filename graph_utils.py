"""
graph_utils.py

Wspolny modul z funkcjami uzywanymi w zadaniach Z3-Z6 projektu analizy grafu crawlingu.
Zebrane tu funkcje byly niezaleznie zwalidowane (m.in. wzgledem networkx) w toku
poszczegolnych zadan - patrz dokumentacja Z3/Z4/Z5.
"""

import networkx as nx
import numpy as np
from collections import deque, Counter


# ============================================================
# Wczytywanie grafu
# ============================================================

def load_graph(path="graph.txt"):
    """Wczytuje graf skierowany z pliku edgelist (format zapisywany przez crawler.py)."""
    return nx.read_edgelist(path, create_using=nx.DiGraph())


# ============================================================
# Z4: Silnie spojne skladowe (Tarjan, implementacja iteracyjna)
# ============================================================

def my_tarjan(G):
    """
    Wlasna, iteracyjna implementacja algorytmu Tarjana do wyznaczania SCC.
    Iteracyjna wersja jest konieczna, bo Python ma limit rekursji ~1000,
    co przy grafie tysiecy wezlow wywalaloby sie na RecursionError.
    Zwalidowana wzgledem nx.strongly_connected_components (patrz dokumentacja Z4).
    """
    counter = 0
    index = {}
    lowlink = {}
    on_stack = set()
    S = []
    wynik = []

    for start in G.nodes():
        if start in index:
            continue

        index[start] = counter
        lowlink[start] = counter
        counter += 1
        S.append(start)
        on_stack.add(start)

        call_stack = [(start, iter(G.successors(start)))]

        while call_stack:
            v, neighbors_iter = call_stack[-1]

            advanced = False
            for w in neighbors_iter:
                if w not in index:
                    index[w] = counter
                    lowlink[w] = counter
                    counter += 1
                    S.append(w)
                    on_stack.add(w)
                    call_stack.append((w, iter(G.successors(w))))
                    advanced = True
                    break
                elif w in on_stack:
                    lowlink[v] = min(lowlink[v], index[w])

            if not advanced:
                call_stack.pop()
                if call_stack:
                    parent, _ = call_stack[-1]
                    lowlink[parent] = min(lowlink[parent], lowlink[v])

                if lowlink[v] == index[v]:
                    nowa_scc = []
                    while S[-1] != v:
                        element = S.pop()
                        nowa_scc.append(element)
                        on_stack.remove(element)
                    last = S.pop()
                    nowa_scc.append(last)
                    on_stack.remove(last)
                    wynik.append(nowa_scc)

    return wynik


# ============================================================
# Z4: BFS pomocnicze do struktury bow-tie
# ============================================================

def bfs_forward(G, sources):
    """BFS 'do przodu' po krawedziach wychodzacych (G.successors)."""
    visited = set(sources)
    queue = deque(sources)
    while queue:
        v = queue.popleft()
        for w in G.successors(v):
            if w not in visited:
                visited.add(w)
                queue.append(w)
    return visited


def bfs_backward(G, sources):
    """BFS 'do tylu' po krawedziach przychodzacych (G.predecessors)."""
    visited = set(sources)
    queue = deque(sources)
    while queue:
        v = queue.popleft()
        for w in G.predecessors(v):
            if w not in visited:
                visited.add(w)
                queue.append(w)
    return visited


def classify_bowtie(G, scc_list):
    """
    Klasyfikuje wezly grafu na strefy struktury bow-tie: SCC, IN, OUT, TENDRILS, DISCONNECTED.
    scc_list: lista list/zbiorow wezlow, kazda jedna SCC (np. wynik my_tarjan(G) lub
    nx.strongly_connected_components(G)).
    """
    largest_scc = max(scc_list, key=len)
    SCC_set = set(largest_scc)

    forward_reachable = bfs_forward(G, SCC_set)
    backward_reachable = bfs_backward(G, SCC_set)

    OUT_set = forward_reachable - SCC_set
    IN_set = backward_reachable - SCC_set

    all_nodes = set(G.nodes())
    remaining = all_nodes - SCC_set - IN_set - OUT_set

    tendrils_from_in = bfs_forward(G, IN_set) & remaining
    tendrils_to_out = bfs_backward(G, OUT_set) & remaining
    TENDRILS_set = tendrils_from_in | tendrils_to_out
    DISCONNECTED_set = remaining - TENDRILS_set

    return {
        'SCC': SCC_set,
        'IN': IN_set,
        'OUT': OUT_set,
        'TENDRILS': TENDRILS_set,
        'DISCONNECTED': DISCONNECTED_set,
        'tendrils_from_in': tendrils_from_in,
        'tendrils_to_out': tendrils_to_out,
    }


# ============================================================
# Z5: Rozklad P(k), dopasowanie OLS
# ============================================================

def build_P_k(values, N):
    """
    Buduje rozklad P(k) = liczba wezlow o stopniu k / N (liczba WSZYSTKICH wezlow w grafie).
    Odfiltrowuje k=0 (log(0) niezdefiniowany).
    """
    counts = Counter(values)
    k_values = sorted(counts.keys())
    k_values = [k for k in k_values if k > 0]
    P_values = [counts[k] / N for k in k_values]
    return np.array(k_values, dtype=float), np.array(P_values, dtype=float)


def ols_fit(log_k, log_P):
    """Regresja liniowa metoda najmniejszych kwadratow na (log_k, log_P). Zwraca (a, b)."""
    n = len(log_k)
    sum_x = np.sum(log_k)
    sum_y = np.sum(log_P)
    sum_xy = np.sum(log_k * log_P)
    sum_x2 = np.sum(log_k ** 2)

    a = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x ** 2)
    b = (sum_y - a * sum_x) / n
    return a, b


def r_squared(log_k, log_P, a, b):
    """Wspolczynnik determinacji R^2 dla dopasowania OLS."""
    y_pred = a * log_k + b
    y_mean = np.mean(log_P)
    ss_res = np.sum((log_P - y_pred) ** 2)
    ss_tot = np.sum((log_P - y_mean) ** 2)
    return 1 - ss_res / ss_tot


# ============================================================
# Z5: MLE (Clauset-Shalizi-Newman) i test K-S
# ============================================================

def compute_mle_gamma(raw_values, k_min=1):
    """
    Estymator MLE wykladnika prawa potegowego dla danych dyskretnych.
    gamma_hat = 1 + n * [ sum_i ln(k_i / (k_min - 0.5)) ]^-1
    WAZNE: raw_values musi byc surowa lista stopni PER WEZEL (z duplikatami),
    nie lista unikalnych wartosci z histogramu OLS - patrz dokumentacja Z5.
    Zwraca (gamma, n, filtered_k) - filtered_k potrzebne pozniej do testu K-S.
    """
    filtered_k = [k for k in raw_values if k >= k_min]
    n = len(filtered_k)

    if n == 0:
        return None, 0, filtered_k

    S = sum(np.log(k / (k_min - 0.5)) for k in filtered_k)
    gamma = 1 + n / S

    return gamma, n, filtered_k


def calculate_ks_stat(filtered_k, k_min, gamma):
    """
    Statystyka testu Kolmogorowa-Smirnowa: D = max_k |S(k) - P(k)|
    S(k) - dystrybuanta empiryczna, P(k) - dystrybuanta teoretyczna rozkladu
    potegowego P(k) ~ k^(-gamma), znormalizowana na obserwowanym zakresie.
    D bliskie 0 -> dobre dopasowanie; wyzsze D -> odstepstwo od modelu.
    """
    filtered_k = np.array(filtered_k)
    n = len(filtered_k)
    k_max = np.max(filtered_k)

    k_range = np.arange(k_min, k_max + 1)

    pmf_theory = k_range.astype(float) ** (-gamma)
    pmf_theory /= np.sum(pmf_theory)
    cdf_theory = np.cumsum(pmf_theory)

    counts = Counter(filtered_k)
    pmf_empirical = np.array([counts.get(k, 0) for k in k_range], dtype=float) / n
    cdf_empirical = np.cumsum(pmf_empirical)

    D = np.max(np.abs(cdf_empirical - cdf_theory))
    return D
