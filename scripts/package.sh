#!/usr/bin/env bash
# Builds taskmanager.zip from the project files: no virtualenv, caches, databases or git data.
# Usage: scripts/package.sh   (from anywhere; the zip lands in the repository root)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NAME="taskmanager"
OUT="$ROOT/$NAME.zip"

rm -f "$OUT"
cd "$ROOT"
zip -q -r "$OUT" . \
  -x ".git/*" ".venv/*" "*/__pycache__/*" "*.pyc" ".ruff_cache/*" \
     "*/.coverage" "*/htmlcov/*" "*/data/*" "*.sqlite3*" ".DS_Store" "*/.DS_Store" \
     ".env" "*.zip"

echo "wrote $OUT ($(du -h "$OUT" | cut -f1))"
unzip -l "$OUT" | tail -1
