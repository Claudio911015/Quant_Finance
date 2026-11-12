#!/usr/bin/env bash
# Arranca QF Desk: compila qfpy si falta, construye la UI y levanta Flask en :5070.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="${QF_PYTHON:-/home/claudio/anaconda3/bin/python}"

if ! "$PY" -c "import QuantLib" 2>/dev/null; then
  echo "[run.sh] falta QuantLib en $PY: $PY -m pip install \"QuantLib==1.42.1\"" >&2
  exit 1
fi

# 1. Binding C++ qfpy
if ! compgen -G "$ROOT/build/src/qfpy*.so" > /dev/null; then
  echo "[run.sh] falta build/src/qfpy*.so; compilando qfpy..."
  cmake -S "$ROOT" -B "$ROOT/build"
  cmake --build "$ROOT/build" --target qfpy -j4
fi

# 2. UI (React + Vite)
cd "$ROOT/desk/ui"
if [ ! -d node_modules ]; then
  npm ci
fi
npm run build

# 3. Backend Flask
cd "$ROOT"
exec "$PY" -m desk.api.app
