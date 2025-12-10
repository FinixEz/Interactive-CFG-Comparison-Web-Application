from flask import Flask, render_template, request, jsonify, flash, redirect, url_for
from visualize_compare import load_cfg_json, compare_graphs, add_legend_to_html
from asm_parser import parse_assembly_file
from pyvis.network import Network
from werkzeug.utils import secure_filename
import tempfile
import os
import logging
import json
import time
import glob

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['UPLOAD_FOLDER'] = os.environ.get('UPLOAD_FOLDER', 'uploads')
ALLOWED_EXTENSIONS = {'json', 's', 'asm'}

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('static', exist_ok=True)


def cleanup_old_cfg_files(max_age_hours=1):
    """
    Remove old CFG HTML files from static directory.
    
    Args:
        max_age_hours: Maximum age in hours before files are deleted
    """
    try:
        pattern = os.path.join('static', 'cfg_*.html')
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600
        
        for filepath in glob.glob(pattern):
            file_age = current_time - os.path.getmtime(filepath)
            if file_age > max_age_seconds:
                try:
                    os.remove(filepath)
                    logger.info(f"Cleaned up old CFG file: {filepath}")
                except Exception as e:
                    logger.warning(f"Failed to remove {filepath}: {e}")
    except Exception as e:
        logger.error(f"Error during CFG cleanup: {e}")


def allowed_file(filename):
    """Check if file has allowed extension"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


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



@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        # Check if using sample data
        if 'sample' in request.form:
            return process_graphs(
                "static/Bodmasv2.json", 
                "static/mocking.json", 
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
        
        # Save uploaded files securely
        try:
            filename1 = secure_filename(g1_file.filename)
            filename2 = secure_filename(g2_file.filename)
            
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
                sample_path = "static/anthrax.asm"
                # Read with robust encoding handling
                with open(sample_path, 'rb') as f:
                    content_bytes = f.read()
                
                asm_content = None
                for encoding in ['utf-8', 'latin-1', 'cp1252']:
                    try:
                        asm_content = content_bytes.decode(encoding)
                        break
                    except UnicodeDecodeError:
                        continue
                
                if asm_content is None:
                    asm_content = content_bytes.decode('utf-8', errors='replace')
                
                # Parse assembly and generate CFG for sample
                try:
                    G = parse_assembly_file(sample_path)
                    
                    # Generate PyVis visualization with hierarchical layout
                    net = Network(height="600px", width="100%", bgcolor="#ffffff", font_color="black", directed=True)
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
                        node['color'] = '#97c2fc'
                        node['shape'] = 'box'
                        node['font'] = {'face': 'monospace', 'align': 'left'}
                        
                        # Add line number metadata from NetworkX graph
                        node_id = node['id']
                        if node_id in G.nodes:
                            node_data = G.nodes[node_id]
                            start_line = node_data.get('start_line', -1)
                            end_line = node_data.get('end_line', -1)
                            
                            # Add to title for visibility
                            lines_info = f"Lines {start_line}-{end_line}" if start_line >= 0 else "No line info"
                            node['title'] = f"{node_id}\n{lines_info}"
                            
                            # Store as custom data for JavaScript access
                            node['start_line'] = start_line
                            node['end_line'] = end_line
                        
                    for edge in net.edges:
                        edge['color'] = '#848484'
                        edge['arrows'] = 'to'
                    
                    # Clean up old CFG files before generating new one
                    cleanup_old_cfg_files(max_age_hours=1)
                    
                    # Save CFG visualization
                    output_filename = f"cfg_{os.urandom(4).hex()}.html"
                    output_path = os.path.join('static', output_filename)
                    net.save_graph(output_path)
                    
                    # Inject interactive JavaScript for node clicking
                    inject_cfg_interaction_js(output_path)
                    
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
        
        # Validate file extension
        if not allowed_file(asm_file.filename):
            flash("Only assembly files (.s, .asm) and JSON files are allowed", "error")
            return render_template("inspector.html")
        
        try:
            # Read assembly content with robust encoding handling
            content_bytes = asm_file.read()
            asm_content = None
            for encoding in ['utf-8', 'latin-1', 'cp1252']:
                try:
                    asm_content = content_bytes.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            
            if asm_content is None:
                asm_content = content_bytes.decode('utf-8', errors='replace')
            
            # Check file size (warn if >5MB)
            file_size_mb = len(asm_content) / (1024 * 1024)
            if file_size_mb > 5:
                flash(f"Warning: Large file ({file_size_mb:.1f}MB) may take time to parse", "warning")
            
            # Parse assembly and generate CFG
            try:
                # Create temporary file for parsing 
                # Save to uploads directory to allow INCLUDE preprocessing
                filename = secure_filename(asm_file.filename)
                temp_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                
                with open(temp_path, 'wb') as f:
                    f.write(content_bytes)
                
                # For .ASM files, check if there's a companion .INC file
                if filename.lower().endswith('.asm'):
                    base_name = os.path.splitext(filename)[0]
                    inc_filename = base_name + '.INC'
                    inc_path = os.path.join(app.config['UPLOAD_FOLDER'], inc_filename)
                    
                    if os.path.exists(inc_path):
                        logger.info(f"Found companion include file: {inc_filename}")
                        flash(f"Found and using companion file: {inc_filename}", "success")
                
                # Parse the assembly file (preprocessor will handle INCLUDEs automatically)
                G = parse_assembly_file(temp_path)
                
                # Generate PyVis visualization with hierarchical layout
                net = Network(height="600px", width="100%", bgcolor="#ffffff", font_color="black", directed=True)
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
                    node['color'] = '#97c2fc'
                    node['shape'] = 'box'
                    node['font'] = {'face': 'monospace', 'align': 'left'}
                    
                    # Add line number metadata from NetworkX graph
                    node_id = node['id']
                    if node_id in G.nodes:
                        node_data = G.nodes[node_id]
                        start_line = node_data.get('start_line', -1)
                        end_line = node_data.get('end_line', -1)
                        
                        # Add to title for visibility
                        lines_info = f"Lines {start_line}-{end_line}" if start_line >= 0 else "No line info"
                        node['title'] = f"{node_id}\n{lines_info}"
                        
                        # Store as custom data for JavaScript access
                        node['start_line'] = start_line
                        node['end_line'] = end_line
                    
                for edge in net.edges:
                    edge['color'] = '#848484'
                    edge['arrows'] = 'to'
                
                # Clean up old CFG files before generating new one
                cleanup_old_cfg_files(max_age_hours=1)
                
                # Save to a string/file to embed
                # PyVis save_graph saves to a file. We can save to static.
                output_filename = f"cfg_{os.urandom(4).hex()}.html"
                output_path = os.path.join('static', output_filename)
                net.save_graph(output_path)
                
                # Inject interactive JavaScript for node clicking
                inject_cfg_interaction_js(output_path)
                
                # Clean up temporary file
                try:
                    os.unlink(temp_path)
                except Exception as e:
                    logger.warning(f"Failed to clean up temp file: {e}")
                
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
        except Exception as e:
            logger.error(f"Error reading assembly file: {str(e)}")
            flash(f"Error reading file: {str(e)}", "error")
            return render_template("inspector.html")
    
    return render_template("inspector.html")


def process_graphs(graph1_path, graph2_path, cleanup=False, filename1="Graph 1", filename2="Graph 2"):
    """Process and visualize graph comparison"""
    try:
        # Load the graphs (supports both JSON and assembly)
        G1 = load_graph_from_file(graph1_path)
        G2 = load_graph_from_file(graph2_path)
        
        if G1 is None or G2 is None:
            flash("Error loading graph files", "error")
            return render_template("index.html", visualized=False)
        
        # Compare graphs
        nodes_in_both, edges_in_both = compare_graphs(G1, G2)
        
        # Calculate statistics with filenames
        stats = {
            'g1_nodes': len(G1.nodes()),
            'g1_edges': len(G1.edges()),
            'g2_nodes': len(G2.nodes()),
            'g2_edges': len(G2.edges()),
            'common_nodes': len(nodes_in_both),
            'common_edges': len(edges_in_both),
            'unique_g1_nodes': len(set(G1.nodes()) - nodes_in_both),
            'unique_g2_nodes': len(set(G2.nodes()) - nodes_in_both),
            'filename1': filename1,
            'filename2': filename2
        }
        
        # Create combined graph visualization
        combined = Network(
            height="700px", 
            width="100%", 
            notebook=False, 
            # heading=f"Comparison: {filename1} vs {filename2}",
            bgcolor="#ffffff",
            font_color="black"
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
        
        all_nodes = set(G1.nodes()).union(set(G2.nodes()))
        all_edges = set(G1.edges()).union(set(G2.edges()))
        
        # Add nodes with colors
        for node in all_nodes:
            if node in nodes_in_both:
                color = "orange"
                title = f"Node: {node} (in both graphs)"
            elif node in G1.nodes():
                color = "lightblue"
                title = f"Node: {node} (only in {filename1})"
            else:
                color = "lightgreen"
                title = f"Node: {node} (only in {filename2})"
            combined.add_node(str(node), color=color, title=title)
        
        # Add edges with colors
        for u, v in all_edges:
            if (u, v) in edges_in_both or (v, u) in edges_in_both:
                color = "red"
                title = "Edge in both graphs"
            elif (u, v) in G1.edges() or (v, u) in G1.edges():
                color = "blue"
                title = f"Edge only in {filename1}"
            else:
                color = "green"
                title = f"Edge only in {filename2}"
            combined.add_edge(str(u), str(v), color=color, title=title)
        
        # Save graph
        output_path = "static/combined_graph.html"
        combined.save_graph(output_path)
        
        # Add legend to the graph with actual filenames
        add_legend_to_html(output_path, filename1, filename2)
        
        # Cleanup temporary files
        if cleanup:
            try:
                os.remove(graph1_path)
                os.remove(graph2_path)
            except Exception as e:
                logger.warning(f"Error cleaning up files: {str(e)}")
        
        flash("Graphs compared successfully!", "success")
        return render_template("index.html", visualized=True, stats=stats)
        
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


@app.errorhandler(413)
def request_entity_too_large(error):
    """Handle file too large error"""
    flash("File too large. Maximum size is 16MB.", "error")
    return render_template("index.html", visualized=False), 413


@app.errorhandler(500)
def internal_error(error):
    """Handle internal server errors"""
    logger.error(f"Internal error: {str(error)}")
    flash("An internal error occurred. Please try again.", "error")
    return render_template("index.html", visualized=False), 500


if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV', 'development') == 'development'
    app.run(debug=debug, host='0.0.0.0', port=port)
