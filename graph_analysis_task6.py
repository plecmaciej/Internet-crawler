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
    average_distance[vertex] = sum(all_distances[vertex].values())/len(all_distances[vertex])

diameter = max(eccentricity)
radius = min(eccentricity)

print(diameter, radius, eccentricity)



