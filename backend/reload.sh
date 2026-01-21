#!/bin/bash
# Quick reload script wrapper
# Activates virtual environment and runs the reload script

cd "$(dirname "$0")"

source venv/bin/activate
python reload_all_auctions.py "$@"
