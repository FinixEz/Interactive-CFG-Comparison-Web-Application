import os
import sys

# App modules live flat inside webapp/ and import each other directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'webapp'))

# Root-level offline tools (pkl.py, convertpkltojson.py, binary_to_cfg.py)
# import each other the same way
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
