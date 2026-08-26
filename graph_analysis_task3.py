import networkx as nx
import matplotlib.pyplot as plt
import numpy as np
import os

# DiGraph - directed graph
G = nx.read_edgelist("graph_fixed.txt", create_using=nx.DiGraph())

print("|E| = ", G.number_of_edges())
print("|V| = ", G.number_of_nodes())
# Density = |E| / (|V| × (|V| - 1))
print("Density = ", nx.density(G))

in_degree = dict(G.in_degree())
out_degree = dict(G.out_degree())

avg_in_degree = sum(in_degree.values()) / G.number_of_nodes()
avg_out_degree = sum(out_degree.values()) / G.number_of_nodes()

print("Average in-degree = ", avg_in_degree)
print("Average out-degree = ", avg_out_degree)

in_values = list(in_degree.values())
out_values = list(out_degree.values())

fig, axes = plt.subplots(2, 2, figsize=(13, 10))

axes[0, 0].hist(in_values, bins=50, color='#4CAF50', edgecolor='black')
axes[0, 0].set_title("In-degree histogram (linear)")
axes[0, 0].set_xlabel("In-degree")
axes[0, 0].set_ylabel("Number of nodes")

axes[0, 1].hist(out_values, bins=50, color='#2196F3', edgecolor='black')
axes[0, 1].set_title("Out-degree histogram (linear)")
axes[0, 1].set_xlabel("Out-degree")
axes[0, 1].set_ylabel("Number of nodes")

in_bins = np.logspace(0, np.log10(max(in_values)), 30)
axes[1, 0].hist(in_values, bins=in_bins, color='#4CAF50', edgecolor='black')
axes[1, 0].set_xscale('log')
axes[1, 0].set_yscale('log')
axes[1, 0].set_title("In-degree histogram (log-log)")
axes[1, 0].set_xlabel("In-degree")
axes[1, 0].set_ylabel("Number of nodes")

out_bins = np.logspace(0, np.log10(max(out_values)), 30)
axes[1, 1].hist(out_values, bins=out_bins, color='#2196F3', edgecolor='black')
axes[1, 1].set_xscale('log')
axes[1, 1].set_yscale('log')
axes[1, 1].set_title("Out-degree histogram (log-log)")
axes[1, 1].set_xlabel("Out-degree")
axes[1, 1].set_ylabel("Number of nodes")

plt.tight_layout()
os.makedirs("graph_analysis_task3", exist_ok=True)
plt.savefig(
    "graph_analysis_task3/degree_histograms.png",
    dpi=300,
    bbox_inches="tight"
)
plt.show()


print("\n" + "=" * 40)
print("Additional analysis")
print("=" * 40)

max_in = max(in_values)
max_out = max(out_values)
in_0 = sum(1 for v in in_values if v == 0)
out_0 = sum(1 for v in out_values if v == 0)
in_1 = sum(1 for v in in_values if v == 1)
out_1 = sum(1 for v in out_values if v == 1)

print(f"Liczba wierzchołków z in-degree = 0:  {in_0}  (Tzw. źródła - nikt do nich nie linkuje)")
print(f"Liczba wierzchołków z out-degree = 0: {out_0}  (Tzw. ujścia/ślepe zaułki - nie linkują nigdzie)")
print(f"Liczba wierzchołków z in-degree = 1:  {in_1}")
print(f"Liczba wierzchołków z out-degree = 1: {out_1}")
print(f"Max z in-degree: {max_in}")
print(f"Max z out-degree: {max_out}")
print("=" * 40 + "\n")