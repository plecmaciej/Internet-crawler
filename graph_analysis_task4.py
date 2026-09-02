import networkx as nx
import matplotlib.pyplot as plt
import numpy as np
from collections import deque
import os


def my_tarjan(G):
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
        on_stack.add(start) # on stack gives quick information about Stack S

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


def bfs_forward(G, sources):
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
    visited = set(sources)
    queue = deque(sources)

    while queue:
        v = queue.popleft()

        for w in G.predecessors(v):
            if w not in visited:
                visited.add(w)
                queue.append(w)

    return visited


def main():
    os.makedirs("graph_analysis_task4", exist_ok=True)
    print("=" * 70)
    print("ANALIZA GRAFU Z PLIKU graph.txt")
    print("=" * 70 + "\n")

    G = nx.read_edgelist(
        "graph.txt",
        create_using=nx.DiGraph()
    )

    print("|V| =", G.number_of_nodes())
    print("|E| =", G.number_of_edges())

    # --------------------------------------------------
    # WCC
    # --------------------------------------------------

    wcc = list(nx.weakly_connected_components(G))
    wcc_sizes = sorted(
        [len(c) for c in wcc],
        reverse=True
    )

    print("\nLiczba WCC =", len(wcc))
    print("Rozmiary WCC (top 10) =", wcc_sizes[:10])

    # --------------------------------------------------
    # SCC
    # --------------------------------------------------

    my_scc = my_tarjan(G)
    nx_scc = list(nx.strongly_connected_components(G))

    my_scc_sorted = sorted(
        [frozenset(s) for s in my_scc],
        key=lambda x: (len(x), sorted(x))
    )

    nx_scc_sorted = sorted(
        [frozenset(s) for s in nx_scc],
        key=lambda x: (len(x), sorted(x))
    )

    print("\nLiczba SCC (moje) =", len(my_scc_sorted))
    print("Liczba SCC (nx)   =", len(nx_scc_sorted))

    scc_sizes = sorted(
        [len(s) for s in my_scc],
        reverse=True
    )

    print("Rozmiary SCC (top 10) =", scc_sizes[:10])

    largest_scc = max(my_scc, key=len)

    print(
        f"\nNajwieksze SCC: {len(largest_scc)} wezlow"
    )

    # --------------------------------------------------
    # IN / OUT / SCC
    # --------------------------------------------------

    forward_reachable = bfs_forward(
        G,
        largest_scc
    )

    backward_reachable = bfs_backward(
        G,
        largest_scc
    )

    SCC_set = set(largest_scc)

    OUT_set = forward_reachable - SCC_set
    IN_set = backward_reachable - SCC_set

    all_nodes = set(G.nodes())

    remaining = (
        all_nodes
        - SCC_set
        - IN_set
        - OUT_set
    )

    print(
        "\n|SCC| =",
        len(SCC_set),
        f"({100 * len(SCC_set) / len(all_nodes):.1f}%)"
    )

    print(
        "|IN|  =",
        len(IN_set),
        f"({100 * len(IN_set) / len(all_nodes):.1f}%)"
    )

    print(
        "|OUT| =",
        len(OUT_set),
        f"({100 * len(OUT_set) / len(all_nodes):.1f}%)"
    )

    print(
        "|pozostale (do sklasyfikowania: "
        "TENDRILS/DISCONNECTED)| =",
        len(remaining),
        f"({100 * len(remaining) / len(all_nodes):.1f}%)"
    )

    # --------------------------------------------------
    # TENDRILS / DISCONNECTED
    # --------------------------------------------------

    tendrils_from_in = (
        bfs_forward(G, IN_set)
        & remaining
    )

    tendrils_to_out = (
        bfs_backward(G, OUT_set)
        & remaining
    )

    TENDRILS_set = (
        tendrils_from_in
        | tendrils_to_out
    )

    DISCONNECTED_set = (
        remaining - TENDRILS_set
    )

    print(
        "\n|TENDRILS| =",
        len(TENDRILS_set),
        f"({100 * len(TENDRILS_set) / len(all_nodes):.1f}%)"
    )

    print(
        "  z czego doczepione do IN  =",
        len(tendrils_from_in)
    )

    print(
        "  z czego doczepione do OUT =",
        len(tendrils_to_out)
    )

    print(
        "  (czesc wspolna obu typow =",
        len(tendrils_from_in & tendrils_to_out),
        ")"
    )

    print(
        "|DISCONNECTED| =",
        len(DISCONNECTED_set),
        f"({100 * len(DISCONNECTED_set) / len(all_nodes):.1f}%)"
    )

    # --------------------------------------------------
    # SANITY CHECK
    # --------------------------------------------------

    suma = (
        len(SCC_set)
        + len(IN_set)
        + len(OUT_set)
        + len(TENDRILS_set)
        + len(DISCONNECTED_set)
    )

    print(
        "\nSanity check: "
        "SCC+IN+OUT+TENDRILS+DISCONNECTED =",
        suma,
        " |V| =",
        len(all_nodes),
        " zgodnosc =",
        suma == len(all_nodes)
    )

    # --------------------------------------------------
    # ROZKLAD SCC
    # --------------------------------------------------

    print("\n" + "=" * 70)
    print("ROZKLAD ROZMIAROW SCC")
    print("=" * 70 + "\n")

    print("Liczba SCC =", len(my_scc))
    print("Rozmiary SCC (top 10) =", scc_sizes[:10])
    print(
        "Najmniejsza SCC =",
        min(scc_sizes),
        " Najwieksza SCC =",
        max(scc_sizes)
    )

    print(
        "Srednia wielkosc SCC =",
        sum(scc_sizes) / len(scc_sizes)
    )

    fig2, (ax_lin, ax_log) = plt.subplots(
        1,
        2,
        figsize=(13, 5)
    )

    ax_lin.hist(
        scc_sizes,
        bins=50,
        color='#FF9800',
        edgecolor='black'
    )

    ax_lin.set_title(
        "Rozklad rozmiarow SCC (linear)"
    )
    ax_lin.set_xlabel("Rozmiar SCC")
    ax_lin.set_ylabel("Liczba SCC")

    scc_bins = np.logspace(
        0,
        np.log10(max(scc_sizes)),
        20
    )

    ax_log.hist(
        scc_sizes,
        bins=scc_bins,
        color='#FF9800',
        edgecolor='black'
    )

    ax_log.set_xscale('log')
    ax_log.set_yscale('log')

    ax_log.set_title(
        "Rozklad rozmiarow SCC (log-log)"
    )
    ax_log.set_xlabel("Rozmiar SCC")
    ax_log.set_ylabel("Liczba SCC")

    plt.tight_layout()
    plt.savefig(
        "graph_analysis_task4/scc_size_distribution.png",
        dpi=300,
        bbox_inches='tight'
    )
    plt.show()

    # --------------------------------------------------
    # DAG KONDENSACJI
    # --------------------------------------------------

    print("\n" + "=" * 70)
    print("DAG KONDENSACJI")
    print("=" * 70 + "\n")

    scc_as_frozensets = [
        frozenset(s)
        for s in my_scc
    ]

    condensation = nx.condensation(
        G,
        scc=scc_as_frozensets
    )

    print(
        "Czy kondensacja jest DAGiem (acykliczna)? =",
        nx.is_directed_acyclic_graph(condensation)
    )

    print(
        "|V| kondensacji (liczba SCC jako wezlow) =",
        condensation.number_of_nodes()
    )

    print(
        "|E| kondensacji =",
        condensation.number_of_edges()
    )

    condensation_out_degrees = dict(
        condensation.out_degree()
    )

    top_hub_scc = max(
        condensation_out_degrees,
        key=condensation_out_degrees.get
    )

    print(
        "\nSCC-wezel kondensacji z najwiekszym "
        "out-degree w DAGu:",
        top_hub_scc,
        "-> out-degree =",
        condensation_out_degrees[top_hub_scc],
        "-> rozmiar tej SCC =",
        len(condensation.nodes[top_hub_scc]['members'])
    )

    nx.write_edgelist(
        condensation,
        "graph_analysis_task4/condensation.txt"
    )

    print(
        "\nDAG kondensacji zapisany do condensation.txt"
    )


if __name__ == "__main__":
    main()