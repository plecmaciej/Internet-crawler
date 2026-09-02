import networkx as nx
import numpy as np
import matplotlib.pyplot as plt
import os

os.makedirs("graph_analysis_task8", exist_ok=True)

G = nx.read_edgelist("graph.txt", create_using=nx.DiGraph())

N = G.number_of_nodes()
nodes = list(G.nodes)

L = {v: G.out_degree(v) for v in nodes}
dangling = [v for v in nodes if L[v] == 0]

epsilon = 1e-6
max_iter = 1500


def pagerank(d, epsilon=epsilon, max_iter=max_iter):
    PR = {v: 1 / N for v in nodes}
    converged = {"L1": None, "L2": None, "Linf": None}

    for iteration in range(1, max_iter + 1):
        S = sum(PR[v] for v in dangling)

        new_PR = {}
        for v in nodes:
            incoming = sum(PR[u] / L[u] for u in G.predecessors(v))
            new_PR[v] = (1 - d) / N + d * (incoming + S / N)

        diff = np.array([new_PR[v] - PR[v] for v in nodes])
        L1 = np.sum(np.abs(diff))
        L2 = np.sqrt(np.sum(diff ** 2))
        Linf = np.max(np.abs(diff))

        if converged["L1"] is None and L1 < epsilon:
            converged["L1"] = iteration
        if converged["L2"] is None and L2 < epsilon:
            converged["L2"] = iteration
        if converged["Linf"] is None and Linf < epsilon:
            converged["Linf"] = iteration

        PR = new_PR
        # Linf ≤ L2 ≤ L1
        if L1 < epsilon:
            break

    return PR, converged, iteration


d_values = [0.50, 0.70, 0.85, 0.90, 0.95, 0.99, 1.00]  # 1.00 = wersja bez tłumienia

results = {}
for d in d_values:
    PR, converged, n_iter = pagerank(d)
    results[d] = {"PR": PR, "converged": converged, "n_iter": n_iter}
    print(f"d={d}: zbieżność po {n_iter} iteracjach (L1), L1={converged['L1']} L2={converged['L2']} Linf={converged['Linf']}")


plt.figure()
for norm_name in ["L1", "L2", "Linf"]:
    ys = [results[d]["converged"][norm_name] for d in d_values]
    plt.plot(d_values, ys, marker="o", label=norm_name)
plt.xlabel("d")
plt.ylabel("liczba iteracji do zbieżności")
plt.title("Iteracje do zbieżności vs d")
plt.legend()
plt.savefig(
    "graph_analysis_task8/pagerank_convergence_vs_d.png",
    dpi=300,
    bbox_inches="tight"
)


# --- Rozkład PR na log-log, dla d=0.85 ---
PR_085 = results[0.85]["PR"]
pr_values = np.array(sorted(PR_085.values(), reverse=True))

plt.figure()
plt.scatter(np.log(np.arange(1, len(pr_values) + 1)), np.log(pr_values), s=8)
plt.xlabel("log(ranga)")
plt.ylabel("log(PR)")
plt.title("Rozkład wartości PageRank (d=0.85), log-log")
plt.savefig(
    "graph_analysis_task8/pagerank_distribution_loglog.png",
    dpi=300,
    bbox_inches="tight"
)


# --- Top-20 pages 
top20 = sorted(PR_085.items(), key=lambda x: x[1], reverse=True)[:20]
print("\nTop-20 stron wg PageRank (d=0.85):")
for rank, (page, pr) in enumerate(top20, 1):
    print(f"{rank}. {page} — PR={pr:.6f}")


print("Suma PR wynosi: ",sum(results[0.85]["PR"].values()))