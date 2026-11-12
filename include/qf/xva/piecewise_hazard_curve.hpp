#pragma once
#include <vector>
#include <qf/xva/credit_curve.hpp>
#include <qf/termstructure/yieldcurve.hpp>

namespace qf::xva {

/// @brief Curva de intensidad constante por tramos (curva de crédito con bootstrap de CDS).
/// hazards[i] rige en (times[i-1], times[i]] con times[-1] = 0; extrapolación plana del último tramo.
class PiecewiseHazardCurve : public ICreditCurve {
public:
    /// @param times    Vértices de los tramos en años, estrictamente crecientes y > 0.
    /// @param hazards  Intensidades de cada tramo en decimal, >= 0; mismo tamaño que `times`, >= 1.
    /// @throws std::invalid_argument si no se cumplen las condiciones anteriores.
    PiecewiseHazardCurve(std::vector<double> times, std::vector<double> hazards);

    /// @param t  Tiempo en años.
    /// @return   exp(-∫_0^t h(s) ds); 1 para t <= 0.
    double survivalProbability(double t) const override;

    /// @param t  Tiempo en años.
    /// @return   Intensidad instantánea vigente en t (tramo que contiene t; plana tras el último vértice).
    double hazardRate(double t) const;

    /// @return   Vértices de los tramos en años.
    const std::vector<double>& times() const;

    /// @return   Intensidades de cada tramo en decimal.
    const std::vector<double>& hazards() const;

private:
    std::vector<double> times_;
    std::vector<double> hazards_;
};

/// @brief Cotización de un CDS par.
struct CdsQuote {
    double tenorYears; ///< Vencimiento del CDS en años.
    double spread;     ///< Spread anual en decimal (0.0080 = 80 pb).
};

/// @brief Valor del CDS para el comprador de protección: pata de protección − pata de prima.
/// Convención: pagos de prima en d_k = round(k·365/4), k = 1..4·T; devengo (d_k − d_{k−1})/360; tiempos d/365.
/// @param quote     Cotización del CDS.
/// @param recovery  Recuperación en [0,1).
/// @param curve     Curva de supervivencia de la contraparte.
/// @param discount  Curva de descuento.
/// @param notional  Nocional (escala el valor).
/// @return          Valor por `notional`.
double cdsValue(const CdsQuote& quote, double recovery, const ICreditCurve& curve,
                const termstructure::YieldCurve& discount, double notional = 1.0);

/// @brief Bootstrap tramo a tramo de intensidades: cada CDS de `quotes` vale 0 con la curva resultante.
/// Los tramos de intensidad terminan en los tenores de las cotizaciones.
/// @param quotes    Cotizaciones con tenores crecientes y únicos; spread > 0.
/// @param recovery  Recuperación en [0,1).
/// @param discount  Curva de descuento.
/// @return          Curva de intensidad por tramos.
/// @throws std::invalid_argument con mensaje claro si quotes está vacío, los tenores no son crecientes,
///         un spread es <= 0 o recovery ∉ [0,1). Si un tramo exige intensidad negativa:
///         "bootstrapCdsCurve: quote at <T>y implies a negative hazard rate".
PiecewiseHazardCurve bootstrapCdsCurve(const std::vector<CdsQuote>& quotes, double recovery,
                                       const termstructure::YieldCurve& discount);

} // namespace qf::xva
