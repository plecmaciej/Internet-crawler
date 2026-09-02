import networkx as nx
from collections import deque, Counter
import numpy as np
import matplotlib.pyplot as plt
import os

os.makedirs("graph_analysis_task6", exist_ok=True)

G = nx.read_edgelist("graph.txt", create_using=nx.DiGraph())

def BFS(graph, start):
    distances = {start: 0}
    queue = deque([start])

    while queue:
        vertex = queue.popleft()
        for neighbour in graph[vertex]:
            if neighbour not in distances:
                queue.append(neighbour)
                distances[neighbour] = distances[vertex] + 1

    return distances

eccentricity = {}
average_distance = {}
reachable_count = {}
distance_counts = Counter()

total_nodes = G.number_of_nodes()
print(f"Rozpoczynam BFS dla WSZYSTKICH {total_nodes} wierzchołków...")

for i, vertex in enumerate(G.nodes, start=1):
    if i % (max(1, total_nodes // 10)) == 0 or i == total_nodes:
        print(f"  Postęp: {i} / {total_nodes} wierzchołków ({(i / total_nodes) * 100:.1f}%)")

    dists = BFS(G, vertex)
    others = {v: d for v, d in dists.items() if v != vertex}

    reachable_count[vertex] = len(others)

    if others:
        eccentricity[vertex] = max(others.values())
        average_distance[vertex] = sum(others.values()) / len(others)
        for d in others.values():
            distance_counts[d] += 1
    else:
        eccentricity[vertex] = None
        average_distance[vertex] = None

# --- METRYKI ---
# 1. Pełne (uwzględniające węzły sięgające 1-2 podstrony)
valid_ecc = [e for e in eccentricity.values() if e is not None]
raw_diameter = max(valid_ecc)
raw_radius = min(valid_ecc)

# 2. Główna składowa (węzły sięgające > 1000 innych węzłów - realna analiza sieci)
main_component_ecc = [
    eccentricity[v] for v in G.nodes
    if eccentricity[v] is not None and reachable_count[v] > 1000
]
real_radius = min(main_component_ecc) if main_component_ecc else raw_radius

def summarize(name, values):
    values = [v for v in values if v is not None]
    values = np.array(values, dtype=float)
    print(f"{name}: n={len(values)}, min={values.min():.3f}, max={values.max():.3f}, "
          f"mean={values.mean():.3f}, median={np.median(values):.3f}")

print("\n" + "=" * 50)
print(f"Średnica (diameter):             {raw_diameter}")
print(f"Promień surowy (radius raw):     {raw_radius} (uwzględnia węzły o zasięgu 1 strony)")
print(f"Promień realiztyczny (zasięg>1k): {real_radius} (dla węzłów w głównej składowej)")
print("-" * 50)

summarize("Ekscentryczność", eccentricity.values())
summarize("Średnia odległość (per wierzchołek)", average_distance.values())

# NAPRAWIONE SORTOWANIE (pomija wartości None)
valid_ecc_items = [(node, ecc, reachable_count[node]) for node, ecc in eccentricity.items() if ecc is not None]
ecc_sorted = sorted(valid_ecc_items, key=lambda x: x[1])

print("\n5 wierzchołków o najmniejszej ekscentryczności [URL, ekscentryczność, liczba osiągalnych]:")
for item in ecc_sorted[:5]:
    print(f"  {item[0]} -> ecc={item[1]}, zasięg={item[2]} węzłów")

print("\n5 wierzchołków o największej ekscentryczności [URL, ekscentryczność, liczba osiągalnych]:")
for item in ecc_sorted[-5:]:
    print(f"  {item[0]} -> ecc={item[1]}, zasięg={item[2]} węzłów")
print("=" * 50 + "\n")

# --- WYKRES 1: ROZKŁAD ODLEGŁOŚCI DLA PAR ---
plt.figure(figsize=(8, 5))
distances = sorted(distance_counts.keys())
counts = [distance_counts[d] for d in distances]

plt.bar(distances, counts, color='#2196F3', edgecolor='black', width=0.8)
plt.xlabel("Odległość d(u, v)")
plt.ylabel("Liczba par")
plt.title("Rozkład odległości między parami wierzchołków")
plt.grid(axis='y', linestyle='--', alpha=0.7)
plt.tight_layout()
plt.savefig("graph_analysis_task6/hist_pairwise_distances.png", dpi=300)
plt.close()

# --- WYKRES 2: ROZKŁAD ŚREDNICH ODLEGŁOŚCI ---
plt.figure(figsize=(8, 5))
means = [v for v in average_distance.values() if v is not None]
plt.hist(means, bins=30, color='#4CAF50', edgecolor='black')
plt.xlabel("Średnia odległość od wierzchołka do innych")
plt.ylabel("Liczba wierzchołków")
plt.title("Rozkład średnich odległości per wierzchołek")
plt.grid(axis='y', linestyle='--', alpha=0.7)
plt.tight_layout()
plt.savefig("graph_analysis_task6/hist_mean_distances.png", dpi=300)
plt.close()

print("✅ Gotowe!")