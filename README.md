# Interactive CFG Comparison Web Application

[![Live Demo](https://img.shields.io/badge/demo-live-success)](https://interactive-cfg-comparison-web.onrender.com)
[![CI](https://github.com/FinixEz/Interactive-CFG-Comparison-Web-Application/actions/workflows/ci.yml/badge.svg)](https://github.com/FinixEz/Interactive-CFG-Comparison-Web-Application/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Flask](https://img.shields.io/badge/flask-3.1.2-green.svg)](https://flask.palletsprojects.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A powerful web-based tool for visualizing and comparing Control Flow Graphs (CFGs) from assembly code and JSON files. This application provides interactive graph visualization, side-by-side comparison, and real-time assembly code inspection with CFG generation.

## 🚀 Live Demo

**Try it now:** [https://interactive-cfg-comparison-web.onrender.com](https://interactive-cfg-comparison-web.onrender.com)

> **Note**: The app is hosted on Render's free tier and may take ~30 seconds to wake up if it has been inactive.

## 🌟 Features

### 1. **CFG Comparison Tool**
- **Multi-format Support**: Upload and compare CFGs from JSON files or assembly code (`.s`, `.asm`)
- **Interactive Visualization**: Zoom, pan, and explore graph structures with physics-based layouts
- **Visual Differentiation**: 
  - 🟠 Amber nodes: Present in both graphs
  - 🔵 Cyan nodes: Unique to Graph 1
  - 🟢 Green nodes: Unique to Graph 2
- **Detailed Statistics**: View node/edge counts and commonalities between graphs
- **Structural Similarity**: Weisfeiler-Lehman fingerprint score that works even when node names can't match (different address spaces); shared/unique coloring falls back to structural matching automatically
- **Node-Importance Classification**: Nodes are ranked by betweenness/degree centrality and tiered (critical / high / normal) — node size reflects the score, critical nodes get a red border, and the top-ranked nodes are listed with the statistics
- **Sample Data**: Quick-start with pre-loaded sample graphs

### 2. **Assembly Inspector**
- **Real-time CFG Generation**: Upload assembly files and instantly generate control flow graphs
- **Interactive Code Highlighting**: Click on CFG nodes to highlight corresponding assembly code
- **Hierarchical Layout**: Top-down waterfall visualization for better code flow understanding
- **Multi-format Support**: Works with `.s` (GNU/AT&T) and `.asm` (MASM/TASM/NASM) files, including colon-less `name label near` / `name proc` labels and TASM `comment` blocks found in real malware sources (theZoo)
- **Large File Handling**: Robust encoding detection and efficient parsing for large assembly files
- **MASM Preprocessor**: Automatic handling of INCLUDE directives for MASM assembly files

### 3. **Technical Capabilities**
- **Assembly Parsing**: Lightweight built-in parser (label/jump analysis) for x86/x86_64 and ARM64 assembly; `angr` is used offline to extract CFGs from binaries (see `convertpkltojson.py`)
- **Graph Analysis**: Built on NetworkX for robust graph operations
- **Responsive Design**: Modern, mobile-friendly interface
- **File Upload Validation**: Secure file handling with size limits (16MB max)
- **Automatic Cleanup**: Temporary files are automatically removed

## 📋 Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- Modern web browser (Chrome, Firefox, Safari, Edge)

## 🚀 Installation

### 1. Clone the Repository
```bash
git clone https://github.com/FinixEz/Interactive-CFG-Comparison-Web-Application.git
cd Interactive-CFG-Comparison-Web-Application
```

### 2. Create Virtual Environment (Recommended)
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

For the web application only (recommended — small and fast):
```bash
pip install -r requirements-production.txt
```

For the full toolchain including the offline `angr`-based utilities
(`pkl.py`, `convertpkltojson.py`):
```bash
pip install -r requirements.txt
```

## 🎮 Usage

### Starting the Application

#### Option 1: Using the Run Script (Linux/Mac)
```bash
cd webapp
chmod +x run.sh
./run.sh
```

#### Option 2: Direct Python Execution
```bash
cd webapp
python app.py
```

#### Option 3: Docker
```bash
docker compose up -d --build
```
Or without compose:
```bash
docker build -t cfg-webapp .
docker run -d -p 127.0.0.1:5000:5000 cfg-webapp
```
> The compose file binds to `127.0.0.1` by default. Docker-published ports
> bypass ufw/host firewalls — set `BIND_ADDR=0.0.0.0` only if you want the
> app reachable from your network, and set a real `SECRET_KEY` (both e.g.
> in a `.env` file next to `docker-compose.yml`).

The application will start on `http://localhost:5000`

### Using the CFG Comparison Tool

1. Navigate to the home page (`/`)
2. **Option A - Upload Files**:
   - Click "Choose File" for Graph 1 and Graph 2
   - Select JSON or assembly files (`.json`, `.s`, `.asm`)
   - Click "Compare Graphs"
3. **Option B - Try Sample Data**:
   - Click "Try Sample Data" to load pre-configured examples
4. View the interactive comparison graph with statistics

### Using the Assembly Inspector

1. Navigate to `/inspect`
2. **Option A - Upload Assembly File**:
   - Click "Choose File" and select an assembly file
   - Click "Inspect Assembly"
3. **Option B - Try Sample Data**:
   - Click "Try Sample Data" to load a sample assembly file
4. **Interact with the CFG**:
   - Click on any node in the CFG to highlight the corresponding assembly code
   - Zoom and pan to explore the graph structure

## 📁 Project Structure

```
Interactive-CFG-Comparison-Web-Application/
├── webapp/                      # Main web application
│   ├── app.py                  # Flask application server
│   ├── asm_parser.py           # Assembly parsing and CFG generation
│   ├── visualize_compare.py    # Graph comparison and visualization
│   ├── templates/              # HTML templates
│   │   ├── index.html         # CFG comparison page
│   │   └── inspector.html     # Assembly inspector page
│   └── static/                # Static assets and generated graphs
│       ├── style.css          # Application styling
│       ├── *.json             # Sample CFG files
│       └── *.asm              # Sample assembly files
├── tests/                      # Pytest suite (parser, similarity, routes)
├── .github/workflows/ci.yml   # CI: pytest + Docker build on every push
├── requirements.txt            # Full Python dependencies (incl. angr utilities)
├── requirements-production.txt # Web application dependencies only
├── requirements-dev.txt        # Production deps + pytest
├── convertpkltojson.py        # Utility: Convert pickle to JSON
├── mockupdata.py              # Utility: Generate mock data
├── pkl.py                     # Utility: Visualize a pickled angr CFG
└── README.md                  # This file
```

## 🧪 Testing

```bash
pip install -r requirements-dev.txt
pytest
```

The suite covers the assembly parser (GAS and TASM/MASM label forms, comment
blocks, jump qualifiers, fall-through rules), structural-similarity invariants
(a graph vs. a renamed copy of itself scores 100%; unrelated structures score
near zero), the Flask routes, and a regression test for filename escaping in
generated graphs. Tests that depend on local malware sources skip automatically
when those files are absent, so the suite runs anywhere. CI runs it plus a
Docker build on every push.

## ⚙️ Configuration

| Environment variable | Default | Purpose |
|---|---|---|
| `SECRET_KEY` | dev placeholder | Flask session signing — set a real value in production |
| `BIND_ADDR` | `127.0.0.1` | Address Docker Compose publishes on; `0.0.0.0` exposes to the network |
| `MAX_VIS_NODES` | `800` | Max nodes rendered per graph view (stats always cover full graphs) |
| `NAME_OVERLAP_THRESHOLD` | `0.05` | Name-overlap fraction below which comparison falls back to structural matching |
| `UPLOAD_FOLDER` | `webapp/uploads` | Where uploads are written |

## 🔧 Key Technologies

- **Backend**: Flask (Python web framework)
- **Graph Processing**: NetworkX
- **Visualization**: PyVis, Vis.js
- **Frontend**: HTML5, CSS3, JavaScript
- **Assembly Analysis**: lightweight built-in parser (web app); angr/pyvex for the offline utilities

## 📊 Supported File Formats

### Input Formats
- **JSON**: CFG data in JSON format (NetworkX-compatible)
- **Assembly**: `.s` (GNU Assembly), `.asm` (MASM/NASM)

### JSON CFG Format

Two formats are accepted:

**Simple format:**
```json
{
  "nodes": ["node1", "node2", "node3"],
  "edges": [["node1", "node2"], ["node2", "node3"]]
}
```

**NetworkX node-link format** (as produced by `convertpkltojson.py`):
```json
{
  "directed": true,
  "multigraph": false,
  "nodes": [{"id": "node1"}, {"id": "node2"}],
  "links": [{"source": "node1", "target": "node2"}]
}
```

## 🎨 Features in Detail

### CFG Node-to-Code Highlighting
When you click on a CFG node in the Assembly Inspector:
1. The node's metadata (line numbers) is extracted
2. A message is sent to the parent window via `postMessage`
3. The corresponding assembly code lines are highlighted
4. The code view automatically scrolls to the highlighted section

### Hierarchical Graph Layout
The CFG uses a top-down hierarchical layout:
- **Direction**: Vertical (top to bottom)
- **Node Spacing**: 150px
- **Level Separation**: 200px
- **Physics**: Disabled for stable positioning

### Graph Comparison Algorithm
1. Load both graphs (JSON or assembly)
2. Compute the name-based intersection of nodes and (direction-sensitive) edges
3. Compute name-independent **structural similarity** using Weisfeiler-Lehman subgraph hashes, seeded with in/out-degree labels (plus block-size buckets for parsed assembly): each node gets a depth-3 neighborhood fingerprint; the similarity score is the multiset-Jaccard of all fingerprints
4. If node names barely overlap (< 5% of the smaller graph — e.g. address-based CFG IDs from two different binaries; tunable via `NAME_OVERLAP_THRESHOLD`), shared/unique classification automatically falls back to **structural matching**: a node counts as "common" when its control-flow neighborhood pattern also occurs in the other graph. Matching is graded — the deepest agreeing fingerprint wins (minimum 2 of 3 WL iterations), so a single edit deep in a neighborhood doesn't void an otherwise-identical block
5. Classify node importance on the combined graph (60% betweenness + 40% degree centrality, normalized; top 10% = critical, next 20% = high)
6. Color-code nodes/edges by presence, size nodes by importance; graphs beyond `MAX_VIS_NODES` (default 800) render only their most important nodes — statistics always cover the full graphs
7. Generate interactive visualization with legend

> **Scope note**: name-based matching is exact — it is meaningful for related
> graphs (same binary pre/post modification, graphs sharing a label space).
> For unrelated samples, rely on the structural similarity score and
> structural matches instead.

## 🛡️ Security Features

- Secure filename handling with `werkzeug.secure_filename`
- HTML-escaping of user-controlled filenames in generated graph pages
- File size limits (16MB maximum)
- File type validation (whitelist-based)
- Automatic cleanup of temporary files
- Upload directory isolation

## 🐛 Troubleshooting

### Issue: "Module not found" errors
**Solution**: Ensure all dependencies are installed
```bash
pip install -r requirements.txt
```

### Issue: CFG not generating for assembly file
**Solution**: 
- Verify the assembly file is valid
- Check that the file uses supported syntax (x86/x64)
- Review Flask logs for parsing errors

### Issue: Large files causing timeout
**Solution**: 
- Files over 5MB may take time to parse
- Consider breaking large assembly files into smaller functions
- Increase Flask timeout settings if needed

### Issue: Graph visualization not loading
**Solution**:
- Clear browser cache
- Check browser console for JavaScript errors
- Ensure static files are being served correctly

## 📝 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET, POST | CFG comparison tool |
| `/inspect` | GET, POST | Assembly inspector |
| `/api/stats` | GET | Get graph statistics (future use) |

## 🤝 Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

### Development Setup
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

**TL;DR**: You can use this project for anything, including commercial purposes, as long as you include the original copyright notice.

## 🙏 Acknowledgments

- **angr**: Binary analysis framework
- **NetworkX**: Graph processing library
- **PyVis**: Python graph visualization
- **Vis.js**: JavaScript visualization library
- **Flask**: Python web framework

## 📧 Contact

For questions or support, please open an issue on GitHub.

---

**Built with ❤️ for malware analysis and reverse engineering research**
