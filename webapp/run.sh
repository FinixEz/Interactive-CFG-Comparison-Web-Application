#!/bin/bash
cd "$(dirname "$0")"

# Activate the first virtual environment found (optional)
for env in ../venv ../.venv ../malwarecfg-env; do
    if [ -f "$env/bin/activate" ]; then
        source "$env/bin/activate"
        break
    fi
done

export FLASK_ENV=production
python app.py
