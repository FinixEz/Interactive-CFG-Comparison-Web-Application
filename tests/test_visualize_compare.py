import json

import networkx as nx
import pytest

from visualize_compare import (add_legend_to_html, compare_graphs,
                               compute_node_importance, load_cfg_json,
                               structural_similarity)


def test_load_simple_format(tmp_path):
    p = tmp_path / "g.json"
    p.write_text(json.dumps({"nodes": ["a", "b"], "edges": [["a", "b"]]}))
    G = load_cfg_json(str(p))
    assert set(G.nodes()) == {"a", "b"}
    assert G.has_edge("a", "b")


def test_load_node_link_format(tmp_path):
    p = tmp_path / "g.json"
    p.write_text(json.dumps({
        "directed": True, "multigraph": False,
        "nodes": [{"id": "a"}, {"id": "b"}],
        "links": [{"source": "a", "target": "b"}]}))
    G = load_cfg_json(str(p))
    assert G.has_edge("a", "b")


def test_compare_graphs_excludes_synthetic_entry():
    G1 = nx.DiGraph([("entry", "a")])
    G2 = nx.DiGraph([("entry", "b")])
    nodes, edges = compare_graphs(G1, G2)
    assert "entry" not in nodes
    assert not edges


def test_self_similarity_is_one():
    G = nx.balanced_tree(2, 3, create_using=nx.DiGraph)
    s = structural_similarity(G, G)
    assert s['score'] == pytest.approx(1.0)
    assert len(s['matched_nodes_1']) == G.number_of_nodes()


def test_rename_invariance():
    G = nx.balanced_tree(2, 3, create_using=nx.DiGraph)
    H = nx.relabel_nodes(G, {n: f"x{n}" for n in G.nodes()})
    s = structural_similarity(G, H)
    assert s['score'] == pytest.approx(1.0)
    assert len(s['matched_nodes_1']) == G.number_of_nodes()
    assert len(s['matched_edges_1']) == G.number_of_edges()


def test_dissimilar_structures_score_low():
    P = nx.path_graph(20, create_using=nx.DiGraph)
    K = nx.complete_graph(20, create_using=nx.DiGraph)
    s = structural_similarity(P, K)
    assert s['score'] < 0.2
    assert not s['matched_nodes_1']


def test_empty_graph_scores_zero():
    s = structural_similarity(nx.DiGraph(), nx.DiGraph([("a", "b")]))
    assert s['score'] == 0.0
    assert not s['matched_nodes_1']


def test_graded_matching_tolerates_one_extra_edge():
    G = nx.balanced_tree(2, 4, create_using=nx.DiGraph)  # 31 nodes
    H = G.copy()
    leaves = [n for n in H if H.out_degree(n) == 0]
    H.add_edge(leaves[-1], leaves[0])
    s = structural_similarity(G, H)
    # Strict depth-3 matching would void every node within 3 hops of the
    # edit; graded matching must keep the bulk of the graph matched
    assert len(s['matched_nodes_1']) >= G.number_of_nodes() * 0.6


def test_similarity_does_not_mutate_inputs():
    G = nx.balanced_tree(2, 3, create_using=nx.DiGraph)
    structural_similarity(G, G)
    assert all('_wl_seed' not in d for _, d in G.nodes(data=True))


def test_importance_tiers_and_range():
    G = nx.balanced_tree(2, 3, create_using=nx.DiGraph)
    imp = compute_node_importance(G)
    assert set(imp) == set(G.nodes())
    assert all(0.0 <= d['score'] <= 1.0 for d in imp.values())
    assert all(d['tier'] in {'critical', 'high', 'normal'} for d in imp.values())
    assert any(d['tier'] == 'critical' for d in imp.values())


def test_importance_empty_graph():
    assert compute_node_importance(nx.DiGraph()) == {}


def test_legend_escapes_user_filenames(tmp_path):
    f = tmp_path / "g.html"
    f.write_text("<html><body></body></html>")
    add_legend_to_html(str(f), '<script>alert(1)</script>.json', 'b.json')
    out = f.read_text()
    assert '<script>alert(1)</script>' not in out
    assert '&lt;script&gt;' in out
