import io
import json
import os
import re

import pytest

import app as webapp


@pytest.fixture()
def client():
    webapp.app.config['TESTING'] = True
    with webapp.app.test_client() as c:
        yield c


def _json_file(nodes, edges):
    return io.BytesIO(json.dumps({'nodes': nodes, 'edges': edges}).encode())


def test_index_get(client):
    assert client.get('/').status_code == 200


def test_sample_comparison(client):
    r = client.post('/', data={'sample': '1'})
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert 'structural similarity' in body
    assert 'combined_' in body


def test_inspector_sample(client):
    r = client.post('/inspect', data={'sample': '1'})
    assert r.status_code == 200
    assert 'cfg_' in r.get_data(as_text=True)


def test_inspector_rejects_non_assembly(client):
    r = client.post('/inspect', data={'assembly_file': (io.BytesIO(b'{}'), 'g.json')},
                    content_type='multipart/form-data')
    assert b'Only assembly files' in r.data


def test_upload_comparison_and_legend_escaping(client):
    r = client.post('/', data={
        'graph1': (_json_file(['a', 'b'], [['a', 'b']]), 'evil<script>x.json'),
        'graph2': (_json_file(['a', 'c'], [['a', 'c']]), 'other.json'),
    }, content_type='multipart/form-data')
    assert r.status_code == 200
    body = r.get_data(as_text=True)

    m = re.search(r'(combined_[0-9a-f]+\.html)', body)
    assert m, "response references no generated graph"
    with open(os.path.join(webapp.STATIC_DIR, m.group(1))) as f:
        generated = f.read()
    # The legend must carry the escaped filename, never the raw one
    assert 'evil<script>' not in generated
    assert 'evil&lt;script&gt;' in generated


def test_large_graph_render_is_capped(client, monkeypatch):
    monkeypatch.setattr(webapp, 'MAX_VIS_NODES', 5)
    nodes = [f'n{i}' for i in range(12)]
    edges = [[f'n{i}', f'n{i + 1}'] for i in range(11)]
    r = client.post('/', data={
        'graph1': (_json_file(nodes, edges), 'a.json'),
        'graph2': (_json_file(nodes, edges), 'b.json'),
    }, content_type='multipart/form-data')
    assert r.status_code == 200
    assert 'most important' in r.get_data(as_text=True)
