#!/bin/bash
cd "$(dirname "$0")"
source ../malwarecfg-env/bin/activate
export FLASK_ENV=production
python app.py
