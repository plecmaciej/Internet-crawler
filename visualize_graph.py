"""
visualize_graph.py

1) Eksportuje graf do formatu GraphML z atrybutami wezlow (bow-tie category,
   in-degree, out-degree) - do otwarcia i wizualizacji w Gephi.
2) Wypisuje szczegolowa analize mniejszych skladowych WCC (izolowanych
   fragmentow sieci): jakie to strony, ile maja wezlow, jakie krawedzie
   je laczy.

Uruchom: python visualize_graph.py
"""

import networkx as nx
from graph_utils import load_graph, classify_bowtie

print("Wczytywanie grafu z graph.txt...")
G = load_graph("graph.txt")
print(f"|V| = {G.number_of_nodes()}, |E| = {G.number_of_edges()}\n")


# ============================================================
# CZESC 1: Klasyfikacja bow-tie i eksport do GraphML
# ============================================================
print("=" * 70)
print("EKSPORT DO GRAPHML (kolorowanie wg struktury bow-tie)")
print("=" * 70)

# Uwaga: tu uzywamy nx.strongly_connected_components (szybsze na duzym grafie).
# Logika wlasnego Tarjana (graph_utils.my_tarjan) zostala juz zwalidowana
# wzgledem networkx w Z4 - do samego eksportu obie implementacje dadza
# identyczny wynik, wiec dla wygody uzywamy gotowej z networkx.
scc_list = [list(s) for s in nx.strongly_connected_components(G)]

print("Klasyfikacja bow-tie (SCC/IN/OUT/TENDRILS/DISCONNECTED)...")
bowtie = classify_bowtie(G, scc_list)

category = {}
for node in bowtie['SCC']:
    category[node] = 'SCC'
for node in bowtie['IN']:
    category[node] = 'IN'
for node in bowtie['OUT']:
    category[node] = 'OUT'
for node in bowtie['TENDRILS']:
    category[node] = 'TENDRILS'
for node in bowtie['DISCONNECTED']:
    category[node] = 'DISCONNECTED'

nx.set_node_attributes(G, category, 'bowtie_category')

in_deg = dict(G.in_degree())
out_deg = dict(G.out_degree())
nx.set_node_attributes(G, in_deg, 'in_degree')
nx.set_node_attributes(G, out_deg, 'out_degree')

print("\nLiczebnosc kategorii wyeksportowanych jako atrybut wezla:")
for cat in ['SCC', 'IN', 'OUT', 'TENDRILS', 'DISCONNECTED']:
    count = sum(1 for c in category.values() if c == cat)
    print(f"  {cat:14s}: {count}")

nx.write_graphml(G, "graph_export.graphml")
print("\nGraf zapisany do graph_export.graphml")
print("W Gephi: Appearance -> Nodes -> Partition -> wybierz atrybut 'bowtie_category',")
print("zeby pokolorowac wezly wg strefy bow-tie.")


# ============================================================
# CZESC 2: Analiza mniejszych skladowych WCC
# ============================================================
print("\n" + "=" * 70)
print("ANALIZA SKLADOWYCH WCC")
print("=" * 70)

wcc_list = list(nx.weakly_connected_components(G))
wcc_sorted = sorted(wcc_list, key=len, reverse=True)

print(f"\nLiczba skladowych WCC: {len(wcc_sorted)}")
for i, comp in enumerate(wcc_sorted, start=1):
    print(f"  WCC #{i}: {len(comp)} wezlow")

if len(wcc_sorted) <= 1:
    print("\nGraf ma tylko jedna skladowa WCC - brak izolowanych fragmentow do analizy.")
else:
    print("\n--- SZCZEGOLY MNIEJSZYCH SKLADOWYCH (wszystkie poza najwieksza) ---")
    print("(przydatne do zdiagnozowania, czy to artefakt normalizacji URL,")
    print(" czy realnie odciety fragment strony)\n")

    for i, comp in enumerate(wcc_sorted[1:], start=2):
        print(f"WCC #{i}  ({len(comp)} wezlow)")
        print("-" * 50)

        subG = G.subgraph(comp)

        print("Wezly (adres, in-degree WEWNATRZ tej skladowej, out-degree WEWNATRZ tej skladowej):")
        for node in sorted(comp):
            print(f"  - {node}")
            print(f"      in={subG.in_degree(node)}  out={subG.out_degree(node)}")

        print("\nKrawedzie wewnatrz tej skladowej (kto do kogo linkuje):")
        edges = list(subG.edges())
        if edges:
            for u, v in edges:
                print(f"  {u}")
                print(f"    -> {v}")
        else:
            print("  (brak krawedzi - pojedynczy izolowany wezel)")

        # Sanity check: skoro to osobna skladowa WCC, z definicji nie powinno
        # byc ZADNYCH krawedzi (w zadnym kierunku) laczacych ja z reszta grafu.
        external_in = sum(1 for n in comp for pred in G.predecessors(n) if pred not in comp)
        external_out = sum(1 for n in comp for succ in G.successors(n) if succ not in comp)
        print(f"\nSanity check - krawedzie wychodzace poza te skladowa: {external_out}")
        print(f"Sanity check - krawedzie wchodzace spoza tej skladowej: {external_in}")
        print("(obie wartosci MUSZA byc 0, bo to jest osobna skladowa WCC z definicji;")
        print(" niezerowa wartosc oznaczalaby blad w danych/analizie)\n")
