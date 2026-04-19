# QuantEngine Merge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Crear el repo `QuantEngine` fusionando Quant_Finance y MarketDataFeed en una sola librería C++20 bajo namespace `qf::`, con web app unificada de 7 tabs y bindings Python conservados.

**Architecture:** QF como base (153 tests, arquitectura post-refactor), MDF absorbido por módulos: `qf::http` → `qf::storage` → `qf::feeds` → `MarketDataBridge`. El bridge conecta `TreasuryYield[]` del SQLite con `YieldCurve::bootstrap()` de QF, permitiendo pricing con curvas reales.

**Tech Stack:** C++20, CMake, GoogleTest, libcurl, SQLite3, nlohmann/json, pybind11, Flask, Plotly.js

---

## Mapa de archivos

### Archivos nuevos (Tasks 2–5)
```
include/qf/http/client.hpp            ← mdf::http → qf::http
src/http/client.cpp
include/qf/storage/database.hpp       ← mdf::storage → qf::storage
src/storage/database.cpp
include/qf/feeds/types.hpp            ← mdf::core → qf::feeds
include/qf/feeds/feed.hpp
include/qf/feeds/sofr_feed.hpp
include/qf/feeds/treasury_feed.hpp
src/feeds/sofr_feed.cpp
src/feeds/treasury_feed.cpp
include/qf/feeds/market_data_bridge.hpp   ← nuevo
src/feeds/market_data_bridge.cpp
tests/test_http_client.cpp
tests/test_storage.cpp
tests/test_sofr_feed.cpp
tests/test_treasury_feed.cpp
tests/test_market_data_bridge.cpp
```

### Archivos modificados
```
CMakeLists.txt                 ← project name, CURL, SQLite3, nlohmann/json
src/CMakeLists.txt             ← targets qf_http, qf_storage, qf_feeds
tests/CMakeLists.txt           ← nuevos test files
src/python_bindings/qfpy.cpp   ← exponer bootstrap + BootstrapInstrument (Task 7)
web/app.py                     ← 7 tabs unificados (Task 6+7)
web/scheduler.py               ← actualizar path binario (Task 6)
```

---

## Task 1: Crear repo QuantEngine desde base QF

**Files:**
- Create: `~/Git/QuantEngine/` (copia de QF)
- Modify: `~/Git/QuantEngine/CMakeLists.txt`

- [ ] **Step 1: Copiar QF al nuevo directorio**

```bash
rsync -av --exclude='build/' --exclude='.git/' \
  ~/Git/Quant_Finance/ ~/Git/QuantEngine/
```

- [ ] **Step 2: Inicializar git**

```bash
cd ~/Git/QuantEngine
git init
git add -A
git commit -m "feat: init QuantEngine from Quant_Finance base" \
  --author="claudiocp_2@hotmail.com <claudiocp_2@hotmail.com>"
```

- [ ] **Step 3: Actualizar nombre del proyecto en CMakeLists.txt**

En `CMakeLists.txt`, cambiar:
```cmake
project(QuantFinance
    VERSION 0.1.0
    DESCRIPTION "C++ quantitative finance library"
    LANGUAGES CXX
)
```
por:
```cmake
project(QuantEngine
    VERSION 0.1.0
    DESCRIPTION "C++20 quantitative finance library with live market data feeds"
    LANGUAGES CXX
)
```

- [ ] **Step 4: Verificar build limpio**

```bash
cd ~/Git/QuantEngine
mkdir -p build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
cmake --build . --target all 2>&1 | tail -5
ctest --output-on-failure 2>&1 | tail -10
```

Esperado: build sin errores, 153 tests pasando.

- [ ] **Step 5: Commit**

```bash
cd ~/Git/QuantEngine
git add CMakeLists.txt
git commit -m "chore: rename project to QuantEngine" \
  --author="claudiocp_2@hotmail.com <claudiocp_2@hotmail.com>"
```

---

## Task 2: Migrar qf::http

**Files:**
- Create: `include/qf/http/client.hpp`
- Create: `src/http/client.cpp`
- Create: `tests/test_http_client.cpp`
- Modify: `CMakeLists.txt`
- Modify: `src/CMakeLists.txt`
- Modify: `tests/CMakeLists.txt`

- [ ] **Step 1: Copiar fuentes de MDF**

```bash
mkdir -p ~/Git/QuantEngine/include/qf/http
mkdir -p ~/Git/QuantEngine/src/http
cp ~/Git/MarketDataFeed/include/mdf/http/client.hpp ~/Git/QuantEngine/include/qf/http/client.hpp
cp ~/Git/MarketDataFeed/src/http/client.cpp ~/Git/QuantEngine/src/http/client.cpp
```

- [ ] **Step 2: Renombrar namespace en client.hpp**

Editar `include/qf/http/client.hpp` — reemplazar:
```cpp
namespace mdf::http {
```
por:
```cpp
namespace qf::http {
```
Y al final reemplazar:
```cpp
} // namespace mdf::http
```
por:
```cpp
} // namespace qf::http
```

- [ ] **Step 3: Renombrar namespace en client.cpp**

Editar `src/http/client.cpp`:
1. Cambiar `#include <mdf/http/client.hpp>` → `#include <qf/http/client.hpp>`
2. Cambiar `namespace mdf::http {` → `namespace qf::http {`
3. Cambiar `} // namespace mdf::http` → `} // namespace qf::http`

- [ ] **Step 4: Añadir dependencia libcurl y target qf_http en CMakeLists.txt**

En `CMakeLists.txt`, después de la sección `option(QF_BUILD_EXAMPLES ...)`:
```cmake
# ── External dependencies ─────────────────────────────────────────────────────
find_package(CURL REQUIRED)
find_package(SQLite3 REQUIRED)

include(FetchContent)
FetchContent_Declare(
    json
    GIT_REPOSITORY https://github.com/nlohmann/json.git
    GIT_TAG        v3.11.3
    GIT_SHALLOW    TRUE
)
FetchContent_MakeAvailable(json)
```

- [ ] **Step 5: Añadir target qf_http en src/CMakeLists.txt**

Al final de `src/CMakeLists.txt`, después del bloque de `qf`:
```cmake
# ── qf_http ────────────────────────────────────────────────────────────────────
add_library(qf_http
    http/client.cpp
)
target_include_directories(qf_http PUBLIC
    $<BUILD_INTERFACE:${CMAKE_SOURCE_DIR}/include>
)
target_link_libraries(qf_http PUBLIC CURL::libcurl)
target_compile_features(qf_http PUBLIC cxx_std_20)
```

- [ ] **Step 6: Escribir test de compilación**

Crear `tests/test_http_client.cpp`:
```cpp
#include <gtest/gtest.h>
#include <qf/http/client.hpp>

// Verifica que Client compila y que HttpError es una std::runtime_error
TEST(HttpClient, ErrorIsRuntimeError) {
    qf::http::HttpError err("test error");
    EXPECT_STREQ(err.what(), "test error");
}

TEST(HttpClient, ResponseHasFields) {
    qf::http::HttpResponse r;
    r.statusCode = 200;
    r.body = "ok";
    EXPECT_EQ(r.statusCode, 200);
    EXPECT_EQ(r.body, "ok");
}
```

- [ ] **Step 7: Registrar test en tests/CMakeLists.txt**

En `tests/CMakeLists.txt`, localizar el bloque `add_executable(qf_tests ...)` y añadir `test_http_client.cpp` a la lista de fuentes. También añadir `qf_http` a `target_link_libraries`:
```cmake
target_link_libraries(qf_tests PRIVATE qf qf_http gtest_main)
```

- [ ] **Step 8: Build y tests**

```bash
cd ~/Git/QuantEngine/build
cmake .. -DCMAKE_BUILD_TYPE=Release
cmake --build . --target all 2>&1 | tail -5
ctest --output-on-failure -R "HttpClient" 2>&1
```

Esperado: 2 tests nuevos pasando, 153 anteriores intactos.

- [ ] **Step 9: Commit**

```bash
cd ~/Git/QuantEngine
git add include/qf/http/ src/http/ tests/test_http_client.cpp CMakeLists.txt src/CMakeLists.txt tests/CMakeLists.txt
git commit -m "feat(http): migrate mdf::http → qf::http (libcurl wrapper)" \
  --author="claudiocp_2@hotmail.com <claudiocp_2@hotmail.com>"
```

---

## Task 3: Migrar qf::storage

**Files:**
- Create: `include/qf/storage/database.hpp`
- Create: `src/storage/database.cpp`
- Create: `tests/test_storage.cpp`
- Modify: `src/CMakeLists.txt`
- Modify: `tests/CMakeLists.txt`

- [ ] **Step 1: Copiar fuentes de MDF**

```bash
mkdir -p ~/Git/QuantEngine/include/qf/storage
mkdir -p ~/Git/QuantEngine/src/storage
cp ~/Git/MarketDataFeed/include/mdf/storage/database.hpp ~/Git/QuantEngine/include/qf/storage/database.hpp
cp ~/Git/MarketDataFeed/src/storage/database.cpp ~/Git/QuantEngine/src/storage/database.cpp
```

- [ ] **Step 2: Actualizar includes y namespaces en database.hpp**

Editar `include/qf/storage/database.hpp`:
1. Cambiar `#include <mdf/core/types.hpp>` → `#include <qf/feeds/types.hpp>`
2. Cambiar `namespace mdf::storage {` → `namespace qf::storage {`
3. Cambiar `core::SOFRRate` → `feeds::SOFRRate` (3 ocurrencias)
4. Cambiar `core::SOFRAverages` → `feeds::SOFRAverages` (2 ocurrencias)
5. Cambiar `core::TreasuryYield` → `feeds::TreasuryYield` (2 ocurrencias)
6. Cambiar `} // namespace mdf::storage` → `} // namespace qf::storage`

Nota: `include/qf/feeds/types.hpp` se creará en Task 4. El header se compila en Task 4.

- [ ] **Step 3: Actualizar includes y namespace en database.cpp**

Editar `src/storage/database.cpp`:
1. Cambiar `#include <mdf/storage/database.hpp>` → `#include <qf/storage/database.hpp>`
2. Cambiar `namespace mdf::storage {` → `namespace qf::storage {`
3. Cambiar `} // namespace mdf::storage` → `} // namespace qf::storage`

- [ ] **Step 4: Añadir target qf_storage en src/CMakeLists.txt**

Después del bloque `qf_http`:
```cmake
# ── qf_storage ────────────────────────────────────────────────────────────────
add_library(qf_storage
    storage/database.cpp
)
target_include_directories(qf_storage PUBLIC
    $<BUILD_INTERFACE:${CMAKE_SOURCE_DIR}/include>
)
target_link_libraries(qf_storage PUBLIC SQLite3::SQLite3)
target_compile_features(qf_storage PUBLIC cxx_std_20)
```

- [ ] **Step 5: Crear tests/test_storage.cpp** (migrado de MDF test_database.cpp)

```cpp
#include <gtest/gtest.h>
#include <qf/storage/database.hpp>
#include <qf/feeds/types.hpp>
#include <memory>

using namespace qf::storage;
using namespace qf::feeds;

namespace {
    std::unique_ptr<Database> makeDB() {
        auto db = std::make_unique<Database>(":memory:");
        db->createTables();
        return db;
    }

    std::vector<SOFRRate> sampleRates() {
        return {
            {"2026-03-05", 4.30, 4.28, 4.29, 4.32, 4.35, 2100.0},
            {"2026-03-06", 4.31, 4.29, 4.30, 4.33, 4.36, 2150.0},
            {"2026-03-07", 4.29, 4.27, 4.28, 4.31, 4.34, 2080.0},
        };
    }

    std::vector<TreasuryYield> sampleTreasury() {
        return {
            {"2026-03-07", "3M", 4.31},
            {"2026-03-07", "1Y", 4.20},
            {"2026-03-07", "2Y", 4.05},
            {"2026-03-07", "5Y", 3.95},
            {"2026-03-07", "10Y", 4.10},
        };
    }
}

TEST(Storage, CreateTablesSucceeds) {
    EXPECT_NO_THROW(makeDB());
}

TEST(Storage, CreateTablesIdempotent) {
    Database db(":memory:");
    EXPECT_NO_THROW(db.createTables());
    EXPECT_NO_THROW(db.createTables());
}

TEST(Storage, InsertAndQuerySOFRRates) {
    auto db = makeDB();
    int inserted = db->insertSOFRRates(sampleRates());
    EXPECT_EQ(inserted, 3);
    EXPECT_EQ(db->rowCount("sofr_rates"), 3);

    auto result = db->querySOFRRates();
    ASSERT_EQ(result.size(), 3u);
    EXPECT_DOUBLE_EQ(result[0].rate, 4.30);
}

TEST(Storage, QuerySOFRRatesByDateRange) {
    auto db = makeDB();
    db->insertSOFRRates(sampleRates());
    auto result = db->querySOFRRates("2026-03-06", "2026-03-07");
    EXPECT_EQ(result.size(), 2u);
}

TEST(Storage, InsertAndQueryTreasuryYields) {
    auto db = makeDB();
    int inserted = db->insertTreasuryYields(sampleTreasury());
    EXPECT_EQ(inserted, 5);

    auto result = db->queryTreasuryYields("2026-03-07", "2026-03-07");
    EXPECT_EQ(result.size(), 5u);
}

TEST(Storage, UpsertTreasuryYields) {
    auto db = makeDB();
    db->insertTreasuryYields(sampleTreasury());
    db->insertTreasuryYields(sampleTreasury());  // upsert — no duplicates
    EXPECT_EQ(db->rowCount("treasury_yields"), 5);
}
```

- [ ] **Step 6: Registrar en tests/CMakeLists.txt**

Añadir `test_storage.cpp` a las fuentes de `qf_tests`. Añadir `qf_storage` a `target_link_libraries`:
```cmake
target_link_libraries(qf_tests PRIVATE qf qf_http qf_storage gtest_main)
```

**Nota:** `qf_feeds` se añadirá en Task 4. El build de este step fallará si se intenta compilar antes de Task 4 porque `qf/feeds/types.hpp` no existe todavía — saltar el build hasta Task 4 Step 7.

- [ ] **Step 7: Commit parcial**

```bash
cd ~/Git/QuantEngine
git add include/qf/storage/ src/storage/ tests/test_storage.cpp src/CMakeLists.txt tests/CMakeLists.txt
git commit -m "feat(storage): migrate mdf::storage → qf::storage (SQLite)" \
  --author="claudiocp_2@hotmail.com <claudiocp_2@hotmail.com>"
```

---

## Task 4: Migrar qf::feeds

**Files:**
- Create: `include/qf/feeds/types.hpp`
- Create: `include/qf/feeds/feed.hpp`
- Create: `include/qf/feeds/sofr_feed.hpp`
- Create: `include/qf/feeds/treasury_feed.hpp`
- Create: `src/feeds/sofr_feed.cpp`
- Create: `src/feeds/treasury_feed.cpp`
- Create: `tests/test_sofr_feed.cpp`
- Create: `tests/test_treasury_feed.cpp`
- Modify: `src/CMakeLists.txt`
- Modify: `tests/CMakeLists.txt`

- [ ] **Step 1: Crear include/qf/feeds/types.hpp**

```cpp
#pragma once
#include <string>
#include <optional>

namespace qf::feeds {

struct SOFRRate {
    std::string effectiveDate;
    double      rate;
    std::optional<double> percentile1;
    std::optional<double> percentile25;
    std::optional<double> percentile75;
    std::optional<double> percentile99;
    std::optional<double> volumeBillions;
};

struct SOFRAverages {
    std::string effectiveDate;
    std::optional<double> average30d;
    std::optional<double> average90d;
    std::optional<double> average180d;
    std::optional<double> sofrIndex;
};

struct TreasuryYield {
    std::string date;      // YYYY-MM-DD
    std::string maturity;  // "1M", "3M", "6M", "1Y", "2Y", "3Y", "5Y", "7Y", "10Y", "20Y", "30Y"
    double      rate;      // yield (%)
};

} // namespace qf::feeds
```

- [ ] **Step 2: Crear include/qf/feeds/feed.hpp**

```cpp
#pragma once
#include <string>

namespace qf::feeds {

class DataFeed {
public:
    virtual ~DataFeed() = default;
    virtual std::string name() const = 0;
    virtual int fetchLatest() = 0;
    virtual int fetchRange(const std::string& startDate,
                           const std::string& endDate) = 0;
};

} // namespace qf::feeds
```

- [ ] **Step 3: Copiar y renombrar feed headers**

```bash
mkdir -p ~/Git/QuantEngine/include/qf/feeds
mkdir -p ~/Git/QuantEngine/src/feeds
cp ~/Git/MarketDataFeed/include/mdf/feeds/sofr_feed.hpp ~/Git/QuantEngine/include/qf/feeds/sofr_feed.hpp
cp ~/Git/MarketDataFeed/include/mdf/feeds/treasury_feed.hpp ~/Git/QuantEngine/include/qf/feeds/treasury_feed.hpp
cp ~/Git/MarketDataFeed/src/feeds/sofr_feed.cpp ~/Git/QuantEngine/src/feeds/sofr_feed.cpp
cp ~/Git/MarketDataFeed/src/feeds/treasury_feed.cpp ~/Git/QuantEngine/src/feeds/treasury_feed.cpp
```

- [ ] **Step 4: Actualizar namespaces en sofr_feed.hpp**

Editar `include/qf/feeds/sofr_feed.hpp`:
1. `#include <mdf/feeds/feed.hpp>` → `#include <qf/feeds/feed.hpp>`
2. `#include <mdf/core/types.hpp>` → `#include <qf/feeds/types.hpp>`
3. `#include <mdf/http/client.hpp>` → `#include <qf/http/client.hpp>`
4. `#include <mdf/storage/database.hpp>` → `#include <qf/storage/database.hpp>`
5. `namespace mdf::feeds {` → `namespace qf::feeds {`
6. `storage::Database&` queda igual (mismo sub-namespace relativo)
7. `http::Client` queda igual
8. `core::SOFRRate` → `SOFRRate` (ya en qf::feeds)
9. `core::SOFRAverages` → `SOFRAverages`
10. `} // namespace mdf::feeds` → `} // namespace qf::feeds`

- [ ] **Step 5: Actualizar namespaces en treasury_feed.hpp**

Editar `include/qf/feeds/treasury_feed.hpp` aplicando el mismo patrón que Step 4 (mismos cambios de includes y namespace, `core::TreasuryYield` → `TreasuryYield`).

- [ ] **Step 6: Actualizar includes y namespaces en sofr_feed.cpp y treasury_feed.cpp**

Para `src/feeds/sofr_feed.cpp`:
1. `#include <mdf/feeds/sofr_feed.hpp>` → `#include <qf/feeds/sofr_feed.hpp>`
2. `namespace mdf::feeds {` → `namespace qf::feeds {`
3. `core::SOFRRate` → `SOFRRate`
4. `core::SOFRAverages` → `SOFRAverages`
5. `} // namespace mdf::feeds` → `} // namespace qf::feeds`

Para `src/feeds/treasury_feed.cpp`: mismo patrón, `core::TreasuryYield` → `TreasuryYield`.

- [ ] **Step 7: Añadir target qf_feeds en src/CMakeLists.txt**

Después del bloque `qf_storage`:
```cmake
# ── qf_feeds ────────────────────────────────────────────────────────────────
add_library(qf_feeds
    feeds/sofr_feed.cpp
    feeds/treasury_feed.cpp
)
target_include_directories(qf_feeds PUBLIC
    $<BUILD_INTERFACE:${CMAKE_SOURCE_DIR}/include>
)
target_link_libraries(qf_feeds PUBLIC qf_http qf_storage nlohmann_json::nlohmann_json)
target_compile_features(qf_feeds PUBLIC cxx_std_20)
```

- [ ] **Step 8: Crear tests/test_sofr_feed.cpp** (migrado de MDF)

```cpp
#include <gtest/gtest.h>
#include <qf/feeds/sofr_feed.hpp>
#include <qf/feeds/types.hpp>

using namespace qf::feeds;

static const char* SAMPLE_RATES_JSON = R"({
    "refRates": [
        {
            "effectiveDate": "2026-03-07",
            "type": "SOFR",
            "percentRate": 4.31,
            "percentPercentile1": 4.28,
            "percentPercentile25": 4.29,
            "percentPercentile75": 4.33,
            "percentPercentile99": 4.36,
            "volumeInBillions": 2150.5,
            "revisionIndicator": ""
        },
        {
            "effectiveDate": "2026-03-06",
            "type": "SOFR",
            "percentRate": 4.30,
            "percentPercentile1": 4.27,
            "percentPercentile25": 4.28,
            "percentPercentile75": 4.32,
            "percentPercentile99": 4.35,
            "volumeInBillions": 2100.0,
            "revisionIndicator": ""
        }
    ]
})";

TEST(SOFRFeed, ParseRatesJSON_Count) {
    auto rates = SOFRFeed::parseRatesJSON(SAMPLE_RATES_JSON);
    ASSERT_EQ(rates.size(), 2u);
}

TEST(SOFRFeed, ParseRatesJSON_Values) {
    auto rates = SOFRFeed::parseRatesJSON(SAMPLE_RATES_JSON);
    EXPECT_EQ(rates[0].effectiveDate, "2026-03-07");
    EXPECT_DOUBLE_EQ(rates[0].rate, 4.31);
    EXPECT_TRUE(rates[0].percentile1.has_value());
    EXPECT_DOUBLE_EQ(rates[0].percentile1.value(), 4.28);
}
```

- [ ] **Step 9: Crear tests/test_treasury_feed.cpp** (migrado de MDF)

Copiar el test de parsing CSV de treasury de MDF y actualizar namespaces:
```cpp
#include <gtest/gtest.h>
#include <qf/feeds/treasury_feed.hpp>
#include <qf/feeds/types.hpp>

using namespace qf::feeds;

static const char* SAMPLE_CSV = R"(Date,1 Mo,3 Mo,6 Mo,1 Yr,2 Yr,3 Yr,5 Yr,7 Yr,10 Yr,20 Yr,30 Yr
2026-01-02,4.35,4.31,4.27,4.21,4.08,4.02,3.97,4.00,4.05,4.25,4.30
2026-01-03,4.36,4.32,4.28,4.22,4.09,4.03,3.98,4.01,4.06,4.26,4.31
)";

TEST(TreasuryFeed, ParseCSV_Count) {
    auto yields = TreasuryFeed::parseCSV(SAMPLE_CSV);
    // 2 dates × 11 maturities = 22 records (skips empty columns)
    EXPECT_GT(yields.size(), 0u);
}

TEST(TreasuryFeed, ParseCSV_Values) {
    auto yields = TreasuryFeed::parseCSV(SAMPLE_CSV);
    auto it = std::find_if(yields.begin(), yields.end(), [](const TreasuryYield& y){
        return y.date == "2026-01-02" && y.maturity == "10Y";
    });
    ASSERT_NE(it, yields.end());
    EXPECT_DOUBLE_EQ(it->rate, 4.05);
}
```

- [ ] **Step 10: Actualizar tests/CMakeLists.txt**

Añadir `test_sofr_feed.cpp` y `test_treasury_feed.cpp` a fuentes de `qf_tests`. Actualizar link:
```cmake
target_link_libraries(qf_tests PRIVATE qf qf_http qf_storage qf_feeds gtest_main)
```

- [ ] **Step 11: Build y tests**

```bash
cd ~/Git/QuantEngine/build
cmake .. -DCMAKE_BUILD_TYPE=Release
cmake --build . --target all 2>&1 | tail -5
ctest --output-on-failure 2>&1 | tail -15
```

Esperado: 153 + tests de Storage, SOFRFeed, TreasuryFeed pasando.

- [ ] **Step 12: Commit**

```bash
cd ~/Git/QuantEngine
git add include/qf/feeds/ src/feeds/ tests/test_sofr_feed.cpp tests/test_treasury_feed.cpp \
        src/CMakeLists.txt tests/CMakeLists.txt
git commit -m "feat(feeds): migrate mdf::feeds → qf::feeds (SOFR + Treasury)" \
  --author="claudiocp_2@hotmail.com <claudiocp_2@hotmail.com>"
```

---

## Task 5: Implementar MarketDataBridge

**Files:**
- Create: `include/qf/feeds/market_data_bridge.hpp`
- Create: `src/feeds/market_data_bridge.cpp`
- Create: `tests/test_market_data_bridge.cpp`
- Modify: `src/CMakeLists.txt`
- Modify: `tests/CMakeLists.txt`

- [ ] **Step 1: Crear include/qf/feeds/market_data_bridge.hpp**

```cpp
#pragma once
#include <qf/feeds/types.hpp>
#include <qf/storage/database.hpp>
#include <qf/termstructure/yieldcurve.hpp>
#include <qf/termstructure/bootstrap.hpp>
#include <qf/core/market_environment.hpp>
#include <string>
#include <vector>
#include <stdexcept>

namespace qf::feeds {

class BridgeError : public std::runtime_error {
public:
    explicit BridgeError(const std::string& msg) : std::runtime_error(msg) {}
};

/// Converts stored TreasuryYield observations into a bootstrapped YieldCurve
/// and populates a MarketEnvironment with it.
class MarketDataBridge {
public:
    explicit MarketDataBridge(storage::Database& db);

    /// Build a YieldCurve bootstrapped from Treasury yields stored for the given date.
    /// Throws BridgeError if fewer than 2 observations are available for asOf.
    termstructure::YieldCurve buildYieldCurve(const std::string& asOf) const;

    /// Populate env with a YieldCurve under the key "treasury".
    void populate(core::MarketEnvironment& env, const std::string& asOf) const;

private:
    storage::Database& db_;

    /// Map Treasury maturity string to years (e.g. "3M" → 0.25, "10Y" → 10.0).
    static double maturityToYears(const std::string& maturity);

    /// Convert TreasuryYield records into BootstrapInstruments.
    static std::vector<termstructure::BootstrapInstrument>
        toBootstrapInstruments(const std::vector<TreasuryYield>& yields);
};

} // namespace qf::feeds
```

- [ ] **Step 2: Crear src/feeds/market_data_bridge.cpp**

```cpp
#include <qf/feeds/market_data_bridge.hpp>
#include <algorithm>
#include <stdexcept>
#include <unordered_map>

namespace qf::feeds {

MarketDataBridge::MarketDataBridge(storage::Database& db) : db_(db) {}

double MarketDataBridge::maturityToYears(const std::string& maturity) {
    static const std::unordered_map<std::string, double> table = {
        {"1M",  1.0/12}, {"2M",  2.0/12}, {"3M",  3.0/12},
        {"4M",  4.0/12}, {"6M",  6.0/12}, {"1Y",  1.0},
        {"2Y",  2.0},    {"3Y",  3.0},    {"5Y",  5.0},
        {"7Y",  7.0},    {"10Y", 10.0},   {"20Y", 20.0},
        {"30Y", 30.0}
    };
    auto it = table.find(maturity);
    if (it == table.end())
        throw BridgeError("Unknown maturity: " + maturity);
    return it->second;
}

std::vector<termstructure::BootstrapInstrument>
MarketDataBridge::toBootstrapInstruments(const std::vector<TreasuryYield>& yields) {
    std::vector<termstructure::BootstrapInstrument> insts;
    insts.reserve(yields.size());
    for (const auto& y : yields) {
        double T = maturityToYears(y.maturity);
        termstructure::BootstrapInstrument::Type type =
            (T <= 1.0)
                ? termstructure::BootstrapInstrument::Deposit
                : termstructure::BootstrapInstrument::Swap;
        double freq = (type == termstructure::BootstrapInstrument::Swap) ? 2.0 : 1.0;
        insts.push_back({T, y.rate / 100.0, type, freq});
    }
    // Must be sorted by maturity for bootstrap to work
    std::sort(insts.begin(), insts.end(),
              [](const auto& a, const auto& b){ return a.maturity < b.maturity; });
    return insts;
}

termstructure::YieldCurve MarketDataBridge::buildYieldCurve(const std::string& asOf) const {
    auto yields = db_.queryTreasuryYields(asOf, asOf);
    if (yields.size() < 2)
        throw BridgeError("Insufficient Treasury data for date " + asOf +
                          " (need ≥2 points, got " + std::to_string(yields.size()) + ")");
    auto instruments = toBootstrapInstruments(yields);
    return termstructure::bootstrap(instruments);
}

void MarketDataBridge::populate(core::MarketEnvironment& env, const std::string& asOf) const {
    auto curve = buildYieldCurve(asOf);
    env.setCurve("treasury", std::move(curve));
}

} // namespace qf::feeds
```

- [ ] **Step 3: Añadir market_data_bridge.cpp a qf_feeds en src/CMakeLists.txt**

Modificar el target `qf_feeds`:
```cmake
add_library(qf_feeds
    feeds/sofr_feed.cpp
    feeds/treasury_feed.cpp
    feeds/market_data_bridge.cpp
)
target_link_libraries(qf_feeds PUBLIC qf_http qf_storage qf nlohmann_json::nlohmann_json)
```

(Se añade `qf` para acceso a `termstructure` y `core::MarketEnvironment`.)

- [ ] **Step 4: Crear tests/test_market_data_bridge.cpp**

```cpp
#include <gtest/gtest.h>
#include <qf/feeds/market_data_bridge.hpp>
#include <qf/storage/database.hpp>
#include <qf/core/market_environment.hpp>
#include <memory>

using namespace qf::feeds;
using namespace qf::storage;

namespace {
    std::unique_ptr<Database> makeDB() {
        auto db = std::make_unique<Database>(":memory:");
        db->createTables();
        return db;
    }

    void populateTreasury(Database& db, const std::string& date) {
        std::vector<TreasuryYield> yields = {
            {date, "3M",  4.31}, {date, "6M",  4.28},
            {date, "1Y",  4.20}, {date, "2Y",  4.05},
            {date, "3Y",  3.98}, {date, "5Y",  3.95},
            {date, "7Y",  4.00}, {date, "10Y", 4.10},
        };
        db.insertTreasuryYields(yields);
    }
}

TEST(MarketDataBridge, BuildYieldCurveReturnsValidCurve) {
    auto db = makeDB();
    populateTreasury(*db, "2026-03-07");
    MarketDataBridge bridge(*db);

    auto curve = bridge.buildYieldCurve("2026-03-07");
    double r1 = curve.zeroRate(1.0);
    double r10 = curve.zeroRate(10.0);
    EXPECT_GT(r1, 0.0);
    EXPECT_GT(r10, 0.0);
    // Sanity: rates in reasonable range (2%–8%)
    EXPECT_GT(r1, 0.02);
    EXPECT_LT(r1, 0.08);
}

TEST(MarketDataBridge, ThrowsOnInsufficientData) {
    auto db = makeDB();
    MarketDataBridge bridge(*db);
    EXPECT_THROW(bridge.buildYieldCurve("2026-03-07"), BridgeError);
}

TEST(MarketDataBridge, PopulatesMarketEnvironment) {
    auto db = makeDB();
    populateTreasury(*db, "2026-03-07");
    MarketDataBridge bridge(*db);

    qf::core::MarketEnvironment env;
    EXPECT_NO_THROW(bridge.populate(env, "2026-03-07"));
    // Curve registered under "treasury"
    auto& curve = env.curve("treasury");
    EXPECT_GT(curve.discountFactor(5.0), 0.0);
    EXPECT_LT(curve.discountFactor(5.0), 1.0);
}
```

- [ ] **Step 5: Registrar en tests/CMakeLists.txt**

Añadir `test_market_data_bridge.cpp` a fuentes de `qf_tests`.

- [ ] **Step 6: Build y tests**

```bash
cd ~/Git/QuantEngine/build
cmake .. -DCMAKE_BUILD_TYPE=Release
cmake --build . --target all 2>&1 | tail -5
ctest --output-on-failure -R "MarketDataBridge" 2>&1
ctest --output-on-failure 2>&1 | tail -5
```

Esperado: 3 tests nuevos de bridge pasando, todos los anteriores intactos.

- [ ] **Step 7: Commit**

```bash
cd ~/Git/QuantEngine
git add include/qf/feeds/market_data_bridge.hpp src/feeds/market_data_bridge.cpp \
        tests/test_market_data_bridge.cpp src/CMakeLists.txt tests/CMakeLists.txt
git commit -m "feat(bridge): add MarketDataBridge (TreasuryYield → YieldCurve → MarketEnvironment)" \
  --author="claudiocp_2@hotmail.com <claudiocp_2@hotmail.com>"
```

---

## Task 6: Fusionar web apps

**Files:**
- Create: `web/app.py` (fusión de ambas apps)
- Create: `web/scheduler.py` (de MDF, path actualizado)
- Move: plantillas de QF → `web/templates/`
- Move: plantillas de MDF → `web/templates/`
- Create: `web/tests/` (tests de ambas)
- Modify: `CMakeLists.txt` (actualizar target run_web_ui)

- [ ] **Step 1: Crear estructura web/**

```bash
mkdir -p ~/Git/QuantEngine/web/templates
mkdir -p ~/Git/QuantEngine/web/tests
```

- [ ] **Step 2: Copiar scheduler.py de MDF**

```bash
cp ~/Git/MarketDataFeed/web/scheduler.py ~/Git/QuantEngine/web/scheduler.py
```

Editar `web/scheduler.py`: cambiar la función `_resolve_fetch_binary` para buscar el binario relativo a la raíz del proyecto (el build estará en `../../build` desde `web/`):
```python
def _resolve_fetch_binary(db_path: str) -> str:
    build_dir = os.path.dirname(os.path.abspath(db_path))
    candidate = os.path.join(build_dir, "examples", "fetch_sofr")
    if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
        return candidate
    return "fetch_sofr"
```
(Sin cambios — la función ya usa la ruta del db_path, que se pasa desde app.py.)

- [ ] **Step 3: Copiar templates de ambas apps**

```bash
# Templates de QF (si existen como archivos separados)
cp -r ~/Git/Quant_Finance/python_web/templates/* ~/Git/QuantEngine/web/templates/ 2>/dev/null || true
# Templates de MDF (si los hay)
cp -r ~/Git/MarketDataFeed/web/templates/* ~/Git/QuantEngine/web/templates/ 2>/dev/null || true
```

**Nota:** Ambas apps usan `render_template_string` (inline HTML) en lugar de archivos .html separados. Los templates viven dentro de `app.py` — no hay archivos en `templates/` que copiar.

- [ ] **Step 4: Crear web/app.py unificado**

Crear `web/app.py` combinando ambas apps. Estructura:

```python
#!/usr/bin/env python3
"""QuantEngine — unified web dashboard (SOFR data + quantitative pricing)."""

import os, sys, re, sqlite3, json, contextlib
import numpy as np
from flask import Flask, render_template_string, jsonify, request

# ── qfpy bindings ─────────────────────────────────────────────────────────────
build_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'build'))
for p in (os.path.join(build_root, 'src'), build_root):
    if p not in sys.path:
        sys.path.insert(0, p)
try:
    import qfpy
except ModuleNotFoundError:
    raise ModuleNotFoundError('qfpy not found. Run: cmake --build build --target qfpy')

from scheduler import init_scheduler, run_fetch_now, last_fetch_result

DB_PATH = os.environ.get("QE_DB", os.path.join(build_root, "market_data.db"))
PORT    = int(os.environ.get("QE_PORT", 5001))

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
def _valid_date(s): return bool(s and _DATE_RE.match(s))

TENOR_ORDER = ["1M","2M","3M","4M","6M","1Y","2Y","3Y","5Y","7Y","10Y","20Y","30Y"]
TENOR_YEARS = {"1M":1/12,"2M":2/12,"3M":3/12,"4M":4/12,"6M":0.5,
               "1Y":1,"2Y":2,"3Y":3,"5Y":5,"7Y":7,"10Y":10,"20Y":20,"30Y":30}

app = Flask(__name__)

@contextlib.contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

# ── API: SOFR (from MDF) ──────────────────────────────────────────────────────
# [copy all /api/sofr/* routes from MarketDataFeed/web/app.py verbatim,
#  replacing DB_PATH references — already uses the module-level DB_PATH]

# ── API: Pricing (from QF) ────────────────────────────────────────────────────
# [copy /api/price, /api/payoff, /api/bond, /api/swap routes from
#  Quant_Finance/python_web/app.py verbatim]

# ── API: IRS with real curves (new — Task 7) ──────────────────────────────────
# [placeholder — implemented in Task 7]

# ── Main route ────────────────────────────────────────────────────────────────
@app.route('/')
def index():
    return render_template_string(MAIN_TEMPLATE)

# MAIN_TEMPLATE: HTML con 7 tabs (SOFR Rates, SOFR Swaps, SOFR Futures,
#                PCA Analysis, Options, Bonds, Interest Rate Swaps)
# [inline HTML combining both apps' UI — tabs nav + content panels]

if __name__ == '__main__':
    init_scheduler(DB_PATH)
    app.run(port=PORT, debug=False)
```

**Implementación completa de app.py:** copiar todos los routes de `~/Git/MarketDataFeed/web/app.py` (routes `/api/sofr/*`, `/api/treasury/*`, `/api/pca`, `/api/fetch`, `/api/fetch/status`) y todos los routes de `~/Git/Quant_Finance/python_web/app.py` (routes `/api/price`, `/api/payoff`, `/api/bond`, `/api/swap`), unificados bajo una sola Flask app. Construir `MAIN_TEMPLATE` combinando los 4 tabs MDF + 3 tabs QF en una sola página con barra de navegación superior.

- [ ] **Step 5: Actualizar CMakeLists.txt target run_web_ui**

En `CMakeLists.txt`, localizar el bloque `run_web_ui` y cambiar:
```cmake
COMMAND ${Python3_EXECUTABLE} ${CMAKE_SOURCE_DIR}/python_web/app.py
```
por:
```cmake
COMMAND ${Python3_EXECUTABLE} ${CMAKE_SOURCE_DIR}/web/app.py
```

- [ ] **Step 6: Copiar tests de Flask de MDF**

```bash
cp ~/Git/MarketDataFeed/web/tests/test_api.py ~/Git/QuantEngine/web/tests/test_mdf_api.py
```

Editar `web/tests/test_mdf_api.py`: actualizar imports para que apunten a la nueva `web/app.py` en lugar de la original de MDF.

- [ ] **Step 7: Instalar dependencias Python si falta algo**

```bash
pip install flask numpy pytest 2>&1 | tail -3
```

- [ ] **Step 8: Verificar que la web app arranca**

```bash
cd ~/Git/QuantEngine
QE_DB=build/market_data.db python3 web/app.py &
sleep 2
curl -s http://127.0.0.1:5001/ | head -5
kill %1
```

Esperado: HTML con los 7 tabs sin errores 500.

- [ ] **Step 9: Commit**

```bash
cd ~/Git/QuantEngine
git add web/
git commit -m "feat(web): unified Flask dashboard — 7 tabs (SOFR + pricing)" \
  --author="claudiocp_2@hotmail.com <claudiocp_2@hotmail.com>"
```

---

## Task 7: Conectar tab IRS a curvas reales vía MarketDataBridge

**Files:**
- Modify: `src/python_bindings/qfpy.cpp` (exponer `bootstrap` + `BootstrapInstrument`)
- Modify: `web/app.py` (endpoint `/api/irs/real-curve`)

- [ ] **Step 1: Exponer BootstrapInstrument y bootstrap en qfpy.cpp**

En `src/python_bindings/qfpy.cpp`, añadir después de la sección de `YieldCurve`:
```cpp
// BootstrapInstrument
py::class_<qf::termstructure::BootstrapInstrument>(m, "BootstrapInstrument")
    .def(py::init<>())
    .def_readwrite("maturity",  &qf::termstructure::BootstrapInstrument::maturity)
    .def_readwrite("rate",      &qf::termstructure::BootstrapInstrument::rate)
    .def_readwrite("frequency", &qf::termstructure::BootstrapInstrument::frequency)
    .def_readwrite("type", &qf::termstructure::BootstrapInstrument::type);

py::enum_<qf::termstructure::BootstrapInstrument::Type>(m, "InstrumentType")
    .value("Deposit", qf::termstructure::BootstrapInstrument::Deposit)
    .value("Swap",    qf::termstructure::BootstrapInstrument::Swap);

// bootstrap function
m.def("bootstrap",
      [](const std::vector<qf::termstructure::BootstrapInstrument>& insts) {
          return qf::termstructure::bootstrap(insts);
      },
      py::arg("instruments"));
```

Añadir include necesario al inicio de qfpy.cpp si no está:
```cpp
#include <qf/termstructure/bootstrap.hpp>
```

- [ ] **Step 2: Build qfpy y verificar**

```bash
cd ~/Git/QuantEngine/build
cmake --build . --target qfpy 2>&1 | tail -5
python3 -c "
import sys; sys.path.insert(0, 'src')
import qfpy
inst = qfpy.BootstrapInstrument()
inst.maturity = 1.0; inst.rate = 0.042; inst.frequency = 1.0
inst.type = qfpy.InstrumentType.Deposit
curve = qfpy.bootstrap([inst])
print('zero_rate(1.0):', curve.zero_rate(1.0))
"
```

Esperado: imprime un número cercano a `0.042`.

- [ ] **Step 3: Añadir endpoint /api/irs/real-curve en web/app.py**

```python
TENOR_YEARS = {"1M":1/12,"2M":2/12,"3M":3/12,"4M":4/12,"6M":0.5,
               "1Y":1.0,"2Y":2.0,"3Y":3.0,"5Y":5.0,"7Y":7.0,
               "10Y":10.0,"20Y":20.0,"30Y":30.0}

@app.route("/api/irs/real-curve", methods=["POST"])
def api_irs_real_curve():
    """Price an IRS using a YieldCurve bootstrapped from stored Treasury yields."""
    data = request.json or {}
    as_of = data.get("asOf", "")
    if not _valid_date(as_of):
        return jsonify({"error": "asOf must be YYYY-MM-DD"}), 400

    with get_db() as conn:
        rows = conn.execute(
            "SELECT maturity, rate FROM treasury_yields WHERE date = ? ORDER BY maturity",
            (as_of,)
        ).fetchall()

    if len(rows) < 2:
        return jsonify({"error": f"No Treasury data for {as_of}"}), 404

    instruments = []
    for row in rows:
        mat = row["maturity"]
        if mat not in TENOR_YEARS:
            continue
        T = TENOR_YEARS[mat]
        inst = qfpy.BootstrapInstrument()
        inst.maturity  = T
        inst.rate      = row["rate"] / 100.0
        inst.type      = qfpy.InstrumentType.Deposit if T <= 1.0 else qfpy.InstrumentType.Swap
        inst.frequency = 1.0 if T <= 1.0 else 2.0
        instruments.append(inst)

    instruments.sort(key=lambda i: i.maturity)

    try:
        curve = qfpy.bootstrap(instruments)
    except Exception as e:
        return jsonify({"error": f"Bootstrap failed: {e}"}), 500

    try:
        notional     = float(data.get("notional", 1_000_000))
        fixed_rate   = float(data.get("fixedRate", 0.04))
        maturity_irs = float(data.get("maturity", 5.0))
        frequency    = float(data.get("frequency", 2.0))
    except (ValueError, TypeError) as e:
        return jsonify({"error": str(e)}), 400

    # Price IRS using bootstrapped curve
    swap = qfpy.InterestRateSwap(notional, fixed_rate, maturity_irs, frequency, curve)
    npv = swap.npv()

    return jsonify({
        "asOf":       as_of,
        "npv":        npv,
        "fixedRate":  fixed_rate,
        "maturity":   maturity_irs,
        "curvePoints": [
            {"tenor": T, "zeroRate": curve.zero_rate(T)}
            for T in [0.25, 0.5, 1, 2, 3, 5, 7, 10]
        ]
    })
```

- [ ] **Step 4: Verificar endpoint**

Con la web app corriendo y datos Treasury en el DB:
```bash
curl -s -X POST http://127.0.0.1:5001/api/irs/real-curve \
  -H "Content-Type: application/json" \
  -d '{"asOf":"2026-03-07","notional":1000000,"fixedRate":0.04,"maturity":5.0}' | python3 -m json.tool
```

Esperado: JSON con `npv`, `fixedRate`, `curvePoints`.

- [ ] **Step 5: Commit**

```bash
cd ~/Git/QuantEngine
git add src/python_bindings/qfpy.cpp web/app.py
git commit -m "feat(web): IRS tab uses real Treasury curve via bootstrap" \
  --author="claudiocp_2@hotmail.com <claudiocp_2@hotmail.com>"
```

---

## Task 8: Unificar tests y verificación final

**Files:**
- Modify: `tests/CMakeLists.txt` (consolidar todos los tests bajo qf_tests)
- Create: `web/tests/test_unified_api.py`

- [ ] **Step 1: Build completo final**

```bash
cd ~/Git/QuantEngine/build
cmake .. -DCMAKE_BUILD_TYPE=Release
cmake --build . --target all 2>&1 | grep -E "error:|warning:|Built target"
```

Esperado: sin errores. Warnings de Doxygen son aceptables.

- [ ] **Step 2: Correr suite C++ completa**

```bash
cd ~/Git/QuantEngine/build
ctest --output-on-failure 2>&1
```

Esperado: todos los tests pasan (153 de QF + tests de http, storage, feeds, bridge).

- [ ] **Step 3: Test de smoke de la web app**

```bash
cd ~/Git/QuantEngine
QE_DB=build/market_data.db python3 web/app.py &
APP_PID=$!
sleep 2

# Verificar que todos los tabs responden
curl -sf http://127.0.0.1:5001/ > /dev/null && echo "OK: index"
curl -sf http://127.0.0.1:5001/api/sofr/rates > /dev/null && echo "OK: sofr/rates"
curl -sf http://127.0.0.1:5001/api/treasury?start=2026-01-01 > /dev/null && echo "OK: treasury"
curl -s -X POST http://127.0.0.1:5001/api/price \
  -H "Content-Type: application/json" \
  -d '{"spot":100,"strike":100,"r":0.05,"vol":0.2,"t":1}' | python3 -m json.tool | grep black_scholes
curl -s -X POST http://127.0.0.1:5001/api/bond \
  -H "Content-Type: application/json" \
  -d '{"faceValue":1000,"couponRate":0.05,"maturity":5,"yieldToMaturity":0.04}' | python3 -m json.tool | grep price

kill $APP_PID
```

Esperado: todos los endpoints responden con datos válidos.

- [ ] **Step 4: Correr tests Python de la web app**

```bash
cd ~/Git/QuantEngine
QE_DB=:memory: pytest web/tests/ -v 2>&1 | tail -20
```

- [ ] **Step 5: Commit final**

```bash
cd ~/Git/QuantEngine
git add -A
git commit -m "chore: unify test suite — all C++ + Python tests passing" \
  --author="claudiocp_2@hotmail.com <claudiocp_2@hotmail.com>"
```

- [ ] **Step 6: Verificar criterios de éxito del spec**

```bash
echo "=== C++ tests ===" && cd ~/Git/QuantEngine/build && ctest --output-on-failure 2>&1 | tail -3
echo "=== qfpy bindings ===" && python3 -c "import sys; sys.path.insert(0,'src'); import qfpy; print('qfpy OK')"
echo "=== qfxva bindings ===" && python3 -c "import sys; sys.path.insert(0,'src'); import qfxva; print('qfxva OK')"
```

Esperado:
- `100% tests passed`
- `qfpy OK`
- `qfxva OK`
