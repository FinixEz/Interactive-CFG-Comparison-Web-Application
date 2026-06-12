import networkx as nx
import pytest

import fingerprint_db as fdb


@pytest.fixture()
def tmp_db(monkeypatch, tmp_path):
    monkeypatch.setattr(fdb, 'BASELINE_DIR', str(tmp_path))
    return tmp_path


def test_add_and_list(tmp_db):
    G = nx.balanced_tree(2, 3, create_using=nx.DiGraph)
    slug = fdb.add_baseline('My Sample!', G)
    assert slug == 'My_Sample'
    baselines = fdb.list_baselines()
    assert len(baselines) == 1
    assert baselines[0]['name'] == 'My_Sample'
    assert baselines[0]['nodes'] == G.number_of_nodes()
    assert baselines[0]['edges'] == G.number_of_edges()


def test_roundtrip_preserves_structure(tmp_db):
    G = nx.balanced_tree(2, 3, create_using=nx.DiGraph)
    fdb.add_baseline('tree', G)
    loaded = fdb.list_baselines()[0]['graph']
    assert nx.is_isomorphic(G, loaded)


def test_match_ranks_identical_structure_first(tmp_db):
    tree = nx.balanced_tree(2, 3, create_using=nx.DiGraph)
    path = nx.path_graph(10, create_using=nx.DiGraph)
    fdb.add_baseline('tree', tree)
    fdb.add_baseline('path', path)

    # Renamed copy: identification must not depend on node names
    target = nx.relabel_nodes(tree, {n: f"x{n}" for n in tree.nodes()})
    results = fdb.match_against_db(target)

    assert [r['name'] for r in results][0] == 'tree'
    assert results[0]['score'] == 100.0
    assert results[0]['matched_pct'] == 100.0
    assert results[1]['score'] < results[0]['score']


def test_match_empty_db(tmp_db):
    assert fdb.match_against_db(nx.path_graph(3, create_using=nx.DiGraph)) == []
