import type {
  Dv01Response,
  PriceResponse,
  ProductId,
  ScenarioSpec,
  ScenariosResponse,
  Snapshot,
  SnapshotSummary,
  Trade,
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
}): Promise<Trade> {
  return request('POST', '/trades', body);
}

export function deleteTrade(id: number): Promise<void> {
  return request('DELETE', `/trades/${id}`);
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
