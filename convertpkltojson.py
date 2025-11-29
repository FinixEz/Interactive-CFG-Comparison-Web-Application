import pickle
import json
import sys
import networkx as nx
from networkx.readwrite import json_graph

def serialize_attr(attr):
    # Serialize attribute dict with fallback to string for unsupported types
    simple_attr = {}
    for k, v in attr.items():
        try:
            json.dumps(v)  # test if serializable
            simple_attr[k] = v
        except TypeError:
            simple_attr[k] = str(v)
    return simple_attr

def serialize_graph(G):
    H = nx.DiGraph()
    for node, attr in G.nodes(data=True):
        # Convert node object to string representation to serve as JSON key
        node_key = str(node)
        simple_attr = serialize_attr(attr)
        H.add_node(node_key, **simple_attr)

    for u, v, attr in G.edges(data=True):
        H.add_edge(str(u), str(v), **serialize_attr(attr))

    return H

def pkl_to_json(pkl_path, json_path):
    with open(pkl_path, 'rb') as f:
        cfg = pickle.load(f)
    G = getattr(cfg, "graph", cfg)

    # Serialize graph for JSON-compatibility
    G_clean = serialize_graph(G)

    data = json_graph.node_link_data(G_clean)
    with open(json_path, 'w') as f:
        json.dump(data, f, indent=2)

    print(f"CFG JSON saved to {json_path}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python convertpkltojson.py <input_pkl> <output_json>")
        sys.exit(1)
    pkl_to_json(sys.argv[1], sys.argv[2])
