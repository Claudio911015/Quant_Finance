# Plan — Corte 12: sensibilidades del XVA por AAD con XAD

Diseño: `/tmp/fableorchestrate/qf-xad/design.md`. Repo `/home/claudio/Git/Quant_Finance`, rama `feat/qf-desk`.
Sondas (fuera del repo, reproducibles): `/tmp/qf-xad-probe/` (`minimal/`, `engine/`, `pymod/`, clon `src/xad`).

## Contexto

### 0. Estado del árbol y trabajo concurrente (leer antes de cualquier tarea)

Al planear (2026-11-11 ~22:10) otro agente tiene sin commitear, en este mismo árbol, el hallazgo H21
(malla de integración del XVA) y el reparto de trayectorias entre hilos:

- `src/xva/exposure_engine.cpp`: añade `forEachPathChunk(nPaths, body)` (un trozo contiguo de trayectorias por
  hilo, `std::thread`) y mete en él el bucle por trayectoria de `ExposureEngine::simulate`.
- `src/CMakeLists.txt`: `find_package(Threads REQUIRED)` + `target_link_libraries(qf PRIVATE Threads::Threads)`.
- `desk/api/risk/xva.py`: `integration_days(report, spec)` (mensual ∪ cada 3 días ∪ cada pago y su víspera),
  `engine(mkt, model, params, integration_days(report, spec))`, `_shown`, `_profile_points(profile, as_of, shown)`.
- `tests/test_ExposureEngine.cpp`, `desk/api/tests/test_xva*.py`, `MethodologyScreen.tsx(.test)`, `cap14_xva.tex`,
  `docs/tex/verificacion/cap14_xva.py`.

**Regla para todas las tareas:** no empezar T2 en adelante hasta que esos archivos estén commiteados por el otro
agente (`git status --short src/ desk/ docs/tex/ tests/` sin esas rutas modificadas). **T1 también espera**
(decisión de Fable): toca `src/CMakeLists.txt`, que el otro agente tiene modificado. Ninguna tarea empieza con
esos archivos sucios.
Las tareas leen siempre la versión commiteada vigente de `xva.py` y reusan sus funciones; **ninguna tarea
modifica `desk/api/risk/xva.py` ni `desk/api/routes/xva.py` salvo T4 en `routes/xva.py`** (una ruta nueva).

### 1. Hechos verificados

**XAD.** Repositorio `auto-differentiation/xad` (Xcelerit Computing Ltd.). `LICENSE.md` = **GNU AGPL-3.0**; los
encabezados dicen «version 3 of the License, or (at your option) any later version». El README declara doble
licencia: «free under the AGPL-3.0 for evaluation, research and open-source use. For production use without AGPL
obligations, a commercial subscription is available» (xcelerit.com/xad-enterprise-support). El párrafo del diseño es
correcto.

Etiquetas: `v2.2.0` (commit `aaf4e9cad59cf1bfe9728b491f95f011db687f18`, **publicada hoy 2026-11-11**),
`v2.1.0` (`71b381ad4a322d7ed5eb8b2b4b79a20c92c646c6`, 2026-03-31), `v2.0.0` (2026-02-06).
**Se fija `v2.2.0` por hash (decisión de Fable, aceptada pese a ser de hoy; R4 valida los números)**, porque `v2.1.0` tiene dos fallos que rompen la cinta por trayectoria (CHANGELOG de
2.2.0, sección *Fixed*: «`resetTo` kept the slots registered after its position, so repeated rollbacks slowed
down» y «`clearDerivativesAfter` dropped variables registered before its position»). Medido con la sonda: con
v2.1.0 el tiempo por trayectoria crece con el número de trayectorias (50 → 0.41 s, 100 → 1.49 s, 200 → 7.1 s;
cuadrático); con v2.2.0 es lineal. `desk/README.md` anota que es una versión recién publicada y que conviene
revisar su estabilidad al actualizarla.

**Compilación.** g++ 15.2 (`/usr/bin/g++`, el de `build/`), C++20, CMake 4.2.3, `FetchContent` desde GitHub:
compila y enlaza (biblioteca estática `xad`, PIC activado por omisión, ~40 s). Opciones usadas:
`XAD_WARNINGS_PARANOID=OFF` (las pruebas y ejemplos de XAD no se construyen como subproyecto) y
**`XAD_USE_STRONG_INLINE=ON`** (decisión de Fable): es una opción de caché de XAD que solo se escribe en su
`XAD/Config.hpp` generado (fuerza `inline` en las plantillas de expresiones); no cambia las banderas de `qf`. El
`XAD_SIMD_OPTION` (AVX por omisión en x86) se aplica solo al objetivo `xad`, no a los consumidores; los flags de
`qf` no cambian. Dentro de un módulo pybind11 (`/tmp/qf-xad-probe/pymod`, Python 3.8 de Anaconda, 4 hilos con una
cinta por hilo, `AReal<double,4>`) funciona y coincide con diferencias finitas
(164.95956854913834 frente a 164.95956852224936). Gotcha: `cmake --build -j8` de un módulo pybind11 con LTO falló
una vez con «invalid --jobserver-auth string» (make de conda); `cmake --build` sin `-j`, o `-j4` como hace el repo,
funciona. `build/` es `CMAKE_BUILD_TYPE=Debug` **pero con `-O2`** (heredado de `CXXFLAGS` de conda:
`-march=nocona -mtune=haswell -O2 … -g`): las mediciones «del proyecto» usan esas banderas.

Instancias de cinta vectorial que trae la biblioteca: `N = 1, 2, 4` (no `3`: `Tape<double,3>` no enlaza). Para
CVA, DVA y FVA en un solo barrido se usa **`xad::AReal<double, 4>`** (la cuarta componente queda libre).

**El camino de exposición no depende de clases no templadas pesadas.** `ExposureEngine` no usa `HullWhite`,
`OisSwap` ni `XccySwap`: compila sus propias patas (`Leg`, `LegPeriod`, `makeLeg`, `compileSet`) y las valúa con su
propia fórmula afín (`computeBonds`, `legValue`, `setValue`). Solo toca dos clases externas:

| Dependencia | Uso en el motor | Qué hacer | Líneas |
|---|---|---|---|
| `termstructure::YieldCurve::discountFactor` (`interp_` = `math::Interpolator`) | `fillCurrencyGrid` y `buildGrid` (q = P_MXN-USD / P_TIIE) | En `double` se sigue llamando a `YieldCurve` (resultado idéntico para cualquier interpolación). En AAD, una curva de pilares activa con interpolación lineal **idéntica** a la rama `Linear` de `Interpolator::operator()` (plana fuera de rango, `lower_bound − 1`, `y[i]*(1−t)+y[i+1]*t`, luego `exp(−r·T)`). Exige `interpolationMethod() == Linear` (las curvas del desk lo son: `bootstrapOis` y `bootstrapXccyDiscount` usan `Linear` por omisión; todas las pruebas del motor también). | ~15 nuevas |
| `xva::ICreditCurve::survivalProbability` (virtual, `double`) | `computeXva` | `computeXva` no cambia. La AAD usa una plantilla `survivalFromHazards<Real>(times, hazards, t)` en `piecewise_hazard_curve.hpp`; `PiecewiseHazardCurve::survivalProbability` pasa a llamarla con `double` (sin duplicar). `FlatHazardRate(λ)` = un tramo `{times={T_max}, hazards={λ}}` (mismo `exp(−(0+λ·(t−0)))` = `exp(−λt)` bit a bit). | ~15 movidas |

Conversión del motor (contada con la sonda `engine/eng.cpp`, que es `exposure_engine.cpp` con `double → Real`):
de 933 líneas de `exposure_engine.cpp`, **~195 cambian solo de tipo** (21 %; `CurrencyGrid`, `Grid`, `Context`,
`PathData`, `Bonds`, `PathView`, `fillCurrencyGrid`, `buildGrid`, `expIntegral`, `Kernel`/`kernelIntegral`,
`choleskySemidefinite`, `ouMoments`, `stepCovariance`, `simulatePath`, `computeBonds`, `discountAt`, `legValue`,
`setValue`); **quedan en `double`** validaciones, `Leg`/`LegPeriod`/`makeLeg`/`compileSet` (signos, nocionales,
tasas, `tau` y días no son insumos), `SimConfig`, malla, normales (`z[5]` y `std::normal_distribution<double>`),
`kDaysPerYear`, cuantil PFE, `deflatedValueStats`, `paidFlowsDeflated`, `computeXva`. A eso se suman ~25 líneas
`template <class Real>` y ~70 de la función nueva. El header público `exposure_engine.hpp` solo gana las
declaraciones nuevas (§2). `detail::ouMoments` y `detail::stepCovariance` conservan su firma `double` (las
pruebas los redeclaran) como envoltorios de las plantillas.

### 2. Interfaces nuevas (contrato exacto)

**C++** — en `include/qf/xva/exposure_engine.hpp`, tras `XvaResult`:

```cpp
/// @brief Derivadas de una medida (CVA, DVA o FVA, en MXN) respecto de cada insumo, por unidad del insumo
/// (tasas cero, volatilidades, reversiones, intensidades y diferencial en decimal; spot en MXN por USD).
struct XvaGreeks {
    std::vector<double> tiie;                 ///< ∂/∂ tasa cero de cada pilar de TIIE-F (orden de maturities()).
    std::vector<double> sofr;                 ///< ∂/∂ tasa cero de cada pilar de SOFR.
    std::vector<double> mxnUsd;               ///< ∂/∂ tasa cero de cada pilar de MXN-USD; vacío sin esa curva.
    double spot = 0.0;                        ///< ∂/∂ USDMXN spot.
    double fxVol = 0.0, sigmaMxn = 0.0, aMxn = 0.0, sigmaUsd = 0.0, aUsd = 0.0;
    std::vector<double> counterpartyHazard;   ///< ∂/∂ intensidad de cada tramo de la contraparte.
    std::vector<double> ownHazard;            ///< ∂/∂ intensidad de cada tramo propio.
    double fundingSpread = 0.0;               ///< ∂/∂ diferencial de fondeo.
};

/// @brief Sensibilidades de primer orden del XVA de un conjunto por diferenciación adjunta.
struct XvaSensitivities {
    XvaResult value;     ///< CVA, DVA, FVA y total de las mismas trayectorias (media de las sumas por trayectoria;
                         ///< coincide con computeXva hasta redondeo, |Δ| ≤ 1e-12 relativo; stdErr como computeXva).
    XvaGreeks cva, dva, fva;
};
```

y en `class ExposureEngine` (pública):

```cpp
    /// @brief CVA, DVA y FVA de `set` y sus derivadas respecto de todos los insumos, por AAD (XAD) con una cinta
    /// por trayectoria, sobre las mismas trayectorias, malla (reportDays) y semilla que simulate().
    /// @param set              Conjunto de compensación.
    /// @param counterparty     PiecewiseHazardCurve o FlatHazardRate de la contraparte.
    /// @param counterpartyLgd  LGD de la contraparte.
    /// @param own              Curva propia (mismos tipos admitidos).
    /// @param ownLgd           LGD propia.
    /// @param fundingSpread    Diferencial de fondeo, decimal.
    /// @return                 Valores y derivadas.
    /// @throws std::invalid_argument  curvas de tasa no Linear, curva de crédito de otro tipo, o lo que lance computeXva.
    /// @throws std::logic_error       si se compiló con QF_WITH_XAD=OFF.
    XvaSensitivities xvaSensitivities(const NettingSetSpec& set, const ICreditCurve& counterparty,
                                      double counterpartyLgd, const ICreditCurve& own, double ownLgd,
                                      double fundingSpread) const;
```

`FlatHazardRate` gana `double hazardRate() const;` (para leer λ por `dynamic_cast`). Con `QF_WITH_XAD=OFF` el
método existe y lanza `std::logic_error("ExposureEngine::xvaSensitivities: qf se compiló sin XAD (QF_WITH_XAD=OFF)")`.
`QF_WITH_XAD` llega como definición **PUBLIC** de `qf` (la ven `qfxva` y las pruebas).

**Binding** (`src/python_bindings/xva_bindings.cpp`, módulo `qfxva`):

```cpp
#ifdef QF_WITH_XAD
m.attr("HAS_XAD") = true;
#else
m.attr("HAS_XAD") = false;
#endif
py::class_<XvaGreeks>(m, "XvaGreeks")  // def_readonly: tiie, sofr, mxn_usd, spot, fx_vol, sigma_mxn, a_mxn,
                                       // sigma_usd, a_usd, counterparty_hazard, own_hazard, funding_spread
py::class_<XvaSensitivities>(m, "XvaSensitivities")  // def_readonly: value, cva, dva, fva
// en ExposureEngine:
.def("xva_sensitivities", &ExposureEngine::xvaSensitivities,
     py::arg("netting_set"), py::arg("counterparty"), py::arg("counterparty_lgd"),
     py::arg("own"), py::arg("own_lgd"), py::arg("funding_spread"),
     py::call_guard<py::gil_scoped_release>())
```

(`std::logic_error` llega a Python como `RuntimeError`; `std::invalid_argument` como `ValueError`.)

**API** — `GET /api/xva/sensitivities?snapshot=<id>&counterparty=<nombre>` (ruta en `desk/api/routes/xva.py`,
lógica en `desk/api/risk/xva_sens.py`). Errores: falta parámetro → 400 con `field`; snapshot inexistente → 404 (lo
da `market.load_context`); contraparte inexistente → 404 `{"error": "Contraparte inexistente: <n>", "field":
"counterparty"}`; `qfxva.HAS_XAD` falso → 501 `{"error": "Sensibilidades no disponibles: el motor se compiló sin
XAD (QF_WITH_XAD=OFF)"}`. Cuerpo 200 (todas las cifras en MXN; una «fila» `S` es
`{"cva": x, "dva": x, "fva": x, "total": x}` con `total = cva − dva + fva`):

```json
{
  "snapshot": "MX-DEMO", "as_of": "2026-11-10", "counterparty": "Banco Alfa (sintético)",
  "notice": "XVA informativo: no entra al PV ni a la contabilidad",
  "method": "Diferenciación adjunta (XAD 2.2.0), cinta por trayectoria, derivadas trayectoria a trayectoria",
  "cds_jacobian": "Reprecio del bootstrap de CDS (diferencia central de 0.01 pb)",
  "params": {"funding_spread": 0.005, "n_paths": 2000, "seed": 42, "pfe_quantile": 0.95},
  "paths": 2000, "seed": 42,
  "elapsed_s": 3.1, "valuation_elapsed_s": 0.42, "n_inputs": 48, "bump_cost_estimate_s": 40.3,
  "xva": {"cva_mxn": 0, "dva_mxn": 0, "fva_mxn": 0, "total_mxn": 0},
  "units": {"curves": "MXN por pb", "fx": "MXN por 1 % del spot", "vols": "MXN por punto",
            "cds": "MXN por pb", "funding": "MXN por pb"},
  "curves": [
    {"curve": "TIIE-F", "pillars": [{"label": "1D", "days": 1, "cva": 0, "dva": 0, "fva": 0, "total": 0}],
     "dv01": {"cva": 0, "dva": 0, "fva": 0, "total": 0}},
    {"curve": "SOFR", "pillars": [], "dv01": {}},
    {"curve": "MXN-USD", "pillars": [], "dv01": {}}
  ],
  "fx": {"label": "USDMXN spot", "cva": 0, "dva": 0, "fva": 0, "total": 0},
  "vols": [{"param": "fx_vol", "label": "Volatilidad USDMXN", "cva": 0, "dva": 0, "fva": 0, "total": 0},
           {"param": "sigma_mxn", "label": "σ Hull-White TIIE-F", "...": 0},
           {"param": "a_mxn", "label": "a Hull-White TIIE-F", "...": 0},
           {"param": "sigma_usd", "label": "σ Hull-White SOFR", "...": 0},
           {"param": "a_usd", "label": "a Hull-White SOFR", "...": 0}],
  "credit": {
    "counterparty": {"kind": "curve", "cds": [{"tenor": "6M", "cva": 0, "dva": 0, "fva": 0, "total": 0}],
                     "hazards": [{"to_years": 0.5, "cva": 0, "dva": 0, "fva": 0, "total": 0}]},
    "own": {"kind": "assumed", "cds": [], "hazards": [{"to_years": null, "...": 0}]}
  },
  "funding": {"cva": 0, "dva": 0, "fva": 0, "total": 0},
  "empty_reason": null,
  "assumptions": ["…las mismas de GET /api/xva para esta contraparte…"],
  "warnings": []
}
```

- `xva` es **exactamente** el de `GET /api/xva` para esa contraparte: se obtiene llamando a
  `xva._counterparty(...)` (misma función, mismos parámetros, malla de integración y trayectorias); su duración es
  `valuation_elapsed_s`. `elapsed_s` es la de `xva_sensitivities`. `bump_cost_estimate_s = 2 · n_inputs ·
  valuation_elapsed_s`.
- Escalas (decisión de Fable): curvas, CDS y fondeo ×1e-4 (por pb); spot ×(0.01·spot) (por 1 %); `fx_vol` ×0.01
  (1 punto); `sigma_mxn`/`sigma_usd` ×1e-4 (1 pb de volatilidad normal); `a_mxn`/`a_usd` ×0.01. `units` lo dice:
  `"vols": "MXN por punto (vol USDMXN), por pb de vol normal (σ Hull-White), por 0.01 (a)"`.
- Derivadas **parciales** (decisión de Fable): la de un pilar es respecto de la tasa cero de ese pilar sin
  recalibrar nada (ni MXN-USD, que el desk calibra desde TIIE-F, SOFR y el spot, ni el bootstrap de CDS, que
  descuenta con TIIE-F). `assumptions` añade a las de `GET /api/xva` la constante
  `xva_sens.PARTIAL_NOTE = "Derivadas parciales: al mover un pilar no se recalibran la curva MXN-USD ni las curvas de crédito (el bootstrap de CDS descuenta con TIIE-F)"`.
- MXN-USD aparece solo si el snapshot la trae (`mkt.csa_available`); etiquetas de pilar de `mkt.pillars[curva]`.
- CDS por plazo: solo si `credit.kind == "curve"`; sensibilidad a la cotización k = Σᵢ (∂X/∂λᵢ)·Jᵢₖ, con
  J = ∂λ/∂s del bootstrap por reprecio central (`credit_curves.build_curve` con la cotización k ± 1e-6). Con
  `kind` `flat` o `assumed`: `cds: []` y un solo tramo con `to_years: null`.
- Contraparte sin operaciones cubiertas: 200 con `curves: []`, `vols: []`, `fx`/`funding` en cero, `credit` con
  listas vacías, `xva` en cero y `empty_reason: "La contraparte no tiene swaps de tasa ni cross currency swaps vivos: no hay sensibilidades del XVA"`.

### 3. Patrón de cinta por trayectoria (probado)

Fragmento mínimo probado (`/tmp/qf-xad-probe/minimal/minimal.cpp`; con v2.1.0 también da números correctos en
este juguete, pero se usa v2.2.0 por el fallo de rendimiento/corrección descrito arriba):

```cpp
using mode = xad::adj<double>; using AD = mode::active_type; mode::tape_type tape;
std::vector<AD> z(z0.begin(), z0.end()); AD s = s0;
tape.registerInputs(z); tape.registerInput(s);
tape.newRecording();
auto grid = makeGrid(t, z);                 // parte común activa (tablas de la malla), se graba UNA vez
auto pos = tape.getPosition();              // posición guardada tras la parte común
for (int p = 0; p < N; ++p) {
    AD y = pathPayoff(t, z, s, grid, p);    // usa max(V, 0.0), exp, interpolación lineal
    tape.registerOutput(y);
    derivative(y) = 1.0 / N;
    tape.computeAdjointsTo(pos);            // adjuntos hasta la parte común; se acumulan allí
    tape.clearDerivativesAfter(pos);
    tape.resetTo(pos);
}
tape.computeAdjoints();                     // de la parte común a los insumos
// derivative(z[i]) == FD central: -2.9902086284 vs -2.9902086295, … ; ds 1.1867361935 vs 1.1867361958
```

En el motor (sonda `engine/eng.cpp`, función `ExposureEngine::sensitivities`): tipo `xad::AReal<double,4>`;
se registran los insumos, se construye `Context` activo (malla, curvas, Cholesky) y los pesos por fecha
`wC_j = LGD_c (S_c(t_{j−1}) − S_c(t_j))/N`, `wO_j` análogo, `wF_j = s_f S_c(t_j) S_o(t_j)(t_j − t_{j−1})/N`, se
guarda `pos`; por trayectoria: `PathData`/`Bonds` **declarados dentro del bucle** (ningún activo vive más allá de
`resetTo`; alternativa: opción `XAD_TAPE_TRACK_LIVE_SLOTS`), `simulatePath`, para cada fecha `j ≥ 1`
`v = setValue(…)`, `posD = max(v, 0.0)·exp(−I)`, `negD = max(−v, 0.0)·exp(−I)`, `cva += posD·wC_j`,
`dva += negD·wO_j`, `fva += (posD − negD)·wF_j`; `registerOutput` de las tres, `derivative(cva)[0] = 1`,
`derivative(dva)[1] = 1`, `derivative(fva)[2] = 1`, `computeAdjointsTo(pos)`, `clearDerivativesAfter(pos)`,
`resetTo(pos)`. Al final `computeAdjoints()` y se leen `derivative(insumo)[0..2]`. Con hilos: una `Tape` por hilo
dentro de `forEachPathChunk` (cada hilo registra su copia de los insumos y graba su propio `Context`; se suman las
derivadas y los valores al final). Las semillas por trayectoria `(seed, p)` no cambian.

### 4. Mediciones (esta máquina: i7-10510U 4C/8T portátil; carga 2–7 de otros agentes, cifras ±20 %)

Sonda = copia del motor real con 3 operaciones (swap TIIE-F 10 a pagador CSA 130 periodos de 28 d; swap SOFR 5 a
receptor 20 trimestres; CCS 5 a PayUsd trimestral CSA), 12+10+8 pilares, 8 parámetros de modelo, 6+6 tramos de
crédito, fondeo (≈ 46 insumos), 2000 trayectorias, horizonte 3630 d, un hilo.

| Malla | Banderas | `double` (simulate+computeXva) | AAD `AReal<double,4>` (CVA,DVA,FVA) | AAD `AReal<double,1>` (solo total) |
|---|---|---|---|---|
| mensual (122 fechas) | Release `-O3` | 1.46–1.66 s | 8.85 s mín. de 5 (≈ 5.3–6.1×) | 7.0 s (≈ 4.2–4.8×) |
| mensual | Release + `XAD_USE_STRONG_INLINE` | — | 7.6 s (≈ 4.6–5.2×) | — |
| mensual | como `build/` (`-O2 -g`) | 1.59–1.62 s | 9.96–11.6 s (**6.2–7.2×**) | 8.2–8.4 s (5.1–5.3×) |
| H21 (cada 3 d + pagos ±1, ~1450 fechas), 500 tr. | como `build/` | 1.47–1.61 s | 13.6–13.8 s (**8.5–9.4×**) | 11.0–11.8 s (≈ 7.3×) |
| H21, 800 tr. | como `build/` | 2.16 s | 20.2 s (9.3×) | — |

- **Memoria de la cinta:** 5.5 MB (mensual) y 6.0 MB (H21), constante con el número de trayectorias (≥ 2000).
- **Hilos:** AAD con 8 hilos (una cinta por hilo) 1.7–1.8× más rápida que con 1 (portátil con 4 núcleos y turbo,
  con carga). El `simulate` del otro agente también se reparte en hilos: el cociente con ambos en hilos debería
  quedar parecido al de un hilo, pero no se midió con el código del otro agente.
- **Por choques:** ≈ 46 insumos × 2 = 92 valuaciones = **92×** (contra 6–9× por AAD).
- **R5 vigente (decisión de Fable):** todas las sensibilidades de un conjunto en **≤ 10×** el tiempo de una valuación
  en `double` con la **misma malla de integración (H21) y el mismo número de hilos** (la AAD va en hilos, una cinta
  por hilo), con `XAD_USE_STRONG_INLINE`; se informa el costo por choques (2 × insumos valuaciones). No se deriva
  sobre la malla mensual: R6 exige la misma malla fina que `GET /api/xva`. Lo medido (8.5–9.4× en un hilo sin
  `STRONG_INLINE`, ≈ 15 % menos con él) deja margen corto: T3 lo mide y, si pasa de 10×, se reporta al orquestador
  antes de seguir (no se optimiza por cuenta propia).
- **Exactitud del valor:** reconstruyendo `epeDisc`/`eneDisc` desde los valores de los `AReal` y aplicando la
  fórmula de `computeXva` en su orden, CVA/DVA/FVA coinciden **bit a bit** con el motor `double` (17 dígitos) en
  las dos mallas. La suma por trayectoria (sin reordenar) difiere en el último dígito (`200752.50223025991` frente a
  `…997`).
- **AAD frente a choque central con las mismas trayectorias** (h = 1e-5 en tasas/vols/a, 1e-3 spot, 1e-6 crédito y
  fondeo): curvas, spot, σ, a, vol FX dentro de 1e-5 relativo (p. ej. ∂CVA/∂z_TIIE(4a) −1 060 978.50 frente a
  −1 061 035.22; ∂CVA/∂σ_MXN 6 571 239.32 frente a 6 571 171.77); crédito y fondeo iguales a 10 dígitos.
- **GET /api/xva actual** (3 contrapartes, 2000 tr., `build/src` vigente): 1.31 s en total. Insumos reales del
  snapshot `MX-DEMO`: TIIE-F 10 pilares, SOFR 10, MXN-USD 9, spot, vol FX, 4 Hull-White, 6+6 tramos, fondeo = **48**;
  CDS 6 por entidad (recuperación 0.4).

### 5. Convenciones

- Commits en español con el porqué, **sin `Co-Authored-By` ni trailers**, rutas explícitas:
  `GRAPHIFY_SKIP_HOOK=1 git commit -m "…" -- <rutas>`. Sin push, sin `git stash`, nunca `graphify-out/`.
  No commitear archivos del otro agente.
- Python del backend: `/home/claudio/anaconda3/bin/python` (3.8: sin `match`, sin `X | Y`, typing con comentarios).
- C++ se compila en serie (una tarea C++ a la vez; `-j4`).
- Mínimo código: el diff de C++ es sobre todo cambio de tipos. Presupuesto de Python nuevo fuera de pruebas: ≤ 120
  líneas (T4).
- Puertos: pruebas con servidor en 5089 con base temporal; Chrome headless en 9349. No tocar 5070, Brave/9222 ni
  `~/Git/MarketDataFeed`.

### 6. Suites

```bash
cd /home/claudio/Git/Quant_Finance
cmake -S . -B build && cmake --build build -j4 && (cd build && ctest --output-on-failure)   # C++ (463 + nuevas)
cmake --build build --target pytests                                                        # bindings
/home/claudio/anaconda3/bin/python -m pytest desk/api/tests -q                              # backend
(cd desk/ui && npm test && npm run build)                                                   # UI
(cd docs/tex && latexmk -pdf -interaction=nonstopmode -halt-on-error qfdesk.tex; echo rc=$?)
/home/claudio/anaconda3/bin/python docs/tex/verificacion/correr.py
/home/claudio/anaconda3/bin/python docs/tex/verificacion/referencias_codigo.py
desk/validation/make_report.sh        # 62 dentro, commit_matches: true
# sin XAD (en /tmp, no en build/):
cmake -S . -B /tmp/qf-noxad -DQF_WITH_XAD=OFF && cmake --build /tmp/qf-noxad -j4 && (cd /tmp/qf-noxad && ctest --output-on-failure)
```

## Tareas

Orden: T1 → T2 → T3 → T4 ∥ T5 → T6 → T7 → T8. T5 (UI) solo depende del contrato JSON de §2 y puede correr en
paralelo con T2–T4 (archivos disjuntos). T6 y T7 necesitan las cifras de T3.

### T1 — Dependencia XAD, opción `QF_WITH_XAD` y contrato C++/binding · **sonnet**

Objetivo: XAD entra por `FetchContent` fijado al commit de v2.2.0 detrás de `QF_WITH_XAD` (ON); se declaran las
interfaces de §2 con una implementación que lanza `logic_error` (siempre, hasta T3); el binding expone
`HAS_XAD` y `xva_sensitivities`; `desk/README.md` documenta la licencia. R1 (parte de CMake y licencia), contrato
de R3/R6.

Archivos: `CMakeLists.txt` (raíz), `src/CMakeLists.txt`, `include/qf/xva/exposure_engine.hpp`,
`include/qf/xva/credit_curve.hpp`, `src/xva/credit_curve.cpp`, `src/xva/exposure_engine.cpp` (solo el stub al final
del archivo), `src/python_bindings/xva_bindings.cpp`, `tests/test_ExposureEngine.cpp` (una prueba nueva al final),
`tests/test_xva_engine_py.py` (una prueba nueva), `desk/README.md`.

Pasos:
1. Raíz, antes de `add_subdirectory(src)`:
   ```cmake
   option(QF_WITH_XAD "Sensibilidades del XVA por AAD con XAD (AGPL-3.0)" ON)
   if(QF_WITH_XAD)
     include(FetchContent)
     set(XAD_WARNINGS_PARANOID OFF CACHE BOOL "" FORCE)
     set(XAD_USE_STRONG_INLINE ON CACHE BOOL "" FORCE)
     FetchContent_Declare(xad GIT_REPOSITORY https://github.com/auto-differentiation/xad.git
                          GIT_TAG aaf4e9cad59cf1bfe9728b491f95f011db687f18   # v2.2.0
                          SYSTEM)
     FetchContent_MakeAvailable(xad)
   endif()
   ```
   (`find_package(XAD)` previo es opcional: si se añade, `find_package(XAD 2.2 QUIET)` y `FetchContent` solo si
   no se encontró.)
2. `src/CMakeLists.txt`: `if(QF_WITH_XAD) target_link_libraries(qf PUBLIC XAD::xad) target_compile_definitions(qf PUBLIC QF_WITH_XAD=1) endif()`.
   Si el archivo trae cambios sin commitear del otro agente, no tocarlos (ver §0).
3. Declarar en `exposure_engine.hpp` `XvaGreeks`, `XvaSensitivities` y `ExposureEngine::xvaSensitivities` tal cual
   §2. `FlatHazardRate::hazardRate()` en `credit_curve.hpp/.cpp`.
4. Al final de `exposure_engine.cpp`, definición provisional que lanza
   `std::logic_error("ExposureEngine::xvaSensitivities: qf se compiló sin XAD (QF_WITH_XAD=OFF)")` en ambos casos
   (T3 sustituye la rama con XAD).
5. Binding de §2 con `#ifdef QF_WITH_XAD` para `HAS_XAD`.
6. Pruebas: GoogleTest `TEST(ExposureEngine, XvaSensitivitiesWithoutXadThrowsLogicError)` envuelta en
   `#ifndef QF_WITH_XAD` (y nada con XAD aún); Python `test_has_xad_flag_is_a_bool` (`isinstance(qfxva.HAS_XAD, bool)`).
7. `desk/README.md`, sección nueva «## XAD y su licencia»: AGPL-3.0 (o posterior) de Xcelerit; licencia comercial
   aparte; implicación (quien use el servicio en red tiene derecho al código fuente completo, salvo licencia
   comercial); repo hoy público → sin conflicto inmediato; decisión de negocio pendiente de Claudio; versión fijada
   (v2.2.0, commit `aaf4e9c…`, publicada el 2026-11-11: recién publicada, revisar su estabilidad al actualizar;
   v2.1.0 no sirve por los fallos de `resetTo`/`clearDerivativesAfter`); cómo apagar
   (`cmake -S . -B build -DQF_WITH_XAD=OFF`: todo compila y la ruta de sensibilidades responde 501).

Verificación:
```bash
cmake -S . -B build && cmake --build build -j4 && (cd build && ctest --output-on-failure | tail -3)
#   → "100% tests passed" (463)
cmake -S . -B /tmp/qf-noxad -DQF_WITH_XAD=OFF && cmake --build /tmp/qf-noxad -j4 && (cd /tmp/qf-noxad && ctest | tail -2)
#   → "100% tests passed" (464, incluye la del logic_error)
cmake --build build --target pytests 2>&1 | tail -2    # OK
PYTHONPATH=build/src /home/claudio/anaconda3/bin/python -c "import qfpy, qfxva; print(qfxva.HAS_XAD)"   # True
```
Commit: `build(xva): XAD 2.2.0 detrás de QF_WITH_XAD y contrato de las sensibilidades del XVA`.
Depende de: commit del otro agente (§0). Cubre: R1 (CMake, licencia), contrato de R3/R6.

### T2 — Motor de exposición templado sobre el escalar, sin cambiar ningún número `double` · **sonnet**

Objetivo: que la misma fuente sirva para `double` y para `xad::AReal<double,4>` (R2). Sin lógica nueva.

Archivos: `src/xva/exposure_engine.cpp`, `include/qf/xva/piecewise_hazard_curve.hpp`,
`src/xva/piecewise_hazard_curve.cpp`, `tests/test_ExposureEngine.cpp` (solo una prueba nueva de valores dorados).

Pasos (prueba primero):
1. **Antes de tocar el motor**, añadir `TEST(ExposureEngine, GoldenValuesUnchangedByTemplating)`: un conjunto
   con swap TIIE-F (CSA), swap SOFR y CCS (reusar los ayudantes del archivo: `tiieCurve`, `sofrCurve`, mercado con
   base), 300 trayectorias, semilla 7, malla mensual a 5 años; `simulate` + `computeXva` con
   `PiecewiseHazardCurve`; afirmar con `EXPECT_EQ` (igualdad exacta) `cva`, `dva`, `fva`, `epeDisc[k]` de 3 fechas
   y `pfe[k]` de 1 fecha contra literales impresos con `%.17g` desde el código **actual** (correr la prueba una vez
   con los literales vacíos para obtenerlos). Commit de la prueba sola.
2. Convertir a `template <class Real>` los tipos y funciones listados en §1 (tabla «Conversión del motor»); dejar
   en `double` lo listado allí. Usar `using std::exp; using std::log; using std::sqrt; using std::expm1; using
   std::max;` y llamadas sin calificar (XAD las encuentra por ADL); en ternarios con un `Real` envolver ambos
   lados (`Real(…)`). `kDaysPerYear` sigue `constexpr double`.
3. Curvas: `fillCurrencyGrid`/`buildGrid` reciben la curva como parámetro de plantilla `Curve` y llaman a
   `discountAt(curve, t)`; sobrecarga `double discountAt(const YieldCurve&, double)` = `curve.discountFactor(t)`, y
   `template <class Real> struct PillarCurve { std::vector<double> t; std::vector<Real> z; }` con
   `discountAt(const PillarCurve<Real>&, double T)` = interpolación lineal de §1 seguida de `exp(-r*T)`, con un
   comentario que declare la excepción aceptada a «sin duplicar»: replica la rama `Linear` de `math::Interpolator`
   para no templar `Interpolator`/`YieldCurve`, que usa todo el repo.
4. `piecewise_hazard_curve.hpp`: `template <class Real> Real survivalFromHazards(const std::vector<double>& times,
   const std::vector<Real>& hazards, double t)` con el cuerpo actual de `survivalProbability`; el miembro la llama.
5. `detail::ouMoments` y `detail::stepCovariance` mantienen su firma `double` como envoltorios.
6. `simulate`, `tradeValuesAtZero`, `deflatedValueStats` instancian con `double` y `YieldCurve`. No se toca la
   lógica de `forEachPathChunk` del otro agente.

Verificación:
```bash
cmake --build build -j4 && (cd build && ctest --output-on-failure | tail -3)    # 100% (463 + 1)
(cd build && ctest -R "ExposureEngine|PiecewiseHazard|CVACalculator|ExposureProfile" --output-on-failure | tail -2)
cmake --build build --target pytests 2>&1 | tail -2
/home/claudio/anaconda3/bin/python -m pytest desk/api/tests -q -k "xva or credit" | tail -2
git diff --stat HEAD~1 -- tests/   # solo la prueba dorada; ninguna prueba existente cambió
```
Salida esperada: todo verde; `GoldenValuesUnchangedByTemplating` pasa sin cambiar sus literales.
Commit: `refactor(xva): motor de exposición templado sobre el escalar para poder diferenciarlo (mismos números en double)`.
Depende de: T1 y del commit del otro agente (§0). Cubre: R2.

### T3 — `xvaSensitivities` por AAD y sus pruebas de corrección · **sonnet**

Objetivo: implementar el método de §2 con el patrón de §3 (cinta por trayectoria, `AReal<double,4>`, una cinta
por hilo con `forEachPathChunk`), y probar R4 y la memoria de R5.

Archivos: `src/xva/exposure_engine.cpp`, `tests/test_ExposureEngine.cpp`, `tests/test_xva_engine_py.py`.

Pasos (prueba primero, todas bajo `#ifdef QF_WITH_XAD`):
1. Ayudante de prueba `bumpCentral(f, h)` que reconstruye `ExposureEngine`/curvas con un insumo ± h
   (`YieldCurve::bumped(i, ±h_bp)` para pilares; struct de modelo y spot copiados; `PiecewiseHazardCurve` con un
   tramo movido; `fundingSpread ± h`) y llama a `simulate` + `computeXva` **con la misma semilla y trayectorias**.
   Tolerancia por derivada: `|aad − fd| ≤ max(0.01·|fd|, kAbs)` con `kAbs = 1.0` MXN por unidad de insumo
   (= 1e-4 MXN por pb), declarada en un comentario. h: 0.1 pb (1e-5) en tasas, 1e-5 en σ/a/vol FX, 1e-3 en spot,
   1e-6 en intensidades y fondeo.
2. Pruebas (400 trayectorias, malla mensual; cada una sobre **todos** los pilares de las curvas que toca):
   `AadMatchesBumpTiieSwap`, `AadMatchesBumpSofrSwap`, `AadMatchesBumpXccySwap` (CSA, con MXN-USD),
   `AadMatchesBumpCombinedSet` (los tres + todos los insumos de modelo, crédito y fondeo; tolerancia
   max(1 %, 1 MXN por unidad de insumo), decisión de Fable),
   `AadValueMatchesComputeXva` (`value` frente a `simulate`+`computeXva`, relativo ≤ 1e-12),
   `AadZeroVolatilityMatchesDeterministicDerivative` (σ_MXN = σ_USD = vol FX = 0, todas las trayectorias iguales:
   derivadas a curvas frente a choque central con h = 1e-7, relativo ≤ 1e-6),
   `AadFlatHazardHasOneTranche`, `AadRejectsNonLinearCurves` (`CubicSpline` → `invalid_argument`).
3. Implementar. Entrada: `dynamic_cast` de las curvas de crédito a `PiecewiseHazardCurve` (times/hazards) o
   `FlatHazardRate` (`{{max(reportDays.back()/365, 1)}, {λ}}`), si no `invalid_argument`; exigir `Linear` en
   `tiie`, `sofr` y `mxnUsd`. Insumos activos: `PillarCurve` de cada curva, spot, `fxVol`, `sigmaMxn`, `aMxn`,
   `sigmaUsd`, `aUsd` (correlaciones pasivas), intensidades, fondeo. Por hilo: `Tape<double,4>`, copia de insumos,
   `registerInputs`, `newRecording`, `buildContext<AD>`, pesos, `getPosition`, bucle de §3 sobre su trozo, suma de
   valores por trayectoria a vectores `double` por trayectoria (para `stdErr` igual que `computeXva`),
   `computeAdjoints`, derivadas a un acumulador del hilo; al final se suman. `value.cva/dva/fva` = media de las
   sumas por trayectoria; `value.total = cva − dva + fva`. Dos comentarios declaran las excepciones aceptadas a
   «sin duplicar»: el bucle por trayectoria de la AAD es paralelo al de `simulate` (compartirlo cambiaría el orden de
   operaciones de `simulate`), y la suma ponderada de CVA/DVA/FVA repite la fórmula de `computeXva` en otro orden
   (reusarla cambiaría sus números `double` por redondeo).
4. **Mutación (R4):** con las pruebas en verde, cambiar temporalmente en `discountAt(PillarCurve…)` el término
   `z[i+1]` por `Real(xad::value(z[i+1]))` y comprobar que `AadMatchesBumpTiieSwap` falla; revertir. Anotar el
   resultado en el mensaje de commit.
5. Python: `test_xva_sensitivities_shape` en `tests/test_xva_engine_py.py` (largos de los vectores = pilares;
   `value.cva` ≈ `compute_xva(...)`).
6. Medir R5 (no es prueba de ctest): prueba `DISABLED_AadTiming` que, con 2000 trayectorias, el conjunto
   combinado y una malla tipo H21 (mensual ∪ cada 3 días ∪ cada pago y su víspera), imprime
   `ratio = t(xvaSensitivities) / t(simulate + computeXva)` (ambos con los hilos de `forEachPathChunk`) y la memoria
   de la cinta por hilo con 500 y 2000 trayectorias (debe ser igual). Criterio: `ratio ≤ 10`. Si no se cumple,
   parar y reportar al orquestador con las cifras (no optimizar por cuenta propia). Reportar las cifras (se usan en
   T6, T7 y T8).

Verificación:
```bash
cmake --build build -j4 && (cd build && ctest -R "ExposureEngine" --output-on-failure | tail -3)   # todas pasan
(cd build && ctest --output-on-failure | tail -2)                                                 # 100%
cmake --build build --target pytests 2>&1 | tail -2
(cd build && ./tests/qf_tests --gtest_filter='*DISABLED_AadTiming*' --gtest_also_run_disabled_tests | grep -E "ratio|tape")
#   → ratio ≤ 10; memoria de la cinta igual con 500 y 2000 trayectorias
cmake --build /tmp/qf-noxad -j4 && (cd /tmp/qf-noxad && ctest | tail -1)                          # 100% sin XAD
```
Commit: `feat(xva): sensibilidades de CVA, DVA y FVA por diferenciación adjunta con una cinta por trayectoria`.
Depende de: T2. Cubre: R3 (a)–(f) en C++, R4, R5 (memoria y medición).

### T4 — `GET /api/xva/sensitivities` · **sonnet**

Objetivo: la ruta de §2, reusando `xva.py` sin duplicar (R6) y con el jacobiano de CDS (R3 última frase).

Archivos: `desk/api/risk/xva_sens.py` (nuevo, ≤ ~100 líneas), `desk/api/routes/xva.py` (+1 ruta, ~5 líneas),
`desk/api/tests/test_xva_sens.py` (nuevo).

Pasos (prueba primero, `n_paths` 200 vía `PUT /api/xva/params` salvo donde se diga):
1. Pruebas: forma del JSON de §2 (claves y largos: TIIE-F 10, SOFR 10, MXN-USD 9 pilares; 6 CDS por entidad con
   curva); `xva` **igual** (`==`) a la contraparte de `GET /api/xva` con los mismos parámetros; `dv01` = suma de
   `pillars`; `total = cva − dva + fva` en cada fila; `assumptions` contiene `PARTIAL_NOTE`;
   **comparación contra choque y reprecio por la API (decisión de Fable)** sobre el conjunto sembrado de Banco
   Alfa, `n_paths` 500, un insumo de cada clase: un pilar de TIIE-F, uno de SOFR, uno de MXN-USD, el spot,
   `fx_vol`, una cotización de CDS de la contraparte y el fondeo. El reprecio en la prueba reproduce la derivada
   **parcial**: arma `spec` con `xva.build_set`, toma las curvas de crédito de `xva.credit_for`/`xva.own_credit`
   **una vez** (fijas), y llama a `qfxva.ExposureEngine(qfxva.ExposureMarket(...), model, config).simulate([spec])`
   + `qfxva.compute_xva` con el insumo ± h (pilar: `curve.bumped(i, ±0.1)`; spot ± 0.01; `fx_vol` ± 1e-4 en un
   `ExposureModel` copiado; fondeo ± 1e-6; CDS: cotización ± 1e-6 → `credit_curves.build_curve` → `compute_xva`),
   misma semilla y malla `xva.integration_days`; compara el choque central (convertido a las unidades de la
   respuesta) con la fila de la API dentro de max(1 %, 1e-4 MXN por pb); contraparte inexistente 404; parámetro
   ausente 400;
   contraparte solo con productos no cubiertos → `empty_reason` y listas vacías; `monkeypatch` de
   `qfxva.HAS_XAD = False` → 501; sin MXN-USD (`strip_csa`) → no aparece esa curva.
2. `xva_sens.compute(conn, snapshot_id, name)`: `market.load_context`, `fixing_store.load_all`,
   `xva.load_params`, `xva.model_from_snapshot`, `xva.own_credit`, `xva.live_by_counterparty(conn, mkt).get(name)`,
   `xva._counterparty(...)` (cronometrado → `xva` y `valuation_elapsed_s`, y el `cp_curve`),
   `xva.build_set`, `xva.report_days` + `xva.integration_days` + `xva.engine` → `eng.xva_sensitivities(spec,
   cp_curve, 1−rec, own_curve, 1−own_rec, funding_spread)` (cronometrado). Escalar y armar filas. Jacobiano CDS
   con `credit_curves.current(conn)[entity]` y `credit_curves.build_curve` sobre copias con la cotización movida.
   Importar `qfxva` dentro de funciones (como `xva._qfxva`). Sin fórmulas financieras: solo escalas, sumas y el
   producto jacobiano.
3. Ruta: `@bp.get("/api/xva/sensitivities")` con `_arg("snapshot")`, `_arg("counterparty")`,
   `jsonify(ensure_finite(xva_sens.compute(...)))`.

Verificación:
```bash
/home/claudio/anaconda3/bin/python -m pytest desk/api/tests/test_xva_sens.py -q      # N passed
/home/claudio/anaconda3/bin/python -m pytest desk/api/tests -q | tail -1               # todo verde
grep -cv '^\s*\(#\|$\)' desk/api/risk/xva_sens.py                                      # ≤ ~100; con la ruta ≤ 120
```
Commit: `feat(desk): GET /api/xva/sensitivities con las sensibilidades por AAD y el jacobiano del bootstrap de CDS`.
Depende de: T3. Cubre: R3 (CDS), R5 (comparación con choques en el JSON), R6, R1 (501).

### T5 — Sección «Sensibilidades» en la pantalla XVA (contra simulados) · **sonnet**

Objetivo: R7 contra datos simulados con la forma exacta de §2.

Archivos: `desk/ui/src/api/xvaTypes.ts` (tipos `XvaSensitivitiesResponse`, `XvaSensRow`…),
`desk/ui/src/api/xvaClient.ts` (`getXvaSensitivities(snapshot, counterparty)` →
`/xva/sensitivities?snapshot=…&counterparty=…`, ambos con `encodeURIComponent`),
`desk/ui/src/screens/xva/XvaSensitivitiesPanel.tsx` (+ `.css` si hace falta),
`desk/ui/src/screens/xva/XvaSensitivitiesPanel.test.tsx`, `desk/ui/src/screens/xva/fixtures.ts` (fixture nuevo),
`desk/ui/src/screens/XvaScreen.tsx` (montar el panel bajo el perfil de la contraparte elegida).

Pasos (prueba primero, vitest + Testing Library, `vi.mock` del cliente):
1. Pruebas: el botón «Calcular sensibilidades» llama una vez con snapshot y contraparte; estado «Calculando…»
   (botón deshabilitado) mientras la promesa no resuelve; tabla por curva y pilar con CVA, DVA, FVA y total
   (MXN por pb) con `fmtMoney`; fila de DV01 paralelo por curva; filas de tipo de cambio, volatilidades, CDS por
   plazo (propio y contraparte) y fondeo; aviso cuando `empty_reason`; error 501 muestra su `error`; al cambiar de
   contraparte se limpia el resultado; rótulos en español; una gráfica de barras (componente `EChart` existente, como
   `XvaProfileChart`) del CVA por pilar con una serie por curva.
2. Implementar; sin desborde a 1280 px (tabla con `overflow-x: auto` dentro del panel, no en la página).

Verificación:
```bash
cd desk/ui && npx vitest run src/screens/xva/XvaSensitivitiesPanel.test.tsx && npm test 2>&1 | tail -3 && npm run build 2>&1 | tail -2
```
Commit: `feat(ui): sección de sensibilidades del XVA por contraparte, a petición`.
Depende de: contrato §2 (puede correr en paralelo con T2–T4). Cubre: R7.

### T6 — Metodología: «Sensibilidades del XVA» · **haiku**

Objetivo: R8 (parte de la aplicación). Un ítem nuevo en `XVA_SECTIONS` de `MethodologyScreen.tsx` y su prueba.

Archivos: `desk/ui/src/screens/MethodologyScreen.tsx`, `desk/ui/src/screens/MethodologyScreen.test.tsx`.

Pasos: añadir a la sección `id: 'xva'` el ítem `{ label: 'Sensibilidades del XVA', text: … }` con este contenido
(rellenar los «⟨…⟩» con las cifras que reporte T3/T8): qué se deriva (CVA, DVA, FVA y total); respecto de qué
(tasa cero de cada pilar de TIIE-F, SOFR y MXN-USD, spot USDMXN, volatilidad USDMXN, σ y a de Hull-White por
moneda, intensidad de cada tramo de crédito propio y de la contraparte, cotizaciones de CDS por el jacobiano del
bootstrap obtenido por reprecio, diferencial de fondeo); unidades (MXN por pb; por 1 % del spot; por punto de
volatilidad); método (diferenciación adjunta con XAD, una cinta por trayectoria, adjuntos acumulados, derivadas
trayectoria a trayectoria con las mismas trayectorias, malla y semilla que el XVA; max(V,0) con su indicador);
unidades de vol: USDMXN por punto (0.01), σ de Hull-White por 1 pb de vol normal (1e-4), reversión a por 0.01;
costo medido (⟨k⟩× una valuación con la misma malla e hilos, objetivo ≤ 10×, frente a 2 × ⟨n⟩ valuaciones por
choques); límites (el PFE no se deriva; no hay segundo orden ni sensibilidad a correlaciones; **derivadas
parciales**: al mover un pilar no se recalibran la curva MXN-USD ni las curvas de crédito, aunque el bootstrap de
CDS descuenta con TIIE-F; derivadas con error de Monte Carlo). Prueba: el texto aparece y menciona
«adjunta» y «MXN por pb».

Verificación: `cd desk/ui && npx vitest run src/screens/MethodologyScreen.test.tsx && npm run build | tail -2`.
Commit: `docs(ui): la Metodología explica las sensibilidades del XVA por diferenciación adjunta`.
Depende de: T3 (cifras), T5 (mismo árbol de UI; correr después para no chocar en `npm`), commit del otro agente
en `MethodologyScreen.tsx` (§0). Cubre: R8 (Metodología).

### T7 — Capítulo LaTeX «Sensibilidades del XVA por diferenciación adjunta» · **sonnet**

Objetivo: R8 (documento técnico) según `docs/tex/README.md` («Añadir un capítulo»).

Archivos: `docs/tex/capitulos/cap16_xva_aad.tex` (nuevo, desde `_plantilla.tex`, etiqueta `cap:xva-aad`),
`docs/tex/qfdesk.tex` (`\include` tras el 15), `docs/tex/simbolos/cap16.tex`, `docs/tex/referencias.bib` (añadir al
final), `docs/tex/verificacion/cap16_xva_aad.py`, `docs/tex/README.md` (lista de capítulos y etiqueta fija).

Contenido mínimo: 8 secciones de la plantilla; modo adjunto (v̄ = ∂y/∂v propagado hacia atrás, costo
O(1)× el directo independiente del número de insumos); estimador trayectoria a trayectoria
∂CVA/∂θ ≈ (1/N) Σ_p Σ_j w_j · 1{V_pj>0} ∂V_pj/∂θ · B_pj⁻¹ + … (lo que hace `xvaSensitivities`, con los pesos de §3) y
su condición (Lipschitz; el indicador de max); cinta por trayectoria (registro de insumos, parte común, posición,
reinicio) y por qué la memoria no crece con N; jacobiano del bootstrap de CDS por reprecio y regla de la cadena;
escalas de §2; recuadro `diferencia` (el libro diferencia también la calibración; aquí son derivadas parciales:
no se recalibra MXN-USD ni el crédito al mover TIIE-F) y `limites` (incluye la razón de costo medida, objetivo ≤ 10×). ≥ 11 `\codigo` (p. ej. `src/xva/exposure_engine.cpp`
`ExposureEngine::xvaSensitivities`, `include/qf/xva/exposure_engine.hpp` `XvaGreeks`, `desk/api/risk/xva_sens.py`
`compute`, `include/qf/xva/piecewise_hazard_curve.hpp` `survivalFromHazards`, pruebas `AadMatchesBumpCombinedSet`,
`AadZeroVolatilityMatchesDeterministicDerivative`, `CMakeLists.txt` `QF_WITH_XAD`…). ≥ 2 `\verif` con su script
(p. ej. `cap16-dcva-dz-tiie-aad` y `cap16-dcva-dz-tiie-choque` de un swap TIIE-F con 400 trayectorias, insumos
construidos en el script y llamando a `qfxva`; y la razón de costo no, porque varía). Referencias **confirmadas
contra Crossref/Open Library antes de escribirlas**: Giles y Glasserman (2006), «Smoking adjoints: fast Monte Carlo
Greeks», *Risk*; Capriotti (2011), «Fast Greeks by algorithmic differentiation», *Journal of Computational Finance*;
Griewank y Walther (2008), *Evaluating Derivatives*, 2.ª ed., SIAM; Savine (2018), *Modern Computational Finance:
AAD and Parallel Simulations*, Wiley; Broadie y Glasserman (1996), «Estimating security price derivatives using
simulation», *Management Science* (estimador trayectoria a trayectoria). XAD como `@manual` (Xcelerit, URL del
repositorio, versión 2.2.0, consultado el día). Si alguna no se confirma, se omite.

Verificación:
```bash
cd docs/tex && OUT=/tmp/qfdocs-t7 && rm -rf $OUT && mkdir -p $OUT/capitulos && latexmk -pdf -interaction=nonstopmode -halt-on-error -outdir=$OUT qfdesk.tex >/dev/null 2>&1; echo rc=$?   # rc=0
grep -aE "(Citation|Reference) .* undefined" $OUT/qfdesk.log | wc -l     # 0
grep -aoE 'Overfull \\[hv]box \(([0-9.]+)pt' $OUT/qfdesk.log | grep -oE '[0-9.]+' | awk '$1>10' | wc -l   # 0
cd /home/claudio/Git/Quant_Finance && /home/claudio/anaconda3/bin/python docs/tex/verificacion/correr.py | tail -2          # código 0
/home/claudio/anaconda3/bin/python docs/tex/verificacion/referencias_codigo.py | tail -1                                     # 0 fallos
```
Commit (solo `docs/tex/`): `docs(tex): capítulo 16, sensibilidades del XVA por diferenciación adjunta con XAD`.
Depende de: T4 (símbolos y rutas definitivas). Cubre: R8 (capítulo).

### T8 — Integración contra el backend real y suites completas · **sonnet**

Objetivo: R9 y la evidencia de R5/R7 con el sistema real.

Archivos: ninguno de producción (solo arreglos mínimos si algo falla, en la tarea que corresponda); captura en
`/tmp/fableorchestrate/qf-xad/sensibilidades.png`.

Pasos:
1. Suites completas de §6, con XAD y sin XAD (`/tmp/qf-noxad`; con esa compilación, `PYTHONPATH=/tmp/qf-noxad/src`
   y `GET /api/xva/sensitivities` → 501).
2. Backend real en 5089 con base temporal (como en cortes anteriores: `create_app(db_path=<tmp>)` sembrada; ver
   `desk/api/tests/conftest.py`), UI construida servida por el mismo backend. `curl` a
   `/api/xva/sensitivities?snapshot=MX-DEMO&counterparty=Banco%20Alfa%20(sint%C3%A9tico)` con los parámetros por
   omisión (2000 trayectorias): anotar `elapsed_s`, `valuation_elapsed_s` (R5: cociente ≤ 10, ambos con hilos y la
malla H21),
   `bump_cost_estimate_s`, y comprobar que `xva` == la contraparte de `/api/xva` (igualdad exacta).
3. Chrome headless en 9349 a 1280 px: pantalla XVA → Alfa → «Calcular sensibilidades» → esperar la tabla; captura
   de la sección; `scrollWidth ≤ clientWidth` del documento; 0 errores de consola.
4. `desk/validation/make_report.sh`: 62 dentro, `commit_matches: true`.
5. Detener el backend y Chrome; borrar la base temporal.

Verificación: las salidas anteriores pegadas en el reporte; la captura existe.
Commit: ninguno (o el de un arreglo puntual con su porqué).
Depende de: T1–T7. Cubre: R9, R5 (medición real), R7 (verificación visual).

### T5 (hecho, commit f299be6)

UI de «Sensibilidades» contra simulados; no se levantó backend. `npm test` 677 en 43 archivos (partida 658 en 42; la diferencia incluye 16 + 2 pruebas mías y alguna ajena), `npm run build` verde.

- **Tipos** (`desk/ui/src/api/xvaTypes.ts`): `XvaSensRow {cva,dva,fva,total}`, `XvaSensPillar` (+`label`,`days`), `XvaSensCurve {curve, pillars, dv01}`, `XvaSensFx`, `XvaSensVol` (+`param` en `'fx_vol'|'sigma_mxn'|'a_mxn'|'sigma_usd'|'a_usd'`, `label`), `XvaSensCds` (+`tenor`), `XvaSensHazard` (+`to_years: number|null`), `XvaSensCredit {kind:'curve'|'flat'|'assumed', cds, hazards}`, `XvaSensitivitiesResponse` (exactamente §2: `xva` es `Pick<XvaComponents,'cva_mxn'|'dva_mxn'|'fva_mxn'|'total_mxn'>`, `units` con claves `curves|fx|vols|cds|funding`, `credit: {counterparty, own}`, `empty_reason: string|null`, `warnings: Warning[]`).
- **Cliente**: `getXvaSensitivities(snapshot, counterparty)` -> `GET /xva/sensitivities?snapshot=…&counterparty=…` (ambos con `encodeURIComponent`; `apiRequest` antepone `/api`).
- **Panel**: `XvaSensitivitiesPanel({snapshotId, counterparty})` en `desk/ui/src/screens/xva/XvaSensitivitiesPanel.tsx` (+`.css`, `.test.tsx`); exporta también `sensitivityOption(curves)`. Fixture `XVA_SENSITIVITIES_FIXTURE` en `screens/xva/fixtures.ts` (TIIE-F 10, SOFR 10, MXN-USD 9 pilares con las etiquetas/días de `seed_market.py`; CDS 6 de Banco Alfa; propio `assumed` con un tramo `to_years: null`).
- **Montaje**: `XvaScreen.tsx` bajo el perfil/operaciones de la contraparte elegida, con `key={reloadTick}`.
- **Lo que el panel espera de T4 (si algo difiere, ajustar T4 o este panel)**:
  1. `error` de las respuestas 4xx/5xx llega como `ApiError.message` (lo hace `apiRequest`); el 501 se muestra tal cual.
  2. `hazards` de crédito se rotulan «Intensidad hasta N años» / «Intensidad (tramo único)» y se muestran **solo si `cds` está vacío** (curva plana/supuesta); se asume que vienen en la misma escala que `cds` (MXN por pb de intensidad). Si T4 no los escala por 1e-4, hay que corregir en uno de los dos lados.
  3. `dv01` presente aun con `pillars` vacío; con `empty_reason` el panel no pinta tablas ni gráfica (solo el aviso, `assumptions`, `method` y tiempos).
  4. El CDS de la contraparte y el propio salen en grupos «Crédito de <contraparte>» y «Crédito propio».
  5. La gráfica agrupa pilares por **días** (categorías `"<etiquetas> (<d> d)"`): pilares con los mismos días de curvas distintas comparten categoría.
- **Desviaciones/añadidos no pedidos**: (a) no se tocó `components/EChart.tsx`: las barras se registran con `use([BarChart])` en el panel, como `PnlExplainTab.tsx`; (b) `key={reloadTick}` en el montaje para descartar sensibilidades obsoletas al guardar parámetros/curvas o pactar (dos pruebas nuevas en `XvaScreen.test.tsx`, que no estaba en la lista de archivos; una verificada por mutación); (c) línea de pie con `elapsed_s`, `valuation_elapsed_s`, `n_inputs` y `bump_cost_estimate_s` (los campos del contrato existen para eso).
- **No comprobado**: aspecto real y desborde a 1280 px en navegador (el CSS usa `.xva-scroll` con `overflow-x:auto`); legibilidad de las etiquetas giradas de la gráfica con 19 categorías. Es parte de T8.

### T1 (HECHO, commit 41b3a62)

- **CMake.** `option(QF_WITH_XAD ... ON)` y el bloque `FetchContent` de XAD (`aaf4e9cad59cf1bfe9728b491f95f011db687f18`, v2.2.0, `SYSTEM`, `XAD_WARNINGS_PARANOID=OFF`, `XAD_USE_STRONG_INLINE=ON`) están en el `CMakeLists.txt` raíz **antes** del bloque de banderas `-Wall -Wextra -Wpedantic` (así esas banderas no se aplican al código de XAD). `src/CMakeLists.txt`: `target_link_libraries(qf PUBLIC XAD::xad)` + `target_compile_definitions(qf PUBLIC QF_WITH_XAD=1)` solo con la opción. La biblioteca estática de XAD se llama `libxad_d.a` (postfijo Debug); no hay `find_package(XAD)` previo (era opcional).
- **Fuente de XAD en `build/_deps/xad-src`** (clon del repositorio oficial, `HEAD` = hash fijado). Primera configuración ~5 s; compilación completa de `build/` ~2 min con `-j4`.
- **C++.** `include/qf/xva/exposure_engine.hpp`: `XvaGreeks` y `XvaSensitivities` tras `XvaResult`, tal cual §2; como `ExposureEngine` queda antes de `XvaResult`, hay una declaración adelantada `struct XvaSensitivities;` justo antes de la clase. `ExposureEngine::xvaSensitivities(set, counterparty, counterpartyLgd, own, ownLgd, fundingSpread) const` declarado en la clase (pública). `FlatHazardRate::hazardRate() const` (`credit_curve.hpp/.cpp`).
- **Stub.** `src/xva/exposure_engine.cpp`, tras `computeXva`, dentro de `namespace qf::xva`: definición **sin** `#ifdef` que lanza `std::logic_error("ExposureEngine::xvaSensitivities: qf se compiló sin XAD (QF_WITH_XAD=OFF)")` con y sin XAD. **T3 debe sustituirla** (rama `#ifdef QF_WITH_XAD` con la AAD; la otra rama conserva este `throw`). Con el stub, una compilación con XAD también lanza ese mensaje (RuntimeError en Python).
- **Binding (`qfxva`).** `HAS_XAD` (bool) justo tras `m.doc()`; clases `XvaGreeks` (`tiie, sofr, mxn_usd, spot, fx_vol, sigma_mxn, a_mxn, sigma_usd, a_usd, counterparty_hazard, own_hazard, funding_spread`) y `XvaSensitivities` (`value, cva, dva, fva`) con `def_readonly`, registradas tras `XvaResult`; `ExposureEngine.xva_sensitivities(netting_set, counterparty, counterparty_lgd, own, own_lgd, funding_spread)` con `gil_scoped_release`.
- **Pruebas.** `TEST(ExposureEngine, XvaSensitivitiesWithoutXadThrowsLogicError)` (al final de `tests/test_ExposureEngine.cpp`, dentro de `#ifndef QF_WITH_XAD`) y `ExposureEngineBindings.test_has_xad_flag_is_a_bool`. Cuentas vigentes: **ctest 508 con XAD** (la prueba nueva no existe con XAD), **509 sin XAD**; bindings **99**.
- **Sin XAD (`/tmp/qf-noxad`).** Para que compile igual que `build/` hay que configurar con los mismos valores de la caché: `cmake -S . -B /tmp/qf-noxad -DQF_WITH_XAD=OFF -DCMAKE_BUILD_TYPE=Debug -DCMAKE_CXX_COMPILER=/usr/bin/g++ -DPYTHON_EXECUTABLE=/home/claudio/anaconda3/bin/python -DGTest_DIR=/home/claudio/anaconda3/lib/cmake/GTest` (el shell exporta `CXX` de conda: sin `-DCMAKE_CXX_COMPILER=/usr/bin/g++` no encuentra pybind11, y sin `GTest_DIR` de conda no enlaza GoogleTest). Con `PYTHONPATH=/tmp/qf-noxad/src`: `HAS_XAD == False`.
- **Desviación del plan:** el bloque `FetchContent` va antes de las banderas de advertencia y no inmediatamente antes de `add_subdirectory(src)` (efecto: XAD se compila sin `-Wall -Wextra -Wpedantic`). Nada más. `desk/README.md`: sección «## XAD y su licencia» antes de «## Tests» (la línea «C++ (506 tests)» de esa sección sigue desactualizada: no se tocó).

### T2 (HECHO, commits 7055cc1 prueba dorada y 0014cf9 refactor)

Motor templado sobre `Real`; `double` idéntico bit a bit. ctest **509** (508 + `GoldenValuesUnchangedByTemplating`), bindings 99, `desk/api/tests -k "xva or credit"` 217. Ninguna prueba existente cambió (solo +35 líneas en `tests/test_ExposureEngine.cpp`).

- **Prueba dorada** (commit aparte, antes de tocar el motor): `TEST(ExposureEngine, GoldenValuesUnchangedByTemplating)` con `setOf({s0(), s1(), s2(), s4()}, {x0(), x1(), x2()})` (aged, csa, USD, xccy con/sin intercambios), 300 trayectorias, semilla 7, malla mensual 0..1800, `PiecewiseHazardCurve`; `EXPECT_EQ` con literales `%.17g` de cva, dva, fva, `valueAtZero`, `epeDisc`/`eneDisc` en los índices 1, 20 y 40, `pfe[20]`, `tradeValuesAtZero` (7 operaciones) y `deflatedValueStats` en días {30, 600}. Reproducible entre corridas y con `taskset -c 0`.
- **Firmas internas (todo en el `namespace {}` anónimo de `src/xva/exposure_engine.cpp`; nada nuevo en el header público de exposición):**
  - `using std::exp/expm1/log/max/sqrt;` en el anónimo: las llamadas van sin calificar (XAD las halla por ADL).
  - `template <class Real> struct ModelT { Real aMxn, sigmaMxn, aUsd, sigmaUsd, fxVol; double rhoMxnUsd, rhoMxnFx, rhoUsdFx; }` y `template <class Real, class Curve> struct MarketT { const Curve* tiie; const Curve* sofr; const Curve* mxnUsd /*nullptr sin base*/; Real spot; }`. Para double: `modelOf(const ExposureModel&)` y `marketOf(const ExposureMarket&)` (`MarketT<double, YieldCurve>`).
  - `template <class Real> struct PillarCurve { std::vector<double> t; std::vector<Real> z; }` y `discountAt(const PillarCurve<Real>&, double T)` (rama `Linear` de `Interpolator` + `exp(-r*T)`); `inline double discountAt(const YieldCurve&, double)`. Con el `Real` de XAD **hay que pasar los pilares en `t`/`z`** (`t` = `curve.maturities()`).
  - `Mat5<Real>`, `Kernel<Real>`, `CurrencyGrid<Real>`, `Grid<Real>`, `Context<Real>`, `PathData<Real>`, `Bonds<Real>`, `PathView<Real>`; `OuMomentsT<Real>` y `ouMomentsT(a, sigma, mu, double t)`; `stepCovarianceT(const ModelT<Real>&, double dt)`; `choleskySemidefinite<Real>`, `fillCurrencyGrid<Real,Curve>`, `buildGrid<Real,Curve>(MarketT, ModelT, horizon)`, `buildContext<Real,Curve>(MarketT, ModelT, sets, minHorizon)`, `simulatePath<Real>(Grid<Real>, seed, p, PathData<Real>&)`, `computeBonds<Real>(Context<Real>, d, Real xMxn, Real xUsd, Bonds<Real>&)`, `legValue<Real>`, `setValue<Real>(CompiledSet, Context<Real>, d, Bonds<Real>, Real qd, PathView<Real>)`. Siguen en `double`: validaciones, `Leg`/`LegPeriod`/`makeLeg`/`compileSet` (`makeLeg`, `compileSet`, `markNeed` son plantillas solo por el `Context<Real>&`), `paidFlowsDeflated` (ahora `PathData<double>`/`Grid<double>`), `forEachPathChunk`, `computeXva`, `detail::ouMoments`/`detail::stepCovariance` (firma `double` intacta, delegan en las plantillas).
  - **Para T3:** instanciar con `using AD = xad::AReal<double, 4>`, `PillarCurve<AD> pt{tiie.maturities(), {AD(...)...}}` y `MarketT<AD, PillarCurve<AD>>{&pt, &ps, &pm /*o nullptr*/, spot}`, `ModelT<AD>{...}`; `buildContext(market, model, {set}, report.back())`. Los argumentos `Real` de una misma llamada deben ser del mismo tipo (no pasar expresiones de XAD sin `Real(...)`; `expIntegral` ya lo hace). `dt` y `t` en años son `double`.
  - `include/qf/xva/piecewise_hazard_curve.hpp`: `template <class Real> Real survivalFromHazards(const std::vector<double>& times, const std::vector<Real>& hazards, double t)`; `PiecewiseHazardCurve::survivalProbability` la llama con `double`.
- **Comprobaciones hechas fuera del repo (sin commit):** (1) instancié temporalmente todo el camino (`buildContext`, `simulatePath`, `computeBonds`, `setValue`, `survivalFromHazards`) con `xad::AReal<double,4>` y `PillarCurve<AD>`: compila sin errores ni avisos; (2) cambié temporalmente `simulate()` para usar `PillarCurve<double>` (pilares de `YieldCurve`) y la prueba dorada pasó con igualdad exacta: la interpolación replicada coincide bit a bit con `YieldCurve` (rama plana inferior y tramo interior; la plana superior no se ejerció: máx. 12 a > horizonte de la prueba). Ambos temporales se revirtieron.
- **Desviaciones:** `dt` y `t` quedaron `double` (no `Real`) en `expIntegral`/`kernelIntegral`/`stepCovarianceT`/`ouMomentsT`: no son insumos y así no se graban en la cinta. Los literales dorados dependen de compilador y banderas (build sin FMA con `-march=nocona`); comentado en la prueba. No se corrió el build sin XAD (`/tmp/qf-noxad`): T2 no toca nada dependiente de XAD.

### T3 (HECHO salvo R5; commit c85df00)

`ExposureEngine::xvaSensitivities` implementado por AAD; **R5 no se cumple con hilos (ratio 20 con 8 hilos)**, ver abajo. Tests: ctest **517** con XAD (509 + 8 nuevas; `AadTiming` sale como Disabled), **510** sin XAD (`/tmp/qf-noxad`, 100 %), bindings **100** (99 + `test_xva_sensitivities_shape`).

- **Dónde.** `src/xva/exposure_engine.cpp`, tras `computeXva`: rama `#ifdef QF_WITH_XAD` (la otra rama conserva el `throw std::logic_error` de T1). Sin cambios en `include/`. Sin duplicar el motor: usa `buildContext/simulatePath/computeBonds/setValue` templados de T2 con `AD = xad::AReal<double,4>` y `PillarCurve<AD>`.
- **Orden de los insumos** (un solo `std::vector<AD>` registrado por hilo): pilares TIIE-F, pilares SOFR, pilares MXN-USD (0 si no hay), spot, `[fxVol, sigmaMxn, aMxn, sigmaUsd, aUsd]`, intensidades de la contraparte, intensidades propias, fondeo. `FlatHazardRate(λ)` → un tramo `{max(reportDays.back()/365, 1)}`; otro tipo de `ICreditCurve` o cualquier curva de tasa no `Linear` → `std::invalid_argument`. LGD/fondeo se validan con los mensajes de `computeXva`.
- **Forma del resultado.** `XvaSensitivities.value`: `cva/dva/fva` = suma sobre trayectorias de la contribución por trayectoria (que ya lleva 1/N), `total = cva − dva + fva`; `cvaStdErr/dvaStdErr = N · standardError(contribuciones)` (igual a `computeXva` hasta redondeo; probado a 1e-12 relativo en valor y en stdErr). `XvaGreeks` son derivadas de cada medida **por separado** (`dva` es ∂DVA, positiva; `total = cva − dva + fva` se arma en la API). Longitudes: `tiie/sofr/mxnUsd` = pilares de la curva (`mxnUsd` vacío sin base), `counterpartyHazard/ownHazard` = tramos (1 si es plana).
- **Reparto en hilos.** `forEachPathChunk`, una `xad::Tape<double,4>` por hilo; cada trozo guarda sus adjuntos en un `std::map` por primera trayectoria y se suman en orden (resultado independiente del orden de llegada de los hilos). Los dos comentarios de excepción a «sin duplicar» están en el código.
- **Diagnóstico.** `qf::xva::detail::aadTapeBytes()` (declarada en el `.cpp` y redeclarada en la prueba, como `ouMoments`): pico de bytes de una cinta en la última llamada; 0 sin XAD. No es API pública.
- **Pruebas** (`tests/test_ExposureEngine.cpp`, bajo `#ifdef QF_WITH_XAD`): `AadMatchesBumpTiieSwap`, `…SofrSwap`, `…XccySwap`, `…CombinedSet`, `AadValueMatchesComputeXva`, `AadZeroVolatilityMatchesDeterministicDerivative`, `AadFlatHazardHasOneTranche`, `AadRejectsNonLinearCurves`, `DISABLED_AadTiming`. Choque central con las mismas trayectorias (400 tr., malla mensual 0..1800, h = 1e-5 tasas/σ/a/vol FX, 1e-3 spot, 1e-6 intensidades/fondeo), tolerancia `max(1 %·|fd|, 1 MXN por unidad)` sin aflojar. Desacuerdo medido: curvas, modelo y spot ≈ 1e-4 relativo (máx. 4.5e-3 en un pilar con derivada pequeña, −22 542 frente a −22 644), crédito y fondeo 1e-10, FVA frente a spot/σ 1e-9. Detalle: `TiieSwap` exige que ∂/∂SOFR, ∂/∂MXN-USD y ∂/∂spot sean exactamente 0; el SOFR/xccy/combinado recorren los tres pares de curvas (el SOFR depende de TIIE-F por la cuenta bancaria y de MXN-USD por la deriva del spot).
- **Desviaciones.** (1) `AadZeroVolatility…` usa `|aad−fd| ≤ 1e-6·|fd| + 1e-3` (el piso 1e-3 MXN/unidad es solo el redondeo del choque de 1e-7, no una holgura sobre la AAD). (2) `AadRejectsNonLinearCurves` incluye además una curva de crédito de otro tipo (rama que el plan declara y nadie probaba). (3) `DISABLED_AadTiming` conserva `EXPECT_LE(ratio, 10)`: hoy falla si se corre a mano (ctest no la ejecuta).
- **Mutación R4 hecha.** `z[i+1]` → `Real(xad::value(z[i+1]))` en `discountAt(PillarCurve)`: fallan `TiieSwap`, `SofrSwap`, `XccySwap`, `Combined` y `ZeroVolatility` (p. ej. ∂CVA/∂z_TIIE(1a): AAD −1 049 708 frente a −1 379 976 por choque); `Golden…` (double) sigue pasando. Revertida (archivo idéntico a antes).

**R5 medido** (`./tests/qf_tests --gtest_filter='*DISABLED_AadTiming*' --gtest_also_run_disabled_tests`; i7-10510U 4C/8T, build como `build/`, carga ajena 1–4; conjunto de 3 operaciones de la sonda, 1407 fechas tipo H21, 2000 tr.):

| hilos (de `forEachPathChunk`) | double simulate+computeXva | AAD | ratio |
|---|---|---|---|
| 1 | 4.87 s | 44.5 s | **9.1** (500 tr.: 9.6) |
| 2 | 2.83 s | 27.7 s | **9.8** |
| 4 | 1.54 s | 26.0 s | 16.8 |
| 8 (valor por omisión) | 1.31 s | 26.4 s | **20.2** (500 tr.: 20.6–21.7) |

- La AAD no baja de ~26 s con más de 2 hilos (speedup 1.7×) mientras el double escala 3.7×. Un hilo reproduce lo medido en la sonda (8.5–9.4×).
- **Dónde se va el tiempo** (1 hilo, 2000 tr., CPU-s; instrumentación temporal ya retirada): AAD = trayectoria 3.2 + `computeBonds` 7.6 + `setValue` 13.1 + resto 0.3 (grabación 24.1) + **barrido de adjuntos 17.8** (40 %). Double por repetición = trayectoria 1.15 + bonos 2.45 + `setValue`/resto 1.17. Con 8 hilos el barrido de adjuntos pasa de 17.8 a 115 CPU-s (×6.5) y la grabación de 24.1 a 82 (×3.4), mientras el double no se infla (9.4 vs 9.5): es ancho de banda de memoria, no cómputo.
- **Memoria de la cinta** (criterio de R5): pico por hilo **48 063 764 B (48.06 MB), idéntico con 500 y con 2000 trayectorias**; la parte común son 4 957 880 B (4.96 MB) y cada trayectoria añade ~43 MB que `resetTo` descarta. (Los «5.5–6.0 MB» de la sonda medían solo la parte común, después de `resetTo`.) Con 8 hilos son ~385 MB de cinta recorrida dos veces por trayectoria, que no cabe en la L3 (8 MB).
- **Opciones para que decida el orquestador (no probadas):** (a) topar los hilos de la AAD en 2 (mismo tiempo, menos memoria; R5 «mismos hilos» pasaría solo si el double se mide también con 2); (b) redefinir R5 como razón de un hilo (9.1–9.6) y documentar que con 8 hilos la AAD tarda ~26 s; (c) bajar el tamaño de la cinta por trayectoria (el 70 % está en `setValue` y `computeBonds`: un adjunto escrito a mano de la fórmula afín evitaría grabar ~2.4 M operaciones por trayectoria); (d) `AReal<double,1>` solo daría −20 % (medido en la sonda). **Consecuencia para T4–T8:** el `elapsed_s` de ejemplo (3.1 s) no es realista para conjuntos pesados con malla H21 y 2000 trayectorias en esta máquina; la API deberá medirlo (el conjunto de 3 operaciones a 10 años tarda ~26 s en AAD frente a ~125 s por choques con 8 hilos de double: sigue siendo ~5× más barata que 2·insumos valuaciones).
- **Prueba ajena inestable (no tocada):** `ExposureEngineBindings.test_simulate_releases_the_gil` (pytests) falla a veces con «0.287 not greater than 0.3, the simulation is too short»: desde que `simulate` reparte trayectorias en hilos (otro agente), 4000 trayectorias tardan ~0.29–0.31 s, justo en el umbral. Pasa y falla en corridas consecutivas; no depende de este commit.

### T6 (HECHO, commit de la Metodología)

- `desk/ui/src/screens/MethodologyScreen.tsx`: ítem `Sensibilidades del XVA` añadido al final de `XVA_SECTIONS` (antes de «Límites del XVA»), con cifras T3: 9.1× con un hilo, 9.8× con dos; AAD ≤ 2 hilos; «decenas de segundos»; choques 2 × insumos; XAD AGPL-3.0; `QF_WITH_XAD=OFF`.
- `MethodologyScreen.test.tsx`: una prueba nueva que comprueba los términos clave de la fila.
- Verificación: `npx vitest run src/screens/MethodologyScreen.test.tsx` → 44 pasan (1 archivo); `npx tsc --noEmit -p .` → exit 0.
- No comprobado: `npm run build` no se corrió (fuera del encargo); la fila no se revisó visualmente en el navegador; la cifra de 9 veces viene de una sola medición (T3) con carga ajena, en una máquina.

### T4 (HECHO; commits f0b47b2 tope de hilos, 98bb664 prueba del GIL, 2b3dd91 ruta)

`GET /api/xva/sensitivities` implementado. ctest **518** con XAD (517 + `AadMaxThreadsCapsTheWorkersAndKeepsTheResult`; `AadTiming` sigue Disabled), **510** sin XAD (`/tmp/qf-noxad`, 100 %), bindings **101** (100 + `test_xva_sensitivities_max_threads`), backend **3804** (3797 + 7 de `test_xva_sens.py`).

- **C++ (decisión de Fable sobre R5).** `ExposureEngine::xvaSensitivities(set, cp, cpLgd, own, ownLgd, fundingSpread, unsigned maxThreads = 2)`; Python `xva_sensitivities(..., max_threads=2)`; `maxThreads == 0` -> `std::invalid_argument` (`ValueError`). `forEachPathChunk(nPaths, body, maxThreads = ilimitado)` (simulate no cambia). `detail::aadThreads()` (diagnóstico, número de cintas de la última llamada; la prueba lo redeclara). **`hardware_concurrency()` no ve la máscara de afinidad** (`taskset` no reduce los hilos de `simulate`), y el tiempo de CPU del proceso NO sirve como sustituto de «un hilo» (8 hilos en 4 núcleos con HT suman 11.9 CPU-s frente a 4.8 s de un hilo): `DISABLED_AadTiming` fija el proceso a un núcleo con `sched_setaffinity` (RAII `OneCpu`, solo Linux; en otro sistema `GTEST_SKIP`) y usa `maxThreads = 1` en la AAD. Desviación de proceso: esto obligó a una **segunda compilación incremental de `qf_tests`** (13 s, sin tocar la biblioteca) además de la compilación única de `build/` (39 s).
- **R5 medido** (`./tests/qf_tests --gtest_filter='*DISABLED_AadTiming*' --gtest_also_run_disabled_tests`, ~100 s, carga ajena ~2): un núcleo para ambos, 1407 fechas: **2000 tr.: double 4.80 s, AAD 44.5 s, razón 9.27**; 500 tr.: 1.11 s / 10.9 s, razón 9.85 (margen corto: T3 midió 9.1/9.6; con carga ajena puede rozar 10). Todos los núcleos: double 1.28 s (8 hilos) y AAD **27.6 s con los 2 hilos por omisión** (7.1 s a 500 tr.); cinta por hilo **48 063 764 B, idéntica con 500 y con 2000**. Es decir, la razón de tiempo real que verá la API/T8 es ~18–21× (AAD en 2 hilos contra valuación en 8).
- **Python** (`desk/api/risk/xva_sens.py`, **116 líneas no vacías ni de comentario**; la ruta añade 3 y cambia 1 de import: **120** en total, presupuesto 120). `compute(conn, snapshot_id, name)` con las firmas de §2; constantes públicas `PARTIAL_NOTE`, `UNITS`, `VOLS`, `KEYS`. Orden de errores: snapshot 404 (`load_context`), contraparte 404 `field: counterparty`, `HAS_XAD` falso 501 (sin `field`), y 400 por parámetro ausente en la ruta. `xva` = `xva._counterparty(...)` (igual, `==`, al de `GET /api/xva`); `valuation_elapsed_s` es el tiempo de esa llamada completa (incluye `build_set`, bootstrap de crédito, simulación, `compute_xva` y el perfil publicado, así que sobreestima un poco la valuación pura); `bump_cost_estimate_s = 2 · n_inputs · valuation_elapsed_s`.
- **Escala de `hazards` (la duda de T5, decidida):** ×1e-4, **MXN por pb de intensidad**, igual que `cds`; con curva de CDS (`kind == "curve"`) vienen **`cds` (6) y `hazards` (6)** a la vez, `hazards[i].to_years` = plazo de la cotización i (como `GET /api/credit/curves`, no `curve.times()`); con `flat`/`assumed`: `cds: []` y un solo tramo `to_years: null`. **T8 debe confirmar** en la pantalla que los rótulos «Intensidad hasta N años» (solo se muestran con `cds` vacío) y la unidad son coherentes. Desviación de texto: `units.cds = "MXN por pb (de cotización de CDS o, sin curva, de intensidad)"` (§2 decía `"MXN por pb"`); `units.vols` es la cadena larga de la decisión de Fable. El panel de T5 imprime `units.*` tal cual.
- **Datos reales de Banco Alfa:** su conjunto vence antes de 5 años, así que las filas de CDS/intensidad de 5Y, 7Y y 10Y valen exactamente 0 (no es un error: la exposición no llega ahí). 48 insumos (TIIE-F 10, SOFR 10, MXN-USD 9, spot, 5 de modelo, 6+6 tramos, fondeo). Las filas de crédito propio salen con `kind: "curve"` (la propia sembrada es una curva, no `assumed` como en el fixture de T5).
- **Desviación — `assumptions`:** son las del modelo (`model_from_snapshot`) + `INTEGRATION_NOTE` + `PARTIAL_NOTE`. **No** incluye las notas de MXN-USD ausente, fondeo por omisión ni crédito supuesto de `GET /api/xva` (esos textos están en línea dentro de `xva.compute_detailed`, que T4 no puede tocar y copiarlos duplicaría texto; el presupuesto de líneas tampoco da). Si se quieren, lo limpio es extraerlas a funciones de `xva.py` en otro corte. `warnings` = los de valuación de las operaciones de esa contraparte.
- **Tiempos reales por la API, 2000 trayectorias, snapshot MX-DEMO** (carga ajena ~1.6): Banco Alfa **6.1 s** (AAD 5.77 s, valuación 0.31 s, choques estimados 30.0 s); Banco Beta **12.4 s** (11.77 / 0.60 / 57.5 s); Banco Gamma **5.6 s** (5.27 / 0.35 / 33.3 s). Con la malla fina y 2000 trayectorias los conjuntos sembrados tardan decenas de segundos como máximo, no los 26 s de la sonda pesada. Pruebas con servidor de prueba (`test_xva_sens.py`, 7 pruebas, 3.9 s en total): `test_aad_matches_bump_and_reprice_for_one_input_of_each_class` (500 tr.; pilar de mayor sensibilidad de TIIE-F/SOFR/MXN-USD, spot, vol FX, fondeo y una cotización de CDS) **2.36 s**; forma y coherencia con `GET /api/xva` (200 tr., fixture de módulo) 0.81 s de preparación; sin MXN-USD (100 tr.) 0.25 s; el resto < 0.05 s. Mutaciones comprobadas (revertidas): jacobiano de CDS omitido, escala del spot ×2 y pilar desalineado hacen fallar la comparación.
- **Prueba del GIL (`tests/test_xva_engine_py.py::test_simulate_releases_the_gil`):** `n_paths = 2500 * os.cpu_count()` (20 000 aquí; la llamada dura ~1.5 s, antes 0.29–0.31 s contra el mínimo de 0.3 s); 5 corridas seguidas y 3 con 8 procesos de CPU compitiendo pasan; el motor no se tocó.
- **No comprobado:** el 501 real (solo con `monkeypatch` de `HAS_XAD`; el camino sin XAD de C++ sí está probado en `/tmp/qf-noxad`); la pantalla contra el backend real (T8).

### T8 (HECHO; commits 6cd4deb notas compartidas, e2f1d26 panel, 0803a8f README, c08d948 validación)

Integración con el backend real (5089, base temporal, Chrome headless 9349 a 1280 px; todo apagado y la base borrada). No se recompiló C++ (los `.so` de `build/` y `/tmp/qf-noxad` ya estaban al día).

- **Suites.** ctest con XAD **518 pasan** (519 listados; `AadTiming` Disabled), sin XAD **510 pasan**; bindings **101**; backend **3805** (3804 + 1 mía); `npm test` **681** en 43 archivos; `npm run build` verde. 501 real: backend arrancado con `/tmp/fableorchestrate/qf-xad/serve_noxad.py` (antepone `/tmp/qf-noxad/src` y pre-importa `qfpy`/`qfxva`, porque `desk/api/qf.py` antepone `build/src` y `PYTHONPATH` solo no basta) → `HAS_XAD False`, `GET /api/xva/sensitivities` = 501 `{"error": "Sensibilidades no disponibles: el motor se compiló sin XAD (QF_WITH_XAD=OFF)", "field": null}` y `GET /api/xva` sigue en 200. Validación QuantLib: 62 dentro / 0 explicadas / 0 fuera, `commit_matches: true` (`GET /api/validation/report`), `desk_commit` = f0b47b2 (último que tocó `VALUATION_PATHS`); las cifras de los JSON no cambiaron (solo commit y hora).
- **Nueva función** `xva.run_notes(conn, mkt, own_info, counterparties) -> List[str]` (`desk/api/risk/xva.py`): notas de MXN-USD ausente, fondeo por omisión, crédito propio supuesto y crédito supuesto por contraparte; las usan `compute_detailed` y `xva_sens.compute` (`assumptions = modelo + INTEGRATION_NOTE + run_notes(..., [cp]) + PARTIAL_NOTE`). `xva_sens.py` queda en 117 líneas de código. Prueba: `test_assumptions_carry_the_same_notes_as_get_xva` (igualdad exacta con `GET /api/xva` + `PARTIAL_NOTE`; falló antes del cambio).
- **Panel** (`XvaSensitivitiesPanel.tsx/.css/.test.tsx`, `fixtures.ts`): aviso previo de que puede tardar decenas de segundos y de que al terminar se muestra tiempo real y costo por choques; mensaje de espera (`aria-live`) mientras calcula; «Calculado en X s (…) Por choques … Y s» sube junto al XVA de la contraparte (ya no en el pie); cada grupo de la tabla de factores lleva su unidad («Tipo de cambio · MXN por 1 % del spot», «Volatilidades · …», «Crédito de X · MXN por pb de cotización de CDS» o «… por pb de intensidad» según las filas mostradas, «Fondeo · MXN por pb»), y se quitó la línea «Unidades.» del pie (`units.cds` ya no se imprime: el rótulo por grupo es más preciso que la cadena de dos casos de T4); nota «Un pilar o plazo en cero queda más allá del último vencimiento…»; etiquetas del eje de la gráfica sin los días (`formatter` quita « (N d)», el tooltip los conserva) y eje «CVA, MXN por pb». La fixture usa ahora el `units.cds` real. Con curva de CDS el panel muestra solo `cds` (los `hazards` llegan en la respuesta pero no se pintan, por diseño de T5); «Intensidad hasta N años» no ocurre con el contrato real (solo `to_years: null` con `flat`/`assumed`). Comprobado en pantalla con un Banco Delta temporal: `assumed` y `flat` → «Intensidad (tramo único)», y la nota de crédito supuesto aparece en `assumptions`.
- **Tiempos reales** (2000 trayectorias, MX-DEMO, AAD en 2 hilos, valuación en 8; carga ajena ~1–3): API/navegador clic→tabla: Alfa 5.8 s / 6.3 s (valuación 0.32 s, choques estimados 30.6 s, razón 18×), Beta 11.9 s / 12.6 s (0.61 s, 58.8 s, 20×), Gamma 5.3 s / 5.6 s (0.34 s, 32.6 s, 15.5×); `xva` == `GET /api/xva` exacto en las tres. El ahorro frente a choques es ~5×.
- **GIL.** Con Beta (12.5 s) corriendo, 38 rondas de `/api/xva/params`, `/api/counterparties` y `/api/trades`: mediana 2–3 ms, máximo 4.4 ms (en reposo 1.3–1.9 ms).
- **Capturas**: `/tmp/fableorchestrate/qf-xad/shots/xva-sensibilidades.png` (Beta) y `xva-sensibilidades-alfa.png`; 1056 px de ancho, `scrollWidth` 1280 = ancho de ventana, 0 desbordes internos, 0 errores de consola, sin rótulos crudos.
- **Cordura económica (Beta, sin ajustar nada):** ver el reporte. Alfa: sus filas de CDS/intensidad a 5Y, 7Y y 10Y y los pilares más allá de ~3 años valen exactamente 0 (el conjunto vence antes).

### T7 (HECHO; commits f93898d referencias, 8be4ab4 hallazgo H25, c59a8d1 capítulo)

Capítulo 16 «Sensibilidades del XVA por diferenciación adjunta» (`docs/tex/capitulos/cap16_xva_aad.tex`, etiqueta `cap:xva-aad`, páginas 154–169 de `qfdesk.pdf`, 16 páginas). 16 ecuaciones numeradas (16.1–16.16), 59 `\codigo` distintos (65 apariciones), 52 `\verif`, 10 citas distintas (9 entradas nuevas en el `.bib` más `glasserman2003`), recuadros `diferencia` y `limites`, símbolos en `simbolos/cap16.tex` y alta en `qfdesk.tex`, `apendice_simbolos.tex` y `README.md` (lista de capítulos, etiqueta fija, requisito de `qfxva` con XAD).
- **Script** `docs/tex/verificacion/cap16_xva_aad.py` (rc=0, 52 `OK`, 30–50 s según la carga; reusa `plana`, `MODELO_DEMO` y `forma_cerrada` de `cap14_xva.py`): AAD contra choque central con las mismas trayectorias (TIIE-F, SOFR, spot, σ_M, intensidad y DV01 paralelo; diferencia relativa máxima 0.0062 %), límite sin volatilidad contra la derivada analítica (CVA, FVA y crédito, a 1e-15), vega contra la forma cerrada del capítulo 14 (20 lotes de 3000 trayectorias, |z| máx 2.26), crédito y ruta (jacobiano del bootstrap por reprecio J11 = 1.675581, regla de la cadena contra reprecio del CDS, ecuación (16.11) rehecha con el perfil, XVA de referencia `==` el de `GET /api/xva`, FVA/s_f) y derivada parcial frente a total en un xccy con MXN-USD recalibrada por `MarketContext.shifted` (CVA: parcial +111.858 por pb, total −145.508; la total se reconstruye con las parciales por AAD de MXN-USD).
- **Referencias** confirmadas en esta sesión: Capriotti 2011 (J. Comput. Finance 14(3), DOI 10.21314/jcf.2011.234), Capriotti, Lee y Peacock 2011 (SSRN, DOI 10.2139/ssrn.1824864), Capriotti y Giles 2024 (Quant. Finance 24(9), DOI 10.1080/14697688.2024.2325158), Broadie y Glasserman 1996 (Manage. Sci. 42(2), DOI 10.1287/mnsc.42.2.269), Griewank y Walther 2008 (ISBN 978-0-89871-659-7), Naumann 2011 (ISBN 978-1-61197-206-1), Savine 2018 (ISBN 978-1-119-53945-2, página de Wiley), XAD como `@manual` (GitHub, v2.2.0 por hash). **Desviación:** Giles y Glasserman «Smoking adjoints» (Risk, 2006) no tiene DOI en Crossref ni pude abrir la página de Risk (404); se cita en su lugar el **informe de Oxford 05/15 (agosto de 2005)**, que abrí en el sitio de la institución (`people.maths.ox.ac.uk/gilesm/files/NA-05-15.pdf`), con la nota de que no se confirmó el DOI de la versión de la revista.
- **Hallazgo H25** (en `HALLAZGOS.md`): la Metodología da el costo como «9 a 10 valuaciones» (cifra a igual número de hilos); la ruta tarda de 15 a 23 veces la valuación porque ésta usa todos los hilos y la adjunta dos (repetido hoy: 21.8, 23.2 y 18.1 en Alfa, Beta y Gamma). Sin corrección de código ni texto.
- **Lo que hallé y conviene saber:** (1) la vega por trayectoria de σ_M es mucho más ruidosa que el CVA (11 % entre corridas de 3000 trayectorias frente a ≈ 1 %), y la ruta no informa el error estándar de las derivadas; (2) con las semillas del script el CVA de esa vega queda ~2.3 errores estándar por debajo de la forma cerrada, pero dos corridas independientes (40×5000 y 60×3000) dan z = +1.03 y −0.89, así que no hay sesgo; (3) la derivada parcial de TIIE-F para un xccy con descuento MXN-USD tiene el signo contrario al de la total (la recalibración de MXN-USD mueve sus pilares de 2 años en adelante ~1 pb por pb de TIIE-F), lo que el capítulo y los límites dicen con todas las letras.
- **No comprobé:** las cifras de costo y memoria (las citan las notas T3 y T4; repetí solo los tiempos por la API de las tres contrapartes, con carga ajena distinta); la compilación sin XAD (`/tmp/qf-noxad`, que T3 y T4 ya corrieron); el aspecto de la sección de la pantalla XVA.

### T9 (HECHO; commits af3a5aa total+recorte, ac7050d mensaje de fondeo, ab65f74 interfaz, 8df15f8 Metodología, 92d6768 docs/tex, 04c36bd validación)

Cierre del corte: derivada total con MXN-USD recalibrada, interfaz, presupuesto, H25 y capítulo 16.

- **Forma de la respuesta** (`desk/api/risk/xva_sens.py`): cada fila de pilar de TIIE-F y de SOFR, `fx` y el `dv01` de esas dos curvas llevan `recalibrated: {cva,dva,fva,total}` (la total); el resto de las claves siguen siendo la parcial. MXN-USD, volatilidades, crédito y fondeo no traen `recalibrated` (MXN-USD es lo que se recalibra; en las demás la total es la parcial). Sin MXN-USD en el snapshot, `recalibrated` == parcial. `_total(sens, mkt)` devuelve un `SimpleNamespace(cva,dva,fva)` con `.tiie/.sofr/.spot` totales y `_row(sens, pick, scale, tot=None)` añade `recalibrated`. Jacobiano: `MarketContext.shifted` (± 1 pb por pilar, ± 0.1 % del spot) y `curves["MXN-USD"].rates()`; 42 recalibraciones, ~0.07 s, incluidas en `elapsed_s`.
- **Quitado:** `hazards` con cotizaciones de CDS (ahora `[]`; con `flat`/`assumed` sigue el tramo único), `+ 7` de `n_inputs` (cuenta `dir(g)` del binding), `UNITS` y `units` de la respuesta (las unidades viven solo en `XvaSensitivitiesPanel.tsx`: `UNIT_CURVES/FX/VOLS/FUNDING`). `assumptions` = `... + [PARTIAL_NOTE, COST_NOTE]` (`COST_NOTE`: `bump_cost_estimate_s` estima choques con la valuación en todos los hilos).
- **Prueba:** `test_total_matches_bump_recalibrate_and_reprice` (500 tr., Alfa; pilar de TIIE-F y de SOFR de mayor total, y spot; choque + `shifted` + reprecio completo, max(1 %, 1 MXN por pb); además total − parcial contra la misma resta por reprecio, 2 %). Tres mutaciones a mano hechas fallar y revertidas.
- **Líneas de código** (sin blancos, comentarios ni docstrings, contadas con `ast`/`tokenize`): `xva_sens.py` 124 + ruta (+3 netas, 4 brutas) + `xva.py` (+4 netas, ~15 brutas, `run_notes`) = 131 netas (≤ 143 brutas) frente al tope de 150.
- **C++:** mensaje del fondeo de `xvaSensitivities` ahora «ExposureEngine::xvaSensitivities: funding spread…»; prueba `AadFundingSpreadErrorNamesTheMethodThatRejectsIt`. `validateLgd` conserva el prefijo «computeXva:» (compartido con `computeXva`; no se tocó).
- **Cuentas:** ctest 519 con XAD (518 + la nueva), 510 sin XAD (`/tmp/qf-noxad`, reconstruido), bindings 101, backend 3806, vitest 684, build verde; validación 62/0/0, `commit_matches` true (desk_commit ac7050d).
- **Docs:** `cap16_xva_aad.tex` (sección parcial/total con ecuación (16.16), ejemplo con fila de la API, costo con Debug, límites), `cap16_xva_aad.py` (`cap16-total-api-cva` = −145.507 y `cap16-total-api-total` = −458.339 contra choque y reconstrucción; las intensidades ya no salen de la API sino del binding), H25 con «Resolución:». `correr.py` 14 scripts/403 valores rc=0, `referencias_codigo.py` 1209 refs/0 fallos, latexmk rc=0, 0 citas sin resolver, 0 cajas > 10 pt, 187 páginas; PDF en `/tmp/fableorchestrate/qf-docs/qfdesk.pdf`.
- **Desviación:** «de 18 a 23 veces» del encargo se escribió «de 15 a 23» (Gamma midió 15.1, 15.5 y hoy 15.5; Alfa 18.7, Beta 19.4).
