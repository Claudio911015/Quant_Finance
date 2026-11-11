// Tipos del corte 6 (riesgo avanzado): transcripción del contrato HTTP del backend.
import type { ScenarioSpec, ScenariosResponse, TradeError, Warning } from './types';

// --- P&L explicado ---

/** `carry`, `curve:<curva>`, `fx`, `vol`, `new_trades`, `events` y `residual`. */
export type ExplainStepKey =
  | 'carry'
  | `curve:${string}`
  | 'fx'
  | 'vol'
  | 'new_trades'
  | 'events'
  | 'residual';

export interface ExplainStep {
  key: ExplainStepKey;
  label: string;
}

export interface ExplainRow {
  id: number;
  product: string;
  counterparty: string;
  /** `null` (y `components` también) si la operación no se pudo valuar. */
  pnl: number | null;
  components: Record<ExplainStepKey, number> | null;
  error: string | null;
  /** Falla de la cascada con `pnl` válido: todo el P&L va a `residual`. */
  explain_error: string | null;
  warnings: Warning[];
}

export interface ExplainResponse {
  from: { snapshot: string; as_of: string };
  to: { snapshot: string; as_of: string };
  steps: ExplainStep[];
  totals: { pnl: number; components: Record<ExplainStepKey, number> };
  rows: ExplainRow[];
}

// --- VaR histórico y historia de factores ---

export type VarMethod = 'parametric' | 'historical';
export type HistorySource = 'synthetic' | 'observed';

export interface HistVarBody {
  horizon_days: number;
  confidence: number;
  window_days?: number;
  history_source?: HistorySource;
}

export interface HistVarResponse {
  snapshot: string;
  method: 'historical';
  var_mxn: number;
  es_mxn: number;
  horizon_days: number;
  confidence: number;
  window_days: number;
  /** `pnl_mxn` sin escalar al horizonte. */
  worst_day: { date: string; pnl_mxn: number };
  history: {
    source: HistorySource;
    label: string;
    from: string;
    to: string;
    observations: number;
    by_source: Record<string, number>;
  };
  factors: { factor: string; unit: string; exposure_mxn: number }[];
  errors: TradeError[];
}

export interface FactorHistorySummary {
  factors: {
    factor: string;
    unit: string;
    sources: { source: string; label: string; count: number; first: string; last: string }[];
  }[];
}

export interface FactorHistoryImport {
  inserted: number;
  unchanged: number;
}

export interface FactorHistoryDerive extends FactorHistoryImport {
  source: string;
  skipped_gaps: number;
}

// --- Límites ---

export type LimitScope = 'counterparty' | 'factor' | 'portfolio';
export type LimitMetric = 'pv_exposure' | 'dv01' | 'fx_delta' | 'var';
export type LimitStatus = 'ok' | 'alerta' | 'exceso';

export interface LimitEvent {
  id: number;
  type: 'create' | 'change' | 'retire';
  amount: number | null;
  reason: string | null;
  created_at: string;
}

export interface Limit {
  id: number;
  scope: LimitScope;
  key: string;
  metric: LimitMetric;
  /** Monto vigente (último `create`/`change`). */
  amount: number;
  status: 'activo' | 'baja';
  created_at: string;
  events: LimitEvent[];
}

export interface CreateLimitBody {
  scope: LimitScope;
  /** Opcional solo en `portfolio`. */
  key?: string;
  metric: LimitMetric;
  amount: number;
  reason?: string;
}

export interface LimitEventBody {
  type: 'change' | 'retire';
  /** Obligatorio en `change`. */
  amount?: number;
  reason?: string;
}

export interface LimitUsage {
  limit_id: number;
  scope: LimitScope;
  key: string;
  metric: LimitMetric;
  amount: number;
  usage: number;
  pct: number;
  status: LimitStatus;
}

export interface LimitUsageResponse {
  snapshot: string;
  as_of: string;
  thresholds: { alert_pct: number; breach_pct: number };
  usage: LimitUsage[];
  errors: TradeError[];
}

export interface LimitBreach {
  id: number;
  limit_id: number;
  scope: LimitScope;
  key: string;
  metric: LimitMetric;
  snapshot: string;
  as_of: string;
  amount: number;
  usage: number;
  pct: number;
  created_at: string;
}

export interface LimitCheckResponse extends LimitUsageResponse {
  new_breaches: LimitBreach[];
}

// --- Crédito ---

export interface CreditParams {
  counterparty: string;
  hazard_rate: number;
  recovery: number;
  /** `null` mientras son los supuestos por omisión. */
  as_of: string | null;
  assumed: boolean;
  /** De la fila más nueva a la más vieja. */
  history: { hazard_rate: number; recovery: number; as_of: string; created_at: string }[];
}

export interface CreditParamsBody {
  counterparty: string;
  hazard_rate: number;
  recovery: number;
}

export interface CreditProfilePoint {
  date: string;
  t: number;
  ee_mxn: number;
  pfe_mxn: number;
}

export interface CreditNettingSet {
  curve: string;
  currency: string;
  trades: number[];
  pv_mxn: number;
  cva_mxn: number;
}

export interface CreditExcluded {
  id: number;
  product: string;
  reason: string;
  /** Solo en la lista global `excluded` de la respuesta. */
  counterparty?: string;
}

export interface CreditCounterparty {
  counterparty: string;
  hazard_rate: number;
  recovery: number;
  assumed: boolean;
  /** `null` si `assumed` es falso. */
  assumed_note: string | null;
  pv_mxn: number;
  cva_mxn: number;
  netting_sets: CreditNettingSet[];
  profile: CreditProfilePoint[];
  excluded: CreditExcluded[];
}

export interface CreditExposureResponse {
  snapshot: string;
  as_of: string;
  n_paths: number;
  seed: number;
  pfe_quantile: number;
  notice: string;
  counterparties: CreditCounterparty[];
  excluded: CreditExcluded[];
  warnings: Warning[];
}

// --- Biblioteca de escenarios ---

/** Choque de un escenario combinado: una especificación sin `name`. */
export type Shock =
  | { type: 'parallel' | 'steepener'; curve: 'TIIE-F' | 'SOFR'; bp: number }
  | { type: 'fx_spot'; pct: number };

export interface CombinedScenario {
  name: string;
  type: 'combined';
  /** De 1 a 8 choques, aplicados en orden; no se anidan. */
  shocks: Shock[];
}

export type LibraryScenario = ScenarioSpec | CombinedScenario;

export interface ScenarioSet {
  /** `null` en los conjuntos de fábrica. */
  id: number | null;
  name: string;
  builtin: boolean;
  /** Los históricos de fábrica son aproximaciones. */
  approximation: boolean;
  status: 'activo' | 'baja';
  description: string | null;
  scenarios: LibraryScenario[];
  created_at: string | null;
}

export interface CreateScenarioSetBody {
  name: string;
  description?: string;
  scenarios: LibraryScenario[];
}

export type SetScenariosResponse = ScenariosResponse & { set: string };
