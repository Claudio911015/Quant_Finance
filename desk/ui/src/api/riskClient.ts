// Cliente HTTP del corte 6 (riesgo avanzado). Usa la misma capa `request` que `client.ts`.
import { apiRequest } from './client';
import type {
  CreateLimitBody,
  CreateScenarioSetBody,
  CreditExposureResponse,
  CreditParams,
  CreditParamsBody,
  ExplainResponse,
  FactorHistoryDerive,
  FactorHistoryImport,
  FactorHistorySummary,
  HistVarBody,
  HistVarResponse,
  Limit,
  LimitBreach,
  LimitCheckResponse,
  LimitEventBody,
  LimitUsageResponse,
  ScenarioSet,
  SetScenariosResponse,
} from './riskTypes';

const q = encodeURIComponent;

export function pnlExplain(from: string, to: string): Promise<ExplainResponse> {
  return apiRequest('GET', `/pnl/explain?from=${q(from)}&to=${q(to)}`);
}

export function riskVarHistorical(snapshot: string, params: HistVarBody): Promise<HistVarResponse> {
  return apiRequest('POST', '/risk/var', { snapshot, method: 'historical', ...params });
}

export function factorHistorySummary(): Promise<FactorHistorySummary> {
  return apiRequest('GET', '/factor-history');
}

export function importFactorHistoryCsv(csv: string): Promise<FactorHistoryImport> {
  return apiRequest('POST', '/factor-history/csv', { csv });
}

export function deriveFactorHistory(source: 'fixings' | 'live'): Promise<FactorHistoryDerive> {
  return apiRequest('POST', '/factor-history/derive', { source });
}

export async function listLimits(): Promise<Limit[]> {
  const res = await apiRequest<{ limits: Limit[] }>('GET', '/limits');
  return res.limits;
}

export function createLimit(body: CreateLimitBody): Promise<Limit> {
  return apiRequest('POST', '/limits', body);
}

export function addLimitEvent(id: number, body: LimitEventBody): Promise<Limit> {
  return apiRequest('POST', `/limits/${id}/events`, body);
}

export function limitUsage(snapshot: string): Promise<LimitUsageResponse> {
  return apiRequest('GET', `/limits/usage?snapshot=${q(snapshot)}`);
}

export function checkLimits(snapshot: string): Promise<LimitCheckResponse> {
  return apiRequest('POST', `/limits/check?snapshot=${q(snapshot)}`);
}

export async function listBreaches(): Promise<LimitBreach[]> {
  const res = await apiRequest<{ breaches: LimitBreach[] }>('GET', '/limits/breaches');
  return res.breaches;
}

export function creditExposure(snapshot: string): Promise<CreditExposureResponse> {
  return apiRequest('GET', `/credit/exposure?snapshot=${q(snapshot)}`);
}

export async function listCreditParams(): Promise<CreditParams[]> {
  const res = await apiRequest<{ params: CreditParams[] }>('GET', '/credit/params');
  return res.params;
}

export function setCreditParams(body: CreditParamsBody): Promise<CreditParams> {
  return apiRequest('POST', '/credit/params', body);
}

export async function listScenarioSets(): Promise<ScenarioSet[]> {
  const res = await apiRequest<{ sets: ScenarioSet[] }>('GET', '/scenario-sets');
  return res.sets;
}

export function createScenarioSet(body: CreateScenarioSetBody): Promise<ScenarioSet> {
  return apiRequest('POST', '/scenario-sets', body);
}

export function retireScenarioSet(id: number): Promise<ScenarioSet> {
  return apiRequest('POST', `/scenario-sets/${id}/retire`);
}

export function runScenarioSet(snapshot: string, set: string): Promise<SetScenariosResponse> {
  return apiRequest('POST', '/risk/scenarios', { snapshot, set });
}
