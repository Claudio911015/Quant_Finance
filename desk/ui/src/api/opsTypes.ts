// Tipos de las rutas de operaciones del corte 5 (flujos, liquidaciones, confirmación, FpML,
// conciliación). Transcripción del contrato HTTP; lo ya definido en `types.ts` se importa de allí.
import type { FlowKind, ProductId, Trade, TradeEvent, Warning } from './types';

/** Monedas que aceptan las rutas de operaciones. */
export type OpsCurrency = 'MXN' | 'USD';

// --- Calendario de flujos ---

export type FlowStatus = 'settled' | 'confirmed' | 'projected';

export interface CashflowRow {
  date: string;
  trade_id: number;
  counterparty: string;
  product: ProductId;
  kind: FlowKind;
  status: FlowStatus;
  currency: string;
  amount: number;
  amount_mxn: number;
  /** Solo en proyectados. */
  df: number | null;
  /** Solo en proyectados. */
  pv: number | null;
  /** Solo en filas `confirmed`. */
  confirmed_amount: number | null;
  /** `confirmed_amount − amount`; solo en filas `confirmed`. */
  difference: number | null;
}

export interface CashflowTotals {
  amount_mxn: number;
  by_date: { date: string; amount_mxn: number; count: number }[];
  by_counterparty: { counterparty: string; amount_mxn: number; count: number }[];
  by_currency: { currency: string; amount: number; amount_mxn: number; count: number }[];
}

export interface CashflowsResponse {
  snapshot: string;
  as_of: string;
  from: string | null;
  to: string | null;
  counterparty: string | null;
  currency: string | null;
  rows: CashflowRow[];
  totals: CashflowTotals;
  /** Operaciones cuyos flujos no se pudieron derivar; no aportan filas. */
  errors: { trade_id: number; message: string }[];
  warnings: Warning[];
}

export interface CashflowsQuery {
  snapshot: string;
  from?: string;
  to?: string;
  counterparty?: string;
  currency?: OpsCurrency;
}

// --- Ajustes y referencia del banco ---

export interface Settings {
  company_name: string;
}

export interface TradeRef {
  trade_id: number;
  ref: string | null;
}

// --- Liquidación confirmada ---

export interface SettlementBody {
  date: string;
  amount: number;
  currency: OpsCurrency;
  snapshot?: string;
}

export interface SettlementResponse {
  event: TradeEvent;
  flow: { date: string; kind: FlowKind; amount: number; currency: string };
  /** Monto confirmado − monto calculado. */
  difference: number;
}

// --- Confirmación de la operación ---

export interface ConfirmationRow {
  key: string;
  label: string;
  value: number | string;
  format: 'amount' | 'rate' | 'number' | 'text' | 'date';
  currency: string | null;
}

export interface ScheduleRow {
  date: string;
  description: string;
  /** `null` = por determinar (depende de fijaciones futuras). */
  amount: number | null;
  currency: string;
}

export interface Confirmation {
  trade_id: number;
  product: ProductId;
  product_label: string;
  generated_at: string;
  parties: {
    company: string;
    counterparty: string;
    company_role: string;
    counterparty_role: string;
  };
  bank_ref: string | null;
  dates: { trade_date: string; start_date: string; maturity_date: string };
  terms: ConfirmationRow[];
  conventions: ConfirmationRow[];
  schedule: ScheduleRow[];
  events_note: string | null;
  notices: string[];
}

// --- FpML ---

export interface FpmlImportResponse {
  trade: Trade;
  warnings: { code: string; message: string }[];
}

// --- Conciliación con el banco ---

export type ReconStatus = 'conciliada' | 'explicable' | 'revisar';

/**
 * Descomposición indicativa de la diferencia. Cada factor es `null` si no aplica al producto;
 * `bp`/`pct` son `null` si la búsqueda no convergió o salió de rango.
 */
export interface ReconDecomposition {
  date: {
    prev_date: string;
    next_date: string;
    pv_prev: number;
    pv_next: number;
    attributed: boolean;
  } | null;
  curve: { curve: string; bp: number | null } | null;
  fx: { spot: number | null; pct: number | null } | null;
}

export interface ReconRow {
  /** Línea del CSV (el encabezado es la 1). */
  line: number;
  trade_id: number;
  bank_ref: string | null;
  product: ProductId;
  currency: string;
  notional_mxn: number;
  /** `null` si la valuación lanzó (`error` trae el mensaje). */
  own_pv_mxn: number | null;
  bank_pv: number;
  bank_currency: string;
  bank_pv_mxn: number;
  /** `propio − banco`, en MXN. */
  difference_mxn: number | null;
  /** `difference_mxn / notional_mxn`; `null` si el nocional es cero. */
  difference_rel: number | null;
  status: ReconStatus;
  decomposition: ReconDecomposition | null;
  /** `null` en `revisar` de un producto sin factores de descomposición (xccy_swap, equity_option): no se probó nada. */
  terms_flag: boolean | null;
  /** Por qué `terms_flag` es `null` («sin descomposición para este producto»); ausente en conciliaciones antiguas. */
  terms_reason?: string | null;
  error: string | null;
}

export interface ReconBankOnly {
  line: number;
  trade_id: number | null;
  bank_ref: string | null;
  bank_pv: number;
  currency: string;
  reason: string;
}

export interface ReconOwnOnly {
  trade_id: number;
  product: ProductId;
  own_pv_mxn: number | null;
}

export interface ReconSummary {
  matched: number;
  conciliada: number;
  explicable: number;
  revisar: number;
  bank_only: number;
  own_only: number;
  own_pv_mxn: number;
  bank_pv_mxn: number;
  difference_mxn: number;
}

/** Detalle de una corrida (respuesta del `POST` y del `GET /api/reconciliations/<id>`). */
export interface Reconciliation {
  id: number;
  snapshot: string;
  as_of: string;
  counterparty: string;
  /** Fracción del nocional (0.0001 = 0.01 %). */
  tolerance: number;
  created_at: string;
  disclaimer: string;
  summary: ReconSummary;
  rows: ReconRow[];
  bank_only: ReconBankOnly[];
  own_only: ReconOwnOnly[];
}

/** Renglón del historial (`GET /api/reconciliations`). */
export interface ReconciliationSummary {
  id: number;
  snapshot: string;
  as_of: string;
  counterparty: string;
  tolerance: number;
  created_at: string;
  summary: ReconSummary;
}

export interface CreateReconciliationBody {
  snapshot: string;
  counterparty: string;
  csv: string;
  /** Fracción del nocional; omitida, el backend usa 0.0001. */
  tolerance?: number;
}
