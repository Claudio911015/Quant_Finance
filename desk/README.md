# QF Desk

Aplicación local para valuar y medir riesgo de una cartera demo (`MX-DEMO`, datos sintéticos) con el motor C++ de Quant_Finance. El backend Flask llama a `qfpy` para toda la matemática financiera; la UI (React + TypeScript) consume la API.

## Requisitos

- Python 3.8 de Anaconda con Flask 2.3.3 y pytest 8.2.0 (`/home/claudio/anaconda3/bin/python`).
- Node 22 y npm 10.
- CMake y compilador C++20.
- GoogleTest (tests C++) y pybind11 (bindings `qfpy`).

## Instalación

Desde la raíz del repo `Quant_Finance`:

```bash
cmake -S . -B build
cmake --build build -j4
cd desk/ui && npm ci && cd ../..
```

## Ejecutar

```bash
./desk/run.sh
```

El script compila `qfpy` si falta `build/src/qfpy*.so`, construye la UI con `npm run build` y levanta el servidor. Abrir `http://localhost:5070`.

Para usar otro intérprete de Python: `QF_PYTHON=/ruta/a/python ./desk/run.sh`.

## Datos

- Base SQLite: `desk/data/desk.db` (no versionada; se crea y siembra al arrancar).
- `MX-DEMO` es una cartera sintética generada por el seed; no representa posiciones reales.

## Tests

Desde la raíz del repo:

```bash
# C++ (347 tests)
cmake --build build -j4 2>&1 | tail -3 && cd build && ctest --output-on-failure 2>&1 | tail -3; cd ..

# Bindings Python existentes
cmake --build build --target pytests 2>&1 | tail -3

# Backend
/home/claudio/anaconda3/bin/python -m pytest desk/api/tests -q 2>&1 | tail -3

# Frontend
cd desk/ui && npm test 2>&1 | tail -5 && npm run build 2>&1 | tail -5
```
