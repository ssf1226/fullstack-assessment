#!/usr/bin/env bash
# Task B - Fulfilment Split Optimiser
# Usage: ./run.sh < input.txt
set -euo pipefail
cd "$(dirname "$0")"
python3 solution.py
