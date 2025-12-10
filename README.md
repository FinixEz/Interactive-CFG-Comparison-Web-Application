# Interactive CFG Comparison Web Application

[![Live Demo](https://img.shields.io/badge/demo-live-success)](https://interactive-cfg-comparison-web.onrender.com)
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Flask](https://img.shields.io/badge/flask-3.1.2-green.svg)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/license-Educational-orange.svg)](LICENSE)

A powerful web-based tool for visualizing and comparing Control Flow Graphs (CFGs) from assembly code and JSON files. This application provides interactive graph visualization, side-by-side comparison, and real-time assembly code inspection with CFG generation.

## 🚀 Live Demo

**Try it now:** [https://interactive-cfg-comparison-web.onrender.com](https://interactive-cfg-comparison-web.onrender.com)

> **Note**: The app is hosted on Render's free tier and may take ~30 seconds to wake up if it has been inactive.

## 🌟 Features

### 1. **CFG Comparison Tool**
- **Multi-format Support**: Upload and compare CFGs from JSON files or assembly code (`.s`, `.asm`)
- **Interactive Visualization**: Zoom, pan, and explore graph structures with physics-based layouts
- **Visual Differentiation**: 
  - 🟠 Orange nodes: Present in both graphs
  - 🔵 Blue nodes: Unique to Graph 1
  - 🟢 Green nodes: Unique to Graph 2
- **Detailed Statistics**: View node/edge counts and commonalities between graphs
- **Sample Data**: Quick-start with pre-loaded sample graphs

### 2. **Assembly Inspector**
- **Real-time CFG Generation**: Upload assembly files and instantly generate control flow graphs
- **Interactive Code Highlighting**: Click on CFG nodes to highlight corresponding assembly code
- **Hierarchical Layout**: Top-down waterfall visualization for better code flow understanding
- **Multi-format Support**: Works with `.s`, `.asm`, and JSON CFG files
- **Large File Handling**: Robust encoding detection and efficient parsing for large assembly files
- **MASM Preprocessor**: Automatic handling of INCLUDE directives for MASM assembly files

### 3. **Technical Capabilities**
- **Assembly Parsing**: Powered by `angr` and `asmcfg` for accurate CFG extraction
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
│   ├── static/                # Static assets and generated graphs
│   │   ├── style.css          # Application styling
│   │   ├── *.json             # Sample CFG files
│   │   └── *.asm              # Sample assembly files
│   └── lib/                   # JavaScript libraries
│       ├── vis-9.1.2/         # Vis.js for graph visualization
│       └── tom-select/        # Tom Select for dropdowns
├── lib/                        # Shared libraries
├── requirements.txt            # Python dependencies
├── convertpkltojson.py        # Utility: Convert pickle to JSON
├── mockupdata.py              # Utility: Generate mock data
└── README.md                  # This file
```

## 🔧 Key Technologies

- **Backend**: Flask (Python web framework)
- **Graph Processing**: NetworkX, angr, asmcfg
- **Visualization**: PyVis, Vis.js
- **Frontend**: HTML5, CSS3, JavaScript
- **Assembly Analysis**: Capstone, angr, pyvex

## 📊 Supported File Formats

### Input Formats
- **JSON**: CFG data in JSON format (NetworkX-compatible)
- **Assembly**: `.s` (GNU Assembly), `.asm` (MASM/NASM)

### JSON CFG Format
```json
{
  "nodes": ["node1", "node2", "node3"],
  "edges": [["node1", "node2"], ["node2", "node3"]]
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
2. Extract nodes and edges from each graph
3. Compute intersection (common elements)
4. Color-code nodes and edges based on presence
5. Generate interactive visualization with legend

## 🛡️ Security Features

- Secure filename handling with `werkzeug.secure_filename`
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

This project is available for educational and research purposes.

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
