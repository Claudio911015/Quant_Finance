# Design Spec — QuantEngine: Merge de Quant_Finance y MarketDataFeed

**Fecha:** 2026-04-19
**Enfoque elegido:** Opción B — QF como base, absorber MDF por módulos

---

## Contexto

Quant_Finance (QF) es una librería C++20 de pricing cuantitativo con pricing engines, modelos de tasas/equity, XVA y bindings Python. MarketDataFeed (MDF) es una librería C++20 de descarga y almacenamiento de datos de mercado reales (SOFR, Treasury yields) con dashboard Flask.

El objetivo es un merge completo en un repo nuevo llamado **QuantEngine**, bajo namespace `qf::`, con una sola web app y todos los bindings Python conservados.

El valor arquitectónico central de la fusión: los feeds reales de MDF alimentan el `MarketEnvironment` de QF vía un `MarketDataBridge`, permitiendo pricing con curvas reales bootstrapped desde datos SOFR/Treasury descargados automáticamente.

---

## Arquitectura general

### Estructura de módulos

```
include/qf/
├── core/           # tipos base (de QF)
├── instruments/    # Option, Bond, IRS, ScheduledSwap (de QF)
├── models/         # IRateModel, IEquityModel, Vasicek, HullWhite, BS, Heston (de QF)
├── pricingengines/ # IPricingEngine, EngineFactory, BS/MC/BT/FDM/Heston engines (de QF)
├── termstructure/  # YieldCurve, bootstrap (de QF)
├── risk/           # risk metrics (de QF)
├── xva/            # CVA engine, NettingSet, FlatHazardRate (de QF)
├── math/           # utilidades numéricas (de QF)
├── http/           # HTTP client libcurl wrapper (de mdf::http)
├── storage/        # SQLite WAL, UPSERT, prepared statements (de mdf::storage)
└── feeds/          # DataFeed, SOFRFeed, TreasuryFeed, MarketDataBridge (de mdf::feeds + nuevo)
```

### Mapeo de namespaces

| Antes (MDF)        | Después (QuantEngine) |
|--------------------|-----------------------|
| `mdf::http`        | `qf::http`            |
| `mdf::storage`     | `qf::storage`         |
| `mdf::feeds`       | `qf::feeds`           |
| `mdf::core::SOFRRate`     | `qf::feeds::SOFRRate`     |
| `mdf::core::SOFRAverages` | `qf::feeds::SOFRAverages` |
| `mdf::core::TreasuryYield`| `qf::feeds::TreasuryYield`|

Todos los namespaces de QF (`qf::instruments`, `qf::models`, etc.) se preservan sin cambios.

### Componente nuevo: `MarketDataBridge`

```cpp
// include/qf/feeds/market_data_bridge.hpp
namespace qf::feeds {
    class MarketDataBridge {
    public:
        explicit MarketDataBridge(qf::storage::Database& db);
        // Lee TreasuryYield desde SQLite y bootstraps una YieldCurve
        qf::termstructure::YieldCurve buildYieldCurve(Date asOf) const;
        // Popula un MarketEnvironment con la curva bootstrapped
        void populate(qf::MarketEnvironment& env, Date asOf) const;
    };
}
```

Este es el puente que conecta los datos reales con el motor de pricing.

---

## Build system

Base: CMakeLists.txt de QF, extendido con dependencias de MDF.

### Dependencias añadidas

| Dependencia    | Integración              |
|----------------|--------------------------|
| nlohmann/json  | FetchContent             |
| libcurl        | find_package (opcional)  |
| SQLite3        | find_package (opcional)  |

GoogleTest v1.14.0 (ya en QF via FetchContent) se reutiliza para los tests de MDF.

### Targets nuevos

```cmake
add_library(qf_http    src/http/client.cpp)
add_library(qf_storage src/storage/database.cpp)
add_library(qf_feeds   src/feeds/sofr_feed.cpp src/feeds/treasury_feed.cpp)
add_library(qf_bridge  src/feeds/market_data_bridge.cpp)
```

### Objetivo de tests

≥153 tests de QF (100% passing en master) + tests de `qf::http`, `qf::storage`, `qf::feeds`, `qf::bridge`. Todos bajo un único suite `qf_tests`.

---

## Web app unificada

Una sola Flask app en `web/app.py`, puerto **5001**.

| Tab               | Origen | Datos          |
|-------------------|--------|----------------|
| SOFR Rates        | MDF    | Feed FRBNY     |
| SOFR Swaps        | MDF    | Feed FRBNY     |
| SOFR Futures      | MDF    | Feed FRBNY     |
| PCA Analysis      | MDF    | SQLite         |
| Options           | QF     | MarketEnvironment |
| Bonds             | QF     | YieldCurve     |
| Interest Rate Swaps | QF   | **YieldCurve bootstrapped desde TreasuryFeed** (vía MarketDataBridge) |

El tab IRS es el único que cambia funcionalmente: pasa de curvas hardcodeadas a curvas reales via `MarketDataBridge`.

---

## Python bindings

Se conservan sin cambios:
- `qfpy` — bindings de instruments, models, pricingengines
- `qfxva` — bindings del CVA engine

Posible extensión futura (fuera de scope de este merge): `qffeeds` para acceso Python a `qf::feeds`.

---

## Secuencia de migración

Cada paso termina con build limpio y todos los tests pasando.

| Paso | Acción |
|------|--------|
| 1 | Crear repo `QuantEngine` en `~/Git/QuantEngine/`, copiar QF como base, ajustar CMakeLists.txt y README |
| 2 | Migrar `qf::http` — copiar `src/http/` y `include/mdf/http/` → `include/qf/http/`, renombrar namespace |
| 3 | Migrar `qf::storage` — copiar `src/storage/` y `include/mdf/storage/`, renombrar namespace |
| 4 | Migrar `qf::feeds` — copiar `src/feeds/` e `include/mdf/feeds/`, renombrar namespaces y tipos `mdf::core::*` → `qf::feeds::*` |
| 5 | Implementar `MarketDataBridge` (`TreasuryYield[]` → `YieldCurve::bootstrap()` → `MarketEnvironment`) |
| 6 | Fusionar web apps — un solo `web/app.py` con los 7 tabs |
| 7 | Conectar tab IRS al `MarketDataBridge` (curvas reales en lugar de hardcodeadas) |
| 8 | Migrar y unificar tests — todos los tests MDF bajo `qf_tests`, objetivo 100% passing |

---

## Criterios de éxito

- Build limpio sin warnings relevantes
- 100% tests passing (QF baseline + tests de módulos MDF migrados)
- Web app corre en puerto 5001 con los 7 tabs funcionales
- El tab IRS usa curvas reales bootstrapped desde datos Treasury descargados
- `qfpy` y `qfxva` siguen compilando y funcionando
