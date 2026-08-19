import networkx as nx

G = nx.read_edgelist("graph.txt", create_using=nx.DiGraph())

def find_C(graph, vertex):
    neighbours = graph[vertex]
    k_v = len(neighbours)
    if k_v < 2:
        return 0
    # e_v number of edges between the neighbours of vertex
    e_v = 0
    for neighbour in neighbours:
        for node in neighbour:
            if node in neighbours:
                e_v += 1

    e_v = e_v/2

    C = e_v/( k_v * (k_v - 1))
    return C


C_v = {}
for vertex in G:
    C_v[vertex] = find_C(G, vertex)

local_C = sum(C_v.values())/G.number_of_nodes()

