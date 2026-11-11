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

function pending(): never {
  throw new Error('pendiente');
}

export function listSnapshots(): Promise<SnapshotSummary[]> {
  return pending();
}

export function getSnapshot(id: string): Promise<Snapshot> {
  return pending();
}

export function updateSnapshot(
  id: string,
  body: { quotes?: { id: string; rate: number }[]; spot?: number },
): Promise<Snapshot> {
  return pending();
}

export function price(product: ProductId, body: Record<string, unknown>): Promise<PriceResponse> {
  return pending();
}

export function listTrades(): Promise<Trade[]> {
  return pending();
}

export function createTrade(body: {
  product: ProductId;
  counterparty: string;
  params: Record<string, unknown>;
}): Promise<Trade> {
  return pending();
}

export function deleteTrade(id: number): Promise<void> {
  return pending();
}

export function valuation(snapshot: string): Promise<ValuationResponse> {
  return pending();
}

export function riskDv01(snapshot: string): Promise<Dv01Response> {
  return pending();
}

export function riskScenarios(
  snapshot: string,
  scenarios: ScenarioSpec[],
): Promise<ScenariosResponse> {
  return pending();
}

export function riskVar(
  snapshot: string,
  horizonDays: number,
  confidence: number,
): Promise<VarResponse> {
  return pending();
}
