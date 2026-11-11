// Cliente de las rutas de operaciones del corte 5. Tiene su propio `opsRequest` (el `request` de
// `client.ts` es privado y ese archivo no se toca en este corte) y lanza el mismo `ApiError`.
import { ApiError } from './client';
import type {
  CashflowsQuery,
  CashflowsResponse,
  Confirmation,
  CreateReconciliationBody,
  FpmlImportResponse,
  Reconciliation,
  ReconciliationSummary,
  SettlementBody,
  SettlementResponse,
  Settings,
  TradeRef,
} from './opsTypes';

const BASE = '/api';

/** Cuerpo que no es JSON (el XML de FpML): se envía tal cual con su `Content-Type`. */
interface RawBody {
  text: string;
  contentType: string;
}

async function opsRequest<T>(
  method: string,
  path: string,
  body?: unknown,
  raw?: RawBody,
): Promise<T> {
  const init: RequestInit = { method };
  if (raw !== undefined) {
    init.headers = { 'Content-Type': raw.contentType };
    init.body = raw.text;
  } else if (body !== undefined) {
    init.headers = { 'Content-Type': 'application/json' };
    init.body = JSON.stringify(body);
  }
  const res = await fetch(`${BASE}${path}`, init);
  if (res.status >= 400) {
    let message = `Error ${res.status}`;
    let field: string | null = null;
    try {
      const data = await res.json();
      if (typeof data?.error === 'string') message = data.error;
      if (typeof data?.field === 'string') field = data.field;
    } catch {
      // cuerpo no JSON: se conserva el mensaje genérico
    }
    throw new ApiError(res.status, message, field);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

/** `?a=1&b=2` con los pares en el orden dado; se omiten `undefined` y cadenas vacías. */
function queryString(pairs: [string, string | undefined][]): string {
  const params = new URLSearchParams();
  for (const [key, value] of pairs) {
    if (value !== undefined && value !== '') params.set(key, value);
  }
  const text = params.toString();
  return text ? `?${text}` : '';
}

function cashflowPairs(q: CashflowsQuery): [string, string | undefined][] {
  return [
    ['snapshot', q.snapshot],
    ['from', q.from],
    ['to', q.to],
    ['counterparty', q.counterparty],
    ['currency', q.currency],
  ];
}

// --- Calendario de flujos ---

export function getCashflows(q: CashflowsQuery): Promise<CashflowsResponse> {
  return opsRequest('GET', `/cashflows${queryString(cashflowPairs(q))}`);
}

/** URL del CSV del calendario, para un `<a download>`; no pasa por `opsRequest`. */
export function cashflowsCsvUrl(q: CashflowsQuery): string {
  return `${BASE}/cashflows${queryString([...cashflowPairs(q), ['format', 'csv']])}`;
}

// --- Liquidación confirmada ---

export function confirmSettlement(tradeId: number, body: SettlementBody): Promise<SettlementResponse> {
  return opsRequest('POST', `/trades/${tradeId}/settlements`, body);
}

// --- Confirmación, ajustes y referencia del banco ---

export function getConfirmation(tradeId: number): Promise<Confirmation> {
  return opsRequest('GET', `/trades/${tradeId}/confirmation`);
}

export function getSettings(): Promise<Settings> {
  return opsRequest('GET', '/settings');
}

export function putSettings(body: Partial<Settings>): Promise<Settings> {
  return opsRequest('PUT', '/settings', body);
}

export function getTradeRef(id: number): Promise<TradeRef> {
  return opsRequest('GET', `/trades/${id}/ref`);
}

/** `null` (o cadena vacía en el backend) borra la referencia. */
export function putTradeRef(id: number, ref: string | null): Promise<TradeRef> {
  return opsRequest('PUT', `/trades/${id}/ref`, { ref });
}

// --- FpML ---

/** URL de la descarga del FpML de una operación, para un `<a download>`. */
export function fpmlUrl(tradeId: number): string {
  return `${BASE}/trades/${tradeId}/fpml`;
}

export function importFpml(xml: string): Promise<FpmlImportResponse> {
  return opsRequest('POST', '/trades/fpml', undefined, { text: xml, contentType: 'application/xml' });
}

// --- Conciliación con el banco ---

export function createReconciliation(body: CreateReconciliationBody): Promise<Reconciliation> {
  return opsRequest('POST', '/reconciliations', body);
}

export async function listReconciliations(q?: {
  counterparty?: string;
}): Promise<ReconciliationSummary[]> {
  const data = await opsRequest<{ reconciliations: ReconciliationSummary[] }>(
    'GET',
    `/reconciliations${queryString([['counterparty', q?.counterparty]])}`,
  );
  return data.reconciliations;
}

export function getReconciliation(id: number): Promise<Reconciliation> {
  return opsRequest('GET', `/reconciliations/${id}`);
}

/** URL del CSV de una corrida, para un `<a download>`. */
export function reconciliationCsvUrl(id: number): string {
  return `${BASE}/reconciliations/${id}?format=csv`;
}
