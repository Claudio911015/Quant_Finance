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

export type TradeStatus = 'no_pactada' | 'viva' | 'vencida' | 'terminada' | 'ejercida';

export type EventType =
  | 'execution'
  | 'reset'
  | 'transfer'
  | 'quantity_change'
  | 'terms_change'
  | 'exercise'
  | 'termination';

export interface TradeEvent {
  id: number;
  trade_id: number;
  type: EventType;
  event_date: string;
  data: Record<string, unknown>;
  prev_event_id: number | null;
  created_at: string;
}

export interface Trade {
  id: number;
  product: ProductId;
  counterparty: string;
  trade_date: string;
  start_date: string;
  maturity_date: string;
  params: Record<string, unknown>;
  notional: number;
  currency: string;
  maturity: string;
  created_at: string;
}

export type TradeDetail = Trade & { events: TradeEvent[] };

export interface TradeState {
  id: number;
  date: string;
  status: TradeStatus;
  notional: number;
  terms: Record<string, unknown>;
}

export type WarningCode =
  | 'missing_fixing'
  | 'fx_fallback'
  | 'no_settlement'
  | 'expired_unexercised';

export interface Warning {
  code: WarningCode;
  index: string | null;
  dates: string[];
  message: string;
}

export type FlowKind = 'coupon' | 'settlement' | 'transfer';

export interface Flow {
  date: string;
  kind: FlowKind;
  status: 'settled' | 'projected';
  amount: number;
  currency: string;
  df: number | null;
  pv: number | null;
}

export interface FlowsResponse {
  id: number;
  snapshot: string;
  as_of: string;
  flows: Flow[];
  warnings: Warning[];
}

export interface ValuationRow {
  id: number;
  product: ProductId;
  counterparty: string;
  trade_date: string;
  start_date: string;
  maturity_date: string;
  status: TradeStatus;
  notional: number;
  currency: string;
  maturity: string;
  pv: number | null;
  pv_mxn: number | null;
  error: string | null;
  warnings: Warning[];
}

export interface ValuationResponse {
  snapshot: string;
  as_of: string;
  total_mxn: number;
  rows: ValuationRow[];
}

export type FixingIndex = 'TIIE-F' | 'SOFR' | 'USDMXN';

export interface Fixing {
  index: FixingIndex;
  date: string;
  value: number;
}

export interface AddFixingResponse {
  fixing: Fixing;
  created: boolean;
}

export interface FixingsCsvResult {
  inserted: number;
  unchanged: number;
}

export interface PnlRow {
  id: number;
  product: ProductId;
  counterparty: string;
  status_from: TradeStatus;
  status_to: TradeStatus;
  pv_from: number | null;
  pv_to: number | null;
  settled: number | null;
  pnl: number | null;
  error: string | null;
  warnings: Warning[];
}

export interface PnlResponse {
  from: { snapshot: string; as_of: string };
  to: { snapshot: string; as_of: string };
  total_mxn: number;
  totals: { pv_from: number; pv_to: number; settled: number; pnl: number };
  rows: PnlRow[];
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
