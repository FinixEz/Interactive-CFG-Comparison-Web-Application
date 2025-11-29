import pickle
import networkx as nx
import matplotlib.pyplot as plt

def load_cfg_pkl(file_path):
    """
    Load a CFG graph object from a pickle file.
    """
    with open(file_path, 'rb') as f:
        graph = pickle.load(f)
    return graph

def visualize_graph(G, max_nodes=500):
    """
    Visualize the graph using NetworkX and Matplotlib.
    If the graph is large, visualize a subgraph limited to max_nodes nodes.
    """
    if G.number_of_nodes() > max_nodes:
        print(f"Graph too large ({G.number_of_nodes()} nodes). Sampling {max_nodes} nodes for visualization.")
        sampled_nodes = list(G.nodes())[:max_nodes]
        G = G.subgraph(sampled_nodes)
    
    pos = nx.spring_layout(G)
    nx.draw(G, pos, node_size=20, node_color='skyblue', with_labels=False, arrowsize=10)
    plt.show()

if __name__ == "__main__":
    # Use raw string or double backslashes for Windows file paths
    pkl_file = r"C:\Users\Admin\Documents\Work\Project\CFGs_y4t1\Sample\c7fc898d12c2b78fc1edc32db76c7ccc87f4b338a8b2d24dd46f5cc583bd8eb7.pkl"
    
    print("Loading graph...")
    graph = load_cfg_pkl(pkl_file)
    print(f"Graph loaded with {graph.number_of_nodes()} nodes and {graph.number_of_edges()} edges.")
    
    visualize_graph(graph)
