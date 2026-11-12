// Datos simulados del corte 9 (XVA y crédito sintético), para pruebas y para la pantalla contra simulados.
// Cifras inventadas; no son mercado. Respetan: total_mxn = cva_mxn − dva_mxn + fva_mxn y pv_mxn = Σ included.
import type { Warning } from '../../api/types';
import type {
  CreditCurve,
  CreditCurveGridPoint,
  CreditCurveHazard,
  CreditCurveQuote,
  CreditCurvesResponse,
  XvaComponents,
  XvaCounterparty,
  XvaIncrementalResponse,
  XvaParams,
  XvaParamsResponse,
  XvaResponse,
  XvaSensCurve,
  XvaSensRow,
  XvaSensitivitiesResponse,
} from '../../api/xvaTypes';

const NO_WARNINGS: Warning[] = [];
const SOURCE = { kind: 'synthetic', label: 'Sintética (inventada para demostración)' };
const SNAPSHOT = 'MX-DEMO';
const AS_OF = '2026-11-10';

const PARAMS: XvaParams = { funding_spread: 0.005, n_paths: 2000, seed: 42, pfe_quantile: 0.95 };

// Intensidades por tramo aproximadas desde los spreads: h_i ≈ (s_i·T_i − s_{i−1}·T_{i−1}) / (T_i − T_{i−1}) / (1 − R).
function hazardsFromQuotes(quotes: CreditCurveQuote[], recovery: number): CreditCurveHazard[] {
  const out: CreditCurveHazard[] = [];
  let fromYears = 0;
  let prevCum = 0;
  for (const q of quotes) {
    const cum = q.spread * q.tenor_years;
    const hazard = (cum - prevCum) / (q.tenor_years - fromYears) / (1 - recovery);
    out.push({ from_years: fromYears, to_years: q.tenor_years, hazard: round(hazard, 4) });
    fromYears = q.tenor_years;
    prevCum = cum;
  }
  return out;
}

// Malla anual 1..10 con extrapolación plana de la última intensidad.
function gridFromHazards(hazards: CreditCurveHazard[]): CreditCurveGridPoint[] {
  const hazardAt = (t: number): number => {
    const seg = hazards.find((h) => t <= h.to_years) ?? hazards[hazards.length - 1];
    return seg.hazard;
  };
  const grid: CreditCurveGridPoint[] = [];
  let cumH = 0;
  let prevS = 1;
  for (let year = 1; year <= 10; year++) {
    // Integral de la intensidad en (year−1, year] con la intensidad del tramo que la contiene (aprox. por tramo).
    cumH += hazardAt(year - 0.5);
    const survival = Math.exp(-cumH);
    grid.push({
      year,
      survival: round(survival, 3),
      cumulative_pd: round(1 - survival, 3),
      marginal_pd: round(prevS - survival, 3),
    });
    prevS = survival;
  }
  return grid;
}

function curve(
  entity: string,
  label: string,
  kind: 'own' | 'counterparty',
  id: number,
  quotes: CreditCurveQuote[],
): CreditCurve {
  const recovery = 0.4;
  const hazards = hazardsFromQuotes(quotes, recovery);
  return {
    entity,
    label,
    kind,
    id,
    as_of: AS_OF,
    recovery,
    quotes,
    hazards,
    grid: gridFromHazards(hazards),
    history: [{ id, as_of: AS_OF, created_at: '2026-11-10T09:00:00Z' }],
    error: null,
  };
}

const Q_ALFA: CreditCurveQuote[] = [
  { tenor_years: 1, spread: 0.006 },
  { tenor_years: 2, spread: 0.007 },
  { tenor_years: 3, spread: 0.008 },
  { tenor_years: 5, spread: 0.0095 },
  { tenor_years: 7, spread: 0.0105 },
  { tenor_years: 10, spread: 0.012 },
];
const Q_BETA: CreditCurveQuote[] = [
  { tenor_years: 1, spread: 0.015 },
  { tenor_years: 2, spread: 0.018 },
  { tenor_years: 3, spread: 0.021 },
  { tenor_years: 5, spread: 0.025 },
  { tenor_years: 7, spread: 0.0275 },
  { tenor_years: 10, spread: 0.03 },
];
const Q_GAMMA: CreditCurveQuote[] = [
  { tenor_years: 1, spread: 0.0095 },
  { tenor_years: 2, spread: 0.0097 },
  { tenor_years: 3, spread: 0.0098 },
  { tenor_years: 5, spread: 0.01 },
  { tenor_years: 7, spread: 0.01 },
  { tenor_years: 10, spread: 0.0101 },
];
const Q_OWN: CreditCurveQuote[] = [
  { tenor_years: 1, spread: 0.007 },
  { tenor_years: 2, spread: 0.008 },
  { tenor_years: 3, spread: 0.009 },
  { tenor_years: 5, spread: 0.0105 },
  { tenor_years: 7, spread: 0.0115 },
  { tenor_years: 10, spread: 0.0125 },
];

const PROFILE_DATES = [
  { date: '2026-11-10', t: 0 },
  { date: '2027-05-10', t: 0.4959 },
  { date: '2027-11-10', t: 1.0 },
  { date: '2028-11-10', t: 2.0027 },
];

function profile(epe: number[], ene: number[], pfe: number[]) {
  return PROFILE_DATES.map((d, i) => ({ ...d, epe_mxn: epe[i], ene_mxn: ene[i], pfe_mxn: pfe[i] }));
}

const ALFA: XvaCounterparty = {
  counterparty: 'Banco Alfa (sintético)',
  credit: { kind: 'curve', recovery: 0.4, source: SOURCE, assumed: false, note: null },
  included: [
    { id: 1, product: 'irs', label: 'Swap de tasas (IRS)', pv_mxn: -940000 },
    { id: 2, product: 'irs', label: 'Swap de tasas (IRS)', pv_mxn: 185000 },
  ],
  excluded: [
    {
      id: 4,
      product: 'fx_forward',
      reason: 'El XVA solo cubre swaps de tasa y cross currency swaps: Forward FX se excluye',
    },
  ],
  pv_mxn: -755000,
  cva_mxn: 120000,
  cva_stderr_mxn: 4000,
  dva_mxn: 30000,
  fva_mxn: 5000,
  total_mxn: 95000,
  epe_max_mxn: 2400000,
  pfe_max_mxn: 3100000,
  profile: profile([0, 1800000, 2400000, 1900000], [0, 900000, 1100000, 1400000], [0, 2300000, 3100000, 2700000]),
};

const BETA: XvaCounterparty = {
  counterparty: 'Banco Beta (sintético)',
  credit: { kind: 'curve', recovery: 0.4, source: SOURCE, assumed: false, note: null },
  included: [
    { id: 4, product: 'irs', label: 'Swap de tasas (IRS)', pv_mxn: 1250000 },
    { id: 5, product: 'xccy_swap', label: 'Cross currency swap', pv_mxn: -330000 },
    { id: 6, product: 'irs', label: 'Swap de tasas (IRS)', pv_mxn: 80000 },
  ],
  excluded: [],
  pv_mxn: 1000000,
  cva_mxn: 310000,
  cva_stderr_mxn: 9000,
  dva_mxn: 60000,
  fva_mxn: 12000,
  total_mxn: 262000,
  epe_max_mxn: 6800000,
  pfe_max_mxn: 8400000,
  profile: profile([0, 4900000, 6800000, 5600000], [0, 2100000, 2600000, 3300000], [0, 6200000, 8400000, 7300000]),
};

const GAMMA: XvaCounterparty = {
  counterparty: 'Banco Gamma (sintético)',
  credit: { kind: 'curve', recovery: 0.4, source: SOURCE, assumed: false, note: null },
  included: [
    { id: 7, product: 'irs', label: 'Swap de tasas (IRS)', pv_mxn: -210000 },
    { id: 8, product: 'irs', label: 'Swap de tasas (IRS)', pv_mxn: 420000 },
    { id: 9, product: 'xccy_swap', label: 'Cross currency swap', pv_mxn: -55000 },
  ],
  excluded: [],
  pv_mxn: 155000,
  cva_mxn: 45000,
  cva_stderr_mxn: 2500,
  dva_mxn: 20000,
  fva_mxn: 3000,
  total_mxn: 28000,
  epe_max_mxn: 1900000,
  pfe_max_mxn: 2600000,
  profile: profile([0, 1100000, 1900000, 1500000], [0, 700000, 900000, 1000000], [0, 1500000, 2600000, 2100000]),
};

export const XVA_FIXTURE: XvaResponse = {
  snapshot: SNAPSHOT,
  as_of: AS_OF,
  notice: 'XVA informativo: no entra al PV ni a la contabilidad',
  collateral_note: 'Exposición sin colateral ni margen: la moneda de colateral solo cambia la curva de descuento',
  params: PARAMS,
  model: {
    hw: { 'TIIE-F': { a: 0.05, sigma: 0.01 }, SOFR: { a: 0.03, sigma: 0.008 } },
    fx_vol: 0.119,
    fx_vol_source: 'surface_atm_1y',
    correlations: { mxn_usd: 0.35, mxn_fx: 0.3, usd_fx: -0.1 },
  },
  assumptions: [
    'Correlaciones tomadas de los cambios diarios de los factores del snapshot (TIIE-F, SOFR, USDMXN): aproximación de las correlaciones de los brownianos del modelo',
  ],
  own_credit: { entity: 'propia', recovery: 0.4, kind: 'curve', source: SOURCE, assumed: false, note: null },
  counterparties: [ALFA, BETA, GAMMA],
  warnings: NO_WARNINGS,
};

export const XVA_PARAMS_FIXTURE: XvaParamsResponse = {
  ...PARAMS,
  assumed: { funding_spread: true },
  defaults: { funding_spread: 0.005, n_paths: 2000, seed: 42, pfe_quantile: 0.95 },
};

const BEFORE: XvaComponents = {
  pv_mxn: -755000,
  cva_mxn: 120000,
  cva_stderr_mxn: 4000,
  dva_mxn: 30000,
  fva_mxn: 5000,
  total_mxn: 95000,
  epe_max_mxn: 2400000,
  pfe_max_mxn: 3100000,
};

const AFTER: XvaComponents = {
  pv_mxn: -743000,
  cva_mxn: 123500,
  cva_stderr_mxn: 4010,
  dva_mxn: 30100,
  fva_mxn: 5020,
  total_mxn: 98420,
  epe_max_mxn: 2450000,
  pfe_max_mxn: 3160000,
};

export const INCREMENTAL_FIXTURE: XvaIncrementalResponse = {
  snapshot: SNAPSHOT,
  as_of: AS_OF,
  counterparty: ALFA.counterparty,
  notice: 'XVA informativo: no entra al PV ni a la contabilidad',
  candidate: {
    product: 'irs',
    label: 'Swap de tasas (IRS)',
    params: { notional: 100000000, fixed_rate: 0.071, payer: false, periods: 36 },
    trade_date: AS_OF,
    start_date: AS_OF,
    maturity_date: '2029-11-10',
    notional: 100000000,
    currency: 'MXN',
    notional_mxn: 100000000,
    pv_mxn: 12000,
  },
  before: BEFORE,
  after: AFTER,
  delta: { cva_mxn: 3500, dva_mxn: 100, fva_mxn: 20, total_mxn: 3420 },
  delta_bp: { cva: 0.35, dva: 0.01, fva: 0.002, total: 0.342 },
  profile: [
    { date: '2026-11-10', t: 0, epe_before_mxn: 0, ene_before_mxn: 0, epe_after_mxn: 0, ene_after_mxn: 0 },
    { date: '2027-05-10', t: 0.4959, epe_before_mxn: 1800000, ene_before_mxn: 900000, epe_after_mxn: 1820000, ene_after_mxn: 890000 },
    { date: '2027-11-10', t: 1.0, epe_before_mxn: 2400000, ene_before_mxn: 1100000, epe_after_mxn: 2450000, ene_after_mxn: 1080000 },
    { date: '2028-11-10', t: 2.0027, epe_before_mxn: 1900000, ene_before_mxn: 1400000, epe_after_mxn: 1930000, ene_after_mxn: 1380000 },
  ],
  warnings: NO_WARNINGS,
};

const BETA_CURVE_ERROR: CreditCurve = {
  entity: 'Banco Beta (sintético)',
  label: 'Banco Beta (sintético)',
  kind: 'counterparty',
  id: 2,
  as_of: AS_OF,
  recovery: 0.4,
  quotes: Q_BETA,
  history: [{ id: 2, as_of: AS_OF, created_at: '2026-11-10T09:00:00Z' }],
  error: 'No se pudo ajustar la curva con el snapshot MX-DEMO',
};

export const CREDIT_CURVES_FIXTURE: CreditCurvesResponse = {
  snapshot: SNAPSHOT,
  as_of: AS_OF,
  discount_curve: 'TIIE-F',
  source: SOURCE,
  curves: [
    curve('propia', 'Propia (el desk)', 'own', 4, Q_OWN),
    curve('Banco Alfa (sintético)', 'Banco Alfa (sintético)', 'counterparty', 1, Q_ALFA),
    BETA_CURVE_ERROR,
    curve('Banco Gamma (sintético)', 'Banco Gamma (sintético)', 'counterparty', 3, Q_GAMMA),
  ],
};

// --- Sensibilidades por AAD (corte 12): cifras inventadas con la forma del contrato de GET /api/xva/sensitivities. ---

const sensRow = (cva: number, dva: number, fva: number): XvaSensRow => ({
  cva,
  dva,
  fva,
  total: round(cva - dva + fva, 2),
});

const sumRows = (rows: XvaSensRow[]): XvaSensRow =>
  sensRow(
    round(rows.reduce((a, r) => a + r.cva, 0), 2),
    round(rows.reduce((a, r) => a + r.dva, 0), 2),
    round(rows.reduce((a, r) => a + r.fva, 0), 2),
  );

/** Curva con pilares `[etiqueta, días, cva, dva, fva]` y su DV01 como suma de los pilares. */
function sensCurve(name: string, pillars: [string, number, number, number, number][]): XvaSensCurve {
  const rows = pillars.map(([label, days, cva, dva, fva]) => ({ label, days, ...sensRow(cva, dva, fva) }));
  return { curve: name, pillars: rows, dv01: sumRows(rows) };
}

const SENS_CDS_TENORS = ['1Y', '2Y', '3Y', '5Y', '7Y', '10Y'];
const SENS_CDS_YEARS = [1, 2, 3, 5, 7, 10];

export const XVA_SENSITIVITIES_FIXTURE: XvaSensitivitiesResponse = {
  snapshot: SNAPSHOT,
  as_of: AS_OF,
  counterparty: 'Banco Alfa (sintético)',
  notice: 'XVA informativo: no entra al PV ni a la contabilidad',
  method: 'Diferenciación adjunta (XAD 2.2.0), cinta por trayectoria, derivadas trayectoria a trayectoria',
  cds_jacobian: 'Reprecio del bootstrap de CDS (diferencia central de 0.01 pb)',
  params: PARAMS,
  paths: 2000,
  seed: 42,
  elapsed_s: 3.1,
  valuation_elapsed_s: 0.42,
  n_inputs: 48,
  bump_cost_estimate_s: 40.3,
  xva: { cva_mxn: 31000, dva_mxn: 4000, fva_mxn: 1500, total_mxn: 28500 },
  units: {
    curves: 'MXN por pb',
    fx: 'MXN por 1 % del spot',
    vols: 'MXN por punto (vol USDMXN), por pb de vol normal (σ Hull-White), por 0.01 (a)',
    cds: 'MXN por pb',
    funding: 'MXN por pb',
  },
  curves: [
    sensCurve('TIIE-F', [
      ['1D', 1, 0.4, 0.1, 0],
      ['1x28', 28, 1.2, 0.3, 0.1],
      ['3x28', 84, 3.5, 0.9, 0.2],
      ['6x28', 168, 7.8, 1.9, 0.5],
      ['13x28', 364, 14.6, 3.2, 1.1],
      ['26x28', 728, 22.4, 4.8, 1.9],
      ['39x28', 1092, -9.7, -2.1, 0.8],
      ['65x28', 1820, -41.3, -8.6, -2.4],
      ['91x28', 2548, -12.5, -2.7, -0.9],
      ['130x28', 3640, -3.1, -0.6, -0.2],
    ]),
    sensCurve('SOFR', [
      ['1D', 1, -0.2, -0.1, 0],
      ['1M', 30, -0.9, -0.2, 0],
      ['3M', 91, -2.6, -0.6, -0.1],
      ['6M', 182, -5.4, -1.2, -0.3],
      ['1Y', 365, -9.8, -2.2, -0.6],
      ['2Y', 730, -14.1, -3.1, -1],
      ['3Y', 1095, 5.2, 1.1, 0.4],
      ['5Y', 1825, 18.7, 3.9, 1.3],
      ['7Y', 2555, 6.3, 1.4, 0.5],
      ['10Y', 3650, 1.8, 0.4, 0.1],
    ]),
    sensCurve('MXN-USD', [
      ['1M', 28, 0.6, 0.1, 0],
      ['3M', 84, 1.9, 0.4, 0.1],
      ['6M', 168, 4.1, 0.9, 0.2],
      ['1Y', 364, 8.3, 1.8, 0.5],
      ['2Y', 728, 11.2, 2.4, 0.7],
      ['3Y', 1092, 6.5, 1.4, 0.4],
      ['5Y', 1820, -4.8, -1, -0.3],
      ['7Y', 2548, -2.2, -0.5, -0.1],
      ['10Y', 3640, -0.7, -0.2, 0],
    ]),
  ],
  fx: { label: 'USDMXN spot', ...sensRow(5200, 900, 310) },
  vols: [
    { param: 'fx_vol', label: 'Volatilidad USDMXN', ...sensRow(820, 150, 40) },
    { param: 'sigma_mxn', label: 'σ Hull-White TIIE-F', ...sensRow(210, 45, 12) },
    { param: 'a_mxn', label: 'a Hull-White TIIE-F', ...sensRow(-95, -20, -6) },
    { param: 'sigma_usd', label: 'σ Hull-White SOFR', ...sensRow(160, 33, 9) },
    { param: 'a_usd', label: 'a Hull-White SOFR', ...sensRow(-70, -15, -4) },
  ],
  credit: {
    counterparty: {
      kind: 'curve',
      cds: SENS_CDS_TENORS.map((tenor, i) => ({ tenor, ...sensRow(round(180 - 25 * i, 2), 0, 0) })),
      hazards: SENS_CDS_YEARS.map((to_years, i) => ({ to_years, ...sensRow(round(95 - 12 * i, 2), 0, round(3 - 0.4 * i, 2)) })),
    },
    own: { kind: 'assumed', cds: [], hazards: [{ to_years: null, ...sensRow(0, -38, -11) }] },
  },
  funding: sensRow(0, 0, 214),
  empty_reason: null,
  assumptions: [
    'Correlaciones tomadas de los cambios diarios de los factores del snapshot (TIIE-F, SOFR, USDMXN): aproximación de las correlaciones de los brownianos del modelo',
    'Derivadas parciales: al mover un pilar no se recalibran la curva MXN-USD ni las curvas de crédito (el bootstrap de CDS descuenta con TIIE-F)',
  ],
  warnings: NO_WARNINGS,
};

function round(x: number, digits: number): number {
  const f = 10 ** digits;
  return Math.round(x * f) / f;
}
