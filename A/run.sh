#!/usr/bin/env bash
# Task A - Inventory Reservation Ledger
# Usage: ./run.sh < input.txt
set -euo pipefail
cd "$(dirname "$0")"
python3 solution.py
