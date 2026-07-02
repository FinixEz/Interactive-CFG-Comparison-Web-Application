"""
Offline binary -> CFG JSON extraction via angr.

Closes the manual-preprocessing gap for the web app, which only accepts
assembly source or pre-computed CFG JSON, never compiled binaries -- see
Home/CFG Project/05 - Improvement Backlog.md (item #4) for why this stays
offline-only: Render's free tier can't run angr at all (z3-solver already
timed out the build once, see requirements-production.txt / commit
bb565e3), and there's no request-isolation infrastructure in this repo to
safely run a multi-minute, memory-heavy analysis in a web request.

Usage:
    python binary_to_cfg.py SAMPLE.exe                  # writes SAMPLE.json
    python binary_to_cfg.py SAMPLE.exe -o out.json
    python binary_to_cfg.py SAMPLE.exe --timeout 600

Then upload the resulting .json through the web app (Compare, Inspect, or
register it as an Identify baseline) exactly like the seeded theZoo
fingerprints already work.

Needs the full requirements.txt (angr and friends), not the lean
requirements-production.txt the web app deploys with:
    pip install -r requirements.txt
"""
import argparse
import json
import os
import signal
import sys

from networkx.readwrite import json_graph

from convertpkltojson import serialize_graph


class AnalysisTimeout(Exception):
    pass


def _timeout_handler(signum, frame):
    raise AnalysisTimeout


def extract_cfg(binary_path, timeout=300):
    """
    Run angr's CFGFast over `binary_path` and return the resulting
    networkx graph.

    Raises AnalysisTimeout if analysis exceeds `timeout` seconds -- CFGFast
    has no built-in cap, and malware samples are exactly the kind of
    adversarial input that can trigger pathological analysis time even
    offline. Unix-only (signal.alarm); fine for this project's Linux/Docker
    deployment target.
    """
    import angr  # deferred: keeps --help and argument-error paths fast,
                 # and means they work without the heavy stack installed

    old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
    signal.alarm(timeout)
    try:
        project = angr.Project(binary_path, auto_load_libs=False)
        cfg = project.analyses.CFGFast()
        return cfg.graph
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)


def write_cfg_json(graph, output_path):
    """
    Serialize a CFG graph to the node-link JSON format the web app's
    load_cfg_json() expects -- same serialization convertpkltojson.py
    already uses for its pickle-to-JSON path, reused here rather than
    duplicated.
    """
    clean = serialize_graph(graph)
    data = json_graph.node_link_data(clean)
    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description='Extract a control-flow graph from a compiled binary via angr, '
                     'writing CFG//DIFF-compatible JSON.',
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('binary', help='Path to the compiled binary (PE/ELF/etc.)')
    parser.add_argument('-o', '--output', help='Output JSON path (default: <binary>.json)')
    parser.add_argument('--timeout', type=int, default=300,
                        help='Max seconds for CFG analysis (default: 300)')
    args = parser.parse_args()

    if not os.path.isfile(args.binary):
        parser.error(f'{args.binary}: no such file')

    output_path = args.output or os.path.splitext(args.binary)[0] + '.json'

    print(f'Loading {args.binary} into angr (auto_load_libs=False)...')
    try:
        graph = extract_cfg(args.binary, timeout=args.timeout)
    except AnalysisTimeout:
        print(f'Error: CFG analysis exceeded {args.timeout}s -- try a longer '
              f'--timeout, or this binary may be adversarial/pathological '
              f'input for angr.', file=sys.stderr)
        sys.exit(1)

    print(f'CFG recovered: {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges')
    write_cfg_json(graph, output_path)
    print(f'Wrote {output_path} -- upload this through the web app '
          f'(Compare, Inspect, or register as an Identify baseline)')


if __name__ == '__main__':
    main()
