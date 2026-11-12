#pragma once
#include <cstddef>
#include <optional>
#include <vector>
#include <qf/termstructure/yieldcurve.hpp>
#include <qf/xva/credit_curve.hpp>

namespace qf::xva {

/// @brief Moneda de un swap de tasa: MXN usa TIIE-F; USD usa SOFR (proyección y descuento).
enum class SwapCurrency { MXN, USD };

/// @brief OIS envejecido (como OisSwap). Tiempos en días desde hoy.
struct RateSwapSpec {
    SwapCurrency currency;            ///< MXN: TIIE-F; USD: SOFR.
    double notional;                  ///< En la moneda del swap.
    double fixedRate;                 ///< Tasa fija en decimal.
    bool   payer;                     ///< true = paga fija.
    int    startDays;                 ///< Inicio del periodo en curso (o del swap) en días desde hoy; <0 si ya empezó.
    std::vector<int> payDays;         ///< Pagos pendientes en días desde hoy, crecientes y > 0.
    double accruedFactor;             ///< Factor compuesto ya fijado del periodo en curso (1 si startDays >= 0).
    double dayBase = 360.0;           ///< Base de devengo de la pata fija y de la compuesta.
    bool   csaDiscount = false;       ///< Solo MXN: descuenta con MXN-USD (base determinista).
};

/// @brief Cross currency swap envejecido (como XccySwap). Tiempos en días desde hoy.
struct XccySwapSpec {
    double notionalUsd;               ///< Nocional en USD.
    double fxRate;                    ///< Tipo de cambio pactado (MXN por USD).
    double spread;                    ///< Diferencial de la pata MXN, decimal.
    int    startDays;                 ///< Inicio del periodo en curso (o del swap) en días desde hoy.
    std::vector<int> payDays;         ///< Pagos pendientes en días desde hoy.
    double accruedFactorUsd;          ///< Factor compuesto fijado de la pata USD.
    double accruedFactorMxn;          ///< Factor compuesto fijado de la pata MXN.
    bool   payUsd;                    ///< true = XccySide::PayUsd (paga USD, recibe MXN).
    bool   initialExchange;           ///< Intercambio inicial de nocionales.
    bool   finalExchange;             ///< Intercambio final de nocionales.
    double dayBase = 360.0;           ///< Base de devengo.
    bool   csaDiscount = true;        ///< Pata MXN descontada con MXN-USD; false = TIIE-F.
};

/// @brief Conjunto de compensación (netting set): swaps de tasa y cross currency swaps.
struct NettingSetSpec {
    std::vector<RateSwapSpec> swaps;
    std::vector<XccySwapSpec> xccys;
};

/// @brief Mercado para el motor de exposición.
struct ExposureMarket {
    termstructure::YieldCurve tiie;                    ///< TIIE-F.
    termstructure::YieldCurve sofr;                    ///< SOFR.
    std::optional<termstructure::YieldCurve> mxnUsd;   ///< MXN-USD; obligatoria si algún spec tiene csaDiscount.
    double spot;                                       ///< USDMXN, MXN por USD.
};

/// @brief Modelo: Hull-White 1F por moneda más FX lognormal, medida riesgo neutral MXN.
struct ExposureModel {
    double aMxn;
    double sigmaMxn;
    double aUsd;
    double sigmaUsd;
    double fxVol;
    double rhoMxnUsd;                 ///< Correlación de los brownianos MXN y USD.
    double rhoMxnFx;                  ///< Correlación de los brownianos MXN y FX.
    double rhoUsdFx;                  ///< Correlación de los brownianos USD y FX.
};

/// @brief Configuración de la simulación.
struct SimConfig {
    std::size_t nPaths;               ///< Número de trayectorias.
    unsigned    seed;                 ///< Semilla base; la trayectoria p usa (seed, p).
    double      pfeQuantile;          ///< Cuantil PFE en (0,1).
    std::vector<int> reportDays;      ///< Malla de reporte en días desde hoy, crecientes; reportDays[0] == 0.
};

/// @brief Perfil de exposición de un conjunto. Todo en MXN; un elemento por reportDays.
struct ExposureProfile {
    std::vector<int>    days;
    std::vector<double> times;            ///< days/365.
    std::vector<double> expectedValue;    ///< E[V(t)] sin descontar.
    std::vector<double> epe;              ///< E[max(V,0)] sin descontar.
    std::vector<double> ene;              ///< E[max(-V,0)] sin descontar.
    std::vector<double> pfe;              ///< Cuantil de max(V,0) sin descontar.
    std::vector<double> epeDisc;          ///< E[max(V,0)/B(t)] con la cuenta bancaria MXN simulada.
    std::vector<double> eneDisc;          ///< E[max(-V,0)/B(t)] con la cuenta bancaria MXN simulada.
    double valueAtZero;                   ///< V(0) neto.
    std::vector<double> pathDiscPos;      ///< nPaths×nDays (fila = trayectoria): max(V,0)/B. No se expone a Python.
    std::vector<double> pathDiscNeg;      ///< nPaths×nDays: max(-V,0)/B. No se expone a Python.
};

/// @brief Media y error estándar de un estadístico simulado.
struct DeflatedStat {
    double mean;
    double stdErr;
};

/// @brief Cuenta de descuento para los deflactores.
enum class Deflator {
    TiieAccount,        ///< B(t) = exp(∫_0^t r_TIIE).
    CollateralAccount   ///< B(t) · P_TIIE(0,t) / P_MXN-USD(0,t).
};

struct XvaSensitivities;   // definida tras XvaResult

/// @brief Motor de exposición multimoneda (simulación y revaluación sobre las mismas trayectorias).
class ExposureEngine {
public:
    /// @brief Valida mercado, modelo y configuración.
    /// @throws std::invalid_argument si algún parámetro es inválido (p. ej. matriz de correlación no definida positiva).
    ExposureEngine(ExposureMarket market, ExposureModel model, SimConfig config);

    /// @brief Simula todos los conjuntos sobre las mismas trayectorias (malla diaria; revaluación en reportDays).
    /// @param sets  Conjuntos de compensación.
    /// @return      Un perfil por conjunto, en el mismo orden.
    std::vector<ExposureProfile> simulate(const std::vector<NettingSetSpec>& sets) const;

    /// @brief Valor en t = 0 de cada operación (swaps primero, luego xccys), en MXN, sin simular.
    /// @param set  Conjunto de compensación.
    /// @return     Valores en MXN.
    std::vector<double> tradeValuesAtZero(const NettingSetSpec& set) const;

    /// @brief Estadístico para la prueba de martingala: media y error estándar de
    /// V(t)/D(t) + Σ_{flujos pagados en (0,t]} flujo/D(t_pago).
    /// @param set       Conjunto de compensación.
    /// @param days      Días desde hoy en los que se evalúa.
    /// @param deflator  Cuenta de descuento D.
    /// @return          Un estadístico por día.
    std::vector<DeflatedStat> deflatedValueStats(const NettingSetSpec& set, const std::vector<int>& days,
                                                 Deflator deflator) const;

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

private:
    ExposureMarket market_;
    ExposureModel model_;
    SimConfig config_;
};

/// @brief Resultado de XVA: CVA, DVA y FVA con sus errores estándar.
struct XvaResult {
    double cva;
    double cvaStdErr;
    double dva;
    double dvaStdErr;
    double fva;
    double total;   ///< cva − dva + fva.
};

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

/// @brief Calcula CVA, DVA y FVA a partir del perfil descontado.
/// CVA = LGD_c Σ_{i>=1} epeDisc_i [S_c(t_{i−1}) − S_c(t_i)]; DVA análogo con eneDisc y la curva propia;
/// FVA = s_f Σ (epeDisc − eneDisc)_i S_c(t_i) S_o(t_i) (t_i − t_{i−1}).
/// Los errores estándar usan la varianza por trayectoria de la suma (pathDiscPos/pathDiscNeg).
/// @param profile             Perfil del motor.
/// @param counterparty        Curva de supervivencia de la contraparte.
/// @param counterpartyLgd     LGD de la contraparte (1 − R).
/// @param own                 Curva de supervivencia propia.
/// @param ownLgd              LGD propia.
/// @param fundingSpread       Diferencial de financiación, decimal.
/// @return                    CVA, DVA, FVA y total.
XvaResult computeXva(const ExposureProfile& profile, const ICreditCurve& counterparty, double counterpartyLgd,
                     const ICreditCurve& own, double ownLgd, double fundingSpread);

} // namespace qf::xva
