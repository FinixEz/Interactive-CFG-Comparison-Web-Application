import json
import random
import networkx as nx
from networkx.readwrite import json_graph

def load_cfg_json(json_path):
    with open(json_path, 'r') as f:
        data = json.load(f)
    return json_graph.node_link_graph(data, edges="links")

def bfs_subgraph(G, start_node, max_nodes):
    visited = set()
    queue = [start_node]

    while queue and len(visited) < max_nodes:
        current = queue.pop(0)
        if current not in visited:
            visited.add(current)
            neighbors = list(G.successors(current)) + list(G.predecessors(current))
            queue.extend(n for n in neighbors if n not in visited)
    return G.subgraph(visited).copy()

def create_branching_mock_nodes(start_addr, count=20):
    G = nx.DiGraph()
    # Create node addresses
    nodes = [start_addr + i * 0x10 for i in range(count)]
    for addr in nodes:
        addr_str = f"0x{addr:x}"
        G.add_node(addr_str, addr=addr_str, size=random.randint(10, 30), ins_count=random.randint(1, 8),
                   function=f"mock_func_{random.randint(1,5)}", type=random.choice(["normal", "call", "conditional_jump"]))

    # Connect nodes in a branching manner
    for i in range(count):
        current = f"0x{nodes[i]:x}"
        # Connect to next node linearly
        if i < count - 1:
            next_node = f"0x{nodes[i + 1]:x}"
            G.add_edge(current, next_node, type=random.choice(["jmp", "call", "conditional_true"]))
        # Add some random branches
        if i < count - 2 and random.random() < 0.3:
            branch_target = f"0x{nodes[random.randint(i + 2, count - 1)]:x}"
            G.add_edge(current, branch_target, type="conditional_false")
    return G

def create_mixed_mock_cfg(malware_graph, sample_size=30, mock_node_count=50):
    # Pick random start node for BFS sampling
    start_node = random.choice(list(malware_graph.nodes()))
    sampled_subgraph = bfs_subgraph(malware_graph, start_node, sample_size)

    # Determine numeric max address among sampled nodes
    def to_int(n, G):
        try:
            if isinstance(n, int):
                return n
            elif isinstance(n, str) and n.startswith('0x'):
                return int(n, 16)
            else:
                node_data = G.nodes[n]
                addr_attr = node_data.get('addr', None)
                if addr_attr is None:
                    return int(n)
                if isinstance(addr_attr, int):
                    return addr_attr
                if isinstance(addr_attr, str) and addr_attr.startswith('0x'):
                    return int(addr_attr, 16)
                return int(n)
        except Exception:
            return 0

    max_addr = max(to_int(n, sampled_subgraph) for n in sampled_subgraph.nodes())
    next_addr = max_addr + 0x10

    mock_graph = create_branching_mock_nodes(next_addr, mock_node_count)

    # Connect mock graph to sampled malware subgraph
    combined = nx.compose(sampled_subgraph, mock_graph)

    # Connect random boundary malware node to start of mock graph
    boundary_nodes = [n for n in sampled_subgraph.nodes() if sampled_subgraph.out_degree(n) == 0]
    if boundary_nodes:
        boundary_node = random.choice(boundary_nodes)
        start_mock_node = f"0x{next_addr:x}"
        combined.add_edge(boundary_node, start_mock_node, type="jmp")

    return combined

def save_cfg_json(G, json_path):
    data = json_graph.node_link_data(G)
    with open(json_path, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"Balanced mock CFG saved as {json_path}")

if __name__ == "__main__":
    malware_json = "boombasv2.json"
    mock_json = "mocking.json"

    malware_graph = load_cfg_json(malware_json)
    mixed_graph = create_mixed_mock_cfg(malware_graph, sample_size=30, mock_node_count=50)
    save_cfg_json(mixed_graph, mock_json)
