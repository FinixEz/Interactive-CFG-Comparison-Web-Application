import sys
import networkx as nx
import json
from pyvis.network import Network
from networkx.readwrite import json_graph

def load_cfg_json(json_path):
    with open(json_path, 'r') as f:
        data = json.load(f)
    G = json_graph.node_link_graph(data, edges="links")
    return G

def compare_graphs(G1, G2):
    nodes_in_both = set(G1.nodes()).intersection(set(G2.nodes()))
    edges_in_both = set(G1.edges()).intersection(set(G2.edges()))
    return nodes_in_both, edges_in_both

def add_legend_to_html(file_path, file1_name, file2_name):
    legend_html = f"""
    <div style="
        position: fixed;
        bottom: 20px;
        left: 20px;
        background: white;
        padding: 10px;
        border: 1px solid black;
        font-family: Arial;
        font-size: 14px;
        z-index: 9999;">
        <b>Legend:</b><br>
        <span style="color: red;">&#9679;</span> Shared nodes/edges (both files)<br>
        <span style="color: blue;">&#9679;</span> Nodes/edges unique to {file1_name}<br>
        <span style="color: green;">&#9679;</span> Nodes/edges unique to {file2_name}<br>
    </div>
    """

    with open(file_path, 'r', encoding='utf-8') as f:
        html = f.read()
    if legend_html.strip() not in html:
        html = html.replace("</body>", legend_html + "</body>")
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(html)

def visualize_graph_comparison(G1, G2, file1_name, file2_name, max_nodes=500):
    combined = nx.compose(G1, G2)
    if combined.number_of_nodes() > max_nodes:
        combined = combined.subgraph(list(combined.nodes())[:max_nodes])

    nodes_in_both, edges_in_both = compare_graphs(G1, G2)

    net = Network(notebook=False, directed=True)

    for node in combined.nodes():
        if node in nodes_in_both:
            color = "red"
        elif node in G1:
            color = "blue"
        else:
            color = "green"
        net.add_node(str(node), label=str(node), color=color)

    for u, v in combined.edges():
        if (u, v) in edges_in_both:
            edge_color = "red"
        elif (u, v) in G1.edges():
            edge_color = "blue"
        else:
            edge_color = "green"
        net.add_edge(str(u), str(v), color=edge_color)

    output_file = "compare_graph.html"
    net.show(output_file, notebook=False)
    add_legend_to_html(output_file, file1_name, file2_name)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python visualize_compare.py <json_cfg1> <json_cfg2>")
        sys.exit(1)
    file1, file2 = sys.argv[1], sys.argv[2]
    cfg1 = load_cfg_json(file1)
    cfg2 = load_cfg_json(file2)
    print(f"Graph 1: {cfg1.number_of_nodes()} nodes, {cfg1.number_of_edges()} edges")
    print(f"Graph 2: {cfg2.number_of_nodes()} nodes, {cfg2.number_of_edges()} edges")
    print("Launching comparative visualization...")
    visualize_graph_comparison(cfg1, cfg2, file1, file2)
