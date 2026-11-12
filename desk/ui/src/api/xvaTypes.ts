// Tipos del corte 9 (XVA y crédito sintético): transcripción 1:1 del contrato HTTP del backend.
import type { Warning } from './types';

// --- Parámetros del XVA ---

export interface XvaParams {
  funding_spread: number;
  n_paths: number;
  seed: number;
  pfe_quantile: number;
}

export interface XvaParamsResponse extends XvaParams {
  assumed: { funding_spread: boolean };
  defaults: XvaParams;
}

export interface XvaParamsBody {
  funding_spread?: number;
  n_paths?: number;
  seed?: number;
  pfe_quantile?: number;
}

// --- Fuentes y crédito ---

export interface XvaSource {
  kind: string;
  label: string;
}

export interface XvaCredit {
  /** `curve`: curva de `credit_curves`; `flat`: respaldo `counterparty_credit`; `assumed`: 1 %/40 %. */
  kind: 'curve' | 'flat' | 'assumed';
  recovery: number;
  source: XvaSource | null;
  assumed: boolean;
  note: string | null;
}

export interface XvaOwnCredit {
  entity: string;
  recovery: number;
  kind: 'curve';
  source: XvaSource | null;
  assumed: boolean;
  note: string | null;
}

// --- Operaciones y perfiles ---

export interface XvaTradeRef {
  id: number;
  product: string;
  label: string;
  pv_mxn: number;
}

export interface XvaExcluded {
  id: number;
  product: string;
  reason: string;
}

export interface XvaProfilePoint {
  date: string;
  t: number;
  epe_mxn: number;
  ene_mxn: number;
  pfe_mxn: number;
}

export interface XvaComponents {
  pv_mxn: number;
  cva_mxn: number;
  cva_stderr_mxn: number;
  dva_mxn: number;
  fva_mxn: number;
  total_mxn: number;
  epe_max_mxn: number;
  pfe_max_mxn: number;
}

// --- GET /api/xva ---

export interface XvaCounterparty {
  counterparty: string;
  credit: XvaCredit;
  included: XvaTradeRef[];
  excluded: XvaExcluded[];
  pv_mxn: number;
  cva_mxn: number;
  cva_stderr_mxn: number;
  dva_mxn: number;
  fva_mxn: number;
  total_mxn: number;
  epe_max_mxn: number;
  pfe_max_mxn: number;
  profile: XvaProfilePoint[];
}

export interface XvaModel {
  hw: Record<string, { a: number; sigma: number }>;
  fx_vol: number;
  fx_vol_source: 'surface_atm_1y' | 'factor_daily_vol' | 'default';
  correlations: { mxn_usd: number; mxn_fx: number; usd_fx: number };
}

export interface XvaResponse {
  snapshot: string;
  as_of: string;
  notice: string;
  collateral_note: string;
  params: XvaParams;
  model: XvaModel;
  assumptions: string[];
  own_credit: XvaOwnCredit;
  counterparties: XvaCounterparty[];
  warnings: Warning[];
}

// --- POST /api/xva/incremental ---

export interface XvaIncrementalBody {
  snapshot: string;
  counterparty: string;
  product: string;
  params: Record<string, unknown>;
  trade_date?: string;
  start_date?: string;
  maturity_date?: string;
}

export interface XvaCandidate {
  product: string;
  label: string;
  params: Record<string, unknown>;
  trade_date: string;
  start_date: string;
  maturity_date: string;
  notional: number;
  currency: string;
  notional_mxn: number;
  pv_mxn: number;
}

export interface XvaIncrementalResponse {
  snapshot: string;
  as_of: string;
  counterparty: string;
  notice: string;
  candidate: XvaCandidate;
  before: XvaComponents;
  after: XvaComponents;
  delta: { cva_mxn: number; dva_mxn: number; fva_mxn: number; total_mxn: number };
  delta_bp: { cva: number; dva: number; fva: number; total: number };
  profile: {
    date: string;
    t: number;
    epe_before_mxn: number;
    ene_before_mxn: number;
    epe_after_mxn: number;
    ene_after_mxn: number;
  }[];
  warnings: Warning[];
}

// --- Curvas de crédito ---

export interface CreditCurveQuote {
  tenor_years: number;
  spread: number;
}

export interface CreditCurveHazard {
  from_years: number;
  to_years: number;
  hazard: number;
}

export interface CreditCurveGridPoint {
  year: number;
  survival: number;
  cumulative_pd: number;
  marginal_pd: number;
}

export interface CreditCurveHistoryEntry {
  id: number;
  as_of: string;
  created_at: string;
}

export interface CreditCurve {
  entity: string;
  label: string;
  kind: 'own' | 'counterparty';
  id: number | null;
  as_of: string | null;
  recovery: number | null;
  quotes: CreditCurveQuote[];
  /** Ausentes cuando `error` no es nulo. */
  hazards?: CreditCurveHazard[];
  /** Ausente cuando `error` no es nulo. */
  grid?: CreditCurveGridPoint[];
  history: CreditCurveHistoryEntry[];
  error: string | null;
}

export interface CreditCurvesResponse {
  snapshot: string;
  as_of: string;
  discount_curve: string;
  source: XvaSource;
  curves: CreditCurve[];
}

export interface CreditCurveBody {
  recovery: number;
  quotes: CreditCurveQuote[];
  snapshot?: string;
}

// --- Sensibilidades del XVA por diferenciación adjunta (corte 12) ---

/** Derivadas del CVA, DVA y FVA respecto de un insumo, en MXN y en la unidad que diga `units`; total = cva − dva + fva. */
export interface XvaSensRow {
  cva: number;
  dva: number;
  fva: number;
  total: number;
}

export interface XvaSensPillar extends XvaSensRow {
  label: string;
  days: number;
}

export interface XvaSensCurve {
  /** `TIIE-F`, `SOFR` o `MXN-USD` (esta última solo si el snapshot la trae). */
  curve: string;
  pillars: XvaSensPillar[];
  /** Suma de los pilares: movimiento paralelo de la curva. */
  dv01: XvaSensRow;
}

export interface XvaSensFx extends XvaSensRow {
  label: string;
}

export interface XvaSensVol extends XvaSensRow {
  param: 'fx_vol' | 'sigma_mxn' | 'a_mxn' | 'sigma_usd' | 'a_usd';
  label: string;
}

export interface XvaSensCds extends XvaSensRow {
  tenor: string;
}

export interface XvaSensHazard extends XvaSensRow {
  /** Fin del tramo de intensidad en años; `null` en el tramo único de una curva plana o supuesta. */
  to_years: number | null;
}

export interface XvaSensCredit {
  kind: 'curve' | 'flat' | 'assumed';
  /** Por plazo de CDS; vacío si `kind` no es `curve`. */
  cds: XvaSensCds[];
  hazards: XvaSensHazard[];
}

export interface XvaSensitivitiesResponse {
  snapshot: string;
  as_of: string;
  counterparty: string;
  notice: string;
  method: string;
  cds_jacobian: string;
  params: XvaParams;
  paths: number;
  seed: number;
  /** Segundos de las sensibilidades, de una valuación del XVA con la misma malla y de las 2 × `n_inputs` valuaciones por choques. */
  elapsed_s: number;
  valuation_elapsed_s: number;
  n_inputs: number;
  bump_cost_estimate_s: number;
  /** Idéntico al de `GET /api/xva` para esta contraparte. */
  xva: Pick<XvaComponents, 'cva_mxn' | 'dva_mxn' | 'fva_mxn' | 'total_mxn'>;
  units: { curves: string; fx: string; vols: string; cds: string; funding: string };
  curves: XvaSensCurve[];
  fx: XvaSensFx;
  vols: XvaSensVol[];
  credit: { counterparty: XvaSensCredit; own: XvaSensCredit };
  funding: XvaSensRow;
  /** Texto cuando la contraparte no tiene operaciones cubiertas (listas vacías y cifras en cero); si no, `null`. */
  empty_reason: string | null;
  assumptions: string[];
  warnings: Warning[];
}
