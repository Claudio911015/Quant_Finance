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
  fx_vol_source: 'surface_atm_1y' | 'factor_daily_vol';
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
