#!/usr/bin/env bash
# Regenera la validación independiente: exporta casos del desk, valúa con QuantLib y compara.
# BACKEND_PY y QL_PY se pueden sobrescribir para correrlo en otra máquina.
set -euo pipefail
cd "$(dirname "$0")/../.."
BACKEND_PY="${BACKEND_PY:-/home/claudio/anaconda3/bin/python}"
QL_PY="${QL_PY:-/home/claudio/anaconda3/envs/quantsuite-oracle/bin/python}"

"$BACKEND_PY" -m desk.validation.export_cases
"$QL_PY" desk/validation/run_quantlib.py
"$BACKEND_PY" -m desk.validation.compare
