import type {
  AddFixingResponse,
  CreateHedgeBody,
  DedesignationCause,
  Dv01Response,
  EffectivenessResponse,
  EventType,
  Fixing,
  FixingIndex,
  FixingsCsvResult,
  FlowsResponse,
  HedgeDetail,
  HedgePeriod,
  HedgeReport,
  HedgeSummary,
  PnlResponse,
  PriceResponse,
  ProductId,
  RefreshResponse,
  ReleaseCause,
  ScenarioSpec,
  ScenariosResponse,
  Snapshot,
  SnapshotSummary,
  Trade,
  TradeDetail,
  TradeEvent,
  TradeState,
  ValuationResponse,
  VarResponse,
} from './types';

export class ApiError extends Error {
  status: number;
  field: string | null;

  constructor(status: number, message: string, field: string | null = null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.field = field;
  }
}

const BASE = '/api';

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const init: RequestInit = { method };
  if (body !== undefined) {
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

export async function listSnapshots(): Promise<SnapshotSummary[]> {
  const data = await request<{ snapshots: SnapshotSummary[] }>('GET', '/market/snapshots');
  return data.snapshots;
}

export function getSnapshot(id: string): Promise<Snapshot> {
  return request('GET', `/market/snapshots/${encodeURIComponent(id)}`);
}

export function updateSnapshot(
  id: string,
  body: { quotes?: { id: string; rate: number }[]; spot?: number },
): Promise<Snapshot> {
  return request('PUT', `/market/snapshots/${encodeURIComponent(id)}`, body);
}

export function refreshMarket(): Promise<RefreshResponse> {
  return request('POST', '/market/refresh');
}

export function price(product: ProductId, body: Record<string, unknown>): Promise<PriceResponse> {
  return request('POST', `/price/${product}`, body);
}

export async function listTrades(): Promise<Trade[]> {
  const data = await request<{ trades: Trade[] }>('GET', '/trades');
  return data.trades;
}

export function createTrade(body: {
  product: ProductId;
  counterparty: string;
  params: Record<string, unknown>;
  snapshot?: string;
  trade_date?: string;
  start_date?: string;
  maturity_date?: string;
}): Promise<Trade> {
  return request('POST', '/trades', body);
}

export function getTrade(id: number): Promise<TradeDetail> {
  return request('GET', `/trades/${id}`);
}

export function tradeState(id: number, date: string): Promise<TradeState> {
  return request('GET', `/trades/${id}/state?date=${encodeURIComponent(date)}`);
}

export function tradeFlows(id: number, snapshot: string): Promise<FlowsResponse> {
  return request('GET', `/trades/${id}/flows?snapshot=${encodeURIComponent(snapshot)}`);
}

/** Devuelve los eventos creados: uno, o dos si el evento genera además un `transfer`. */
export async function postEvent(
  id: number,
  body: { type: EventType; event_date: string; data: Record<string, unknown> },
): Promise<TradeEvent[]> {
  const data = await request<{ events: TradeEvent[] }>('POST', `/trades/${id}/events`, body);
  return data.events;
}

export function deleteTrade(id: number): Promise<void> {
  return request('DELETE', `/trades/${id}`);
}

export async function listFixings(q?: {
  index?: FixingIndex;
  from?: string;
  to?: string;
}): Promise<Fixing[]> {
  const parts = Object.entries(q ?? {})
    .filter(([, v]) => v)
    .map(([k, v]) => `${k}=${encodeURIComponent(v as string)}`);
  const data = await request<{ fixings: Fixing[] }>(
    'GET',
    `/fixings${parts.length ? `?${parts.join('&')}` : ''}`,
  );
  return data.fixings;
}

export function addFixing(body: {
  index: FixingIndex;
  date: string;
  value: number;
}): Promise<AddFixingResponse> {
  return request('POST', '/fixings', body);
}

export function importFixingsCsv(csv: string): Promise<FixingsCsvResult> {
  return request('POST', '/fixings/csv', { csv });
}

export function rollSnapshot(
  sourceId: string,
  body: { id: string; as_of: string },
): Promise<Snapshot> {
  return request('POST', `/market/${encodeURIComponent(sourceId)}/roll`, body);
}

export function pnl(from: string, to: string): Promise<PnlResponse> {
  return request('GET', `/pnl?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`);
}

export function valuation(snapshot: string): Promise<ValuationResponse> {
  return request('GET', `/portfolio/valuation?snapshot=${encodeURIComponent(snapshot)}`);
}

export function riskDv01(snapshot: string): Promise<Dv01Response> {
  return request('POST', '/risk/dv01', { snapshot });
}

export function riskScenarios(
  snapshot: string,
  scenarios: ScenarioSpec[],
): Promise<ScenariosResponse> {
  return request('POST', '/risk/scenarios', { snapshot, scenarios });
}

export function riskVar(
  snapshot: string,
  horizonDays: number,
  confidence: number,
): Promise<VarResponse> {
  return request('POST', '/risk/var', {
    snapshot,
    horizon_days: horizonDays,
    confidence,
  });
}

export async function listHedges(q?: { trade_id?: number }): Promise<HedgeSummary[]> {
  const query = q?.trade_id !== undefined ? `?trade_id=${q.trade_id}` : '';
  const data = await request<{ hedges: HedgeSummary[] }>('GET', `/hedges${query}`);
  return data.hedges;
}

export function getHedge(id: number): Promise<HedgeDetail> {
  return request('GET', `/hedges/${id}`);
}

export function createHedge(body: CreateHedgeBody): Promise<HedgeDetail> {
  return request('POST', '/hedges', body);
}

export function closeHedgePeriod(id: number, snapshot: string): Promise<HedgePeriod> {
  return request('POST', `/hedges/${id}/periods`, { snapshot });
}

/** La fecha de la desdesignación es el `as_of` del snapshot; si es posterior al último cierre, el backend lo mide primero. */
export function dedesignateHedge(
  id: number,
  body: { snapshot: string; reason: string; cause: DedesignationCause },
): Promise<HedgeDetail> {
  return request('POST', `/hedges/${id}/dedesignate`, body);
}

/** `amount` lleva el signo del saldo de la reserva; omitido, se libera todo. */
export function releaseHedgeReserve(
  id: number,
  body: { snapshot: string; amount?: number; cause: ReleaseCause },
): Promise<HedgeDetail> {
  return request('POST', `/hedges/${id}/release`, body);
}

export function hedgeEffectiveness(id: number, snapshot: string): Promise<EffectivenessResponse> {
  return request('GET', `/hedges/${id}/effectiveness?snapshot=${encodeURIComponent(snapshot)}`);
}

export function hedgeReport(id: number, snapshot?: string): Promise<HedgeReport> {
  const query = snapshot ? `?snapshot=${encodeURIComponent(snapshot)}` : '';
  return request('GET', `/hedges/${id}/report${query}`);
}

/** URL del CSV de asientos, para un `<a download>`; no pasa por `request`. */
export function hedgeReportCsvUrl(id: number): string {
  return `${BASE}/hedges/${id}/report?format=csv`;
}
