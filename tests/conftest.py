import os
import sys

# App modules live flat inside webapp/ and import each other directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'webapp'))
