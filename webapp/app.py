from flask import Flask, render_template, request, jsonify, flash, send_from_directory, abort
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from visualize_compare import (load_cfg_json, compare_graphs, add_legend_to_html,
                               compute_node_importance, structural_similarity,
                               apply_dark_chrome)
from asm_parser import parse_assembly_file
from fingerprint_db import list_baselines, add_baseline, match_against_db
from pyvis.network import Network
import networkx as nx
from werkzeug.utils import secure_filename
import os
import logging
import re
import time
import glob

# Anchor all paths to this file's directory so the app works from any CWD
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, 'static')

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_DEV_SECRET_KEY = 'dev-secret-key-change-in-production'

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', _DEV_SECRET_KEY)
if app.secret_key == _DEV_SECRET_KEY and os.environ.get('FLASK_ENV') == 'production':
    logger.error(
        "SECRET_KEY is unset — running production with the public dev default. "
        "Set SECRET_KEY in the environment.")
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['UPLOAD_FOLDER'] = os.environ.get('UPLOAD_FOLDER', os.path.join(BASE_DIR, 'uploads'))
ALLOWED_EXTENSIONS = {'json', 's', 'asm'}
ASSEMBLY_EXTENSIONS = {'s', 'asm'}

# In-memory storage: per-worker, not shared across gunicorn processes — good
# enough to blunt casual scripted abuse of the baseline DB, not a hard cap.
limiter = Limiter(get_remote_address, app=app, storage_uri="memory://",
                   default_limits=[])

# If set, /identify register+delete require this token (?token=... or
# X-Admin-Token header); unset means the routes stay open (dev default).
ADMIN_TOKEN = os.environ.get('ADMIN_TOKEN')


def _admin_authorized():
    if not ADMIN_TOKEN:
        return True
    supplied = request.headers.get('X-Admin-Token') or request.form.get('token')
    return supplied == ADMIN_TOKEN

# vis.js degrades badly past ~1-2k nodes; cap what we render (stats are
# always computed on the full graphs)
MAX_VIS_NODES = int(os.environ.get('MAX_VIS_NODES', 800))

# Below this name overlap (fraction of the smaller graph) node names are
# considered unrelated (e.g. address-based IDs from different binaries) and
# shared/unique classification falls back to structural matching
NAME_OVERLAP_THRESHOLD = float(os.environ.get('NAME_OVERLAP_THRESHOLD', 0.05))

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)

# PyVis (cdn_resources='remote') loads vis-network/tom-select from cdnjs and
# Bootstrap from jsdelivr, then embeds the actual graph data and dark-theme
# overrides as inline <script>/<style> in the generated HTML -- so script-src
# and style-src need 'unsafe-inline' plus both CDN hosts, or the combined
# graph iframe renders blank. Escaping of user-controlled filenames (upload
# names embedded in that HTML) happens separately in add_legend_to_html().
_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com https://cdn.jsdelivr.net https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com; "
    "img-src 'self' data:; "
    "connect-src 'self'; "
    "frame-src 'self'; "
    "frame-ancestors 'self'; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "form-action 'self'"
)


@app.after_request
def set_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    # SAMEORIGIN, not DENY: the compare/identify pages embed the generated
    # graph HTML in a same-origin <iframe>, which DENY would also block.
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Content-Security-Policy'] = _CSP
    return response


def cleanup_old_cfg_files(max_age_hours=1):
    """
    Remove old CFG HTML files from static directory.
    
    Args:
        max_age_hours: Maximum age in hours before files are deleted
    """
    try:
        patterns = [os.path.join(STATIC_DIR, 'cfg_*.html'),
                    os.path.join(STATIC_DIR, 'combined_*.html')]
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600

        for filepath in [f for p in patterns for f in glob.glob(p)]:
            file_age = current_time - os.path.getmtime(filepath)
            if file_age > max_age_seconds:
                try:
                    os.remove(filepath)
                    logger.info(f"Cleaned up old CFG file: {filepath}")
                except Exception as e:
                    logger.warning(f"Failed to remove {filepath}: {e}")
    except Exception as e:
        logger.error(f"Error during CFG cleanup: {e}")


def allowed_file(filename, allowed=ALLOWED_EXTENSIONS):
    """Check if file has allowed extension"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed


def decode_bytes(content_bytes):
    """Decode raw bytes trying several encodings, replacing on failure."""
    for encoding in ['utf-8', 'latin-1', 'cp1252']:
        try:
            return content_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content_bytes.decode('utf-8', errors='replace')


def truncate_to_important(G, importance, max_nodes=None):
    """
    Reduce a graph to its max_nodes most important nodes for rendering.

    Returns (subgraph, dropped_count); dropped_count is 0 when no cap applied.
    """
    max_nodes = max_nodes or MAX_VIS_NODES
    n = G.number_of_nodes()
    if n <= max_nodes:
        return G, 0
    keep = sorted(G.nodes(), key=lambda node: importance[node]['score'],
                  reverse=True)[:max_nodes]
    return G.subgraph(keep), n - max_nodes


def generate_cfg_visualization(G):
    """
    Render a CFG as an interactive PyVis HTML file in the static directory.

    Returns the generated filename (relative to static/).
    """
    # Node-importance classification (betweenness/degree centrality)
    importance = compute_node_importance(G)

    G, dropped = truncate_to_important(G, importance)
    if dropped:
        flash(f"Large graph: showing the {G.number_of_nodes()} most important "
              f"nodes ({dropped} hidden)", "warning")

    net = Network(height="600px", width="100%", bgcolor="#0e131b",
                  font_color="#d7e0ec", directed=True, cdn_resources='remote')
    net.from_nx(G)

    # Configure hierarchical layout (waterfall/top-down)
    net.set_options("""
    {
      "layout": {
        "hierarchical": {
          "enabled": true,
          "direction": "UD",
          "sortMethod": "directed",
          "nodeSpacing": 150,
          "levelSeparation": 200,
          "treeSpacing": 200
        }
      },
      "physics": {
        "enabled": false
      },
      "edges": {
        "smooth": {
          "type": "cubicBezier",
          "forceDirection": "vertical"
        }
      }
    }
    """)

    # Style nodes and edges with line number metadata
    for node in net.nodes:
        node['shape'] = 'box'
        node['font'] = {'face': 'monospace', 'align': 'left', 'color': '#d7e0ec'}

        node_id = node['id']

        # Importance tier shown via border color/width
        imp = importance.get(node_id, {'score': 0.0, 'tier': 'normal'})
        if imp['tier'] == 'critical':
            node['color'] = {'background': '#223049', 'border': '#ff5d5d'}
            node['borderWidth'] = 3
        elif imp['tier'] == 'high':
            node['color'] = {'background': '#223049', 'border': '#ffa94d'}
            node['borderWidth'] = 2
        else:
            node['color'] = {'background': '#223049', 'border': '#41557a'}

        # Add line number metadata from NetworkX graph
        if node_id in G.nodes:
            node_data = G.nodes[node_id]
            start_line = node_data.get('start_line', -1)
            end_line = node_data.get('end_line', -1)

            # Add to title for visibility
            lines_info = f"Lines {start_line}-{end_line}" if start_line >= 0 else "No line info"
            node['title'] = (f"{node_id}\n{lines_info}\n"
                             f"Importance: {imp['tier']} (score {imp['score']:.2f})")

            # Store as custom data for JavaScript access
            node['start_line'] = start_line
            node['end_line'] = end_line

    for edge in net.edges:
        edge['color'] = '#46546b'
        edge['arrows'] = 'to'

    # Clean up old CFG files before generating new one
    cleanup_old_cfg_files(max_age_hours=1)

    # Save CFG visualization
    output_filename = f"cfg_{os.urandom(4).hex()}.html"
    output_path = os.path.join(STATIC_DIR, output_filename)
    net.save_graph(output_path)
    apply_dark_chrome(output_path)

    # Inject interactive JavaScript for node clicking
    inject_cfg_interaction_js(output_path)

    return output_filename


def detect_file_type(filepath):
    """Detect if file is JSON or assembly based on extension"""
    ext = filepath.rsplit('.', 1)[1].lower() if '.' in filepath else ''
    if ext == 'json':
        return 'json'
    elif ext in ['s', 'asm']:
        return 'assembly'
    return 'unknown'


def load_graph_from_file(filepath):
    """Load graph from either JSON or assembly file"""
    file_type = detect_file_type(filepath)
    
    if file_type == 'json':
        return load_cfg_json(filepath)
    elif file_type == 'assembly':
        return parse_assembly_file(filepath)
    else:
        raise ValueError(f"Unsupported file type: {file_type}")


def validate_graph_file(filepath):
    """Validate that the file is a valid graph (JSON or assembly)"""
    try:
        graph = load_graph_from_file(filepath)
        if graph is None or len(graph.nodes()) == 0:
            return False, "Graph file is empty or invalid"
        return True, None
    except Exception as e:
        return False, f"Invalid graph file: {str(e)}"


def inject_cfg_interaction_js(html_path):
    """
    Inject JavaScript into PyVis HTML to enable node click interaction.
    This allows the CFG to communicate with the parent window for code highlighting.
    """
    try:
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        # JavaScript to inject - captures node clicks and sends data to parent
        interaction_js = """
        <script type="text/javascript">
        // Add click event listener to network
        network.on("click", function(params) {
            if (params.nodes.length > 0) {
                var nodeId = params.nodes[0];
                var nodeData = nodes.get(nodeId);
                
                // Extract line number data
                var startLine = nodeData.start_line;
                var endLine = nodeData.end_line;
                
                // Send message to parent window
                if (window.parent && startLine !== undefined && startLine >= 0) {
                    window.parent.postMessage({
                        type: 'cfg_node_click',
                        nodeId: nodeId,
                        startLine: startLine,
                        endLine: endLine
                    }, '*');
                }
            }
        });
        </script>
        """
        
        # Inject before closing body tag
        if '</body>' in html_content:
            html_content = html_content.replace('</body>', interaction_js + '\n</body>')
        else:
            # Fallback: append to end
            html_content += interaction_js
        
        # Write back
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return True
    except Exception as e:
        logger.error(f"Error injecting JavaScript into CFG HTML: {e}")
        return False


_GRAPH_FILENAME_RE = re.compile(r'^(combined|cfg)_[0-9a-f]{8}\.html$')


@app.route("/download-graph/<path:filename>")
def download_graph(filename):
    """
    Force-download a generated graph HTML file with a friendly name.

    The plain /static/ URL (used by the viewer <iframe>) stays inline; this
    route sets Content-Disposition: attachment, which every browser honors
    reliably -- unlike the client-side `download` HTML attribute, which
    Firefox does not consistently respect for same-origin text/html
    responses. Restricted to the exact combined_/cfg_<hex>.html filenames
    this app generates (see build_comparison/generate_cfg_visualization),
    so this can't be used to fetch arbitrary files from STATIC_DIR.
    """
    if not _GRAPH_FILENAME_RE.match(filename):
        abort(404)
    friendly = 'cfg-diff-graph.html' if filename.startswith('combined_') else 'cfg-inspector-graph.html'
    if not os.path.isfile(os.path.join(STATIC_DIR, filename)):
        abort(404)
    return send_from_directory(STATIC_DIR, filename, as_attachment=True, download_name=friendly)


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        # Check if using sample data
        if 'sample' in request.form:
            return process_graphs(
                os.path.join(STATIC_DIR, "Bodmasv2.json"),
                os.path.join(STATIC_DIR, "mocking.json"),
                cleanup=False,
                filename1="Bodmasv2.json",
                filename2="mocking.json"
            )
        
        # Validate file uploads
        if 'graph1' not in request.files or 'graph2' not in request.files:
            flash("Please upload both graph files", "error")
            return render_template("index.html", visualized=False)
        
        g1_file = request.files['graph1']
        g2_file = request.files['graph2']
        
        # Check if files are selected
        if g1_file.filename == '' or g2_file.filename == '':
            flash("Please select both graph files", "error")
            return render_template("index.html", visualized=False)
        
        # Validate file extensions
        if not (allowed_file(g1_file.filename) and allowed_file(g2_file.filename)):
            flash("Only JSON and assembly files (.json, .s, .asm) are allowed", "error")
            return render_template("index.html", visualized=False)
        
        # Save original filenames before securing them
        original_filename1 = g1_file.filename
        original_filename2 = g2_file.filename
        
        # Save uploaded files securely.
        # Prefix with a random token so two uploads with the same name
        # (or concurrent users) never overwrite each other.
        try:
            filename1 = f"g1_{os.urandom(4).hex()}_{secure_filename(g1_file.filename)}"
            filename2 = f"g2_{os.urandom(4).hex()}_{secure_filename(g2_file.filename)}"

            graph1_path = os.path.join(app.config['UPLOAD_FOLDER'], filename1)
            graph2_path = os.path.join(app.config['UPLOAD_FOLDER'], filename2)
            
            g1_file.save(graph1_path)
            g2_file.save(graph2_path)
            
            # Validate graph files
            valid1, error1 = validate_graph_file(graph1_path)
            if not valid1:
                os.remove(graph1_path)
                os.remove(graph2_path)
                flash(f"Graph 1: {error1}", "error")
                return render_template("index.html", visualized=False)
            
            valid2, error2 = validate_graph_file(graph2_path)
            if not valid2:
                os.remove(graph1_path)
                os.remove(graph2_path)
                flash(f"Graph 2: {error2}", "error")
                return render_template("index.html", visualized=False)
            
            return process_graphs(
                graph1_path, 
                graph2_path, 
                cleanup=True,
                filename1=original_filename1,
                filename2=original_filename2
            )
            
        except Exception as e:
            logger.error(f"Error processing uploaded files: {str(e)}")
            flash(f"Error processing files: {str(e)}", "error")
            return render_template("index.html", visualized=False)
    
    return render_template("index.html", visualized=False)


@app.route("/inspect", methods=["GET", "POST"])
def inspect():
    """Assembly inspector page with real-time CFG visualization"""
    if request.method == "POST":
        # Check if using sample data
        if 'sample' in request.form:
            # Load sample assembly file
            try:
                sample_path = os.path.join(STATIC_DIR, "anthrax.asm")
                # Read with robust encoding handling
                with open(sample_path, 'rb') as f:
                    content_bytes = f.read()
                asm_content = decode_bytes(content_bytes)

                # Parse assembly and generate CFG for sample
                try:
                    G = parse_assembly_file(sample_path)
                    output_filename = generate_cfg_visualization(G)

                    file_size_mb = len(asm_content) / (1024 * 1024)
                    return render_template("inspector.html",
                                         assembly_code=asm_content,
                                         filename="anthrax.asm",
                                         file_size_mb=file_size_mb,
                                         cfg_html=output_filename)
                except Exception as e:
                    logger.error(f"Error generating CFG for sample: {e}")
                    flash(f"Error generating CFG: {e}", "warning")
                    return render_template("inspector.html",
                                         assembly_code=asm_content,
                                         filename="anthrax.asm")
            except Exception as e:
                flash(f"Error loading sample file: {str(e)}", "error")
                return render_template("inspector.html")
        
        # Handle file upload
        if 'assembly_file' not in request.files:
            flash("Please upload an assembly file", "error")
            return render_template("inspector.html")
        
        asm_file = request.files['assembly_file']
        
        if asm_file.filename == '':
            flash("Please select an assembly file", "error")
            return render_template("inspector.html")
        
        # Validate file extension (the inspector parses assembly only)
        if not allowed_file(asm_file.filename, ASSEMBLY_EXTENSIONS):
            flash("Only assembly files (.s, .asm) are allowed", "error")
            return render_template("inspector.html")

        try:
            # Read assembly content with robust encoding handling
            content_bytes = asm_file.read()
            asm_content = decode_bytes(content_bytes)

            # Check file size (warn if >5MB)
            file_size_mb = len(asm_content) / (1024 * 1024)
            if file_size_mb > 5:
                flash(f"Warning: Large file ({file_size_mb:.1f}MB) may take time to parse", "warning")

            # Parse assembly and generate CFG
            temp_path = None
            try:
                # Create temporary file for parsing.
                # Save to uploads directory to allow INCLUDE preprocessing;
                # random prefix avoids collisions between concurrent uploads.
                filename = f"insp_{os.urandom(4).hex()}_{secure_filename(asm_file.filename)}"
                temp_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

                with open(temp_path, 'wb') as f:
                    f.write(content_bytes)

                # Parse the assembly file (preprocessor will handle INCLUDEs automatically)
                G = parse_assembly_file(temp_path)
                output_filename = generate_cfg_visualization(G)

                return render_template("inspector.html",
                                     assembly_code=asm_content,
                                     filename=asm_file.filename,
                                     file_size_mb=file_size_mb,
                                     cfg_html=output_filename)

            except Exception as e:
                logger.error(f"Error generating CFG: {e}")
                flash(f"Error generating CFG: {e}", "warning")
                return render_template("inspector.html",
                                     assembly_code=asm_content,
                                     filename=asm_file.filename,
                                     file_size_mb=file_size_mb)
            finally:
                # Always clean up the temporary file
                if temp_path and os.path.exists(temp_path):
                    try:
                        os.unlink(temp_path)
                    except Exception as e:
                        logger.warning(f"Failed to clean up temp file: {e}")
        except Exception as e:
            logger.error(f"Error reading assembly file: {str(e)}")
            flash(f"Error reading file: {str(e)}", "error")
            return render_template("inspector.html")
    
    return render_template("inspector.html")


# Calibrated against calibrate_thresholds.py (repo root): a synthetic
# edit-distance perturbation study over the 4 locally-available CFGs
# (anthrax/whore/relock/Bodmasv2), cross-checked against the 3 genuinely
# unrelated real-malware pairs the repo has (anthrax/whore/relock -- theZoo
# has no usable same-family variant pairs, see Home/CFG Project/05 in the
# project's Obsidian vault). Findings: the real unrelated pairs score
# 1.3-4.3%, and these thresholds already sit with clear margin above that
# floor while tracking where the sample graphs land under light-to-moderate
# synthetic perturbation -- kept unchanged rather than tuned, since the data
# didn't call for different numbers. Caveat: reliability is graph-density
# dependent -- dense/well-connected CFGs decay out of the 'strong' band much
# faster than sparse ones for the same edit distance, so a 'strong' verdict
# is more fragile for large, dense graphs than small, sparse ones.
VERDICT_TIERS = ((70, 'strong'), (30, 'related'), (10, 'weak'))


def _verdict(score):
    """Coarse human label for a similarity percentage."""
    for threshold, label in VERDICT_TIERS:
        if score >= threshold:
            return label
    return 'none'


def _is_admin_mutation():
    return request.method == "POST" and ('register' in request.form or 'delete' in request.form)


@app.route("/identify", methods=["GET", "POST"])
@limiter.limit("5 per hour", exempt_when=lambda: not _is_admin_mutation())
def identify():
    """Single-file identification against the baseline fingerprint database."""
    def baseline_summaries():
        return [{'name': b['name'], 'nodes': b['nodes'], 'edges': b['edges'], 'slug': b['slug']}
                for b in list_baselines()]

    if request.method != "POST":
        return render_template("identify.html", baselines=baseline_summaries())

    if _is_admin_mutation() and not _admin_authorized():
        flash("Not authorized to modify the baseline database", "error")
        return render_template("identify.html", baselines=baseline_summaries()), 403

    # Branch 0: delete a baseline
    if 'delete' in request.form:
        from fingerprint_db import delete_baseline
        slug = request.form['delete']
        try:
            delete_baseline(slug)
            flash(f"Baseline '{slug}' deleted", "success")
        except FileNotFoundError:
            flash(f"Baseline '{slug}' not found", "error")
        return render_template("identify.html", baselines=baseline_summaries())

    # Branch 1: register a new baseline fingerprint
    if 'register' in request.form:
        bl_file = request.files.get('baseline_file')
        if not bl_file or bl_file.filename == '':
            flash("Please select a file to register", "error")
            return render_template("identify.html", baselines=baseline_summaries())
        if not allowed_file(bl_file.filename):
            flash("Only .json, .s and .asm files can be registered", "error")
            return render_template("identify.html", baselines=baseline_summaries())
        temp_path = os.path.join(
            app.config['UPLOAD_FOLDER'],
            f"bl_{os.urandom(4).hex()}_{secure_filename(bl_file.filename)}")
        try:
            bl_file.save(temp_path)
            G = load_graph_from_file(temp_path)
            name = (request.form.get('baseline_name', '').strip()
                    or os.path.splitext(bl_file.filename)[0])
            slug = add_baseline(name, G)
            flash(f"Baseline '{slug}' registered ({G.number_of_nodes()} nodes, "
                  f"{G.number_of_edges()} edges)", "success")
        except Exception as e:
            logger.error(f"Error registering baseline: {e}")
            flash(f"Error registering baseline: {e}", "error")
        finally:
            if os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except Exception as e:
                    logger.warning(f"Failed to clean up temp file: {e}")
        return render_template("identify.html", baselines=baseline_summaries())

    # Branch 2: identify a file against the database
    temp_path = None
    if 'sample' in request.form:
        target_path = os.path.join(STATIC_DIR, "anthrax.asm")
        target_name = "anthrax.asm"
    else:
        target = request.files.get('target')
        if not target or target.filename == '':
            flash("Please select a file to identify", "error")
            return render_template("identify.html", baselines=baseline_summaries())
        if not allowed_file(target.filename):
            flash("Only .json, .s and .asm files are supported", "error")
            return render_template("identify.html", baselines=baseline_summaries())
        temp_path = os.path.join(
            app.config['UPLOAD_FOLDER'],
            f"id_{os.urandom(4).hex()}_{secure_filename(target.filename)}")
        target.save(temp_path)
        target_path = temp_path
        target_name = target.filename

    try:
        G = load_graph_from_file(target_path)
        results = match_against_db(G)
        for r in results:
            r['verdict'] = _verdict(r['score'])

        if not results:
            flash("The fingerprint database is empty — register a baseline first",
                  "warning")
            return render_template("identify.html", baselines=baseline_summaries(),
                                   target_name=target_name,
                                   target_nodes=G.number_of_nodes(),
                                   target_edges=G.number_of_edges())

        # Render the full comparison against the best match
        stats = graph_file = None
        best = results[0]
        if best['score'] > 0:
            G_best = load_cfg_json(best['path'])
            stats, graph_file = build_comparison(
                G, G_best, target_name, f"{best['name']} (baseline)")

        # Downloadable report excludes 'path' (server filesystem detail,
        # not meant for the client) that match_against_db() attaches for
        # the internal load_cfg_json() call above.
        results_export = [
            {k: r[k] for k in ('name', 'nodes', 'edges', 'score', 'matched', 'matched_pct', 'verdict')}
            for r in results
        ]

        return render_template("identify.html", baselines=baseline_summaries(),
                               results=results, results_export=results_export,
                               target_name=target_name,
                               target_nodes=G.number_of_nodes(),
                               target_edges=G.number_of_edges(),
                               stats=stats, graph_file=graph_file)
    except Exception as e:
        logger.error(f"Error identifying file: {e}")
        flash(f"Error identifying file: {e}", "error")
        return render_template("identify.html", baselines=baseline_summaries())
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except Exception as e:
                logger.warning(f"Failed to clean up temp file: {e}")


def build_comparison(G1, G2, filename1="Graph 1", filename2="Graph 2"):
    """
    Compare two loaded graphs and render the combined visualization.

    Returns (stats, output_filename); output_filename is relative to static/.
    Used by the two-file comparison page and the identify-against-baseline page.
    """
    # Compare graphs by node name
    nodes_in_both, edges_in_both = compare_graphs(G1, G2)

    # Name-independent structural comparison (WL fingerprints)
    struct = structural_similarity(G1, G2)

    # When node names barely overlap (e.g. address-based IDs from two
    # different binaries), name matching is meaningless — fall back to
    # structural matching for the shared/unique classification
    min_nodes = min(len(G1.nodes()), len(G2.nodes()))
    name_overlap = len(nodes_in_both) / min_nodes if min_nodes else 0
    match_mode = 'name' if name_overlap >= NAME_OVERLAP_THRESHOLD else 'structure'

    if match_mode == 'name':
        common_nodes = len(nodes_in_both)
        common_edges = len(edges_in_both)
    else:
        common_nodes = len(struct['matched_nodes_1'])
        common_edges = len(struct['matched_edges_1'])

    # Node-importance classification on the combined structure
    combined_graph = nx.compose(G1, G2)
    importance = compute_node_importance(combined_graph)
    top_nodes = sorted(importance.items(), key=lambda kv: kv[1]['score'], reverse=True)[:5]

    # Calculate statistics with filenames
    stats = {
        'g1_nodes': len(G1.nodes()),
        'g1_edges': len(G1.edges()),
        'g2_nodes': len(G2.nodes()),
        'g2_edges': len(G2.edges()),
        'common_nodes': common_nodes,
        'common_edges': common_edges,
        'unique_g1_nodes': len(G1.nodes()) - common_nodes,
        'unique_g2_nodes': len(G2.nodes()) - common_nodes,
        'structural_score': round(struct['score'] * 100, 1),
        'verdict': _verdict(round(struct['score'] * 100, 1)),
        'match_mode': match_mode,
        'critical_nodes': sum(1 for d in importance.values() if d['tier'] == 'critical'),
        'top_nodes': [
            {
                'name': str(node),
                'tier': d['tier'],
                'score': round(d['score'], 2),
                'where': 'both' if node in nodes_in_both
                         else (filename1 if node in G1.nodes() else filename2)
            }
            for node, d in top_nodes
        ],
        'filename1': filename1,
        'filename2': filename2
    }

    # Create combined graph visualization
    combined = Network(
        height="700px",
        width="100%",
        notebook=False,
        bgcolor="#0e131b",
        font_color="#aab7c9",
        directed=True,
        cdn_resources='remote'
    )

    # Set physics options for better layout
    combined.set_options("""
    {
      "physics": {
        "forceAtlas2Based": {
          "gravitationalConstant": -50,
          "centralGravity": 0.01,
          "springLength": 100,
          "springConstant": 0.08
        },
        "maxVelocity": 50,
        "solver": "forceAtlas2Based",
        "timestep": 0.35,
        "stabilization": {"iterations": 150}
      }
    }
    """)

    g1_nodes, g2_nodes = set(G1.nodes()), set(G2.nodes())
    g1_edges, g2_edges = set(G1.edges()), set(G2.edges())

    # Cap what we render (stats above already cover the full graphs)
    render_graph, dropped = truncate_to_important(combined_graph, importance)
    if dropped:
        flash(f"Large graph: rendering the {render_graph.number_of_nodes()} "
              f"most important nodes ({dropped} hidden — stats cover all)",
              "warning")
    all_nodes = set(render_graph.nodes())
    all_edges = set(render_graph.edges())

    # Add nodes with colors (provenance) and size/border (importance)
    for node in all_nodes:
        in_g1, in_g2 = node in g1_nodes, node in g2_nodes
        if match_mode == 'name':
            is_shared = node in nodes_in_both
            shared_label = "in both graphs"
        else:
            is_shared = ((in_g1 and node in struct['matched_nodes_1'])
                         or (in_g2 and node in struct['matched_nodes_2'])
                         or (in_g1 and in_g2))
            shared_label = "structure matched in both files"

        if is_shared:
            color = "#ffb454"   # amber — in both
            title = f"Node: {node} ({shared_label})"
        elif in_g1:
            color = "#56c8ff"   # cyan — graph 1 only
            title = f"Node: {node} (only in {filename1})"
        else:
            color = "#6fdb8d"   # green — graph 2 only
            title = f"Node: {node} (only in {filename2})"

        imp = importance.get(node, {'score': 0.0, 'tier': 'normal'})
        title += f"\nImportance: {imp['tier']} (score {imp['score']:.2f})"
        node_kwargs = {'size': 10 + 18 * imp['score']}
        if imp['tier'] == 'critical':
            node_kwargs['borderWidth'] = 3
            node_kwargs['color'] = {'background': color, 'border': '#ff5d5d'}
        else:
            node_kwargs['color'] = color
        combined.add_node(str(node), title=title, **node_kwargs)

    # Add edges with colors. Direction matters in a CFG, so A->B and
    # B->A are treated as different edges (matching the stats above).
    for u, v in all_edges:
        if match_mode == 'name':
            is_shared = (u, v) in edges_in_both
            shared_label = "Edge in both graphs"
        else:
            is_shared = ((u, v) in struct['matched_edges_1']
                         or (u, v) in struct['matched_edges_2'])
            shared_label = "Edge structurally matched in both files"

        if is_shared:
            color = "#ff6b6b"   # red — in both
            title = shared_label
        elif (u, v) in g1_edges:
            color = "#3d8bff"   # blue — graph 1 only
            title = f"Edge only in {filename1}"
        else:
            color = "#2ecc71"   # green — graph 2 only
            title = f"Edge only in {filename2}"
        combined.add_edge(str(u), str(v), color=color, title=title)

    # Clean up old generated graphs, then save under a unique name so
    # concurrent users don't overwrite each other's results
    cleanup_old_cfg_files(max_age_hours=1)
    output_filename = f"combined_{os.urandom(4).hex()}.html"
    output_path = os.path.join(STATIC_DIR, output_filename)
    combined.save_graph(output_path)
    apply_dark_chrome(output_path)

    # Add legend to the graph with actual filenames
    add_legend_to_html(output_path, filename1, filename2, match_mode)

    return stats, output_filename


def process_graphs(graph1_path, graph2_path, cleanup=False, filename1="Graph 1", filename2="Graph 2"):
    """Process and visualize graph comparison"""
    try:
        # Load the graphs (supports both JSON and assembly)
        G1 = load_graph_from_file(graph1_path)
        G2 = load_graph_from_file(graph2_path)

        if G1 is None or G2 is None:
            flash("Error loading graph files", "error")
            return render_template("index.html", visualized=False)

        stats, output_filename = build_comparison(G1, G2, filename1, filename2)

        # Cleanup temporary files
        if cleanup:
            try:
                os.remove(graph1_path)
                os.remove(graph2_path)
            except Exception as e:
                logger.warning(f"Error cleaning up files: {str(e)}")

        flash("Graphs compared successfully!", "success")
        return render_template("index.html", visualized=True, stats=stats,
                               graph_file=output_filename)

    except Exception as e:
        logger.error(f"Error processing graphs: {str(e)}")
        flash(f"Error processing graphs: {str(e)}", "error")
        if cleanup:
            try:
                os.remove(graph1_path)
                os.remove(graph2_path)
            except:
                pass
        return render_template("index.html", visualized=False)



@app.route("/api/stats", methods=["GET"])
def get_stats():
    """API endpoint to get graph statistics"""
    # This could be expanded to return cached statistics
    return jsonify({"status": "ready"})


@app.errorhandler(404)
def not_found(error):
    """Custom 404 page matching the dark forensic theme"""
    return render_template("404.html"), 404


@app.errorhandler(413)
def request_entity_too_large(error):
    """Handle file too large error"""
    flash("File too large. Maximum size is 16MB.", "error")
    return render_template("index.html", visualized=False), 413


@app.errorhandler(500)
def internal_error(error):
    """Handle internal server errors, rendering the template for the route that failed"""
    logger.error(f"Internal error on {request.path}: {str(error)}")
    flash("An internal error occurred. Please try again.", "error")
    if request.path.startswith("/inspect"):
        return render_template("inspector.html"), 500
    if request.path.startswith("/identify"):
        return render_template("identify.html", baselines=[
            {'name': b['name'], 'nodes': b['nodes'], 'edges': b['edges'], 'slug': b['slug']}
            for b in list_baselines()]), 500
    return render_template("index.html", visualized=False), 500


if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV', 'production') == 'development'
    app.run(debug=debug, host='0.0.0.0', port=port)
