import sys
import pickle
import networkx as nx
import matplotlib.pyplot as plt

def load_cfg_pkl(file_path):
    with open(file_path, 'rb') as f:
        cfg = pickle.load(f)
    # Extract the NetworkX graph from the CFGFast object
    graph = cfg.graph  
    return graph

def visualize_graph(G, max_nodes=500):
    if G.number_of_nodes() > max_nodes:
        print(f"Graph too large ({G.number_of_nodes()} nodes). Sampling {max_nodes} nodes for visualization.")
        sampled_nodes = list(G.nodes())[:max_nodes]
        G = G.subgraph(sampled_nodes)
    pos = nx.spring_layout(G)
    nx.draw(G, pos, node_size=20, node_color='skyblue', with_labels=False, arrowsize=10)
    plt.show()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python pkl.py <path_to_pkl_file>")
        sys.exit(1)
    pkl_file = sys.argv[1]
    print("Loading CFG...")
    graph = load_cfg_pkl(pkl_file)
    print(f"Graph loaded with {graph.number_of_nodes()} nodes and {graph.number_of_edges()} edges.")
    visualize_graph(graph)
