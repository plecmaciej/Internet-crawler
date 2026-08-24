import networkx as nx
import numpy as np
import random
from collections import deque
import matplotlib.pyplot as plt

from graph_analysis_task4 import my_tarjan  # SCC

G_original = nx.read_edgelist("graph.txt", create_using=nx.DiGraph())
N = G_original.number_of_nodes()

fractions = [0.01, 0.02, 0.05, 0.10, 0.20, 0.30, 0.50]


# --- Metryki liczone po każdym progu ---

def largest_scc_size(G):
    sccs = my_tarjan(G)
    return max(len(c) for c in sccs) if sccs else 0


def largest_wcc_size(G):
    ccs = list(nx.weakly_connected_components(G))
    return max(len(c) for c in ccs) if ccs else 0


def bfs(graph, start):
    distances = {start: 0}
    queue = deque([start])
    while queue:
        vertex = queue.popleft()
        for neighbour in graph[vertex]:
            if neighbour not in distances:
                queue.append(neighbour)
                distances[neighbour] = distances[vertex] + 1
    return distances


def avg_distance_and_diameter(G):
    all_pairs = []
    eccentricities = []
    for v in G.nodes:
        dist = bfs(G, v)
        others = [d for u, d in dist.items() if u != v]
        if others:
            all_pairs.extend(others)
            eccentricities.append(max(others))
    if not all_pairs:
        return None, None
    return sum(all_pairs) / len(all_pairs), max(eccentricities)


# --- Generowanie kolejności usuwania ---

def random_removal_order(G, seed=42):
    nodes = list(G.nodes())
    rng = random.Random(seed)
    rng.shuffle(nodes)
    return nodes


def attack_removal_order(G, max_count):
    G_work = G.copy()
    order = []
    for _ in range(max_count):
        node = max(G_work.nodes(), key=lambda v: G_work.degree(v))
        order.append(node)
        G_work.remove_node(node)
    return order


# --- Eksperyment kumulatywny: usuwanie wg gotowej kolejności, pomiar na progach ---

def run_experiment(G, order, fractions, N):
    results = []
    removed_so_far = 0
    G_work = G.copy()

    for frac in fractions:
        target = int(round(frac * N))
        to_remove_now = order[removed_so_far:target]
        G_work.remove_nodes_from(to_remove_now)
        removed_so_far = target

        avg_dist, diameter = avg_distance_and_diameter(G_work)

        results.append({
            "frac": frac,
            "n_removed": removed_so_far,
            "largest_wcc": largest_wcc_size(G_work),
            "largest_scc": largest_scc_size(G_work),
            "avg_distance": avg_dist,
            "diameter": diameter,
        })

    return results


max_to_remove = int(round(max(fractions) * N))

random_order = random_removal_order(G_original)
attack_order = attack_removal_order(G_original, max_to_remove)

results_random = run_experiment(G_original, random_order, fractions, N)
results_attack = run_experiment(G_original, attack_order, fractions, N)

def fmt(x, spec):
    return format(x, spec) if x is not None else "   —"

print(f"{'frakcja':>8} | {'metoda':>7} | {'WCC':>6} | {'SCC':>6} | {'śr.odl.':>8} | {'średnica':>8}")
for r in results_random:
    print(f"{r['frac']:>8.0%} | {'losowe':>7} | {r['largest_wcc']:>6} | {r['largest_scc']:>6} | "
          f"{r['avg_distance']:>8.3f} | {r['diameter']:>8}")
for r in results_attack:
    print(f"{r['frac']:>8.0%} | {'atak':>7} | {r['largest_wcc']:>6} | {r['largest_scc']:>6} | "
          f"{fmt(r['avg_distance'], '8.3f')} | {fmt(r['diameter'], '8')}")

def comparison_plot(metric_key, ylabel, title, filename):
    x = [r["frac"] for r in results_random]
    y_random = [r[metric_key] for r in results_random]
    y_attack = [r[metric_key] for r in results_attack]

    plt.figure()
    plt.plot(x, y_random, marker="o", label="losowe (awarie)")
    plt.plot(x, y_attack, marker="o", label="wg stopnia (ataki)")
    plt.xlabel("frakcja usuniętych wierzchołków")
    plt.ylabel(ylabel)
    plt.title(title)
    plt.legend()
    plt.savefig(filename)


comparison_plot("largest_wcc", "rozmiar największej WCC", "Największa WCC vs frakcja usunięć", "robustness_wcc.png")
comparison_plot("largest_scc", "rozmiar największej SCC", "Największa SCC vs frakcja usunięć", "robustness_scc.png")
comparison_plot("avg_distance", "średnia odległość", "Średnia odległość vs frakcja usunięć", "robustness_avg_dist.png")
comparison_plot("diameter", "średnica", "Średnica vs frakcja usunięć", "robustness_diameter.png")