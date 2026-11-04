#!/usr/bin/env bash
# run_demo.sh — One-command demo for the RBAC-to-ABAC Miner.
# Runs the full pipeline (upload → train → extract → optimise → validate → approve → export)
# using the seed_hospital dataset with seed=42, entirely in-process (no server needed).
#
# Usage (from repository root):
#   bash scripts/run_demo.sh
#
# Requirements: Python 3.9+, backend dependencies installed.
#   pip install -r backend/requirements.txt

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

echo "Running RBAC-to-ABAC Miner demo (seed=42, dataset=seed_hospital) ..."
python "$REPO_ROOT/scripts/run_demo.py" --inline
