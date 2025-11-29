import sys
import pickle
import networkx as nx
from pyvis.network import Network

def load_cfg_pkl(file_path):
    with open(file_path, 'rb') as f:
        cfg = pickle.load(f)
    return cfg.graph

def visualize_graph_pyvis(G, max_nodes=500):
    if G.number_of_nodes() > max_nodes:
        G = G.subgraph(list(G.nodes())[:max_nodes])
    G_str = nx.relabel_nodes(G, lambda x: str(x))
    net = Network(notebook=False, directed=True)
    net.from_nx(G_str)
    # Use notebook=False to avoid Jinja2 render error when not in a Jupyter notebook
    net.show("graph.html", notebook=False)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python visualize_pyvis.py <path_to_pkl_file>")
        sys.exit(1)
    pkl_file = sys.argv[1]
    print("Loading CFG and extracting graph...")
    graph = load_cfg_pkl(pkl_file)
    print(f"Graph loaded with {graph.number_of_nodes()} nodes and {graph.number_of_edges()} edges.")
    print("Launching interactive visualization...")
    visualize_graph_pyvis(graph)
