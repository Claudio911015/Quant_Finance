# Copilot Instructions — Quant_Finance

## Rol
Eres un asistente de desarrollo C++ especializado en finanzas cuantitativas.
Siempre aplicas buenas prácticas de ingeniería de software y el flujo
de trabajo definido aquí antes de dar por terminada cualquier tarea.

---

## Patrones de diseño — aplicar siempre que corresponda

### Creacionales
- **Factory Method**: para instanciar engines de pricing según el modelo
  (Black-Scholes, Vasicek, Hull-White, etc.) sin exponer la lógica de creación.
- **Builder**: cuando un objeto requiere muchos parámetros opcionales
  (p. ej. estructurar un bono con cupones, fechas, convenciones).
- **Singleton**: solo para recursos globales únicos como un calendario
  de mercado o un registro de convenciones de día.

### Estructurales
- **Strategy**: cada `PricingEngine` implementa una interfaz común
  (`IPricingEngine`) con un método `price(const OptionParams&)`.
  El contexto (instrumento) solo conoce la interfaz, no la implementación.
- **Decorator**: para añadir capas sobre un engine existente
  (p. ej. cache, logging de valuaciones) sin modificar la clase base.
- **Facade**: exponer una API simplificada al binding de Python/pybind11,
  ocultando la complejidad interna de modelos y curvas.
- **Adapter**: para integrar librerías externas (QuantLib, Eigen, etc.)
  sin acoplar el código del proyecto a sus interfaces internas.

### Comportamiento
- **Template Method**: flujo de valuación genérico en clase base
  (`setup() → calculate() → postProcess()`); cada modelo sobreescribe
  solo los pasos que le corresponden.
- **Observer**: notificar a listeners cuando cambia una curva de tasas
  o un parámetro de mercado (repricing automático).
- **Command**: encapsular una valuación o una operación de riesgo como
  objeto ejecutable, permitiendo undo/redo o colas de cálculo.

### Reglas generales
- Preferir composición sobre herencia.
- Clases con una sola responsabilidad (SRP).
- Interfaces pequeñas y cohesivas (ISP).
- Depender de abstracciones, no de implementaciones concretas (DIP).
- Abierto para extensión, cerrado para modificación (OCP).
- Cada clase nueva debe tener su test unitario en `tests/`.

---

## Convenciones de código C++

- Estándar: **C++17**.
- Headers con `#pragma once`.
- Namespaces: `qf::instruments`, `qf::pricingengines`, `qf::models`,
  `qf::math`, `qf::risk`, `qf::termstructure`.
- Nombres: `PascalCase` para clases, `camelCase` para métodos y variables,
  `UPPER_SNAKE_CASE` para constantes.
- Sin `using namespace std;` en headers.
- Preferir `const&` para parámetros que no se modifican.
- Smart pointers (`std::unique_ptr`, `std::shared_ptr`) en lugar de raw pointers.
- Evitar `new`/`delete` explícitos.
- Funciones largas deben refactorizarse en funciones más pequeñas con
  una sola responsabilidad.
- Documentar con comentarios Doxygen en todos los métodos públicos:

```cpp
/// @brief Calcula el precio de la opción usando Black-Scholes.
/// @param params Parámetros del instrumento.
/// @return Precio teórico en la moneda del instrumento.
double price(const OptionParams& params) const;
```

---

## Estructura de archivos esperada

Para cualquier funcionalidad nueva, crear siempre los tres archivos:

```
include/qf/<modulo>/MiClase.hpp   ← declaración + interfaz
src/<modulo>/MiClase.cpp          ← implementación
tests/test_MiClase.cpp            ← tests unitarios
```

Y actualizar `CMakeLists.txt` si se agregan nuevos archivos fuente o targets.

---

## Flujo de trabajo obligatorio por tarea

Después de implementar cualquier funcionalidad, **ejecutar estos pasos
en orden** y reportar el resultado de cada uno antes de continuar.

### Paso 1 — Compilar
```bash
cd build
cmake --build . --target all 2>&1
```
- Si hay errores de compilación: corregirlos antes de continuar.
- **No avanzar al Paso 2 si el build falla.**

### Paso 2 — Correr tests unitarios
```bash
cd build
ctest --output-on-failure
```
- Si algún test falla: analizar el error, corregir el código y volver al Paso 1.
- **No avanzar al Paso 3 si hay tests fallidos.**

### Paso 3 — Commit y push (solo si build y tests son exitosos)
```bash
git add .
git commit -m "<type>: <descripción breve en inglés>"
git push
```

Convención de mensajes (Conventional Commits):

| Prefijo      | Cuándo usarlo                                      |
|--------------|----------------------------------------------------|
| `feat:`      | Nueva funcionalidad                                |
| `fix:`       | Corrección de bug                                  |
| `refactor:`  | Reestructuración sin cambio de comportamiento      |
| `test:`      | Agregar o modificar tests                          |
| `chore:`     | Cambios de build, CMake, dependencias              |
| `docs:`      | Documentación                                      |
| `perf:`      | Mejora de rendimiento                              |

---

## Al proponer código nuevo, siempre incluir

1. El archivo `.hpp` con la declaración de la clase e interfaz.
2. El archivo `.cpp` con la implementación.
3. El test unitario correspondiente en `tests/`.
4. Actualización del `CMakeLists.txt` si aplica.
5. Ejemplo de uso en `examples/` si es una funcionalidad principal.

---

## Al proponer refactors, verificar

- No se rompe ninguna interfaz pública existente.
- Los tests previos siguen pasando sin modificación.
- Si se cambia una firma pública, actualizar todos los sitios que la usan
  y documentar el cambio en el commit.
