import io
import json
import os
import re

import pytest

import app as webapp


@pytest.fixture()
def client():
    webapp.app.config['TESTING'] = True
    webapp.limiter.reset()
    with webapp.app.test_client() as c:
        yield c


def _json_file(nodes, edges):
    return io.BytesIO(json.dumps({'nodes': nodes, 'edges': edges}).encode())


def test_index_get(client):
    assert client.get('/').status_code == 200


def test_security_headers_present(client):
    r = client.get('/')
    assert r.headers.get('X-Content-Type-Options') == 'nosniff'
    assert r.headers.get('X-Frame-Options') == 'SAMEORIGIN'
    assert r.headers.get('Referrer-Policy') == 'strict-origin-when-cross-origin'
    csp = r.headers.get('Content-Security-Policy')
    assert csp is not None
    assert "default-src 'self'" in csp
    assert 'cdnjs.cloudflare.com' in csp
    assert 'cdn.jsdelivr.net' in csp
    assert "frame-ancestors 'self'" in csp
    assert "object-src 'none'" in csp


def test_security_headers_on_404(client):
    r = client.get('/this-route-does-not-exist')
    assert r.status_code == 404
    assert r.headers.get('X-Content-Type-Options') == 'nosniff'
    assert r.headers.get('Content-Security-Policy') is not None


def test_theme_toggle_has_accessible_name(client):
    body = client.get('/').get_data(as_text=True)
    assert 'aria-label="Toggle dark mode"' in body
    assert 'aria-pressed=' in body


def test_dropzone_inputs_have_accessible_names(client):
    body = client.get('/').get_data(as_text=True)
    assert 'aria-label="Graph 1 file"' in body
    assert 'aria-label="Graph 2 file"' in body


def test_similarity_meter_is_a_progressbar(client):
    r = client.post('/', data={'sample': '1'})
    body = r.get_data(as_text=True)
    assert 'role="progressbar"' in body
    assert 'aria-valuenow=' in body


def test_combined_graph_iframe_has_accessible_title(client):
    r = client.post('/', data={'sample': '1'})
    body = r.get_data(as_text=True)
    assert 'title="Combined Graph Visualization"' in body


def test_sample_comparison(client):
    r = client.post('/', data={'sample': '1'})
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert 'structural similarity' in body
    assert 'combined_' in body


def test_compare_page_has_download_buttons(client):
    r = client.post('/', data={'sample': '1'})
    body = r.get_data(as_text=True)
    assert '/download-graph/combined_' in body
    assert "downloadReport('report-data'" in body

    m = re.search(r'<script type="application/json" id="report-data">(.*?)</script>', body, re.S)
    assert m, "report-data JSON blob not found"
    data = json.loads(m.group(1))
    assert data['filename1'] == 'Bodmasv2.json'
    assert data['filename2'] == 'mocking.json'
    assert 'structural_score' in data
    assert 'top_nodes' in data


def test_download_graph_route_forces_attachment(client):
    r = client.post('/', data={'sample': '1'})
    m = re.search(r'/download-graph/(combined_[0-9a-f]+\.html)', r.get_data(as_text=True))
    assert m, "no download-graph link in the response"

    dl = client.get(f'/download-graph/{m.group(1)}')
    assert dl.status_code == 200
    disposition = dl.headers.get('Content-Disposition', '')
    assert 'attachment' in disposition
    assert 'cfg-diff-graph.html' in disposition


def test_download_graph_route_rejects_arbitrary_filenames(client):
    # Only the app's own generated combined_/cfg_<hex>.html names are
    # servable -- anything else (path traversal, other static assets,
    # made-up names) must 404, not fall through to STATIC_DIR.
    for bad in ['../app.py', '..%2F..%2Fapp.py', 'style.css',
                'combined_deadbeef.txt', 'combined_not-hex.html',
                'cfg_' + 'a' * 40 + '.html']:
        assert client.get(f'/download-graph/{bad}').status_code == 404


def test_download_graph_route_404_for_nonexistent_file(client):
    # Well-formed name, matches the pattern, but was never generated
    assert client.get('/download-graph/combined_deadbeef.html').status_code == 404


def test_compare_report_json_is_safe_inside_script_tag(client):
    # tojson must escape '<'/'>'/'&' for <script> context -- plain HTML
    # escaping (used for the legend) is not sufficient here, since '&lt;'
    # would still read as a literal '<' once parsed as JS/JSON text.
    r = client.post('/', data={
        'graph1': (_json_file(['a', 'b'], [['a', 'b']]), 'evil</script><script>x.json'),
        'graph2': (_json_file(['a', 'c'], [['a', 'c']]), 'other.json'),
    }, content_type='multipart/form-data')
    assert r.status_code == 200
    body = r.get_data(as_text=True)

    m = re.search(r'<script type="application/json" id="report-data">(.*?)</script>', body, re.S)
    assert m
    assert '</script>' not in m.group(1)
    data = json.loads(m.group(1))
    assert data['filename1'] == 'evil</script><script>x.json'


def test_inspector_sample(client):
    r = client.post('/inspect', data={'sample': '1'})
    assert r.status_code == 200
    assert 'cfg_' in r.get_data(as_text=True)


def test_inspector_rejects_non_assembly(client):
    r = client.post('/inspect', data={'assembly_file': (io.BytesIO(b'{}'), 'g.json')},
                    content_type='multipart/form-data')
    assert b'Only assembly files' in r.data


def test_inspector_cfg_iframe_has_accessible_title(client):
    r = client.post('/inspect', data={'sample': '1'})
    body = r.get_data(as_text=True)
    assert 'title="Control-flow graph visualization"' in body


def test_inspector_has_download_link(client):
    r = client.post('/inspect', data={'sample': '1'})
    body = r.get_data(as_text=True)
    assert '/download-graph/cfg_' in body


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


def test_identify_page_lists_baselines(client):
    r = client.get('/identify')
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert 'fingerprint database' in body
    # baseline delete buttons must have a name-specific accessible label,
    # not just a bare icon/word that's ambiguous outside the table row
    assert 'aria-label="Delete baseline' in body


def test_identify_match_report_meter_is_a_progressbar(client):
    r = client.post('/identify', data={'sample': '1'})
    body = r.get_data(as_text=True)
    assert 'role="progressbar"' in body
    assert 'aria-valuenow=' in body


def test_identify_page_has_download_buttons(client):
    r = client.post('/identify', data={'sample': '1'})
    body = r.get_data(as_text=True)

    # match-report export
    assert "downloadReport('match-report-data'" in body
    m = re.search(r'<script type="application/json" id="match-report-data">(.*?)</script>', body, re.S)
    assert m, "match-report-data JSON blob not found"
    match_data = json.loads(m.group(1))
    assert match_data['target'] == 'anthrax.asm'
    assert len(match_data['results']) >= 1
    # internal server filesystem path must not leak into the export
    assert not any('path' in r for r in match_data['results'])
    assert all('verdict' in r for r in match_data['results'])

    # best-match comparison export (anthrax sample scores 'strong' -- 0 --
    # so build_comparison runs and this section renders)
    assert '/download-graph/combined_' in body
    assert "downloadReport('comparison-report-data'" in body
    m2 = re.search(r'<script type="application/json" id="comparison-report-data">(.*?)</script>', body, re.S)
    assert m2, "comparison-report-data JSON blob not found"
    comparison_data = json.loads(m2.group(1))
    assert 'structural_score' in comparison_data


def test_identify_sample_matches_anthrax_baseline(client):
    r = client.post('/identify', data={'sample': '1'})
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    # The sample is anthrax.asm and the seeded DB contains its fingerprint:
    # it must be reported as a strong match
    assert 'anthrax' in body
    assert 'strong' in body


def test_register_baseline(client, monkeypatch, tmp_path):
    import fingerprint_db as fdb
    monkeypatch.setattr(fdb, 'BASELINE_DIR', str(tmp_path))
    r = client.post('/identify', data={
        'register': '1',
        'baseline_name': 'tiny',
        'baseline_file': (_json_file(['a', 'b'], [['a', 'b']]), 't.json'),
    }, content_type='multipart/form-data')
    assert r.status_code == 200
    assert b'registered' in r.data
    assert (tmp_path / 'tiny.json').exists()


def test_delete_baseline(client, monkeypatch, tmp_path):
    import fingerprint_db as fdb
    monkeypatch.setattr(fdb, 'BASELINE_DIR', str(tmp_path))
    fdb.add_baseline('tiny', webapp.nx.DiGraph([('a', 'b')]))
    assert (tmp_path / 'tiny.json').exists()

    r = client.post('/identify', data={'delete': 'tiny'})
    assert r.status_code == 200
    assert b'deleted' in r.data
    assert not (tmp_path / 'tiny.json').exists()


def test_admin_token_blocks_unauthorized_mutation(client, monkeypatch, tmp_path):
    import fingerprint_db as fdb
    monkeypatch.setattr(fdb, 'BASELINE_DIR', str(tmp_path))
    monkeypatch.setattr(webapp, 'ADMIN_TOKEN', 'secret123')

    r = client.post('/identify', data={
        'register': '1',
        'baseline_name': 'tiny',
        'baseline_file': (_json_file(['a', 'b'], [['a', 'b']]), 't.json'),
    }, content_type='multipart/form-data')
    assert r.status_code == 403
    assert not (tmp_path / 'tiny.json').exists()


def test_admin_token_allows_authorized_mutation(client, monkeypatch, tmp_path):
    import fingerprint_db as fdb
    monkeypatch.setattr(fdb, 'BASELINE_DIR', str(tmp_path))
    monkeypatch.setattr(webapp, 'ADMIN_TOKEN', 'secret123')

    r = client.post('/identify', data={
        'register': '1',
        'token': 'secret123',
        'baseline_name': 'tiny',
        'baseline_file': (_json_file(['a', 'b'], [['a', 'b']]), 't.json'),
    }, content_type='multipart/form-data')
    assert r.status_code == 200
    assert (tmp_path / 'tiny.json').exists()


def test_identify_mutation_rate_limited(client, monkeypatch, tmp_path):
    import fingerprint_db as fdb
    monkeypatch.setattr(fdb, 'BASELINE_DIR', str(tmp_path))

    for _ in range(5):
        r = client.post('/identify', data={'delete': 'nonexistent'})
        assert r.status_code == 200

    r = client.post('/identify', data={'delete': 'nonexistent'})
    assert r.status_code == 429


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


def test_500_handler_renders_route_specific_template():
    with webapp.app.test_request_context('/inspect'):
        body, status = webapp.internal_error(Exception('boom'))
        assert status == 500
        assert 'Assembly Inspector' in body

    with webapp.app.test_request_context('/identify'):
        body, status = webapp.internal_error(Exception('boom'))
        assert status == 500
        assert 'Identify' in body

    with webapp.app.test_request_context('/'):
        body, status = webapp.internal_error(Exception('boom'))
        assert status == 500
        assert 'Compare' in body
