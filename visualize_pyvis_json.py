import sys
import networkx as nx
import json
from pyvis.network import Network
from networkx.readwrite import json_graph

def load_cfg_json(json_path):
    with open(json_path, 'r') as f:
        data = json.load(f)
    G = json_graph.node_link_graph(data)
    return G

def visualize_graph_pyvis(G, max_nodes=500):
    if G.number_of_nodes() > max_nodes:
        G = G.subgraph(list(G.nodes())[:max_nodes])
    G_str = nx.relabel_nodes(G, lambda x: str(x))
    net = Network(notebook=False, directed=True)
    net.from_nx(G_str)
    net.show("graph.html", notebook=False)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python visualize_pyvis_json.py <path_to_json_file>")
        sys.exit(1)
    json_file = sys.argv[1]
    print("Loading CFG from JSON...")
    graph = load_cfg_json(json_file)
    print(f"Graph loaded with {graph.number_of_nodes()} nodes and {graph.number_of_edges()} edges.")
    print("Launching interactive visualization...")
    visualize_graph_pyvis(graph)
