import networkx as nx
import numpy as np
from collections import defaultdict
import matplotlib.pyplot as plt

G = nx.read_edgelist("graph.txt", create_using=nx.DiGraph())

def find_C(graph, vertex):
    neighbours = set(graph.successors(vertex)) | set(graph.predecessors(vertex))
    neighbours.discard(vertex)
    k_v = len(neighbours)
    if k_v < 2:
        return 0.0, 0, k_v  # C, e_v, k_v

    e_v = 0
    for j in neighbours:
        for k in graph.successors(j):
            if k in neighbours:
                e_v += 1

    C = e_v / (k_v * (k_v - 1))
    return C, e_v, k_v


C_v = {}
e_v_dict = {}
k_v_dict = {}

for vertex in G:
    C, e_v, k_v = find_C(G, vertex)
    C_v[vertex] = C
    e_v_dict[vertex] = e_v
    k_v_dict[vertex] = k_v

# --- Globalne miary ---
average_local = sum(C_v.values()) / len(C_v)
transitivity = sum(e_v_dict.values()) / sum(k * (k - 1) for k in k_v_dict.values())

print(f"Średni lokalny C: {average_local:.4f}")
print(f"Tranzytywność (globalna): {transitivity:.4f}")

# --- Histogram C(v) ---
plt.figure()
plt.hist(list(C_v.values()), bins=30)
plt.xlabel("C(v)")
plt.ylabel("liczba wierzchołków")
plt.title("Rozkład lokalnego współczynnika klasteryzacji")
plt.savefig("hist_clustering.png")

# --- C(k) vs k ---
degree_to_C = defaultdict(list)
for v in G.nodes:
    degree_to_C[k_v_dict[v]].append(C_v[v])

C_k = {k: np.mean(vals) for k, vals in degree_to_C.items()}

ks = np.array(sorted(C_k.keys()))
Cs = np.array([C_k[k] for k in ks])

# log(0) nie istnieje — odrzucamy k=0 i C(k)=0
mask = (ks > 0) & (Cs > 0)
log_k = np.log(ks[mask])
log_C = np.log(Cs[mask])

slope, intercept = np.polyfit(log_k, log_C, 1)
print(f"Wykładnik regresji: {slope:.3f} (oczekiwane w okolicach -1)")

plt.figure()
plt.scatter(log_k, log_C, s=10, label="C(k)")
plt.plot(log_k, slope * log_k + intercept, color="red", label=f"dopasowanie, nachylenie={slope:.2f}")
plt.xlabel("log(k)")
plt.ylabel("log(C(k))")
plt.title("C(k) vs k (log-log)")
plt.legend()
plt.savefig("clustering_vs_degree.png")