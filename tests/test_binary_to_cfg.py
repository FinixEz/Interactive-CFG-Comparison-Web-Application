import networkx as nx
import pytest

from binary_to_cfg import write_cfg_json
from visualize_compare import load_cfg_json


def test_write_cfg_json_round_trips_and_loads(tmp_path):
    G = nx.DiGraph()
    G.add_node('main', size=42)
    G.add_node('exit')
    G.add_edge('main', 'exit', jumpkind='Ijk_Boring')

    out = tmp_path / 'out.json'
    write_cfg_json(G, str(out))

    loaded = load_cfg_json(str(out))
    assert set(loaded.nodes()) == {'main', 'exit'}
    assert loaded.has_edge('main', 'exit')
    assert loaded.nodes['main']['size'] == 42


def test_write_cfg_json_stringifies_non_serializable_node_keys(tmp_path):
    # Real angr CFGFast graphs key nodes by CFGNode objects, not plain
    # strings -- serialize_graph() (reused from convertpkltojson.py) must
    # convert those to strings or json.dump blows up.
    class FakeCFGNode:
        def __init__(self, addr):
            self.addr = addr

        def __str__(self):
            return f'<CFGNode 0x{self.addr:x}>'

    G = nx.DiGraph()
    a, b = FakeCFGNode(0x1000), FakeCFGNode(0x1010)
    G.add_node(a)
    G.add_node(b)
    G.add_edge(a, b)

    out = tmp_path / 'out.json'
    write_cfg_json(G, str(out))  # must not raise

    loaded = load_cfg_json(str(out))
    assert loaded.number_of_nodes() == 2
    assert loaded.number_of_edges() == 1


def test_extract_cfg_rejects_missing_file():
    angr = pytest.importorskip('angr')
    from binary_to_cfg import extract_cfg

    with pytest.raises(Exception):
        extract_cfg('/no/such/binary/exists')
