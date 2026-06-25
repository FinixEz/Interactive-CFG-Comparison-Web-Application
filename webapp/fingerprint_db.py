"""
Baseline fingerprint database for single-file identification.

Baselines are CFGs stored as NetworkX node-link JSON files under
BASELINE_DIR — derived structural data only, never sample sources, so the
repository can carry fingerprints of malware without carrying malware.
Matching reuses the WL-fingerprint structural_similarity, so identification
holds across renamed labels and different address spaces.
"""
import json
import os
import re

from networkx.readwrite import json_graph

from visualize_compare import load_cfg_json, structural_similarity

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BASELINE_DIR = os.environ.get('BASELINE_DIR', os.path.join(BASE_DIR, 'baselines'))


def _slug(name):
    """Filesystem-safe baseline name."""
    name = re.sub(r'[^A-Za-z0-9._-]+', '_', name).strip('._')
    return name or 'baseline'


def list_baselines():
    """
    Return [{'name', 'slug', 'path', 'nodes', 'edges', 'graph'}] sorted by name.
    Unreadable files are skipped.
    """
    entries = []
    if not os.path.isdir(BASELINE_DIR):
        return entries
    for fn in sorted(os.listdir(BASELINE_DIR)):
        if not fn.endswith('.json'):
            continue
        path = os.path.join(BASELINE_DIR, fn)
        try:
            G = load_cfg_json(path)
        except Exception:
            continue
        slug = fn[:-5]
        entries.append({'name': slug, 'slug': slug, 'path': path, 'graph': G,
                        'nodes': G.number_of_nodes(),
                        'edges': G.number_of_edges()})
    return entries


def add_baseline(name, G):
    """Store a graph as a named baseline; returns the slug used."""
    os.makedirs(BASELINE_DIR, exist_ok=True)
    slug = _slug(name)
    data = json_graph.node_link_data(G, edges='links')
    with open(os.path.join(BASELINE_DIR, slug + '.json'), 'w') as f:
        json.dump(data, f)
    return slug


def match_against_db(G):
    """
    Rank every baseline by structural similarity against G.

    Returns a list sorted by score (percent, desc) of dicts:
    {'name', 'path', 'nodes', 'edges', 'score', 'matched', 'matched_pct'}
    where matched counts G's nodes whose control-flow pattern also occurs
    in the baseline.
    """
    n = G.number_of_nodes()
    results = []
    for entry in list_baselines():
        s = structural_similarity(G, entry['graph'])
        matched = len(s['matched_nodes_1'])
        results.append({
            'name': entry['name'],
            'path': entry['path'],
            'nodes': entry['nodes'],
            'edges': entry['edges'],
            'score': round(s['score'] * 100, 1),
            'matched': matched,
            'matched_pct': round(100 * matched / n, 1) if n else 0.0,
        })
    results.sort(key=lambda r: r['score'], reverse=True)
    return results


def delete_baseline(slug):
    """Remove a baseline file by slug. Raises FileNotFoundError if missing."""
    path = os.path.join(BASELINE_DIR, _slug(slug) + '.json')
    if os.path.exists(path):
        os.remove(path)
    else:
        raise FileNotFoundError(f"Baseline '{slug}' not found")
