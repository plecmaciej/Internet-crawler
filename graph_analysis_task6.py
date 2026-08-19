import networkx as nx
from collections import deque

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


all_distances = {}
eccentricity = {}
average_distance = {}
diameter = 0
radius = 0

for vertex in G.nodes:

    all_distances[vertex] = BFS(G,vertex)
    eccentricity[vertex] = max(all_distances[vertex].values())

    others = {v: d for v, d in all_distances[vertex].items() if v != vertex}
    if others:
        average_distance[vertex] = sum(others.values()) / len(others)
    else:
        average_distance[vertex] = None

diameter = max(eccentricity.values())
radius = min(eccentricity.values())

valid_means = [v for v in average_distance.values() if v is not None]

global_avg_method_a = sum(valid_means) / len(valid_means)

print(list(G.successors("https://stanford.edu")))

import numpy as np

def summarize(name, values):
    values = [v for v in values if v is not None]
    values = np.array(values, dtype=float)
    print(f"{name}: n={len(values)}, min={values.min():.3f}, max={values.max():.3f}, "
          f"mean={values.mean():.3f}, median={np.median(values):.3f}")

print(f"Średnica (diameter): {diameter}")
print(f"Promień (radius): {radius}")
summarize("Ekscentryczność", eccentricity.values())
summarize("Średnia odległość (per wierzchołek)", average_distance.values())

ecc_sorted = sorted(eccentricity.items(), key=lambda x: x[1])
print("5 wierzchołków o najmniejszej ekscentryczności:", ecc_sorted[:5])
print("5 wierzchołków o największej ekscentryczności:", ecc_sorted[-5:])

import matplotlib.pyplot as plt


pairwise = [d for u in all_distances for v, d in all_distances[u].items() if v != u]

plt.figure()
plt.hist(pairwise, bins=range(min(pairwise), max(pairwise) + 2))
plt.xlabel("odległość d(u, v)")
plt.ylabel("liczba par")
plt.title("Rozkład odległości między parami wierzchołków")
plt.savefig("hist_pairwise_distances.png")


means = [v for v in average_distance.values() if v is not None]
plt.hist(means, bins=30)

plt.xlabel("średnia odległość od wierzchołka do innych")
plt.ylabel("liczba wierzchołków")
plt.title("Rozkład średnich odległości per wierzchołek")
plt.savefig("hist_mean_distances.png")