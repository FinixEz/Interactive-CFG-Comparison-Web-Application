import sys
import networkx as nx
import json
from collections import Counter
from html import escape as html_escape
from pyvis.network import Network
from networkx.readwrite import json_graph

def load_cfg_json(json_path):
    with open(json_path, 'r') as f:
        data = json.load(f)

    # Simple format: {"nodes": ["a", "b"], "edges": [["a", "b"], ...]}
    nodes = data.get("nodes") if isinstance(data, dict) else None
    if nodes and not isinstance(nodes[0], dict):
        G = nx.DiGraph()
        G.add_nodes_from(nodes)
        G.add_edges_from(tuple(e) for e in data.get("edges", []))
        return G

    # NetworkX node-link format (as produced by convertpkltojson.py)
    edge_key = "links" if "links" in data else "edges"
    G = json_graph.node_link_graph(data, edges=edge_key)
    return G

# Pseudo-block ids the parser invents (not real shared identifiers). They
# carry the same name across unrelated files, so counting them as "common"
# manufactures false matches — exclude them from name-based comparison.
SYNTHETIC_NODES = frozenset({'entry'})


def compare_graphs(G1, G2):
    nodes_in_both = (set(G1.nodes()) & set(G2.nodes())) - SYNTHETIC_NODES
    edges_in_both = {
        (u, v) for (u, v) in set(G1.edges()) & set(G2.edges())
        if u not in SYNTHETIC_NODES and v not in SYNTHETIC_NODES
    }
    return nodes_in_both, edges_in_both


def _wl_seed_labels(G):
    """
    Initial WL labels per node: in|out degree pair (plus a log2 block-size
    bucket when the assembly parser recorded line spans). More discriminative
    than the networkx default seed (total degree) — a 2-in/1-out join and a
    1-in/2-out branch no longer start out identical.
    """
    labels = {}
    for node, data in G.nodes(data=True):
        if G.is_directed():
            label = f"{G.in_degree(node)}|{G.out_degree(node)}"
        else:
            label = str(G.degree(node))
        start, end = data.get('start_line', -1), data.get('end_line', -1)
        if isinstance(start, int) and isinstance(end, int) and 0 <= start <= end:
            label += f"|{(end - start + 1).bit_length()}"
        labels[node] = label
    return labels


def structural_similarity(G1, G2, iterations=3):
    """
    Name-independent structural comparison via Weisfeiler-Lehman fingerprints.

    Every node gets a depth-k neighborhood fingerprint (WL subgraph hash,
    seeded with in/out-degree labels — see _wl_seed_labels); two nodes share
    a fingerprint only if their k-hop neighborhoods have identical structure.
    This stays meaningful when node names cannot match — e.g. address-based
    CFG node IDs from two different binaries.

    Returns a dict with:
        score            multiset-Jaccard of all fingerprints, 0..1
        matched_nodes_1  nodes of G1 whose fingerprint also occurs in G2
        matched_nodes_2  nodes of G2 whose fingerprint also occurs in G1
        matched_edges_1  edges of G1 whose (src, dst) fingerprint pair occurs in G2
        matched_edges_2  edges of G2 whose (src, dst) fingerprint pair occurs in G1

    Node matching is graded: a node unmatched at full depth is retried at
    shallower depths (down to 2 iterations), so a single extra edge deep in
    its neighborhood no longer voids an otherwise-identical block. Edge
    matching stays strict (deepest fingerprints). All matches are capped
    multiset-style: three copies of a pattern in one graph match at most the
    number of copies present in the other graph.
    """
    if G1.number_of_nodes() == 0 or G2.number_of_nodes() == 0:
        return {'score': 0.0, 'matched_nodes_1': set(), 'matched_nodes_2': set(),
                'matched_edges_1': set(), 'matched_edges_2': set()}

    # Copies so the seed attribute never leaks into callers' graphs
    G1, G2 = G1.copy(), G2.copy()
    nx.set_node_attributes(G1, _wl_seed_labels(G1), '_wl_seed')
    nx.set_node_attributes(G2, _wl_seed_labels(G2), '_wl_seed')
    h1 = nx.weisfeiler_lehman_subgraph_hashes(G1, node_attr='_wl_seed',
                                              iterations=iterations)
    h2 = nx.weisfeiler_lehman_subgraph_hashes(G2, node_attr='_wl_seed',
                                              iterations=iterations)

    # Graded similarity: pool fingerprints from every refinement depth so
    # coarse structural agreement still counts even when deep ones differ
    c1 = Counter(h for hashes in h1.values() for h in hashes)
    c2 = Counter(h for hashes in h2.values() for h in hashes)
    union = sum((c1 | c2).values())
    score = sum((c1 & c2).values()) / union if union else 0.0

    # Graded node matching: deepest agreeing depth wins, minimum 2 iterations
    matched_nodes_1, matched_nodes_2 = _graded_node_matches(h1, h2, min_depth=1)

    # Edge matching by the fingerprint pair of the endpoints (direction kept)
    f1 = {n: hashes[-1] for n, hashes in h1.items()}
    f2 = {n: hashes[-1] for n, hashes in h2.items()}

    # Edge matching by the fingerprint pair of the endpoints (direction kept)
    e1 = {(u, v): (f1[u], f1[v]) for u, v in G1.edges()}
    e2 = {(u, v): (f2[u], f2[v]) for u, v in G2.edges()}
    shared_ep = Counter(e1.values()) & Counter(e2.values())
    matched_edges_1 = _capped_matches(e1.items(), shared_ep)
    matched_edges_2 = _capped_matches(e2.items(), shared_ep)

    return {'score': score,
            'matched_nodes_1': matched_nodes_1, 'matched_nodes_2': matched_nodes_2,
            'matched_edges_1': matched_edges_1, 'matched_edges_2': matched_edges_2}


def _capped_matches(items, shared_counts):
    """Greedily select items whose fingerprint still has shared quota left."""
    remaining = Counter(shared_counts)
    matched = set()
    for key, fp in items:
        if remaining[fp] > 0:
            remaining[fp] -= 1
            matched.add(key)
    return matched


def _graded_node_matches(h1, h2, min_depth=1):
    """
    Match nodes at the deepest WL depth where their fingerprints still agree.

    h1/h2 map node -> [hash after 1 iteration, ..., hash after k iterations].
    Starting from the deepest hashes, nodes whose fingerprint occurs in the
    other graph are matched (capped multiset semantics) and removed; the
    leftovers retry one depth shallower, down to index min_depth. Depths
    below min_depth are too coarse to call a block "shared".
    """
    matched1, matched2 = set(), set()
    unmatched1, unmatched2 = set(h1), set(h2)
    depth_count = len(next(iter(h1.values())))
    for d in range(depth_count - 1, min_depth - 1, -1):
        if not unmatched1 or not unmatched2:
            break
        shared = (Counter(h1[n][d] for n in unmatched1)
                  & Counter(h2[n][d] for n in unmatched2))
        m1 = _capped_matches(((n, h1[n][d]) for n in unmatched1), shared)
        m2 = _capped_matches(((n, h2[n][d]) for n in unmatched2), shared)
        matched1 |= m1
        matched2 |= m2
        unmatched1 -= m1
        unmatched2 -= m2
    return matched1, matched2


def compute_node_importance(G):
    """
    Classify nodes by structural importance.

    Importance is a weighted mix of betweenness centrality (nodes that act
    as chokepoints on control-flow paths) and degree centrality (how
    connected a node is). Nodes are ranked and tiered: the top 10% are
    'critical', the next 20% 'high', the rest 'normal'.

    Returns:
        dict mapping node -> {'score': float in [0, 1], 'tier': str}
    """
    n = G.number_of_nodes()
    if n == 0:
        return {}

    # Sample betweenness on large graphs to keep uploads responsive
    k = 200 if n > 200 else None
    bc = nx.betweenness_centrality(G, k=k, seed=42)
    dc = nx.degree_centrality(G)
    raw = {node: 0.6 * bc[node] + 0.4 * dc[node] for node in G.nodes()}

    max_raw = max(raw.values())
    if max_raw == 0:
        return {node: {'score': 0.0, 'tier': 'normal'} for node in G.nodes()}
    scores = {node: v / max_raw for node, v in raw.items()}

    ranked = sorted(scores, key=scores.get, reverse=True)
    n_critical = max(1, round(n * 0.10))
    n_high = max(1, round(n * 0.20))

    importance = {}
    for i, node in enumerate(ranked):
        if i < n_critical and scores[node] > 0:
            tier = 'critical'
        elif i < n_critical + n_high and scores[node] > 0:
            tier = 'high'
        else:
            tier = 'normal'
        importance[node] = {'score': scores[node], 'tier': tier}
    return importance

# Dark overrides for the chrome PyVis puts around the canvas
# (white body, lightgray card border, bright grey stabilization loader)
DARK_CHROME_CSS = """
<style>
  html, body { height: 100%; }
  body { background: #0e131b !important; margin: 0; }
  .card { background: transparent !important; border: none !important; height: 100% !important; }
  #mynetwork { border: none !important; background: #0e131b !important; height: 100% !important; }
  #loadingBar { background: rgba(10, 13, 18, 0.92) !important; }
  .outerBorder { background: #11161f !important; border: 1px solid #232c3b !important; }
  #border { background: #1a2230 !important; border: none !important; }
  #bar { background: #ffb454 !important; }
  #text { color: #8b98ab !important; font-family: 'JetBrains Mono', Consolas, monospace !important; }
  div.vis-tooltip { background: #11161f !important; color: #d7e0ec !important;
                    border: 1px solid #232c3b !important; border-radius: 6px !important;
                    font-family: 'JetBrains Mono', Consolas, monospace !important;
                    font-size: 12px !important; }
</style>
"""


def apply_dark_chrome(file_path):
    """Inject dark-theme overrides into a generated PyVis HTML file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        html = f.read()
    if DARK_CHROME_CSS not in html and '</head>' in html:
        html = html.replace('</head>', DARK_CHROME_CSS + '</head>')
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(html)


def add_legend_to_html(file_path, file1_name, file2_name, match_mode='name'):
    # Filenames come straight from the upload form — escape before
    # interpolating into raw HTML (Jinja autoescaping doesn't cover this path)
    file1_name = html_escape(file1_name)
    file2_name = html_escape(file2_name)
    if match_mode == 'structure':
        shared_line = (
            'Structurally matched nodes/edges '
            '(same control-flow pattern in both files)')
    else:
        shared_line = 'Nodes/edges present in both files'
    legend_html = f"""
    <div style="
        position: fixed;
        bottom: 16px;
        left: 16px;
        background: #11161f;
        color: #d7e0ec;
        padding: 10px 14px;
        border: 1px solid #232c3b;
        border-radius: 6px;
        font-family: 'JetBrains Mono', Consolas, monospace;
        font-size: 12px;
        line-height: 1.7;
        z-index: 9999;">
        <b style="color: #ffb454;">// legend</b><br>
        <span style="color: #ffb454;">&#9679;</span> /
        <span style="color: #ff6b6b;">&#9644;</span> {shared_line}<br>
        <span style="color: #56c8ff;">&#9679;</span> Nodes /
        <span style="color: #3d8bff;">&#9644;</span> Edges unique to {file1_name}<br>
        <span style="color: #6fdb8d;">&#9679;</span> Nodes /
        <span style="color: #2ecc71;">&#9644;</span> Edges unique to {file2_name}<br>
        <span style="font-size: 11px; color: #8b98ab;">node size &#8733; importance
        (betweenness/degree) &middot; <span style="color:#ff5d5d;">red border</span> = critical</span>
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

    net = Network(notebook=False, directed=True, cdn_resources='remote')

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
