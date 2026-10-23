#!/usr/bin/env bash
# One-command verification for the whole repository.
# Runs Task A and Task B unit tests; app tests are run from their own dirs.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "== Task A =="
(cd A && python3 -m unittest discover -s tests -v)

echo "== Task B =="
(cd B && python3 -m unittest discover -s tests -v)

if [ -d app/backend/.venv ]; then
  echo "== App backend =="
  (cd app/backend && .venv/bin/python -m pytest tests -q)
else
  echo "(skip app backend tests: app/backend/.venv not present)"
fi

if [ -d app/frontend/node_modules ]; then
  echo "== App frontend =="
  (cd app/frontend && npm test -- --run)
else
  echo "(skip app frontend tests: node_modules not present)"
fi

echo "All checks passed."
