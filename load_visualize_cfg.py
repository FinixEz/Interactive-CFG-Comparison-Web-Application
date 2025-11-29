import pickle
import networkx as nx
import matplotlib.pyplot as plt
import importlib
try:
    importlib.import_module('cle.backends.pe.relocation.amd64')
except ModuleNotFoundError:
    print("Warning: cle.backends.pe.relocation.amd64 not found. Unpickling may fail.")

def load_cfg_pkl(file_path):
    with open(file_path, 'rb') as f:
        graph = pickle.load(f)
    return graph

def visualize_graph(G):
    # Visualize a sampled subgraph if the graph is too large
    if G.number_of_nodes() > 500:
        print(f"Large graph with {G.number_of_nodes()} nodes, sampling subgraph for visualization")
        nodes = list(G.nodes())[:500]
        subgraph = G.subgraph(nodes)
        G = subgraph

    pos = nx.spring_layout(G)
    nx.draw(G, pos, node_size=20, node_color='skyblue', with_labels=False, arrowsize=10)
    plt.show()

if __name__ == "__main__":
    pkl_file = r"C:\Users\Admin\Documents\Work\Project\CFGs_y4t1\Sample\c7fc898d12c2b78fc1edc32db76c7ccc87f4b338a8b2d24dd46f5cc583bd8eb7.pkl"
    
    print("Loading graph...")
    G = load_cfg_pkl(pkl_file)
    print(f"Loaded graph with {G.number_of_nodes()} nodes and {G.number_of_edges()} edges.")
    
    visualize_graph(G)
