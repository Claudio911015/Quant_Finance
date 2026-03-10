#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if ! command -v doxygen >/dev/null 2>&1; then
  echo "Error: doxygen is not installed. Install it via apt or brew." >&2
  exit 1
fi

if ! command -v dot >/dev/null 2>&1; then
  echo "Warning: graphviz dot not installed; class diagrams won't render." >&2
fi

echo "Generating Doxygen docs..."
doxygen Doxyfile

echo "Done. Open docs/doxygen/html/index.html in a browser."
