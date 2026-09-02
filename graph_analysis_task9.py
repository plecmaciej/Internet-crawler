import networkx as nx
import numpy as np
import random
from collections import deque
import matplotlib.pyplot as plt
import os

os.makedirs("graph_analysis_task9", exist_ok=True)

G_original = nx.read_edgelist("graph.txt", create_using=nx.DiGraph())
N = G_original.number_of_nodes()

fractions = [0.01, 0.02, 0.05, 0.10, 0.20, 0.30, 0.50]

# --- 1. WIERZCHOŁKI ROZSPAJĄCE (Hopcroft-Tarjan / Articulation Points) ---
print("🔍 Szukanie wierzchołków rozspajających (Hopcroft-Tarjan)...")
G_undirected = G_original.to_undirected()
articulation_points = list(nx.articulation_points(G_undirected))
print(f"Liczba wierzchołków rozspajających w grafie nieskierowanym: {len(articulation_points)}")
if articulation_points:
    print(f"Przykładowe punkty artykulacji: {articulation_points[:5]}\n")


# --- METRYKI ---

def largest_scc_size(G):
    if len(G) == 0:
        return 0
    sccs = list(nx.strongly_connected_components(G))
    return max(len(c) for c in sccs) if sccs else 0


def largest_wcc_size(G):
    if len(G) == 0:
        return 0
    ccs = list(nx.weakly_connected_components(G))
    return max(len(c) for c in ccs) if ccs else 0


def bfs(graph, start):
    distances = {start: 0}
    queue = deque([start])
    while queue:
        vertex = queue.popleft()
        d_next = distances[vertex] + 1
        for neighbour in graph[vertex]:
            if neighbour not in distances:
                distances[neighbour] = d_next
                queue.append(neighbour)
    return distances


def avg_distance_and_diameter_FULL(G, step_label=""):
    """
    Oblicza średnią odległość i średnicę dla WSZYSTKICH wierzchołków w grafie (bez próbkowania).
    Wyświetla bieżący postęp wewnątrz pętli BFS.
    """
    nodes = list(G.nodes())
    total_v = len(nodes)
    if total_v == 0:
        return None, None

    all_pairs_sum = 0
    all_pairs_count = 0
    max_eccentricity = 0

    # Częstotliwość wypisywania postępu (co 10% wierzchołków)
    log_interval = max(1, total_v // 10)

    for i, v in enumerate(nodes, start=1):
        if i % log_interval == 0 or i == total_v:
            pct = (i / total_v) * 100
            print(f"   [{step_label}] BFS dla wierzchołków: {i}/{total_v} ({pct:.1f}%)", end="\r", flush=True)

        dists = bfs(G, v)
        others = [d for u, d in dists.items() if u != v]

        if others:
            all_pairs_sum += sum(others)
            all_pairs_count += len(others)
            local_max = max(others)
            if local_max > max_eccentricity:
                max_eccentricity = local_max

    print()  # przejście do nowej linii po zakończeniu BFS dla całego grafu

    if all_pairs_count == 0:
        return None, None

    return all_pairs_sum / all_pairs_count, max_eccentricity


# --- KOLEJNOŚĆ USUWANIA ---

def random_removal_order(G, seed=42):
    nodes = list(G.nodes())
    rng = random.Random(seed)
    rng.shuffle(nodes)
    return nodes


def attack_removal_order(G, max_count):
    print("⚔️ Generowanie kolejności ataku (po malejącym stopniu)...")
    G_work = G.copy()
    order = []
    for step in range(max_count):
        if step % 2000 == 0 and step > 0:
            print(f"  Wyznaczono {step}/{max_count} wierzchołków do ataku...")
        node = max(G_work.nodes(), key=lambda v: G_work.degree(v))
        order.append(node)
        G_work.remove_node(node)
    print("  Kolejność ataku gotowa.\n")
    return order


# --- EKSPERYMENT ---

def run_experiment(G, order, fractions, N, exp_name=""):
    results = []
    removed_so_far = 0
    G_work = G.copy()

    total_steps = len(fractions)
    for idx, frac in enumerate(fractions, 1):
        target = int(round(frac * N))
        to_remove_now = order[removed_so_far:target]
        G_work.remove_nodes_from(to_remove_now)
        removed_so_far = target

        step_tag = f"{exp_name} {frac:.0%}"
        print(
            f"\n▶ [{exp_name}] Krok {idx}/{total_steps}: Frakcja usunięta = {frac:.0%} ({removed_so_far}/{N} wierzchołków)")

        wcc = largest_wcc_size(G_work)
        scc = largest_scc_size(G_work)
        print(f"   WCC={wcc}, SCC={scc}. Rozpoczynam pełny BFS dla wszystkich {len(G_work)} wierzchołków...")

        avg_dist, diameter = avg_distance_and_diameter_FULL(G_work, step_label=step_tag)

        degrees = [d for n, d in G_work.degree()]

        results.append({
            "frac": frac,
            "n_removed": removed_so_far,
            "largest_wcc": wcc,
            "largest_scc": scc,
            "avg_distance": avg_dist,
            "diameter": diameter,
            "mean_degree": np.mean(degrees) if degrees else 0,
            "degrees": degrees
        })

    return results


# Przebieg eksperymentu
max_to_remove = int(round(max(fractions) * N))

random_order = random_removal_order(G_original)
attack_order = attack_removal_order(G_original, max_to_remove)

print("🚀 Rozpoczynam symulację uszkodzeń losowych (Awarie) - PEŁNE OBLICZENIA...")
results_random = run_experiment(G_original, random_order, fractions, N, exp_name="Awarie")

print("\n🚀 Rozpoczynam symulację uszkodzeń celowanych (Ataki) - PEŁNE OBLICZENIA...")
results_attack = run_experiment(G_original, attack_order, fractions, N, exp_name="Ataki")


# --- TABELA WYNIKÓW ---

def fmt(x, spec):
    return format(x, spec) if x is not None else "   —"


print("\n" + "=" * 75)
print(
    f"{'frakcja':>8} | {'metoda':>7} | {'WCC':>6} | {'SCC':>6} | {'śr.odl.':>8} | {'średnica':>8} | {'śr.stopień':>10}")
print("=" * 75)
for r in results_random:
    print(f"{r['frac']:>8.0%} | {'losowe':>7} | {r['largest_wcc']:>6} | {r['largest_scc']:>6} | "
          f"{fmt(r['avg_distance'], '8.3f')} | {fmt(r['diameter'], '8')} | {r['mean_degree']:>10.2f}")
print("-" * 75)
for r in results_attack:
    print(f"{r['frac']:>8.0%} | {'atak':>7} | {r['largest_wcc']:>6} | {r['largest_scc']:>6} | "
          f"{fmt(r['avg_distance'], '8.3f')} | {fmt(r['diameter'], '8')} | {r['mean_degree']:>10.2f}")
print("=" * 75 + "\n")


# --- GENEROWANIE WYKRESÓW PORÓWNAWCZYCH ---

def comparison_plot(metric_key, ylabel, title, filename):
    x = [r["frac"] for r in results_random]
    y_random = [r[metric_key] for r in results_random]
    y_attack = [r[metric_key] for r in results_attack]

    plt.figure(figsize=(7, 5))
    plt.plot(x, y_random, marker="o", label="losowe (awarie)", color='#1f77b4')
    plt.plot(x, y_attack, marker="s", label="wg stopnia (ataki)", color='#d62728')
    plt.xlabel("frakcja usuniętych wierzchołków")
    plt.ylabel(ylabel)
    plt.title(title)
    plt.grid(True, linestyle="--", alpha=0.6)
    plt.legend()
    plt.tight_layout()
    plt.savefig(filename, dpi=300)
    plt.close()


comparison_plot("largest_wcc", "rozmiar największej WCC", "Największa WCC vs frakcja usunięć",
                "graph_analysis_task9/robustness_wcc.png")
comparison_plot("largest_scc", "rozmiar największej SCC", "Największa SCC vs frakcja usunięć",
                "graph_analysis_task9/robustness_scc.png")
comparison_plot("avg_distance", "średnia odległość", "Średnia odległość vs frakcja usunięć",
                "graph_analysis_task9/robustness_avg_dist.png")
comparison_plot("diameter", "średnica", "Średnica vs frakcja usunięć", "graph_analysis_task9/robustness_diameter.png")
comparison_plot("mean_degree", "średni stopień wierzchołka", "Średni stopień vs frakcja usunięć",
                "graph_analysis_task9/robustness_mean_degree.png")

print("✅ Wszystkie obliczenia dla 100% wierzchołków zakończone! Wykresy i dane zapisane w 'graph_analysis_task9/'.")