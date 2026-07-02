"""
Empirical calibration of VERDICT_TIERS (webapp/app.py) against
structural_similarity() score behavior.

The repo has no genuine "two variants of the same malware family" pair --
the only independent real-malware samples are anthrax/whore/relock, three
mutually unrelated families (see Home/CFG Project/05 - Improvement
Backlog.md, item #5, for why theZoo doesn't have a usable substitute: its
disassembled-source category has no same-family duplicates, and same-family
entries elsewhere are almost certainly VB/Delphi source this project's
assembly parser can't read).

So thresholds are calibrated via controlled synthetic perturbation instead:
take each of the 4 locally-available CFGs as a base, generate variants at
increasing edit-distance levels (composite of node drops, edge drops, edge
adds, and small grafted branches -- the kinds of change a real "evolved"
variant would plausibly show), and measure how the WL structural-similarity
score decays. Every perturbed variant also has all nodes renamed, forcing
pure structural comparison -- matching real-world usage, where CFG node IDs
are address-based and never coincide across different builds.

The three genuinely-unrelated real-malware pairs (anthrax x whore, anthrax
x relock, whore x relock) are computed as an independent "these should
score near zero" anchor alongside the synthetic curves.

Run (needs matplotlib/numpy, not in the lean venv -- see requirements.txt):
    source venv/bin/activate && pip install matplotlib numpy
    python calibrate_thresholds.py
Writes calibration_results.csv and calibration_curve.png to the repo root.
"""
import csv
import random
import statistics
import sys

import networkx as nx

sys.path.insert(0, 'webapp')
from visualize_compare import load_cfg_json, structural_similarity  # noqa: E402

BASES = ['anthrax', 'whore', 'relock', 'Bodmasv2']
LEVELS = [0.0, 0.05, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
TRIALS = 15
UNRELATED_PAIRS = [('anthrax', 'whore'), ('anthrax', 'relock'), ('whore', 'relock')]


def perturb(G, level, rng):
    """
    Return a structurally-perturbed, fully-renamed copy of G at the given
    edit-distance level (0.0 = same structure, ~1.0 = heavily rewritten).
    """
    H = G.copy()

    # 1. Drop some nodes (and their incident edges)
    nodes = list(H.nodes())
    drop_n = int(len(nodes) * level * 0.3)
    for node in rng.sample(nodes, min(drop_n, max(len(nodes) - 1, 0))):
        if node in H:
            H.remove_node(node)

    # 2. Drop some remaining edges
    edges = list(H.edges())
    drop_e = int(len(edges) * level * 0.4)
    for u, v in rng.sample(edges, min(drop_e, len(edges))):
        if H.has_edge(u, v):
            H.remove_edge(u, v)

    # 3. Add random edges (noise / rewired control flow)
    remaining = list(H.nodes())
    add_e = int(len(edges) * level * 0.3)
    for _ in range(add_e):
        if len(remaining) >= 2:
            u, v = rng.sample(remaining, 2)
            H.add_edge(u, v)

    # 4. Graft small branches (simulate added functionality)
    graft_count = max(1, int(level * 6)) if level > 0 else 0
    for i in range(graft_count):
        if not remaining:
            break
        attach = rng.choice(remaining)
        new_node = f'__grafted_{i}_{rng.randint(0, 10**9)}'
        H.add_node(new_node)
        H.add_edge(attach, new_node)
        remaining.append(new_node)

    # 5. Rename every node -- forces pure structural (name-independent)
    # comparison, matching how the app actually falls back to WL matching
    # once name overlap is low (see NAME_OVERLAP_THRESHOLD in app.py).
    mapping = {node: f'n{i}' for i, node in enumerate(H.nodes())}
    return nx.relabel_nodes(H, mapping)


def main():
    baseline_graphs = {name: load_cfg_json(f'webapp/baselines/{name}.json') for name in BASES}
    for name, G in baseline_graphs.items():
        print(f'{name}: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges')

    rows = []
    curve = {name: {} for name in BASES}
    for name, G in baseline_graphs.items():
        for level in LEVELS:
            scores = []
            for trial in range(TRIALS):
                rng = random.Random(f'{name}|{level}|{trial}')
                H = perturb(G, level, rng)
                if H.number_of_nodes() == 0:
                    continue
                s = structural_similarity(G, H)
                scores.append(s['score'] * 100)
            mean = statistics.fmean(scores) if scores else 0.0
            stdev = statistics.pstdev(scores) if len(scores) > 1 else 0.0
            curve[name][level] = (mean, stdev)
            rows.append({'base': name, 'level': level, 'mean_score': round(mean, 2),
                         'stdev': round(stdev, 2), 'n_trials': len(scores)})
            print(f'  {name} @ level {level:.2f}: {mean:5.1f}% (+/- {stdev:4.1f}, n={len(scores)})')

    print()
    unrelated = {}
    for a, b in UNRELATED_PAIRS:
        s = structural_similarity(baseline_graphs[a], baseline_graphs[b])
        unrelated[f'{a}x{b}'] = s['score'] * 100
        print(f'unrelated pair {a} x {b}: {s["score"] * 100:.2f}%')

    with open('calibration_results.csv', 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['base', 'level', 'mean_score', 'stdev', 'n_trials'])
        writer.writeheader()
        writer.writerows(rows)
        for pair, score in unrelated.items():
            writer.writerow({'base': pair, 'level': 'unrelated', 'mean_score': round(score, 2),
                             'stdev': 0, 'n_trials': 1})
    print('\nWrote calibration_results.csv')

    try:
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(9, 6))
        for name in BASES:
            xs = [lvl * 100 for lvl in LEVELS]
            ys = [curve[name][lvl][0] for lvl in LEVELS]
            errs = [curve[name][lvl][1] for lvl in LEVELS]
            ax.errorbar(xs, ys, yerr=errs, marker='o', capsize=3, label=name)
        unrelated_max = max(unrelated.values())
        ax.axhline(unrelated_max, color='red', linestyle='--', alpha=0.6,
                   label=f'unrelated-pair ceiling ({unrelated_max:.1f}%)')
        for pair, score in unrelated.items():
            ax.scatter([0], [score], color='red', marker='x', s=60, zorder=5)
        ax.set_xlabel('Perturbation level (%)')
        ax.set_ylabel('Structural similarity score (%)')
        ax.set_title('WL structural similarity vs. synthetic edit distance')
        ax.legend()
        ax.grid(alpha=0.3)
        fig.tight_layout()
        fig.savefig('calibration_curve.png', dpi=150)
        print('Wrote calibration_curve.png')
    except ImportError:
        print('matplotlib not installed -- skipped plot, CSV still written')


if __name__ == '__main__':
    main()
