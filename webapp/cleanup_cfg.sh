#!/bin/bash
# Cleanup script to remove old CFG HTML files from static directory

cd "$(dirname "$0")"

echo "Cleaning up old CFG files..."
count=$(ls -1 static/cfg_*.html 2>/dev/null | wc -l)

if [ $count -eq 0 ]; then
    echo "No CFG files found."
else
    echo "Found $count CFG files. Removing..."
    rm -f static/cfg_*.html
    echo "✓ Cleaned up $count CFG files."
fi
