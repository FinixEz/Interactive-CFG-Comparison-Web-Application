import sys
import pickle
import networkx as nx
import matplotlib.pyplot as plt


def load_cfg_pkl(file_path):
    with open(file_path, 'rb') as f:
        cfg = pickle.load(f)
    return cfg.graph


def find_similarity_nodes(G1, G2):
    # Finding common nodes (by node IDs, typically addresses)
    common = set(G1.nodes()).intersection(set(G2.nodes()))
    return common


def visualize_similarity(G1, G2, common_nodes):
    fig, axes = plt.subplots(1, 2, figsize=(16, 8))

    def draw_graph_with_highlights(graph, ax):
        colors = ['lightgray'] * len(graph.nodes())
        labels = {}
        for idx, node in enumerate(graph.nodes()):
            if node in common_nodes:
                colors[idx] = 'orange'  # highlight color
            labels[node] = str(node)

        pos = nx.spring_layout(graph)
        nx.draw(graph, pos, node_color=colors, with_labels=False, edge_color='gray', node_size=30, ax=ax)
        ax.set_title('Graph Highlighting Similar Nodes')

    draw_graph_with_highlights(G1, axes[0])
    axes[0].set_title('Graph 1 with Similar Nodes Highlighted')

    draw_graph_with_highlights(G2, axes[1])
    axes[1].set_title('Graph 2 with Similar Nodes Highlighted')

    plt.show()


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python visualize.py <path_to_pkl_file_1> <path_to_pkl_file_2>")
        sys.exit(1)

    g1_path = sys.argv[1]
    g2_path = sys.argv[2]

    graph1 = load_cfg_pkl(g1_path)
    graph2 = load_cfg_pkl(g2_path)

    similarity_nodes = find_similarity_nodes(graph1, graph2)
    print(f"Found {len(similarity_nodes)} similar nodes.")

    visualize_similarity(graph1, graph2, similarity_nodes)
