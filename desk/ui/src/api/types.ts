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

// --- Contabilidad de coberturas (corte 4) ---

export type HedgeType = 'cash_flow' | 'fair_value';
export type ItemKind = 'floating_loan' | 'fixed_loan' | 'forecast_fx';
export type HedgeStatus = 'activa' | 'desdesignada';
/** Causa de una desdesignación (IFRS 9 6.5.6: no hay desdesignación voluntaria sin causa). */
export type DedesignationCause = 'instrument_ended' | 'criteria_not_met' | 'risk_objective_changed';
/** Causa de la liberación de la reserva congelada. */
export type ReleaseCause = 'flow_occurred' | 'flow_no_longer_expected';

export interface FloatingLoanTerms {
  index: 'TIIE-F' | 'SOFR';
  notional: number;
  start_date: string;
  maturity_date: string;
  side: 'pays_floating' | 'receives_floating';
}

export interface FixedLoanTerms {
  index: 'TIIE-F' | 'SOFR';
  notional: number;
  start_date: string;
  maturity_date: string;
  side: 'pays_fixed' | 'receives_fixed';
}

export interface ForecastFxTerms {
  amount_usd: number;
  date: string;
  side: 'buy_usd' | 'sell_usd';
}

export type ItemTerms = FloatingLoanTerms | FixedLoanTerms | ForecastFxTerms;

export interface HedgeDocumentation {
  risk_management_objective: string;
  hedged_risk: string;
  effectiveness_method: string;
  ineffectiveness_sources: string;
}

export interface HedgeEvent {
  id: number;
  relationship_id: number;
  type: 'designation' | 'period_close' | 'dedesignation' | 'reserve_release';
  event_date: string;
  data: Record<string, unknown>;
  created_at: string;
}

/** Aviso que el alta devuelve y guarda en el evento de designación; `message` ya viene en español. */
export interface HedgeWarning {
  code: 'no_economic_relationship' | 'instrument_off_market' | 'forecast_date_weekend';
  message: string;
}

/** `data` de un evento `reserve_release`. */
export interface ReserveReleaseData {
  snapshot: string;
  cause: ReleaseCause;
  amount: number;
  reserve_before: number;
  reserve_after: number;
  entries: JournalEntry[];
}

export interface JournalEntry {
  account: string;
  debit: number;
  credit: number;
  memo: string;
}

export interface HedgePeriodFlow {
  date: string;
  kind: FlowKind;
  amount: number;
  currency: string;
  amount_mxn: number;
}

export interface HedgePeriod {
  id: number;
  snapshot: string;
  as_of: string;
  created_at: string;
  prev_snapshot: string;
  prev_as_of: string;
  data_quality: DataQuality;
  trade_status: TradeStatus;
  hedge_type: HedgeType;
  fraction: number;
  pv_inst: number;
  pv_hypo: number;
  inst_cum: number;
  hypo_cum: number;
  d_inst_cum: number;
  d_hypo_cum: number;
  inst_total: number;
  hypo_total: number;
  effective_cum: number;
  settled_period: number;
  hypo_settled_period: number;
  settled_flows: HedgePeriodFlow[];
  oci: number;
  d_oci: number;
  ineffectiveness: number;
  recycled: number;
  item_adjustment: number;
  fv_result: number;
  instrument_pnl: number;
  identity_residual: number;
  entries: JournalEntry[];
  warnings: Warning[];
}

export interface HedgeSummary {
  id: number;
  trade_id: number;
  product: ProductId;
  counterparty: string;
  hedge_type: HedgeType;
  item_kind: ItemKind;
  fraction: number;
  hedge_ratio: number;
  designation_date: string;
  status: HedgeStatus;
  oci_balance: number;
  last_close: string | null;
  periods_count: number;
}

/** `cause` y `snapshot` son `null` solo en desdesignaciones anteriores a la causa obligatoria. */
export interface HedgeDedesignation {
  date: string;
  reason: string;
  cause: DedesignationCause | null;
  snapshot: string | null;
  frozen_oci: number;
}

export interface HedgeDetail {
  id: number;
  trade_id: number;
  product: ProductId;
  counterparty: string;
  fraction: number;
  hedge_type: HedgeType;
  item_kind: ItemKind;
  item_terms: ItemTerms;
  hedge_ratio: number;
  designation_date: string;
  designation_snapshot: string;
  documentation: HedgeDocumentation;
  hypothetical: {
    product: ProductId;
    trade_date: string;
    start_date: string;
    maturity_date: string;
    params: Record<string, unknown>;
  };
  designation: {
    snapshot: string;
    as_of: string;
    data_quality: DataQuality;
    pv_inst: number;
    pv_hypo: number;
  };
  status: HedgeStatus;
  dedesignation: HedgeDedesignation | null;
  warnings: HedgeWarning[];
  /** Reserva vigente: lo congelado menos lo liberado. */
  oci_balance: number;
  last_close: string | null;
  events: HedgeEvent[];
  periods: HedgePeriod[];
  created_at: string;
}

export interface CriticalTerm {
  term: 'notional' | 'index' | 'currency' | 'start_date' | 'maturity_date' | 'side';
  label: string;
  /** En `side`: `payer`/`receiver` (lado del swap) o `buy`/`sell` (forward). */
  instrument: string | number;
  item: string | number;
  result: 'match' | 'mismatch';
}

export interface ScenarioRatio {
  name: string;
  d_inst: number;
  d_hypo: number;
  ratio: number | null;
}

export interface EffectivenessResponse {
  id: number;
  snapshot: string;
  as_of: string;
  critical_terms: CriticalTerm[];
  scenarios: ScenarioRatio[];
  economic_relationship: boolean;
  in_reference_range: number;
  scenarios_counted: number;
  reference_note: string;
  warnings: Warning[];
}

export interface HedgeReport {
  id: number;
  generated_at: string;
  notice: string;
  relationship: Omit<HedgeDetail, 'events' | 'periods'>;
  documentation: {
    risk_management_objective: string;
    hedged_risk: string;
    hedged_item: { item_kind: ItemKind; item_terms: ItemTerms };
    hedging_instrument: {
      trade_id: number;
      product: ProductId;
      counterparty: string;
      fraction: number;
      notional: number;
      currency: string;
      start_date: string;
      maturity_date: string;
    };
    hedge_ratio: number;
    effectiveness_method: string;
    ineffectiveness_sources: string;
  };
  /** Respuesta de la prueba prospectiva, o `{error}` si la operación ya no está viva en ese snapshot. */
  prospective: EffectivenessResponse | { error: string };
  periods: {
    id: number;
    snapshot: string;
    as_of: string;
    data_quality: DataQuality;
    inst_cum: number;
    hypo_cum: number;
    oci: number;
    d_oci: number;
    ineffectiveness: number;
    recycled: number;
    item_adjustment: number;
    fv_result: number;
    settled_period: number;
  }[];
  entries_by_period: { period_id: number; as_of: string; entries: JournalEntry[] }[];
  entries_total: { account: string; debit: number; credit: number }[];
  fair_value_hierarchy: {
    level: number;
    basis: string;
    snapshots: {
      role: 'designation' | 'period';
      snapshot: string;
      as_of: string;
      data_quality: DataQuality;
    }[];
  };
  reserve_releases: {
    id: number;
    snapshot: string;
    as_of: string;
    cause: ReleaseCause;
    amount: number;
    reserve_after: number;
    entries: JournalEntry[];
  }[];
  /** `balance` es la reserva vigente; `released` la suma de lo liberado. */
  reserve: { balance: number; frozen: boolean; note: string | null; released: number };
}

export interface CreateHedgeBody {
  trade_id: number;
  snapshot: string;
  designation_date?: string;
  hedge_type: HedgeType;
  item_kind: ItemKind;
  item_terms: ItemTerms;
  fraction: number;
  hedge_ratio?: number;
  documentation: HedgeDocumentation;
}
