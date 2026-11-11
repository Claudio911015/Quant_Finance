export type ProductId =
  | 'irs'
  | 'fx_forward'
  | 'fx_option'
  | 'cap_floor'
  | 'swaption'
  | 'bond'
  | 'equity_option';

export type SourceKind = 'live' | 'proxy' | 'synthetic' | 'mixed';
export type DataQuality = 'synthetic' | 'live' | 'mixed';
export type SourceKey =
  | 'curve:TIIE-F'
  | 'curve:SOFR'
  | 'spot'
  | 'surface'
  | 'hw'
  | 'factor_vols'
  | 'factor_corr';

export interface Source {
  kind: SourceKind;
  label: string;
  as_of: string | null;
}

export interface SnapshotSummary {
  id: string;
  label: string;
  synthetic: boolean;
  as_of: string;
  data_quality: DataQuality;
  sources: Record<SourceKey, Source>;
}

export interface Quote {
  id: string;
  curve: string;
  label: string;
  type: string;
  days: number;
  rate: number;
}

export interface CurvePoint {
  label: string;
  days: number;
  t: number;
  zero: number;
  df: number;
  forward: number;
}

export interface Snapshot extends SnapshotSummary {
  read_only: boolean;
  quotes: Quote[];
  curves: Record<string, { currency: string; period_days: number; points: CurvePoint[] }>;
  fx: { pair: string; spot: number };
  vol_surface: { pair: string; expiry_days: number[]; strikes: number[]; vols: number[][] };
  hw: Record<string, { a: number; sigma: number }>;
  factors: { names: string[]; units: string[]; daily_vols: number[]; correlations: number[][] };
}

export interface RefreshResponse {
  ran_at: string;
  mdf_exit_code: number;
  treasury_latest: string;
  sofr_latest: string;
  fred_latest: string;
  snapshot: Snapshot;
}

export interface Cashflow {
  date: string;
  days: number;
  amount: number;
  df: number;
  pv: number;
}

export interface PriceResponse {
  product: ProductId;
  currency: string;
  pv: number;
  pv_mxn: number;
  risk: Record<string, number>;
  cashflows: Cashflow[] | null;
  details: Record<string, unknown>;
}

export interface Trade {
  id: number;
  product: ProductId;
  counterparty: string;
  params: Record<string, unknown>;
  notional: number;
  currency: string;
  maturity: string;
  created_at: string;
}

export interface ValuationRow {
  id: number;
  product: ProductId;
  counterparty: string;
  notional: number;
  currency: string;
  maturity: string;
  pv: number | null;
  pv_mxn: number | null;
  error: string | null;
}

export interface ValuationResponse {
  snapshot: string;
  as_of: string;
  total_mxn: number;
  rows: ValuationRow[];
}

export interface TradeError {
  id: number;
  error: string;
}

export interface Dv01Response {
  snapshot: string;
  total_mxn: number;
  parallel_mxn: number;
  curves: Record<
    string,
    { parallel_mxn: number; points: { label: string; days: number; dv01_mxn: number }[] }
  >;
  errors: TradeError[];
}

export type ScenarioSpec =
  | { name: string; type: 'parallel' | 'steepener'; curve: 'TIIE-F' | 'SOFR'; bp: number }
  | { name: string; type: 'fx_spot'; pct: number };

export interface ScenariosResponse {
  snapshot: string;
  scenarios: {
    name: string;
    total_mxn: number;
    trades: { id: number; pnl_mxn: number | null; error: string | null }[];
  }[];
}

export interface VarResponse {
  snapshot: string;
  var_mxn: number;
  horizon_days: number;
  confidence: number;
  factors: {
    factor: string;
    unit: string;
    exposure_mxn: number;
    daily_vol: number;
    var_mxn: number;
  }[];
  errors: TradeError[];
}
