from flask import Flask, render_template, request, jsonify, flash, redirect, url_for
from visualize_compare import load_cfg_json, compare_graphs, add_legend_to_html
from pyvis.network import Network
from werkzeug.utils import secure_filename
import tempfile
import os
import logging

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Required for flash messages
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['UPLOAD_FOLDER'] = 'uploads'
ALLOWED_EXTENSIONS = {'json'}

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('static', exist_ok=True)


def allowed_file(filename):
    """Check if file has allowed extension"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def validate_graph_file(filepath):
    """Validate that the file is a valid graph JSON"""
    try:
        graph = load_cfg_json(filepath)
        if graph is None or len(graph.nodes()) == 0:
            return False, "Graph file is empty or invalid"
        return True, None
    except Exception as e:
        return False, f"Invalid graph file: {str(e)}"


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
            flash("Only JSON files are allowed", "error")
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


def process_graphs(graph1_path, graph2_path, cleanup=False, filename1="Graph 1", filename2="Graph 2"):
    """Process and visualize graph comparison"""
    try:
        # Load the graphs
        G1 = load_cfg_json(graph1_path)
        G2 = load_cfg_json(graph2_path)
        
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
    app.run(debug=True, host='0.0.0.0', port=5000)
